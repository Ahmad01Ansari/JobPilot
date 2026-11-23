"""Automation worker and application manager coordinator for JobPilot desktop UI."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QThread, Signal, Slot
from sqlalchemy.orm import sessionmaker

from app.db.models.automation_run import AutomationRun
from app.db.session import SessionLocal, get_db_session
from app.repositories.automation_run_repository import AutomationRunRepository
from app.services.automation_bridge import AutomationBridge
from app.services.automation_events import (
    ApplicationSubmittedEvent,
    AutomationInterventionEvent,
    AutomationProgressEvent,
    AutomationRunResult,
    AutomationState,
    InterventionType,
    JobDiscoveredEvent,
    JobEvaluatedEvent,
)

logger = logging.getLogger(__name__)


class AutomationWorker(QThread):
    """Worker thread owning Selenium execution and browser lifecycle."""

    state_changed = Signal(str, str)  # (run_id, state)
    progress_updated = Signal(object)  # AutomationProgressEvent
    job_discovered = Signal(object)  # JobDiscoveredEvent
    job_evaluated = Signal(object)  # JobEvaluatedEvent
    application_submitted = Signal(object)  # ApplicationSubmittedEvent
    intervention_required = Signal(object)  # AutomationInterventionEvent
    intervention_dismissed = Signal()
    activity_logged = Signal(str, str)  # (timestamp, message)
    finished_result = Signal(object)  # AutomationRunResult

    def __init__(
        self,
        run_id: str,
        platform: str,
        session_factory: Optional[sessionmaker] = None,
        engine_runner: Optional[Callable[["AutomationWorker"], None]] = None,
        parent: Optional[QObject] = None,
        target_url: Optional[str] = None,
        job_title: Optional[str] = None,
        company: Optional[str] = None,
        candidate_context: Optional[Dict[str, Any]] = None,
        headless: Optional[bool] = None,
        on_review_requested: Optional[Callable[..., Any]] = None,
        orchestrator: Optional[Any] = None,
    ):
        super().__init__(parent)
        self.run_id = run_id
        self.platform = (platform or "linkedin").strip().lower()
        self.engine_runner = engine_runner
        self.target_url = target_url
        self.job_title = job_title
        self.company = company
        self.candidate_context = candidate_context or {}
        if headless is None:
            try:
                from app.services.settings_service import SettingsService
                self.headless = bool(SettingsService().get_setting("run_in_background", False))
            except Exception:
                self.headless = False
        else:
            self.headless = bool(headless)
        self.on_review_requested = on_review_requested
        self.orchestrator = orchestrator
        self._active_orchestrator: Optional[Any] = None

        self._session_factory = session_factory or SessionLocal
        try:
            with get_db_session(self._session_factory) as _s:
                from app.repositories.user_repository import UserRepository
                primary_u = UserRepository(_s).get_primary_user()
                self.user_id = primary_u.id if primary_u else 1
        except Exception:
            self.user_id = 1
        self.bridge = AutomationBridge(session_factory=self._session_factory)
        self.bridge.on_intervention = self.record_intervention
        self.bridge.on_dismiss_intervention = self.intervention_dismissed.emit

        self._stop_requested = False
        self._is_paused = False
        self._active_router = None
        self._active_platform = None
        self._discovered_keys = set()
        self.progress = AutomationProgressEvent(run_id=self.run_id, platform=self.platform)
        self.start_time = datetime.now(timezone.utc)

    def confirm_review(self, notes: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> None:
        """Approves pending human review, OTP, or candidate question input."""
        # Save learned answer if provided by candidate
        val = (data and data.get("value")) or (notes and not any(notes.startswith(p) for p in ["I've Solved", "I have solved", "I am logged in"]))
        if val:
            ans_str = str((data.get("value") if data else None) or notes).strip()
            if ans_str:
                try:
                    from modules.qna_engine import QnAEngine
                    q_label = (data or {}).get("field_name") or (data or {}).get("prompt") or "Manual Screening Input"
                    engine = QnAEngine(user_id=self.user_id)
                    engine.save_learned_answer(q_label, ans_str, category="user_override", source="user")
                    self.emit_activity(f"Saved candidate response for '{q_label}': '{ans_str}'")
                except Exception as e:
                    logger.debug("Notice saving learned answer: %s", e)

        if self._active_orchestrator:
            try:
                self._active_orchestrator.confirm_submission(notes=notes, data=data)
            except TypeError:
                self._active_orchestrator.confirm_submission(notes=notes)
            self.emit_activity("Intervention resolution confirmed by user.")
        if self.bridge:
            if val:
                ans_str = str((data.get("value") if data else None) or notes).strip()
                try:
                    self.bridge.provide_input(ans_str, metadata=data)
                except Exception as err:
                    logger.debug("Notice providing input to bridge: %s", err)
            try:
                self.bridge.mark_captcha_resolved()
            except Exception:
                pass
            try:
                if hasattr(self.bridge, "resolve_intervention"):
                    self.bridge.resolve_intervention(data or {"action": "RESUME", "notes": notes})
            except Exception as err:
                logger.debug("Notice resolving intervention on bridge: %s", err)
            self.emit_activity("Intervention resolution confirmed by user.")

        if self._is_paused:
            self.resume()

    def takeover_manually(self, notes: Optional[str] = None) -> None:
        """Transfers control of current universal application to user."""
        if self._active_orchestrator:
            self._active_orchestrator.takeover_manually(notes=notes)
            self.emit_activity("Manual takeover requested: session handed over to user.")

    def cancel_intervention(self, reason: str = "User cancelled application.") -> None:
        """Aborts current universal intervention or run."""
        if self._active_orchestrator:
            self._active_orchestrator.cancel(reason=reason)
            self.emit_activity(f"Intervention cancelled: {reason}")

    def mark_captcha_resolved(self) -> None:
        """Signals bridge and active orchestrator that user has solved the CAPTCHA in the UI."""
        if self.bridge:
            self.bridge.mark_captcha_resolved()
        if self._active_orchestrator and hasattr(self._active_orchestrator, "intervention_manager"):
            try:
                self._active_orchestrator.intervention_manager.resolve_resume({"action": "CAPTCHA_RESOLVED"})
            except Exception:
                pass

    def mark_captcha_cancelled(self) -> None:
        """Signals bridge and active orchestrator that user has cancelled/skipped the CAPTCHA."""
        if self.bridge:
            self.bridge.mark_captcha_cancelled()
        if self._active_orchestrator and hasattr(self._active_orchestrator, "intervention_manager"):
            try:
                self._active_orchestrator.intervention_manager.resolve_skip({"action": "CAPTCHA_CANCELLED"})
            except Exception:
                pass

    def reset_captcha_status(self) -> None:
        """Resets manual CAPTCHA resolution flag on bridge."""
        if self.bridge:
            self.bridge.reset_captcha_status()

    def provide_intervention_input(self, value: str, intervention_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Delivers user input from UI or Copilot chat to the active worker and bridge."""
        if self.bridge:
            self.bridge.provide_input(value, intervention_id=intervention_id, metadata=metadata)
        if self._active_orchestrator and hasattr(self._active_orchestrator, "intervention_manager"):
            try:
                self._active_orchestrator.intervention_manager.resolve_resume({"value": value, "intervention_id": intervention_id})
            except Exception:
                pass
        self.intervention_dismissed.emit()

    def pause(self) -> None:
        """Cooperatively suspends execution loop without closing browsers or sessions."""
        self._is_paused = True
        if self._active_router and hasattr(self._active_router, "pause"):
            try:
                self._active_router.pause()
            except Exception:
                pass
        if self._active_platform and hasattr(self._active_platform, "pause"):
            try:
                self._active_platform.pause()
            except Exception:
                pass
        self.state_changed.emit(self.run_id, AutomationState.PAUSED.value)
        self.emit_activity("Automation execution paused by user.")

    def resume(self) -> None:
        """Resumes cooperatively suspended execution loop."""
        self._is_paused = False
        if self._active_router and hasattr(self._active_router, "resume"):
            try:
                self._active_router.resume()
            except Exception:
                pass
        if self._active_platform and hasattr(self._active_platform, "resume"):
            try:
                self._active_platform.resume()
            except Exception:
                pass
        self.state_changed.emit(self.run_id, AutomationState.RUNNING.value)
        self.emit_activity("Automation execution resumed.")

    def is_paused(self) -> bool:
        """Returns True if the worker is currently paused."""
        return self._is_paused

    def request_stop(self) -> None:
        """Sets cooperative cancellation flag and terminates active engines/browsers."""
        self._stop_requested = True
        self._is_paused = False
        self.state_changed.emit(self.run_id, AutomationState.STOP_REQUESTED.value)
        self.emit_activity("Stop requested by user. Terminating engine...")
        if self._active_orchestrator:
            try:
                self._active_orchestrator.cancel(reason="Stopped by user")
            except Exception:
                pass
        if self._active_router:
            try:
                self._active_router.close()
            except Exception:
                pass
        if self._active_platform:
            try:
                self._active_platform.close()
            except Exception:
                pass

    def is_stop_requested(self) -> bool:
        """Returns whether a cancellation has been requested, cooperatively pausing while paused."""
        while self._is_paused and not self._stop_requested:
            self.msleep(200)
        return self._stop_requested

    def emit_activity(self, message: str) -> None:
        """Emits an activity line for live event streaming in local time."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.activity_logged.emit(timestamp, message)

    def record_job_discovered(self, event: JobDiscoveredEvent) -> Optional[int]:
        """Dispatches job discovery to database bridge and UI signals."""
        job_id = self.bridge.handle_job_discovered(event)
        self.progress.jobs_discovered += 1
        self.job_discovered.emit(event)
        self.emit_activity(f"Job Discovered: {event.title} @ {event.company}")
        self.progress_updated.emit(self.progress)
        try:
            from app.ui.state import AppState
            AppState.get_instance().notify_data_updated("jobs")
        except Exception:
            pass
        return job_id

    def record_job_evaluated(self, event: JobEvaluatedEvent) -> None:
        """Dispatches job qualification decision, ensuring discovered count is always >= evaluated count."""
        self.progress.jobs_evaluated += 1
        if self.progress.jobs_discovered < self.progress.jobs_evaluated:
            self.progress.jobs_discovered = self.progress.jobs_evaluated
        if event.is_qualified:
            self.progress.jobs_qualified += 1
            self.emit_activity(f"Qualified: {event.title} @ {event.company}")
        else:
            self.progress.jobs_skipped += 1
            reason = f" ({event.reason})" if event.reason else ""
            self.emit_activity(f"Skipped: {event.title}{reason}")
        self.job_evaluated.emit(event)
        self.progress_updated.emit(self.progress)

    def record_application_submitted(self, event: ApplicationSubmittedEvent) -> Optional[int]:
        """Dispatches application submission to database bridge and UI signals."""
        app_id = self.bridge.handle_application_submitted(event)
        self.progress.applications_submitted += 1
        self.application_submitted.emit(event)
        self.emit_activity(f"Application Submitted: {event.title} @ {event.company}")
        self.progress_updated.emit(self.progress)
        try:
            from app.ui.state import AppState
            AppState.get_instance().notify_data_updated("applications")
            AppState.get_instance().notify_data_updated("dashboard")
            AppState.get_instance().notify_data_updated("pipeline")
        except Exception:
            pass
        return app_id

    def record_intervention(self, event: AutomationInterventionEvent) -> None:
        """Dispatches manual intervention requirement."""
        self.intervention_required.emit(event)
        self.emit_activity(f"Intervention Required [{event.intervention_type.value}]: {event.message}")

    def record_error(self, message: str) -> None:
        """Dispatches error count and activity message."""
        self.progress.errors_count += 1
        self.emit_activity(f"Error: {message}")
        self.progress_updated.emit(self.progress)

    def _on_platform_log(self, message: str) -> None:
        """Pipes real-time platform logs into the activity stream."""
        if message and message.strip():
            self.emit_activity(message.strip())

    def _on_tracker_record(self, record: Any) -> None:
        """Receives live application records from ApplicationTracker and dispatches UI events."""
        try:
            status = getattr(record, "status", None)
            title = getattr(record, "title", "Job")
            company = getattr(record, "company", "Company")
            job_id = getattr(record, "job_id", "")
            location = getattr(record, "location", "")
            source_url = getattr(record, "source_url", "")
            platform = getattr(record, "platform", self.platform)
            skip_reason = getattr(record, "skip_reason", None)
            fail_reason = getattr(record, "failure_reason", None)

            job_key = (str(platform).lower(), str(job_id).strip() or str(title))

            if status == "DISCOVERED":
                self._discovered_keys.add(job_key)
                event = JobDiscoveredEvent(
                    run_id=self.run_id,
                    platform=platform,
                    title=title,
                    company=company,
                    external_job_id=job_id,
                    location=location,
                    url=source_url,
                )
                self.record_job_discovered(event)

            elif status in ("QUALIFIED", "SKIPPED"):
                if job_key not in self._discovered_keys:
                    self._discovered_keys.add(job_key)
                    disc_event = JobDiscoveredEvent(
                        run_id=self.run_id,
                        platform=platform,
                        title=title,
                        company=company,
                        external_job_id=job_id,
                        location=location,
                        url=source_url,
                    )
                    self.record_job_discovered(disc_event)

                is_qual = (status == "QUALIFIED")
                event = JobEvaluatedEvent(
                    run_id=self.run_id,
                    platform=platform,
                    title=title,
                    company=company,
                    is_qualified=is_qual,
                    external_job_id=job_id,
                    reason=skip_reason if not is_qual else None,
                )
                self.record_job_evaluated(event)

            elif status == "APPLYING":
                self.progress.current_job = f"{title} @ {company}"
                self.progress_updated.emit(self.progress)

            elif status == "SUBMITTED":
                event = ApplicationSubmittedEvent(
                    run_id=self.run_id,
                    platform=platform,
                    title=title,
                    company=company,
                    external_job_id=job_id,
                    source_url=source_url,
                )
                self.record_application_submitted(event)

            elif status == "EXTERNAL":
                self.emit_activity(f"External Apply (Company Portal): {title} @ {company}")
                ext_url = getattr(record, "external_job_link", None) or getattr(record, "application_url", None)
                if ext_url and any(d in str(ext_url).lower() for d in ["naukri.com", "linkedin.com", "indeed.com"]):
                    ext_url = None
                disc_event = JobDiscoveredEvent(
                    run_id=self.run_id,
                    platform=platform,
                    title=title,
                    company=company,
                    external_job_id=job_id,
                    location=location,
                    url=source_url,
                    application_method="COMPANY_PORTAL",
                    application_url=ext_url,
                )
                self.record_job_discovered(disc_event)
                event = JobEvaluatedEvent(
                    run_id=self.run_id,
                    platform=platform,
                    title=title,
                    company=company,
                    is_qualified=False,
                    external_job_id=job_id,
                    reason="External application required",
                )
                self.record_job_evaluated(event)


            elif status in ("FAILED", "UNKNOWN"):
                self.record_error(f"{title} @ {company}: {fail_reason or 'Failed'}")

            elif status == "MANUAL_REQUIRED":
                is_captcha = "captcha" in str(fail_reason or "").lower()
                if is_captcha:
                    event = AutomationInterventionEvent(
                        run_id=self.run_id,
                        platform=platform,
                        intervention_type=InterventionType.CAPTCHA_DETECTED,
                        message=f"CAPTCHA challenge detected for {title} @ {company}",
                    )
                    self.record_intervention(event)
                elif self.headless:
                    # In unattended headless mode, Chrome has no visible window and the modal has been discarded.
                    # Do not freeze the pipeline with an interactive modal; record and proceed.
                    self.emit_activity(f"Notice: Job requires manual review ({title} @ {company}): {fail_reason or 'unanswered questions'}. Saved to Review List.")
                else:
                    event = AutomationInterventionEvent(
                        run_id=self.run_id,
                        platform=platform,
                        intervention_type=InterventionType.MANUAL_ACTION_REQUIRED,
                        message=f"Manual review required for {title} @ {company}",
                        details={
                            "title": title,
                            "company": company,
                            "failure_reason": fail_reason,
                            "prompt": fail_reason,
                            "field_name": fail_reason or "Screening Question",
                        },
                    )
                    self.record_intervention(event)

        except Exception as e:
            logger.debug("Error in _on_tracker_record: %s", e)

    def run(self) -> None:
        """Worker execution loop executing Selenium pipeline off UI thread."""
        self.state_changed.emit(self.run_id, AutomationState.RUNNING.value)
        self.emit_activity(f"Automation execution started for target: {self.platform.upper()}")

        final_state = AutomationState.COMPLETED
        stop_reason = None
        wakelock_acquired = False

        try:
            from modules.helpers import add_log_listener, remove_log_listener
            from modules.tracker import ApplicationTracker
            add_log_listener(self._on_platform_log)
            ApplicationTracker.add_listener(self._on_tracker_record)

            try:
                from app.services.settings_service import SettingsService
                keep_awake = bool(SettingsService().get_setting("keep_screen_awake", True))
                if keep_awake:
                    from app.services.os.system_service import SystemService
                    wakelock_acquired = SystemService.acquire_wakelock("JobPilot automation running")
            except Exception as e:
                logger.debug("Failed to acquire system wakelock: %s", e)

            if self.engine_runner:
                # Pluggable runner (used for FakeAutomationEngine or custom injections)
                self.engine_runner(self)
            else:
                self._execute_real_automation()

            if self.is_stop_requested():
                final_state = AutomationState.COMPLETED
                stop_reason = "Stopped by user"
            else:
                final_state = AutomationState.COMPLETED
                stop_reason = "Completed naturally"

        except Exception as exc:
            logger.exception("Uncaught error during automation execution: %s", exc)
            self.record_error(str(exc))
            final_state = AutomationState.FAILED
            stop_reason = str(exc)

        finally:
            if wakelock_acquired:
                try:
                    from app.services.os.system_service import SystemService
                    SystemService.release_wakelock()
                except Exception:
                    pass

            try:
                from modules.helpers import remove_log_listener
                from modules.tracker import ApplicationTracker
                remove_log_listener(self._on_platform_log)
                ApplicationTracker.remove_listener(self._on_tracker_record)
            except Exception:
                pass

            finished_at = datetime.now(timezone.utc)
            result = AutomationRunResult(
                run_id=self.run_id,
                platform=self.platform,
                status=final_state,
                started_at=self.start_time,
                finished_at=finished_at,
                jobs_discovered=self.progress.jobs_discovered,
                jobs_evaluated=self.progress.jobs_evaluated,
                jobs_qualified=self.progress.jobs_qualified,
                jobs_skipped=self.progress.jobs_skipped,
                applications_submitted=self.progress.applications_submitted,
                errors_count=self.progress.errors_count,
                stop_reason=stop_reason,
            )
            self.state_changed.emit(self.run_id, final_state.value)
            self.emit_activity(f"Automation finished with state: {final_state.value} ({stop_reason or 'None'})")
            self.finished_result.emit(result)

    def _is_platform_enabled(self, platform_name: str) -> bool:
        """Checks if a platform is currently enabled for automation."""
        try:
            from app.services.platform_service import PlatformService
            plat_svc = PlatformService()
            return plat_svc.is_platform_enabled(platform_name)
        except Exception:
            try:
                import json
                from pathlib import Path
                profile_path = Path(__file__).resolve().parent.parent.parent / "config" / "profile.json"
                if profile_path.exists():
                    with open(profile_path, "r", encoding="utf-8") as f:
                        p_data = json.load(f)
                    return bool(p_data.get("platforms", {}).get(platform_name.lower(), {}).get("enabled", True))
            except Exception:
                pass
            return True

    def _execute_real_automation(self) -> None:
        """Dispatches execution to actual LinkedIn/Naukri/Indeed Selenium engines sequentially."""
        try:
            from app.services.settings_service import SettingsService
            settings_svc = SettingsService()
            self.headless = bool(settings_svc.get_setting("run_in_background", False))
        except Exception:
            pass

        if self.platform == "all":
            from app.services.settings_service import SettingsService
            settings_svc = SettingsService()
            batch_slice = int(settings_svc.get_setting("batch_size_per_platform", 10))
            daily_goal = int(settings_svc.get_setting("batch_daily_goal_per_platform", 25))

            candidate_platforms = [
                ("linkedin", "LinkedIn", self._run_linkedin_engine),
                ("naukri", "Naukri.com", self._run_naukri_engine),
                ("indeed", "Indeed", self._run_indeed_engine),
                ("foundit", "Foundit", self._run_foundit_engine),
                ("glassdoor", "Glassdoor", self._run_glassdoor_engine),
            ]

            enabled_platforms = [
                (p_id, p_name, runner)
                for p_id, p_name, runner in candidate_platforms
                if self._is_platform_enabled(p_id)
            ]

            if not enabled_platforms:
                self.emit_activity("============================================================")
                self.emit_activity("BATCH AUTOMATION HALTED: No platforms are currently enabled.")
                self.emit_activity("Please enable at least one platform in the Platforms view and retry.")
                self.emit_activity("============================================================")
                return

            platform_applied = {p_id: 0 for p_id, _, _ in enabled_platforms}
            total_active = len(enabled_platforms)
            rotation_order = " -> ".join([f"[{idx+1}/{total_active}] {p_name}" for idx, (_, p_name, _) in enumerate(enabled_platforms)])

            mode_desc = "Unattended Headless (running in background)" if self.headless else "Attended Foreground (Chrome visible in foreground)"
            self.emit_activity("============================================================")
            self.emit_activity("MULTI-PLATFORM ROUND-ROBIN BATCH PIPELINE")
            self.emit_activity(f"Configuration: {batch_slice} apps/cycle per platform | Daily Goal: {daily_goal} apps/platform")
            self.emit_activity(f"Active Queue ({total_active} platforms): {rotation_order}")
            self.emit_activity(f"Mode: {mode_desc}")
            self.emit_activity("============================================================")

            cycle = 1
            max_consecutive_zero_cycles = 2
            consecutive_zero_cycles = 0

            while not self.is_stop_requested():
                pending = [p for p, count in platform_applied.items() if count < daily_goal]
                if not pending:
                    self.emit_activity(f"Batch Automation: Daily goal ({daily_goal}) reached across all active platforms. Batch completed!")
                    break

                self.emit_activity("============================================================")
                self.emit_activity(f">>> STARTING ROUND-ROBIN CYCLE {cycle}")
                self.emit_activity("============================================================")
                cycle_total_applied = 0

                for idx, (p_id, p_name, runner) in enumerate(enabled_platforms):
                    if self.is_stop_requested():
                        break

                    if platform_applied[p_id] < daily_goal:
                        rem = daily_goal - platform_applied[p_id]
                        cur_slice = min(batch_slice, rem)
                        self.emit_activity(
                            f">>> [Cycle {cycle}] STAGE [{idx+1}/{total_active}]: "
                            f"Launching {p_name} (Cap: {cur_slice} apps, Progress: {platform_applied[p_id]}/{daily_goal})..."
                        )
                        applied = runner(max_applications=cur_slice)
                        platform_applied[p_id] += applied
                        cycle_total_applied += applied

                        if self.is_stop_requested():
                            self.emit_activity(f"Batch Automation: Stopped during {p_name} stage.")
                            return

                        self.msleep(3000)

                if cycle_total_applied == 0:
                    consecutive_zero_cycles += 1
                    if consecutive_zero_cycles >= max_consecutive_zero_cycles:
                        self.emit_activity("Batch Automation: No more eligible applications available across active platforms. Ending run gracefully.")
                        break
                else:
                    consecutive_zero_cycles = 0

                cycle += 1

            self.emit_activity("============================================================")
            self.emit_activity(">>> BATCH AUTOMATION: Multi-platform cycles completed.")
            self.emit_activity("============================================================")
        elif self.platform == "naukri":
            self._run_naukri_engine()
        elif self.platform == "indeed":
            self._run_indeed_engine()
        elif self.platform == "foundit":
            self._run_foundit_engine()
        elif self.platform == "glassdoor":
            self._run_glassdoor_engine()
        elif self.platform == "universal":
            self._run_universal_engine()
        else:
            self._run_linkedin_engine()

    def _run_linkedin_engine(self, max_applications: Optional[int] = None) -> int:
        """Executes LinkedIn automation loop."""
        self.emit_activity("Agent Action: Preparing LinkedIn browser profile and launching stealth engine...")
        applied_count = 0
        try:
            from platforms.router import PlatformRouter
            router = PlatformRouter()
            if hasattr(router, "linkedin_platform") and router.linkedin_platform:
                router.linkedin_platform.platform_config = router.linkedin_platform.platform_config or {}
                router.linkedin_platform.platform_config["run_in_background"] = self.headless
                if max_applications is not None:
                    router.linkedin_platform.platform_config["max_applications"] = max_applications
                    router.linkedin_platform.platform_config["batch_slice"] = max_applications
                    router.linkedin_platform.platform_config["is_batch_run"] = True
                    router.linkedin_platform.platform_config["switch_number"] = max_applications
            self._active_router = router
            self.emit_activity("Portal Navigation: Connecting to LinkedIn jobs search...")
            res = router.run_linkedin(
                stop_check=self.is_stop_requested,
                log_callback=self.emit_activity,
            )
            applied_count = int(res.get("jobs_applied", 0))
            self.emit_activity(f"LinkedIn session ended: {res.get('status', 'finished')} (Applied: {applied_count})")
        except Exception as e:
            if not self.is_stop_requested():
                self.record_error(f"LinkedIn engine error: {e}")
        finally:
            self._active_router = None
        return applied_count

    def _run_naukri_engine(self, max_applications: Optional[int] = None) -> int:
        """Executes Naukri automation loop with browser isolation."""
        self.emit_activity("Agent Action: Preparing persistent Naukri profile and clearing locks...")
        applied_count = 0
        try:
            from platforms.router import NaukriPlatform
            user_id = getattr(self, "user_id", 1)
            platform = NaukriPlatform(user_id=user_id, automation_bridge=self.bridge)
            platform.platform_config = platform.platform_config or {}
            try:
                from app.services.platform_service import PlatformService
                p_cfg = PlatformService().get_platform_config("naukri") or {}
                platform.platform_config.update(p_cfg)
            except Exception:
                pass
            platform.platform_config["run_in_background"] = self.headless
            if max_applications is not None:
                platform.platform_config["max_applications"] = max_applications
                platform.platform_config["batch_slice"] = max_applications
                platform.platform_config["is_batch_run"] = True
                platform.platform_config["switch_number"] = max_applications
            self._active_platform = platform
            try:
                self.emit_activity("Agent Action: Launching isolated stealth Chrome browser for Naukri...")
                platform.initialize()
                if self.is_stop_requested():
                    return 0
                self.emit_activity("Session State: Navigating to Naukri portal and verifying session...")
                if not platform.login():
                    self.record_intervention(
                        AutomationInterventionEvent(
                            run_id=self.run_id,
                            platform="naukri",
                            intervention_type=InterventionType.LOGIN_REQUIRED,
                            message="Naukri login/OTP authentication required in browser.",
                        )
                    )
                    return 0
                if self.is_stop_requested():
                    return 0
                self.emit_activity("Portal Navigation: Active session confirmed. Beginning multi-query job search...")
                stats = platform.search_and_apply(stop_check=self.is_stop_requested)
                applied_count = int(stats.get("jobs_applied", 0))
                self.emit_activity(f"Naukri session completed. Applied: {applied_count}")
            finally:
                platform.close()
        except Exception as e:
            if not self.is_stop_requested():
                self.record_error(f"Naukri engine error: {e}")
        finally:
            self._active_platform = None
        return applied_count

    def _run_indeed_engine(self, max_applications: Optional[int] = None) -> int:
        """Executes Indeed automation loop with browser isolation."""
        self.emit_activity("Agent Action: Preparing persistent Indeed profile and clearing locks...")
        applied_count = 0
        try:
            from platforms.router import IndeedPlatform
            user_id = getattr(self, "user_id", 1)
            platform = IndeedPlatform(user_id=user_id, automation_bridge=self.bridge)
            platform.platform_config = platform.platform_config or {}
            try:
                from app.services.platform_service import PlatformService
                p_cfg = PlatformService().get_platform_config("indeed") or {}
                platform.platform_config.update(p_cfg)
            except Exception:
                pass
            platform.platform_config["run_in_background"] = self.headless
            if max_applications is not None:
                platform.platform_config["max_applications"] = max_applications
                platform.platform_config["batch_slice"] = max_applications
                platform.platform_config["is_batch_run"] = True
                platform.platform_config["switch_number"] = max_applications
            self._active_platform = platform
            try:
                self.emit_activity("Agent Action: Launching isolated stealth Chrome browser for Indeed...")
                platform.initialize()
                if self.is_stop_requested():
                    return 0
                self.emit_activity("Session State: Navigating to Indeed portal and checking session...")
                if not platform.login():
                    self.record_intervention(
                        AutomationInterventionEvent(
                            run_id=self.run_id,
                            platform="indeed",
                            intervention_type=InterventionType.LOGIN_REQUIRED,
                            message="Indeed login/OTP authentication required in browser.",
                        )
                    )
                    return 0
                if self.is_stop_requested():
                    return 0
                self.emit_activity("Portal Navigation: Active session confirmed. Beginning multi-query rotation search...")
                stats = platform.search_and_apply(stop_check=self.is_stop_requested)
                applied_count = int(stats.get("jobs_applied", 0))
                self.emit_activity(f"Indeed session completed. Applied: {applied_count}")
            finally:
                platform.close()
        except Exception as e:
            if not self.is_stop_requested():
                self.record_error(f"Indeed engine error: {e}")
        finally:
            self._active_platform = None
        return applied_count

    def _run_foundit_engine(self, max_applications: Optional[int] = None) -> int:
        """Executes Foundit automation loop with browser isolation."""
        self.emit_activity("Initializing Foundit automation engine...")
        applied_count = 0
        try:
            from platforms.router import FounditPlatform
            user_id = getattr(self, "user_id", 1)
            platform = FounditPlatform(user_id=user_id, automation_bridge=self.bridge)
            platform.platform_config = platform.platform_config or {}
            try:
                from app.services.platform_service import PlatformService
                p_cfg = PlatformService().get_platform_config("foundit") or {}
                platform.platform_config.update(p_cfg)
            except Exception:
                pass
            platform.platform_config["run_in_background"] = self.headless
            if max_applications is not None:
                platform.platform_config["max_applications"] = max_applications
                platform.platform_config["batch_slice"] = max_applications
                platform.platform_config["is_batch_run"] = True
                platform.platform_config["switch_number"] = max_applications
            self._active_platform = platform
            try:
                platform.initialize()
                if self.is_stop_requested():
                    return 0
                if not platform.login():
                    self.record_intervention(
                        AutomationInterventionEvent(
                            run_id=self.run_id,
                            platform="foundit",
                            intervention_type=InterventionType.LOGIN_REQUIRED,
                            message="Foundit login/OTP authentication required in browser.",
                        )
                    )
                    return 0
                if self.is_stop_requested():
                    return 0
                stats = platform.search_and_apply(stop_check=self.is_stop_requested, log_callback=self.emit_activity)
                applied_count = int(stats.get("jobs_applied", 0))
                self.emit_activity(f"Foundit session completed. Applied: {applied_count}")
            finally:
                platform.close()
        except Exception as e:
            if not self.is_stop_requested():
                self.record_error(f"Foundit engine error: {e}")
        finally:
            self._active_platform = None
        return applied_count

    def _run_glassdoor_engine(self, max_applications: Optional[int] = None) -> int:
        """Executes Glassdoor automation loop with browser isolation."""
        self.emit_activity("Initializing Glassdoor automation engine...")
        applied_count = 0
        try:
            from platforms.router import GlassdoorPlatform
            user_id = getattr(self, "user_id", 1)
            platform = GlassdoorPlatform(user_id=user_id, automation_bridge=self.bridge)
            platform.platform_config = platform.platform_config or {}
            try:
                from app.services.platform_service import PlatformService
                p_cfg = PlatformService().get_platform_config("glassdoor") or {}
                platform.platform_config.update(p_cfg)
            except Exception:
                pass
            platform.platform_config["run_in_background"] = self.headless
            if max_applications is not None:
                platform.platform_config["max_applications"] = max_applications
                platform.platform_config["batch_slice"] = max_applications
                platform.platform_config["is_batch_run"] = True
                platform.platform_config["switch_number"] = max_applications
            self._active_platform = platform
            try:
                platform.initialize()
                if self.is_stop_requested():
                    return 0
                if not platform.login():
                    self.record_intervention(
                        AutomationInterventionEvent(
                            run_id=self.run_id,
                            platform="glassdoor",
                            intervention_type=InterventionType.LOGIN_REQUIRED,
                            message="Glassdoor login/OTP authentication required in browser.",
                        )
                    )
                    return 0
                if self.is_stop_requested():
                    return 0
                stats = platform.search_and_apply(stop_check=self.is_stop_requested, log_callback=self.emit_activity)
                applied_count = int(stats.get("jobs_applied", 0))
                self.emit_activity(f"Glassdoor session completed. Applied: {applied_count}")
            finally:
                platform.close()
        except Exception as e:
            if not self.is_stop_requested():
                self.record_error(f"Glassdoor engine error: {e}")
        finally:
            self._active_platform = None
        return applied_count

    def _run_universal_engine(self) -> None:
        """Executes the universal AI application orchestrator in an isolated asyncio event loop."""
        self.emit_activity("Initializing Universal AI Application Agent...")
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_run_universal())
        except Exception as e:
            if not self.is_stop_requested():
                self.record_error(f"Universal engine error: {e}")
        finally:
            try:
                # Gracefully cancel all remaining pending tasks (Stagehand CDP/RPC readers, keepalive)
                pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            finally:
                try:
                    loop.close()
                except Exception:
                    pass
                try:
                    asyncio.set_event_loop(None)
                except Exception:
                    pass
            self._active_orchestrator = None

    async def _async_run_universal(self) -> None:
        """Asynchronous execution flow for universal portal automation."""
        try:
            from app.services.settings_service import SettingsService
            settings_svc = SettingsService()
            if not settings_svc.is_universal_agent_enabled():
                self.record_error("Universal AI Application Agent is currently disabled in Settings.")
                return
        except Exception:
            pass

        target_url = self.target_url
        if not target_url:
            try:
                from app.repositories.job_repository import JobRepository
                repo = JobRepository()
                jobs = repo.get_jobs(limit=20)
                portal_jobs = [
                    j for j in jobs
                    if getattr(j, "application_method", "") in ("COMPANY_PORTAL", "EXTERNAL")
                    and (getattr(j, "application_url", None) or getattr(j, "url", None))
                ]
                if portal_jobs:
                    target_url = getattr(portal_jobs[0], "application_url", None) or getattr(portal_jobs[0], "url", None)
                    if not self.job_title:
                        self.job_title = getattr(portal_jobs[0], "title", "Target Position")
                    if not self.company:
                        self.company = getattr(portal_jobs[0], "company", "Target Company")
                    self.emit_activity(f"Selected pending company portal job: {self.job_title} @ {self.company}")
            except Exception:
                pass

        if not target_url:
            self.record_error("No target application URL specified. Please enter a portal URL or select a discovered job.")
            return

        title = self.job_title or "Target Position"
        comp = self.company or "Target Company"

        # Record discovery & qualification in database & UI
        disc_event = JobDiscoveredEvent(
            run_id=self.run_id,
            platform="universal",
            title=title,
            company=comp,
            url=target_url,
            application_method="COMPANY_PORTAL",
            application_url=target_url,
        )
        self.record_job_discovered(disc_event)

        eval_event = JobEvaluatedEvent(
            run_id=self.run_id,
            platform="universal",
            title=title,
            company=comp,
            is_qualified=True,
        )
        self.record_job_evaluated(eval_event)

        self.progress.current_job = f"{title} @ {comp}"
        self.progress_updated.emit(self.progress)

        # Setup orchestrator
        if self.orchestrator:
            orch = self.orchestrator
        else:
            from app.services.automation.universal_agent.orchestrator import UniversalApplicationOrchestrator
            cand_ctx = dict(self.candidate_context or {})
            try:
                from app.services.profile_service import ProfileService
                from app.services.resume_service import ResumeService
                ps = ProfileService()
                p_user, p_prof, p_pro = ps.get_primary_user_profile()
                if p_user and p_prof:
                    cand_ctx.setdefault("user.first_name", p_prof.first_name)
                    cand_ctx.setdefault("user.last_name", p_prof.last_name)
                    cand_ctx.setdefault("user.name", p_user.name)
                    cand_ctx.setdefault("user.email", p_user.email)
                    phone_val = getattr(p_prof, "phone_number", None) or p_user.phone
                    if phone_val:
                        cand_ctx.setdefault("profile.phone_number", phone_val)
                    if p_prof.current_city:
                        cand_ctx.setdefault("profile.current_city", p_prof.current_city)
                    if p_prof.state:
                        cand_ctx.setdefault("profile.state", p_prof.state)
                    if p_prof.zipcode:
                        cand_ctx.setdefault("profile.zipcode", p_prof.zipcode)
                    if p_prof.country:
                        cand_ctx.setdefault("profile.country", p_prof.country)
                if p_pro:
                    if p_pro.cover_letter:
                        cand_ctx.setdefault("profile.cover_letter", p_pro.cover_letter)
                        cand_ctx.setdefault("cover_letter", p_pro.cover_letter)
                    if p_pro.summary:
                        cand_ctx.setdefault("profile.summary", p_pro.summary)
                        cand_ctx.setdefault("summary", p_pro.summary)
                    if p_pro.headline:
                        cand_ctx.setdefault("profile.headline", p_pro.headline)
                    if p_pro.linkedin_url:
                        cand_ctx.setdefault("profile.linkedin_url", p_pro.linkedin_url)
                        cand_ctx.setdefault("linkedin_url", p_pro.linkedin_url)
                    if p_pro.github_url:
                        cand_ctx.setdefault("profile.github_url", p_pro.github_url)
                        cand_ctx.setdefault("github_url", p_pro.github_url)
                    if p_pro.portfolio_url:
                        cand_ctx.setdefault("profile.portfolio_url", p_pro.portfolio_url)
                        cand_ctx.setdefault("portfolio_url", p_pro.portfolio_url)
                    if p_pro.years_of_experience is not None:
                        cand_ctx.setdefault("profile.years_of_experience", p_pro.years_of_experience)
                        cand_ctx.setdefault("years_of_experience", p_pro.years_of_experience)
                    if p_pro.current_title:
                        cand_ctx.setdefault("profile.current_title", p_pro.current_title)
                    if p_pro.current_employer:
                        cand_ctx.setdefault("profile.current_employer", p_pro.current_employer)
                    if p_pro.current_ctc is not None:
                        cand_ctx.setdefault("profile.current_ctc", p_pro.current_ctc)
                    if p_pro.expected_ctc is not None:
                        cand_ctx.setdefault("profile.expected_ctc", p_pro.expected_ctc)
                    if p_pro.notice_period_days is not None:
                        cand_ctx.setdefault("profile.notice_period_days", p_pro.notice_period_days)
                    if p_pro.skills:
                        cand_ctx.setdefault("skills", p_pro.skills)
                        cand_ctx.setdefault("profile.skills", p_pro.skills)
                    if p_pro.work_experiences:
                        cand_ctx.setdefault("work_experience", p_pro.work_experiences)
                        cand_ctx.setdefault("profile.work_experiences", p_pro.work_experiences)
                    if p_pro.education_history:
                        cand_ctx.setdefault("education", p_pro.education_history)
                        cand_ctx.setdefault("profile.education", p_pro.education_history)
                if p_user:
                    rs = ResumeService()
                    default_res = rs.get_default_resume(user_id=p_user.id)
                    if default_res and default_res.file_path:
                        cand_ctx.setdefault("resume.file_path", default_res.file_path)

                try:
                    from modules.config_loader import get_workday_credentials
                    wd_creds = get_workday_credentials()
                    if wd_creds.get("username"):
                        cand_ctx.setdefault("workday_username", wd_creds["username"])
                    if wd_creds.get("password"):
                        cand_ctx.setdefault("workday_password", wd_creds["password"])
                except Exception:
                    pass
            except Exception as e:
                logger.warning("Could not auto-populate candidate_context from primary profile: %s", e)

            orch = UniversalApplicationOrchestrator(
                candidate_context=cand_ctx,
                on_review_requested=self.on_review_requested,
            )
        self._active_orchestrator = orch

        def _on_intervention(req):
            int_type = InterventionType.MANUAL_ACTION_REQUIRED
            reason_val = getattr(req.reason, "value", str(req.reason))
            if reason_val == "PRE_SUBMISSION_REVIEW":
                int_type = InterventionType.PRE_SUBMISSION_REVIEW
            elif reason_val == "UNKNOWN_REQUIRED_FIELD":
                int_type = InterventionType.UNKNOWN_REQUIRED_FIELD
            elif reason_val == "CAPTCHA_CHALLENGE":
                int_type = InterventionType.CAPTCHA_DETECTED
            elif reason_val == "LOGIN_REQUIRED":
                int_type = InterventionType.LOGIN_REQUIRED
            elif reason_val in ("TWO_FACTOR_AUTH", "OTP_REQUIRED"):
                int_type = InterventionType.TWO_FACTOR_AUTH

            ev = AutomationInterventionEvent(
                run_id=self.run_id,
                platform="universal",
                intervention_type=int_type,
                message=req.message,
                action_url=target_url,
                details=req.details,
            )
            self.record_intervention(ev)

        def _on_state_transition(prev, new, reason, msg):
            new_val = getattr(new, "value", str(new))
            self.emit_activity(f"[{new_val}] {msg or ''}".strip())

        orch.intervention_manager.add_listener(_on_intervention)
        orch.state_machine.add_listener(_on_state_transition)

        res = await orch.run(
            portal_url=target_url,
            job_title=title,
            company=comp,
            headless=self.headless,
        )

        if getattr(res, "is_success", False):
            sub_event = ApplicationSubmittedEvent(
                run_id=self.run_id,
                platform="universal",
                title=title,
                company=comp,
                source_url=target_url,
            )
            self.record_application_submitted(sub_event)
            ref_num = getattr(res, "reference_number", None)
            if ref_num and ref_num != "N/A":
                self.emit_activity(f"Application reference confirmed: {ref_num}")
        elif getattr(getattr(res, "terminal_result", None), "value", None) == "MANUAL_COMPLETED":
            self.emit_activity(f"Universal application handed over to user: {title} @ {comp}")
        else:
            err_msg = getattr(res, "error_message", None) or getattr(getattr(res, "terminal_result", None), "value", "Failed")
            self.record_error(f"Universal application: {err_msg}")

        # Ensure any pending intervention state is cleared
        self.intervention_dismissed.emit()


class AutomationManager(QObject):
    """Application-level automation coordinator managing worker lifecycle and persistence."""

    state_changed = Signal(str, str)  # (run_id, new_state)
    progress_updated = Signal(object)
    job_discovered = Signal(object)
    job_evaluated = Signal(object)
    application_submitted = Signal(object)
    intervention_required = Signal(object)
    intervention_dismissed = Signal()
    activity_logged = Signal(str, str)
    run_finished = Signal(object)  # AutomationRunResult

    _instance: Optional["AutomationManager"] = None

    @classmethod
    def get_instance(cls) -> Optional["AutomationManager"]:
        """Returns the active AutomationManager instance if instantiated."""
        return cls._instance

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        AutomationManager._instance = self
        self._session_factory = session_factory or SessionLocal
        self._current_state = AutomationState.IDLE
        self._current_worker: Optional[AutomationWorker] = None
        self._current_run: Optional[AutomationRun] = None
        self._cleanup_orphaned_runs()

    def stop_and_wait(self, timeout_ms: int = 3000) -> bool:
        """Signals active worker to stop cooperatively and waits boundedly for termination."""
        if not self._current_worker:
            return True
        self.request_stop()
        if self._current_worker.isRunning():
            return self._current_worker.wait(timeout_ms)
        return True

    def provide_intervention_input(self, value: str, intervention_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Delivers user input from UI or Copilot chat to the active worker and bridge."""
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.provide_intervention_input(value, intervention_id=intervention_id, metadata=metadata)
        self.intervention_dismissed.emit()

    def dismiss_intervention(self, intervention_id: Optional[str] = None) -> None:
        """Dismisses the active intervention dialog across the UI."""
        if self._current_worker and hasattr(self._current_worker, "bridge") and self._current_worker.bridge:
            self._current_worker.bridge.dismiss_intervention(intervention_id)
        self.intervention_dismissed.emit()

    def _cleanup_orphaned_runs(self) -> None:
        """Recovers stale or crashed runs left in non-terminal states from prior sessions."""
        try:
            with get_db_session(self._session_factory) as session:
                stale_runs = session.query(AutomationRun).filter(
                    AutomationRun.status.in_([
                        AutomationState.STARTING.value,
                        AutomationState.RUNNING.value,
                        AutomationState.STOP_REQUESTED.value,
                        AutomationState.STOPPING.value,
                    ])
                ).all()
                for r in stale_runs:
                    r.status = AutomationState.COMPLETED.value if (r.applications_submitted or 0) > 0 else "STOPPED"
                    r.finished_at = datetime.now(timezone.utc)
                    r.stop_reason = "Interrupted by session exit"
                if stale_runs:
                    session.commit()
        except Exception as exc:
            logger.debug("Notice cleaning up orphaned runs: %s", exc)

    def get_state(self) -> AutomationState:
        """Returns the current state machine state."""
        return self._current_state

    def get_current_run(self) -> Optional[AutomationRun]:
        """Returns current active run model if one is executing."""
        return self._current_run

    def is_running(self) -> bool:
        """Returns True if automation is active, paused, or stopping."""
        return self._current_state in (
            AutomationState.STARTING,
            AutomationState.RUNNING,
            AutomationState.PAUSED,
            AutomationState.STOP_REQUESTED,
            AutomationState.STOPPING,
        )

    def is_paused(self) -> bool:
        """Returns True if automation is currently paused."""
        return self._current_state == AutomationState.PAUSED

    def get_recent_runs(self, limit: int = 5) -> List[Any]:
        """Fetches recent run records from persistent AutomationRunRepository for UI display."""
        try:
            with get_db_session(self._session_factory) as session:
                repo = AutomationRunRepository(session)
                return repo.list_recent(limit=limit)
        except Exception as exc:
            logger.debug("Failed to fetch recent runs: %s", exc)
            return []

    def start_automation(
        self,
        platform: str = "linkedin",
        custom_runner: Optional[Callable[[AutomationWorker], None]] = None,
        target_url: Optional[str] = None,
        job_title: Optional[str] = None,
        company: Optional[str] = None,
        candidate_context: Optional[Dict[str, Any]] = None,
        headless: Optional[bool] = None,
        on_review_requested: Optional[Callable[..., Any]] = None,
        orchestrator: Optional[Any] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Initiates an automation run if idle."""
        if self.is_running():
            return False, "Automation is already running."

        run_id = str(uuid.uuid4())
        platform_clean = (platform or "linkedin").strip().lower()

        try:
            with get_db_session(self._session_factory) as session:
                repo = AutomationRunRepository(session)
                self._current_run = repo.create_run(
                    run_id=run_id,
                    platform=platform_clean,
                    status=AutomationState.STARTING.value,
                )
        except Exception as exc:
            logger.error("Failed to create AutomationRun database record: %s", exc)

        self._set_state(AutomationState.STARTING, run_id=run_id)

        # Instantiate worker
        self._current_worker = AutomationWorker(
            run_id=run_id,
            platform=platform_clean,
            session_factory=self._session_factory,
            engine_runner=custom_runner,
            parent=self,
            target_url=target_url,
            job_title=job_title,
            company=company,
            candidate_context=candidate_context,
            headless=headless,
            on_review_requested=on_review_requested,
            orchestrator=orchestrator,
        )

        # Wire worker signals to manager handlers and external subscribers
        self._current_worker.state_changed.connect(self._on_worker_state_changed)
        self._current_worker.progress_updated.connect(self._on_worker_progress)
        self._current_worker.job_discovered.connect(self._on_worker_job_discovered)
        self._current_worker.job_evaluated.connect(self._on_worker_job_evaluated)
        self._current_worker.application_submitted.connect(self._on_worker_application_submitted)
        self._current_worker.intervention_required.connect(self._on_worker_intervention_required)
        self._current_worker.intervention_dismissed.connect(self.intervention_dismissed.emit)
        self._current_worker.activity_logged.connect(self._on_worker_activity_logged)
        self._current_worker.finished_result.connect(self._on_worker_finished)

        self._current_worker.start()
        return True, None

    def request_stop(self) -> Tuple[bool, Optional[str]]:
        """Signals active worker to stop cooperatively."""
        if not self.is_running() or not self._current_worker:
            return False, "No active automation run to stop."

        self._set_state(AutomationState.STOP_REQUESTED)
        self._current_worker.request_stop()
        return True, None

    def pause_automation(self) -> Tuple[bool, Optional[str]]:
        """Pauses active automation execution."""
        if not self.is_running() or not self._current_worker:
            return False, "No active automation run to pause."
        if self._current_state == AutomationState.PAUSED:
            return True, None
        self._current_worker.pause()
        self._set_state(AutomationState.PAUSED)
        return True, None

    def resume_automation(self) -> Tuple[bool, Optional[str]]:
        """Resumes paused automation execution."""
        if not self._current_worker:
            return False, "No active automation run to resume."
        if self._current_state != AutomationState.PAUSED:
            return True, None
        self._current_worker.resume()
        self._set_state(AutomationState.RUNNING)
        return True, None

    def toggle_pause(self) -> Tuple[bool, Optional[str]]:
        """Toggles between paused and running states."""
        if self._current_state == AutomationState.PAUSED:
            return self.resume_automation()
        elif self.is_running():
            return self.pause_automation()
        return False, "Automation is not active."

    def confirm_current_review(self, notes: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> bool:
        """Approves pending human review or OTP resolution on the active worker."""
        if self._current_worker and hasattr(self._current_worker, "confirm_review"):
            self._current_worker.confirm_review(notes=notes, data=data)
            self.intervention_dismissed.emit()
            return True
        return False

    def pause(self) -> None:
        """Alias for pause_automation."""
        self.pause_automation()

    def resume(self) -> None:
        """Alias for resume_automation."""
        self.resume_automation()

    def confirm_review(self, notes: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> bool:
        """Alias for confirm_current_review."""
        return self.confirm_current_review(notes=notes, data=data)

    def takeover_current_manually(self, notes: Optional[str] = None) -> bool:
        """Transfers control of current application session to the user."""
        if self._current_worker and hasattr(self._current_worker, "takeover_manually"):
            self._current_worker.takeover_manually(notes=notes)
            self.intervention_dismissed.emit()
            return True
        return False

    def cancel_current_review(self, reason: str = "User cancelled application.") -> bool:
        """Cancels pending review or active application."""
        if self._current_worker and hasattr(self._current_worker, "cancel_intervention"):
            self._current_worker.cancel_intervention(reason=reason)
            self.intervention_dismissed.emit()
            return True
        return False

    def mark_captcha_resolved(self) -> None:
        """Signals active worker that user has resolved CAPTCHA via human-in-the-loop dialog."""
        if self._current_worker:
            self._current_worker.mark_captcha_resolved()
            self.intervention_dismissed.emit()

    def mark_captcha_cancelled(self) -> None:
        """Signals active worker that user has cancelled/skipped CAPTCHA via human-in-the-loop dialog."""
        if self._current_worker:
            self._current_worker.mark_captcha_cancelled()
            self.intervention_dismissed.emit()

    def reset_captcha_status(self) -> None:
        """Resets manual CAPTCHA resolution flag on current worker."""
        if self._current_worker:
            self._current_worker.reset_captcha_status()

    def _set_state(self, new_state: AutomationState, run_id: Optional[str] = None) -> None:
        """Updates internal state and emits signal."""
        self._current_state = new_state
        rid = run_id or (self._current_worker.run_id if self._current_worker else "")
        self.state_changed.emit(rid, new_state.value)

    @Slot(str, str)
    def _on_worker_state_changed(self, run_id: str, state_str: str) -> None:
        """Handles worker state transitions."""
        try:
            new_state = AutomationState(state_str)
            self._current_state = new_state
            self.state_changed.emit(run_id, state_str)
        except ValueError:
            pass

    @Slot(object)
    def _on_worker_progress(self, progress: AutomationProgressEvent) -> None:
        """Updates persistent run record and emits progress."""
        try:
            with get_db_session(self._session_factory) as session:
                repo = AutomationRunRepository(session)
                repo.update_progress(
                    run_id=progress.run_id,
                    current_keyword=progress.current_term,
                    discovered=progress.jobs_discovered,
                    evaluated=progress.jobs_evaluated,
                    qualified=progress.jobs_qualified,
                    skipped=progress.jobs_skipped,
                    applied=progress.applications_submitted,
                    errors=progress.errors_count,
                )
        except Exception as exc:
            logger.error("DATABASE_PERSISTENCE_ERROR updating progress: %s", exc)

        self.progress_updated.emit(progress)

    @Slot(object)
    @Slot(object)
    def _on_worker_job_discovered(self, event: JobDiscoveredEvent) -> None:
        self.job_discovered.emit(event)

    @Slot(object)
    def _on_worker_job_evaluated(self, event: JobEvaluatedEvent) -> None:
        self.job_evaluated.emit(event)

    @Slot(object)
    def _on_worker_application_submitted(self, event: ApplicationSubmittedEvent) -> None:
        self.application_submitted.emit(event)

    @Slot(object)
    def _on_worker_intervention_required(self, event: AutomationInterventionEvent) -> None:
        self.intervention_required.emit(event)

    @Slot(str, str)
    def _on_worker_activity_logged(self, timestamp: str, message: str) -> None:
        self.activity_logged.emit(timestamp, message)

    @Slot(object)
    def _on_worker_finished(self, result: AutomationRunResult) -> None:
        """Finalizes run record in database and resets active state."""
        try:
            with get_db_session(self._session_factory) as session:
                repo = AutomationRunRepository(session)
                repo.finalize_run(
                    run_id=result.run_id,
                    status=result.status.value,
                    finished_at=result.finished_at,
                    stop_reason=result.stop_reason,
                )
        except Exception as exc:
            logger.error("DATABASE_PERSISTENCE_ERROR finalizing run: %s", exc)

        self._set_state(result.status, run_id=result.run_id)
        self.run_finished.emit(result)
        self._current_worker = None
        self._current_run = None

        # Notify global UI event bus so all views reflect latest database changes
        try:
            from app.ui.state import AppState
            state = AppState.get_instance()
            state.notify_data_updated("applications")
            state.notify_data_updated("jobs")
            state.notify_data_updated("dashboard")
            state.notify_data_updated("analytics")
        except Exception:
            pass


AutomationService = AutomationManager
