"""End-to-End Universal Application Orchestrator.

Coordinates browser session, DOM analysis, semantic fact mapping, hybrid form filling,
file uploading, human-in-the-loop intervention, and cryptographic audit snapshot recording.
Strictly enforces the V1 Human Review Gate before executing final application submissions.
"""

import asyncio
from dataclasses import dataclass, field
import json
import logging
import os
import random
import re
from typing import Any, Callable, Dict, List, Optional

from app.services.automation.universal_agent.browser_agent.base import BrowserAgent
from app.services.automation.universal_agent.browser_agent.session_manager import UniversalSessionManager
from app.services.automation.universal_agent.browser_agent.stagehand_agent import StagehandBrowserAgent
from app.services.automation.universal_agent.captcha_handler import UniversalCaptchaHandler
from app.services.automation.universal_agent.field_mapper import SemanticFieldMapper
from app.services.automation.universal_agent.file_uploader import FileUploader
from app.services.automation.universal_agent.form_filler import FormFiller, FormFillResult
from app.services.automation.universal_agent.intervention_manager import InterventionManager, InterventionRequest
from app.services.automation.universal_agent.page_analyzer import FormAnalysisResult, PageAnalyzer
from app.services.automation.universal_agent.result_verifier import ResultVerifier, VerificationResult
from app.services.automation.universal_agent.snapshot_recorder import ApplicationSubmissionSnapshot, SnapshotRecorder
from app.services.automation.universal_agent.state_machine import (
    AgentExecutionState,
    InterventionReason,
    TerminalResult,
    UniversalApplicationStateMachine,
)
from app.services.automation.universal_agent.checkpoint_manager import CheckpointManager, ExecutionCheckpoint
from app.services.automation.universal_agent.frame_resolver import FrameResolver
from app.services.automation.universal_agent.page_classifier import PageClassifier, PageHealthChecker, PageClass
from app.services.automation.universal_agent.popup_manager import PopupManager, PopupClassification
from app.services.automation.universal_agent.recovery_manager import RecoveryManager, FailureCategory
from app.services.automation.universal_agent.timeline import AgentRunTimeline
from app.services.automation.universal_agent.validation_resolver import ValidationResolver

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationResult:
    """Consolidated outcome of an end-to-end universal application run."""

    terminal_result: TerminalResult
    is_success: bool
    state: AgentExecutionState
    current_url: str
    job_title: Optional[str] = None
    company: Optional[str] = None
    reference_number: Optional[str] = None
    snapshot: Optional[ApplicationSubmissionSnapshot] = None
    verification: Optional[VerificationResult] = None
    fill_result: Optional[FormFillResult] = None
    timeline: Optional[AgentRunTimeline] = None
    error_message: Optional[str] = None


class UniversalApplicationOrchestrator:
    """Full-lifecycle automation engine for universal ATS portals with mandatory human confirmation."""

    def __init__(
        self,
        browser_agent: Optional[BrowserAgent] = None,
        session_manager: Optional[UniversalSessionManager] = None,
        page_analyzer: Optional[PageAnalyzer] = None,
        field_mapper: Optional[SemanticFieldMapper] = None,
        form_filler: Optional[FormFiller] = None,
        file_uploader: Optional[FileUploader] = None,
        intervention_manager: Optional[InterventionManager] = None,
        result_verifier: Optional[ResultVerifier] = None,
        captcha_handler: Optional[UniversalCaptchaHandler] = None,
        snapshot_recorder: Optional[SnapshotRecorder] = None,
        state_machine: Optional[UniversalApplicationStateMachine] = None,
        timeline: Optional[AgentRunTimeline] = None,
        candidate_context: Optional[Dict[str, Any]] = None,
        on_review_requested: Optional[Callable[["UniversalApplicationOrchestrator", FormAnalysisResult, FormFillResult], Any]] = None,
        recovery_manager: Optional[RecoveryManager] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ) -> None:
        self.timeline = timeline or AgentRunTimeline()
        self.state_machine = state_machine or UniversalApplicationStateMachine(timeline=self.timeline)
        self.session_manager = session_manager or UniversalSessionManager()
        self.browser_agent = browser_agent or StagehandBrowserAgent(session_manager=self.session_manager)
        self.page_analyzer = page_analyzer or PageAnalyzer()
        self.candidate_context = candidate_context or {}
        self.field_mapper = field_mapper or SemanticFieldMapper(candidate_context=self.candidate_context)
        self.file_uploader = file_uploader or FileUploader()
        self.form_filler = form_filler or FormFiller(file_uploader=self.file_uploader)
        self.intervention_manager = intervention_manager or InterventionManager()
        self.result_verifier = result_verifier or ResultVerifier()
        self.captcha_handler = captcha_handler or UniversalCaptchaHandler()
        self.snapshot_recorder = snapshot_recorder or SnapshotRecorder()
        self.on_review_requested = on_review_requested
        self.recovery_manager = recovery_manager or RecoveryManager()
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()

        self._last_analysis: Optional[FormAnalysisResult] = None
        self._last_fill_result: Optional[FormFillResult] = None

    def confirm_submission(self, notes: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> None:
        """User confirms pre-submission review or OTP resolution: approves action."""
        payload = {"action": "CONFIRM_SUBMIT", "notes": notes}
        if data:
            payload.update(data)
        if notes and "code" not in payload:
            payload["code"] = notes
        self.intervention_manager.resolve_resume(payload)

    async def _handle_otp_resolution(self, res: Any) -> bool:
        """Populates OTP/PIN code if provided in resolution and clicks Verify button."""
        otp_code = None
        if res and hasattr(res, "resolution_data") and res.resolution_data:
            otp_code = (
                res.resolution_data.get("code")
                or res.resolution_data.get("value")
                or res.resolution_data.get("notes")
            )
        import json
        js_fill_and_verify = f"""(() => {{
            const code = {json.dumps(str(otp_code or '').strip())};
            let filled = false;
            if (code && code.length > 0) {{
                // 1. Check for individual PIN boxes (e.g. #pin-code-1 to #pin-code-6, .pin-code-input__input)
                const pinInputs = Array.from(document.querySelectorAll('input[id*="pin-code"], input[class*="pin-code"], .pin-code-input__input, input[name*="pin-code"]'));
                if (pinInputs.length >= 4) {{
                    for (let i = 0; i < pinInputs.length && i < code.length; i++) {{
                        const inp = pinInputs[i];
                        inp.focus();
                        inp.value = code[i];
                        inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        inp.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true, key: code[i] }}));
                    }}
                    filled = true;
                }} else {{
                    // 2. Single OTP / code input
                    const singleInput = document.querySelector('input[autocomplete="one-time-code"], input[name*="code" i], input[id*="code" i], input[name*="otp" i], input[id*="otp" i], input[placeholder*="code" i]');
                    if (singleInput) {{
                        singleInput.focus();
                        singleInput.value = code;
                        singleInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        singleInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        filled = true;
                    }}
                }}
            }}

            // 3. Click Verify / Confirm / Submit button
            const allBtns = Array.from(document.querySelectorAll('button, oj-button, input[type="submit"], [role="button"], a.btn, .apply-flow-dialog__button--primary'));
            for (const b of allBtns) {{
                const t = (b.innerText || b.value || b.getAttribute('aria-label') || '').trim().toLowerCase();
                const isPrimaryVerify = b.classList.contains('apply-flow-dialog__button--primary');
                if (isPrimaryVerify || /^(verify|confirm|submit code|continue|next|sign in)$/i.test(t)) {{
                    const target = b.querySelector('button') || b;
                    target.click();
                    return true;
                }}
            }}
            return filled;
        }})()"""
        try:
            r = self.browser_agent.evaluate(js_fill_and_verify)
            if asyncio.iscoroutine(r):
                await r
        except Exception as e:
            logger.warning("Error running OTP fill & verify script: %s", e)
        await asyncio.sleep(3.5)
        if hasattr(self.browser_agent, "sync_active_page"):
            sync_r = self.browser_agent.sync_active_page()
            if asyncio.iscoroutine(sync_r):
                await sync_r
        return True

    async def _click_button_resilient(self, selector: str, button_text_hint: str = "next") -> bool:
        """Clicks a wizard advance or submit button with multi-tier custom element & JS fallbacks."""
        import json
        js_click = f"""(() => {{
            const sel = {json.dumps(selector)};
            const hint = {json.dumps(button_text_hint.lower())};
            let el = null;
            try {{
                if (sel) el = document.querySelector(sel);
            }} catch(e) {{}}

            if (!el) {{
                // Search candidate buttons by hint or role
                const candidates = Array.from(document.querySelectorAll('button, oj-button, oj-c-button, input[type="submit"], input[type="button"], a, [role="button"], div[role="button"], span[role="button"], [class*="apply" i]'));
                for (const c of candidates) {{
                    const t = (c.innerText || c.value || c.getAttribute('aria-label') || c.textContent || '').trim().toLowerCase();
                    const cleanT = t.replace(/[\\s\\u25b6\\u25b8\\u203a\\u00bb>]+/g, ' ').trim();
                    if (cleanT === hint || cleanT.startsWith(hint) || cleanT.includes(hint) || (hint.includes('next') && /^(next|continue|proceed)(\\s|$)/i.test(cleanT)) || (hint.includes('apply') && /^(apply|apply\\s+now)/i.test(cleanT))) {{
                        el = c;
                        break;
                    }}
                }}
            }}

            if (!el) {{
                // Search leaf elements for exact text
                const all = Array.from(document.querySelectorAll('*:not(script):not(style)'));
                for (const node of all) {{
                    if (node.children.length === 0) {{
                        const t = (node.innerText || node.textContent || '').trim().toLowerCase();
                        const cleanT = t.replace(/[\\s\\u25b6\\u25b8\\u203a\\u00bb>]+/g, ' ').trim();
                        if (cleanT === hint || cleanT.startsWith(hint) || (hint.includes('apply') && /^apply(\\s+now)?$/i.test(cleanT))) {{
                            el = node.closest('button, a, [role="button"], oj-button, oj-c-button') || node;
                            break;
                        }}
                    }}
                }}
            }}

            if (el) {{
                let target = el.querySelector('button, a, input');
                if (!target && el.shadowRoot) {{
                    target = el.shadowRoot.querySelector('button, a, input');
                }}
                if (!target) target = el;

                try {{ target.scrollIntoView({{ behavior: 'instant', block: 'center' }}); }} catch(e) {{}}
                try {{ target.focus(); }} catch(e) {{}}
                const opts = {{ bubbles: true, cancelable: true, view: window }};
                target.dispatchEvent(new PointerEvent('pointerdown', opts));
                target.dispatchEvent(new MouseEvent('mousedown', opts));
                target.dispatchEvent(new PointerEvent('pointerup', opts));
                target.dispatchEvent(new MouseEvent('mouseup', opts));
                target.click();
                if (el !== target) {{
                    try {{ el.click(); }} catch(e) {{}}
                }}
                return true;
            }}
            return false;
        }})()"""
        js_ok = False
        try:
            js_res = self.browser_agent.evaluate(js_click)
            js_ok = bool(await js_res if asyncio.iscoroutine(js_res) else js_res)
        except Exception as e:
            logger.debug("Resilient JS click error: %s", e)

        # Tier 2: Direct browser agent click
        direct_ok = False
        try:
            direct_ok = await self.browser_agent.click(selector)
        except Exception:
            try:
                direct_ok = await self.browser_agent.click(f"{selector} button, {selector} a")
            except Exception:
                direct_ok = False

        return js_ok or direct_ok

    def cancel(self, reason: str = "User cancelled application.") -> None:
        """User aborts the application run."""
        self.intervention_manager.resolve_cancel(self.state_machine, reason=reason)

    def takeover_manually(self, notes: Optional[str] = None) -> None:
        """Transfers control directly to the user, leaving the browser open."""
        self.intervention_manager.resolve_manual_takeover(
            state_machine=self.state_machine,
            agent=self.browser_agent,
            notes=notes,
        )

    async def run(
        self,
        portal_url: str,
        job_title: Optional[str] = None,
        company: Optional[str] = None,
        headless: bool = False,
        max_wizard_steps: int = 10,
        job_id: Optional[Any] = None,
    ) -> OrchestrationResult:
        """Executes full application lifecycle from navigation to certified submission."""
        current_url = portal_url
        step_idx = 0
        latest_fill_result: Optional[FormFillResult] = None
        latest_verification: Optional[VerificationResult] = None
        latest_snapshot: Optional[ApplicationSubmissionSnapshot] = None

        # Duplicate Application Protection Gate (Section 22)
        if job_id:
            try:
                from app.services.application_service import ApplicationService
                app_svc = ApplicationService()
                existing = app_svc.get_by_job_id(int(job_id))
                if existing and str(existing.status).upper() in ("SUBMITTED", "APPLIED", "UNDER_REVIEW", "SHORTLISTED", "INTERVIEW", "OFFER"):
                    logger.warning("Duplicate application detected for job_id=%s (status=%s). Duplicate prevented.", job_id, existing.status)
                    self.state_machine.complete(
                        terminal_result=TerminalResult.SKIPPED_DISQUALIFIED,
                        message=f"Job already has a recorded submission (Status: {existing.status}). Duplicate prevented.",
                    )
                    return self._build_result(portal_url, job_title, company)
            except Exception as e:
                logger.debug("Duplicate check bypassed: %s", e)

        try:
            # 1. INITIALIZING
            self.state_machine.transition_to(
                AgentExecutionState.INITIALIZING,
                message="Starting universal browser agent session.",
                metadata={"portal_url": portal_url, "job_title": job_title, "company": company},
            )

            if not self.browser_agent.is_initialized:
                await self.browser_agent.initialize(headless=headless)

            # Check for existing checkpoint to resume partially completed applications (GAP-04)
            start_step = 1
            if job_id:
                prior_cp = self.checkpoint_manager.load_checkpoint(str(job_id))
                if prior_cp and prior_cp.current_step > 1:
                    logger.info("Found prior execution checkpoint for job %s at step %d (url: %s). Resuming...",
                                job_id, prior_cp.current_step, prior_cp.current_url)
                    start_step = prior_cp.current_step
                    if prior_cp.current_url and prior_cp.current_url.startswith("http"):
                        portal_url = prior_cp.current_url

            # 2. NAVIGATING
            self.state_machine.transition_to(
                AgentExecutionState.NAVIGATING,
                message=f"Navigating to {portal_url}",
                metadata={"url": portal_url},
            )
            nav_ok = await self.browser_agent.navigate(portal_url)
            if not nav_ok:
                self.state_machine.pause_for_intervention(
                    reason=InterventionReason.NAVIGATION_OR_NETWORK_STALL,
                    message=f"Failed to navigate to {portal_url}",
                )
                res = await self.intervention_manager.wait_for_resolution()
                if res.resolution_action != "RESUME":
                    return self._build_result(current_url, job_title, company)

            # 3. Step Loop (Single page application or multi-step wizard)
            for step_idx in range(start_step, max_wizard_steps + 1):
                current_url = await self.browser_agent.get_url()

                # Save execution checkpoint (Section 24)
                self.checkpoint_manager.save_checkpoint(
                    ExecutionCheckpoint(
                        application_id=None,
                        job_id=str(job_id) if job_id else None,
                        current_url=current_url,
                        page_role="APPLICATION_STEP",
                        execution_state=self.state_machine.state.value,
                        current_step=step_idx,
                        completed_steps=[f"step_{i}" for i in range(1, step_idx)],
                    )
                )

                # Wait for SPA DOM mutation settling and dismiss unexpected popups (Sections 5 & 11)
                await PageHealthChecker.wait_for_page_ready(self.browser_agent, timeout=5.0)
                _, detected_popup = await PopupManager.scan_and_dismiss_popups(self.browser_agent)
                if detected_popup:
                    if detected_popup.classification == PopupClassification.AUTHENTICATION:
                        self.intervention_manager.trigger_intervention(
                            self.state_machine,
                            reason=InterventionReason.LOGIN_REQUIRED,
                            message=f"Authentication modal detected: {detected_popup.text_content[:80]}",
                            details={"popup_text": detected_popup.text_content},
                        )
                        res = await self.intervention_manager.wait_for_resolution()
                        if res.resolution_action != "RESUME":
                            return self._build_result(current_url, job_title, company)
                    elif detected_popup.classification == PopupClassification.SECURITY:
                        self.intervention_manager.trigger_intervention(
                            self.state_machine,
                            reason=InterventionReason.CAPTCHA_CHALLENGE,
                            message="Security verification overlay detected.",
                            details={"popup_text": detected_popup.text_content},
                        )
                        res = await self.intervention_manager.wait_for_resolution()
                        if res.resolution_action != "RESUME":
                            return self._build_result(current_url, job_title, company)

                # Page Health Evaluation (Section 7 & 28)
                health = await PageHealthChecker.evaluate_health(self.browser_agent)
                if health.page_class == PageClass.CAPTCHA:
                    self.intervention_manager.trigger_intervention(
                        self.state_machine,
                        reason=InterventionReason.CAPTCHA_CHALLENGE,
                        message="Security challenge page detected. Please complete verification in browser.",
                    )
                    res = await self.intervention_manager.wait_for_resolution()
                    if res.resolution_action != "RESUME":
                        return self._build_result(current_url, job_title, company)
                elif health.page_class == PageClass.TWO_FACTOR_AUTH:
                    self.intervention_manager.trigger_intervention(
                        self.state_machine,
                        reason=InterventionReason.TWO_FACTOR_AUTH,
                        message="One-time verification code (OTP) required. Please enter the verification code in the JobPilot dialog (or into the browser) and click 'Verify & Continue'.",
                        details={"url": current_url, "type": "OTP_VERIFICATION"},
                    )
                    res = await self.intervention_manager.wait_for_resolution()
                    if res.resolution_action != "RESUME":
                        return self._build_result(current_url, job_title, company)
                    # Settle and let any auto-advance or manual submission take effect
                    await self._handle_otp_resolution(res)
                    continue

                # A. ANALYZING PAGE
                self.state_machine.transition_to(
                    AgentExecutionState.ANALYZING_PAGE,
                    message=f"Analyzing page structure (Step {step_idx}).",
                    metadata={"step": step_idx, "url": current_url},
                )
                analysis = await self.page_analyzer.analyze(self.browser_agent)
                self._last_analysis = analysis

                # Check for security challenges / login gates / OTP
                if analysis.challenge_detected:
                    if analysis.challenge_detected == "CAPTCHA_CHALLENGE":
                        reason = InterventionReason.CAPTCHA_CHALLENGE
                        msg = "Security gate detected: CAPTCHA_CHALLENGE"
                    elif analysis.challenge_detected == "TWO_FACTOR_AUTH":
                        reason = InterventionReason.TWO_FACTOR_AUTH
                        msg = "One-time verification code (OTP) required. Please check your email or phone, enter the code in the browser window, then click 'I've Solved It / Continue'."
                    else:
                        reason = InterventionReason.LOGIN_REQUIRED
                        msg = f"Security gate detected: {analysis.challenge_detected}"

                    self.intervention_manager.trigger_intervention(
                        self.state_machine,
                        reason=reason,
                        message=msg,
                        details={"challenge": analysis.challenge_detected},
                    )
                    res = await self.intervention_manager.wait_for_resolution()
                    if res.resolution_action == "MANUAL_TAKEOVER":
                        return self._build_result(current_url, job_title, company)
                    elif res.resolution_action == "CANCEL":
                        return self._build_result(current_url, job_title, company)
                    # Resumed: if OTP, check if verify/continue needs clicking
                    if reason == InterventionReason.TWO_FACTOR_AUTH:
                        await self._handle_otp_resolution(res)
                    # Re-analyze page
                    analysis = await self.page_analyzer.analyze(self.browser_agent)
                    self._last_analysis = analysis

                # Check if current page is an overview/landing page with 0 form fields
                if len(analysis.fields) == 0:
                    # If forms were already filled in prior steps, check if the page is already confirmed / thank-you
                    if latest_fill_result is not None:
                        verification = await self.result_verifier.verify_submission(self.browser_agent)
                        if verification.is_success:
                            logger.info("Application confirmation detected on 0-field page (%s). Finalizing...", current_url)
                            self.result_verifier.verify_and_update_state(self.state_machine, verification)
                            snapshot = await self.snapshot_recorder.capture_snapshot(
                                agent=self.browser_agent,
                                verification=verification,
                                terminal_result=self.state_machine.terminal_result,
                                filled_fields={k: v.get("value") for k, v in latest_fill_result.field_details.items()},
                                job_title=job_title,
                                company=company,
                            )
                            return self._build_result(
                                current_url=await self.browser_agent.get_url(),
                                job_title=job_title,
                                company=company,
                                verification=verification,
                                snapshot=snapshot,
                                fill_result=latest_fill_result,
                            )

                    # Sync active tab/page in case a popup or external redirect opened
                    if hasattr(self.browser_agent, "sync_active_page"):
                        sync_r = self.browser_agent.sync_active_page()
                        if asyncio.iscoroutine(sync_r):
                            await sync_r

                    # Re-check analysis in case tab switch changed the page to an external portal
                    new_url = await self.browser_agent.get_url()
                    if new_url and new_url != current_url:
                        logger.info("Tab switch detected (%s -> %s). Re-analyzing page...", current_url, new_url)
                        current_url = new_url
                        analysis = await self.page_analyzer.analyze(self.browser_agent)
                        self._last_analysis = analysis

                    # Check if this is a 0-field landing page needing an entry click (e.g. "Apply Now")
                    # Note: If previous fields were already filled in earlier steps,
                    # this is the final review/submit step of a wizard, not an overview landing page!
                    is_wizard_final_step = (latest_fill_result is not None and (bool(analysis.submit_buttons) or bool(analysis.apply_now_buttons) or analysis.is_multi_step))
                    if is_wizard_final_step and not analysis.submit_buttons and analysis.apply_now_buttons:
                        analysis.submit_buttons = analysis.apply_now_buttons

                    # BUG-08: Check if application form is embedded inside an iframe (e.g. Greenhouse/Jobvite widget)
                    if len(analysis.fields) == 0 and not is_wizard_final_step:
                        try:
                            app_frame = await FrameResolver.find_application_frame(self.browser_agent)
                            if app_frame:
                                logger.info("Application form detected in iframe '%s' (inputs: %d, src: %s)", app_frame.selector, app_frame.input_count, app_frame.src)
                                if app_frame.src and app_frame.src.startswith("http") and not app_frame.is_accessible:
                                    logger.info("Navigating directly to iframe source URL: %s", app_frame.src)
                                    await self.browser_agent.navigate(app_frame.src)
                                    await asyncio.sleep(2.0)
                                    analysis = await self.page_analyzer.analyze(self.browser_agent)
                                    self._last_analysis = analysis
                        except Exception as frame_err:
                            logger.debug("Frame resolution probe error: %s", frame_err)

                    needs_entry_click = (len(analysis.fields) == 0 and not is_wizard_final_step) or (latest_fill_result is None and bool(analysis.apply_now_buttons))

                    if needs_entry_click:
                        entry_candidate = None
                        if analysis.apply_now_buttons:
                            entry_candidate = analysis.apply_now_buttons[0]
                        elif analysis.submit_buttons and latest_fill_result is None:
                            entry_candidate = analysis.submit_buttons[0]

                        if entry_candidate:
                            entry_sel = entry_candidate.get("selector", "a.btn")
                            entry_txt = entry_candidate.get("text", "Apply") or "Apply"
                            logger.info("Landing page detected. Clicking entry button '%s' (%s) to reach form.", entry_txt, entry_sel)
                            self.state_machine.transition_to(
                                AgentExecutionState.NAVIGATING,
                                message=f"Job overview detected. Clicking '{entry_txt}' to open application form.",
                                metadata={"selector": entry_sel},
                            )
                            await self._click_button_resilient(entry_sel, button_text_hint=entry_txt)
                            await asyncio.sleep(2.5)
                            if hasattr(self.browser_agent, "sync_active_page"):
                                sync_r = self.browser_agent.sync_active_page()
                                if asyncio.iscoroutine(sync_r):
                                    await sync_r
                            continue
                        else:
                            # LOW-03: Refined dynamic heuristic fallback for external job board buttons (e.g. Naukri "Apply on company site", Oracle CX, Workday)
                            js_find_entry = """(() => {
                                // 1. Scan leaf elements for exact or prominent Apply text
                                const allLeafs = Array.from(document.querySelectorAll('*:not(script):not(style)'));
                                for (const leaf of allLeafs) {
                                    if (leaf.children.length === 0) {
                                        const lt = (leaf.innerText || leaf.textContent || '').trim().toLowerCase();
                                        if (/^apply(\s+now)?$/i.test(lt)) {
                                            const target = leaf.closest('button, a, [role="button"], oj-button, oj-c-button, div, span') || leaf;
                                            let innerBtn = target.querySelector('button, a, input');
                                            if (!innerBtn && target.shadowRoot) innerBtn = target.shadowRoot.querySelector('button, a, input');
                                            if (!innerBtn) innerBtn = target;

                                            try { innerBtn.scrollIntoView({ behavior: 'instant', block: 'center' }); } catch(e) {}
                                            try { innerBtn.focus(); } catch(e) {}
                                            const opts = { bubbles: true, cancelable: true, view: window };
                                            innerBtn.dispatchEvent(new PointerEvent('pointerdown', opts));
                                            innerBtn.dispatchEvent(new MouseEvent('mousedown', opts));
                                            innerBtn.dispatchEvent(new PointerEvent('pointerup', opts));
                                            innerBtn.dispatchEvent(new MouseEvent('mouseup', opts));
                                            innerBtn.click();
                                            if (target !== innerBtn) {
                                                try { target.click(); } catch(e) {}
                                            }
                                            return true;
                                        }
                                    }
                                }

                                const els = Array.from(document.querySelectorAll('a, button, [role="button"], input[type="submit"], oj-button, oj-c-button, [data-qa*="apply" i], [data-automation-id*="apply" i], [class*="apply" i], [id*="apply" i]'));
                                for (const el of els) {
                                    const txt = (el.innerText || el.value || el.textContent || '').trim().toLowerCase();
                                    const href = (el.getAttribute('href') || '').toLowerCase();
                                    const id = (el.id || '').toLowerCase();
                                    const cls = (el.className || '').toLowerCase();
                                    const combined = txt + ' ' + id + ' ' + cls + ' ' + href;

                                    const isExplicitApply = /apply/i.test(txt) || /apply/i.test(href) || /apply/i.test(id) || /apply/i.test(cls);

                                    // Exclude header, nav, footer, menus, search modal, but NEVER exclude explicit apply buttons
                                    if (!isExplicitApply && el.closest('header, nav, footer, #header, #footer, #mainMenu, .main-menu, .menu, .dropdown-menu, .navigation, .site-header, .site-footer, .header-extras, .mega-menu, #search, .search-form, .search-suggestion, [class*="navbar" i], [id*="mainmenu" i]')) {
                                        continue;
                                    }

                                    // Filter out non-job application elements (filters, coupons, sharing, newsletter, cart, cancel, login)
                                    if (/filter|refine|search|voucher|promo|coupon|share|linkedin\\.com\\/sharing|twitter|facebook|cart|cancel|reset|login|sign-in/i.test(combined)) {
                                        continue;
                                    }

                                    // Filter out corporate consulting and service items only if not explicit apply
                                    if (!isExplicitApply && /services|solutions|portfolio|integration|architecture|consulting|outsourcing/i.test(txt)) {
                                        continue;
                                    }

                                    if (txt.includes('apply on company') || txt.includes('apply on employer') ||
                                        txt.includes('apply now') || txt === 'apply' || txt.includes('apply for this') ||
                                        txt.includes('submit application') || txt.includes('submit resume') ||
                                        href.includes('resume-registration') || href.includes('/apply') ||
                                        id.includes('apply-btn') || id.includes('apply-button') || id.includes('company-site') ||
                                        cls.includes('apply-btn') || cls.includes('apply-button') || cls.includes('company-site')) {
                                        let clickTarget = el.querySelector('button, a, input');
                                        if (!clickTarget && el.shadowRoot) clickTarget = el.shadowRoot.querySelector('button, a, input');
                                        if (!clickTarget) clickTarget = el;

                                        try { clickTarget.scrollIntoView({ behavior: 'instant', block: 'center' }); } catch(e) {}
                                        try { clickTarget.focus(); } catch(e) {}
                                        const opts = { bubbles: true, cancelable: true, view: window };
                                        clickTarget.dispatchEvent(new PointerEvent('pointerdown', opts));
                                        clickTarget.dispatchEvent(new MouseEvent('mousedown', opts));
                                        clickTarget.dispatchEvent(new PointerEvent('pointerup', opts));
                                        clickTarget.dispatchEvent(new MouseEvent('mouseup', opts));
                                        clickTarget.click();
                                        if (el !== clickTarget) {
                                            try { el.click(); } catch(e) {}
                                        }
                                        return true;
                                    }
                                }
                                return false;
                            })()"""
                            try:
                                clicked_res = self.browser_agent.evaluate(js_find_entry)
                                clicked = await clicked_res if asyncio.iscoroutine(clicked_res) else clicked_res
                                if clicked:
                                    logger.info("Discovered and clicked Apply / Company Site button via heuristic scan.")
                                    await asyncio.sleep(2.5)
                                    if hasattr(self.browser_agent, "sync_active_page"):
                                        sync_r2 = self.browser_agent.sync_active_page()
                                        if asyncio.iscoroutine(sync_r2):
                                            await sync_r2
                                    continue
                            except Exception:
                                pass

                            # Settle wait retry for dynamic SPA career portals (Knockout/Oracle JET/Angular)
                            if not getattr(self, "_retried_hydration_wait", False) and any(spa in current_url.lower() for spa in ["oraclecloud.com", "candidateexperience", "myworkdayjobs.com", "icims.com"]):
                                self._retried_hydration_wait = True
                                logger.info("Dynamic SPA career portal detected (%s). Settling for 2.5s for components to hydrate...", current_url)
                                await asyncio.sleep(2.5)
                                continue

                            logger.warning("No interactive form fields or 'Apply' links found on page: %s", current_url)
                            self.intervention_manager.trigger_intervention(
                                self.state_machine,
                                reason=InterventionReason.MANUAL_ACTION_REQUIRED,
                                message="No application form fields or 'Apply' links could be detected on this page. Please navigate to the application form or take over manually.",
                                details={"url": current_url},
                            )
                            res = await self.intervention_manager.wait_for_resolution()
                            if res.resolution_action != "RESUME":
                                return self._build_result(current_url, job_title, company)
                            continue

                # B. MAPPING FIELDS
                self.state_machine.transition_to(
                    AgentExecutionState.MAPPING_FIELDS,
                    message=f"Mapping {len(analysis.fields)} input fields to candidate data.",
                    metadata={"fields_count": len(analysis.fields)},
                )
                mapping_result = self.field_mapper.map_fields(analysis)

                if mapping_result.has_blocking_intervention:
                    missing_labels = [m.field_info.label for m in mapping_result.unresolved_required_fields]
                    self.intervention_manager.trigger_intervention(
                        self.state_machine,
                        reason=InterventionReason.UNKNOWN_REQUIRED_FIELD,
                        message=f"Missing required candidate facts for: {', '.join(missing_labels)}",
                        details={"unresolved_fields": missing_labels},
                    )
                    res = await self.intervention_manager.wait_for_resolution()
                    if res.resolution_action != "RESUME":
                        return self._build_result(current_url, job_title, company)

                    # Update context with user-supplied answers, persist to QnA bank, and re-map
                    if res.resolution_data:
                        self.field_mapper.candidate_context.update(res.resolution_data)
                        # Persist user-resolved answers into QnA bank so future forms never prompt again
                        for q_key, ans_val in res.resolution_data.items():
                            if ans_val and str(ans_val).strip():
                                try:
                                    if hasattr(self.field_mapper, "qna_engine") and self.field_mapper.qna_engine:
                                        self.field_mapper.qna_engine.save_learned_answer(
                                            question=q_key,
                                            answer=str(ans_val).strip(),
                                            category="user_resolved",
                                            source="manual",
                                        )
                                    elif hasattr(self.field_mapper, "qna_service") and self.field_mapper.qna_service:
                                        self.field_mapper.qna_service.add_entry(
                                            question=q_key,
                                            answer=str(ans_val).strip(),
                                            category="user_resolved",
                                            source="MANUAL",
                                            confidence=1.0,
                                        )
                                except Exception as e:
                                    logger.warning("Failed to persist user-resolved answer for '%s' to QnA bank: %s", q_key, e)
                    mapping_result = self.field_mapper.map_fields(analysis)

                # C. FILLING FORM
                self.state_machine.transition_to(
                    AgentExecutionState.FILLING_FORM,
                    message="Populating form fields with verified candidate facts.",
                )
                fill_res = await self.form_filler.fill_form(self.browser_agent, mapping_result)
                self._last_fill_result = fill_res
                latest_fill_result = fill_res

                # C2. Dynamic Field Re-Scan: After filling, re-analyze DOM to discover
                # conditionally revealed fields (e.g. selecting "Yes" to visa sponsorship
                # reveals a follow-up country dropdown). Up to 2 re-scan cycles.
                for _rescan_idx in range(2):
                    try:
                        re_analysis = await self.page_analyzer.analyze(self.browser_agent)
                    except (StopIteration, StopAsyncIteration):
                        break
                    new_field_ids = {f.field_id or f.name for f in re_analysis.fields}
                    old_field_ids = {f.field_id or f.name for f in analysis.fields}
                    newly_revealed = new_field_ids - old_field_ids
                    if not newly_revealed:
                        break
                    logger.info("Dynamic re-scan #%d: discovered %d newly revealed fields: %s",
                                _rescan_idx + 1, len(newly_revealed),
                                [f.label or f.name for f in re_analysis.fields if (f.field_id or f.name) in newly_revealed])
                    analysis = re_analysis
                    self._last_analysis = analysis
                    mapping_result = self.field_mapper.map_fields(analysis)
                    fill_res = await self.form_filler.fill_form(self.browser_agent, mapping_result)
                    self._last_fill_result = fill_res
                    latest_fill_result = fill_res

                # D. Progression Decision: Intermediate Wizard Step vs Final Submit
                has_next = bool(analysis.next_buttons)
                has_submit = bool(analysis.submit_buttons)

                if (analysis.is_multi_step or has_next) and has_next and not has_submit:
                    # Intermediate Wizard Progression
                    next_sel = analysis.next_buttons[0].get("selector", "button[type='submit']")
                    next_txt = analysis.next_buttons[0].get("text", "Next")
                    self.state_machine.transition_to(
                        AgentExecutionState.NAVIGATING_NEXT_STEP,
                        message=f"Navigating to next step using selector '{next_sel}'.",
                    )
                    # BUG-10: Dismiss any delayed popup overlays before clicking
                    try:
                        await PopupManager.scan_and_dismiss_popups(self.browser_agent)
                    except Exception:
                        pass
                    click_ok = await self._click_button_resilient(next_sel, button_text_hint=next_txt)
                    logger.info("Clicked next step button '%s' (%s, ok=%s). Settling 2.5s for step transition...", next_txt, next_sel, click_ok)
                    await asyncio.sleep(2.5)

                    if hasattr(self.browser_agent, "sync_active_page"):
                        sync_r = self.browser_agent.sync_active_page()
                        if asyncio.iscoroutine(sync_r):
                            await sync_r

                    # Check for form validation errors after advancing (Section 14)
                    val_report = await ValidationResolver.inspect_validation_errors(self.browser_agent)
                    if val_report.has_errors:
                        # GAP-05: Attempt auto-remedy for invalid/unchecked fields
                        remedied = await ValidationResolver.attempt_auto_remedy(self.browser_agent, val_report)
                        if remedied > 0:
                            logger.info("Auto-remedied %d validation error inputs. Re-attempting step advance...", remedied)
                            await self._click_button_resilient(next_sel, button_text_hint=next_txt)
                            await asyncio.sleep(2.0)
                            val_report = await ValidationResolver.inspect_validation_errors(self.browser_agent)

                        if val_report.has_errors:
                            error_texts = [e.error_text for e in val_report.field_errors]
                            if error_texts or val_report.summary_banners:
                                logger.warning("Active validation errors detected after clicking next: %s", error_texts)
                                # BUG-05: Trigger intervention instead of silently continuing
                                self.intervention_manager.trigger_intervention(
                                    self.state_machine,
                                    reason=InterventionReason.POST_SUBMIT_VALIDATION_ERROR,
                                    message=f"Validation errors after step navigation: {'; '.join((error_texts + val_report.summary_banners)[:5])}. Please resolve in browser.",
                                    details={"field_errors": error_texts, "summary_banners": val_report.summary_banners},
                                )
                                res = await self.intervention_manager.wait_for_resolution()
                                if res.resolution_action != "RESUME":
                                    return self._build_result(current_url, job_title, company, fill_result=latest_fill_result)
                    continue

                else:
                    # Guardrail: If 0 fields were populated on a non-multi-step page and an Apply button exists, we are still on the overview page!
                    if fill_res.filled_fields == 0 and not analysis.is_multi_step and analysis.apply_now_buttons:
                        entry_candidate = analysis.apply_now_buttons[0]
                        entry_sel = entry_candidate.get("selector", "a.btn")
                        entry_txt = entry_candidate.get("text", "Apply Now") or "Apply Now"
                        logger.info("Zero fields populated and Apply button detected. Clicking '%s' (%s) to reach form.", entry_txt, entry_sel)
                        self.state_machine.transition_to(
                            AgentExecutionState.NAVIGATING,
                            message=f"Job overview detected. Clicking '{entry_txt}' to open application form.",
                            metadata={"selector": entry_sel},
                        )
                        await self._click_button_resilient(entry_sel, button_text_hint=entry_txt)
                        await asyncio.sleep(2.5)
                        if hasattr(self.browser_agent, "sync_active_page"):
                            sync_r = self.browser_agent.sync_active_page()
                            if asyncio.iscoroutine(sync_r):
                                await sync_r
                        continue

                    # Invariant: Bot must answer all screening questions and required fields before review
                    unfilled_required = [
                        f_name for f_name, f_data in fill_res.field_details.items()
                        if f_data.get("required") and f_data.get("status") != "FILLED"
                    ]
                    unfilled_screening_questions = [
                        f.label for f in analysis.fields
                        if f.label and f.input_type != "file" and ("?" in f.label or any(k in f.label.lower() for k in ["rpa", "experience", "ctc", "salary", "notice", "location", "authorized", "visa", "sponsorship"]))
                        and f.label not in [k for k, v in fill_res.field_details.items() if v.get("status") == "FILLED"]
                    ]

                    all_missing = list(dict.fromkeys(unfilled_required + unfilled_screening_questions))
                    if all_missing:
                        logger.warning("Unanswered questions detected before pre-submission review: %s", all_missing)
                        self.intervention_manager.trigger_intervention(
                            self.state_machine,
                            reason=InterventionReason.UNKNOWN_REQUIRED_FIELD,
                            message=f"Form questions unanswered: {', '.join(all_missing[:5])}. Please provide answers before review.",
                            details={"unresolved_fields": all_missing},
                        )
                        res = await self.intervention_manager.wait_for_resolution()
                        if res.resolution_action != "RESUME":
                            return self._build_result(current_url, job_title, company, fill_result=latest_fill_result)
                        if res.resolution_data:
                            self.field_mapper.candidate_context.update(res.resolution_data)
                            for q_k, a_v in res.resolution_data.items():
                                if a_v and str(a_v).strip():
                                    try:
                                        if hasattr(self.field_mapper, "qna_engine") and self.field_mapper.qna_engine:
                                            self.field_mapper.qna_engine.save_learned_answer(question=q_k, answer=str(a_v).strip(), category="user_resolved", source="manual")
                                        elif hasattr(self.field_mapper, "qna_service") and self.field_mapper.qna_service:
                                            self.field_mapper.qna_service.add_entry(question=q_k, answer=str(a_v).strip(), category="user_resolved", source="MANUAL", confidence=1.0)
                                    except Exception:
                                        pass
                        mapping_result = self.field_mapper.map_fields(analysis)
                        fill_res = await self.form_filler.fill_form(self.browser_agent, mapping_result)
                        self._last_fill_result = fill_res
                        latest_fill_result = fill_res

                    # Pre-review file upload assurance: Ensure resume is attached
                    cv_file_fields = [
                        f for f in analysis.fields 
                        if f.input_type == "file" and (
                            f.required 
                            or bool(re.search(r"cv|resume|curriculum|résumé", f.label or "", re.I))
                            or bool(re.search(r"cv|resume|curriculum|résumé", f.name or "", re.I))
                        )
                    ]
                    for cv_field in cv_file_fields:
                        cv_status = fill_res.field_details.get(cv_field.label, {}).get("status")
                        is_attached = await self.file_uploader.verify_upload(self.browser_agent, cv_field.selector)
                        if cv_status != "FILLED" or not is_attached:
                            resume_path = (
                                self.candidate_context.get("resume.file_path") or
                                (self.candidate_context.get("resume", {}) if isinstance(self.candidate_context.get("resume"), dict) else {}).get("resume.file_path") or
                                self.candidate_context.get("resume_path") or
                                (self.candidate_context.get("resume", {}) if isinstance(self.candidate_context.get("resume"), dict) else {}).get("file_path")
                            )
                            if not resume_path:
                                try:
                                    from modules.config_loader import get_resume
                                    resume_path = get_resume()
                                except Exception:
                                    pass
                            if resume_path:
                                # BUG-02 fix: Validate file exists before attempting upload
                                if not os.path.exists(resume_path):
                                    logger.error("Resume file does not exist at '%s'. Triggering intervention.", resume_path)
                                    self.intervention_manager.trigger_intervention(
                                        self.state_machine,
                                        reason=InterventionReason.UNKNOWN_REQUIRED_FIELD,
                                        message=f"Resume file not found at '{resume_path}'. Please provide a valid resume file path.",
                                        details={"field": cv_field.label, "missing_path": resume_path},
                                    )
                                    res = await self.intervention_manager.wait_for_resolution()
                                    if res.resolution_action != "RESUME":
                                        return self._build_result(current_url, job_title, company, fill_result=latest_fill_result)
                                    # Check if resolution provided a new path
                                    if res.resolution_data and res.resolution_data.get("resume_path"):
                                        resume_path = res.resolution_data["resume_path"]
                                    else:
                                        continue
                                logger.info("Ensuring resume upload for field '%s'...", cv_field.label)
                                ok_up, up_err = await self.file_uploader.upload_file(self.browser_agent, cv_field.selector, resume_path)
                                if ok_up:
                                    fill_res.field_details[cv_field.label] = {
                                        "status": "FILLED",
                                        "label": cv_field.label,
                                        "value": resume_path,
                                        "required": True,
                                        "input_type": "file",
                                        "provenance": "RESUME_FACT",
                                    }
                                else:
                                    # BUG-02 fix: Log and handle upload failure instead of silently proceeding
                                    logger.error("Resume upload FAILED for field '%s': %s", cv_field.label, up_err)
                                    self.intervention_manager.trigger_intervention(
                                        self.state_machine,
                                        reason=InterventionReason.UNKNOWN_REQUIRED_FIELD,
                                        message=f"Resume upload failed for '{cv_field.label}': {up_err or 'Unknown error'}. Please upload manually.",
                                        details={"field": cv_field.label, "error": up_err},
                                    )
                                    res = await self.intervention_manager.wait_for_resolution()
                                    if res.resolution_action != "RESUME":
                                        return self._build_result(current_url, job_title, company, fill_result=latest_fill_result)

                    # Ensure all mandatory consent & privacy checkboxes are accepted before presenting review
                    try:
                        await self.form_filler.ensure_mandatory_consent_accepted(self.browser_agent)
                    except Exception as e:
                        logger.warning("Error running consent sweep before review: %s", e)

                    # Final Submission Step -> ENFORCE V1 HUMAN REVIEW GATE
                    self.state_machine.transition_to(
                        AgentExecutionState.PENDING_HUMAN_REVIEW,
                        message="Form completed. Paused for mandatory candidate review before submission.",
                        metadata={"required_completion_rate": fill_res.required_completion_rate},
                    )

                    # Trigger intervention for human pre-submission review
                    self.intervention_manager.trigger_intervention(
                        self.state_machine,
                        reason=InterventionReason.PRE_SUBMISSION_REVIEW,
                        message="All required fields populated. Please review and confirm final submission.",
                        details={"fill_result": fill_res.field_details},
                    )

                    # Fire review requested hook if configured
                    if self.on_review_requested:
                        try:
                            cb_res = self.on_review_requested(self, analysis, fill_res)
                            if asyncio.iscoroutine(cb_res):
                                await cb_res
                        except Exception as e:
                            logger.error("Error in on_review_requested hook: %s", e)

                    resolution = await self.intervention_manager.wait_for_resolution()
                    if resolution.resolution_action == "MANUAL_TAKEOVER":
                        return self._build_result(current_url, job_title, company, fill_result=latest_fill_result)
                    elif resolution.resolution_action == "CANCEL":
                        return self._build_result(current_url, job_title, company, fill_result=latest_fill_result)

                    # Human Confirmed: Prepare Final Submission
                    self.state_machine.transition_to(
                        AgentExecutionState.SUBMITTING,
                        message="Human review confirmed. Executing final submission.",
                    )

                    # 1. Pre-Submission Security Challenge / CAPTCHA Check
                    is_captcha, c_type, _ = await self.captcha_handler.detect_captcha(self.browser_agent)
                    if is_captcha:
                        logger.info("Active %s detected before submission. Attempting auto-clear...", c_type)
                        auto_ok = await self.captcha_handler.attempt_auto_click(self.browser_agent)
                        if not auto_ok:
                            logger.info("CAPTCHA unsolved by auto-click. Triggering cooperative HITL pause...")
                            self.intervention_manager.trigger_intervention(
                                self.state_machine,
                                reason=InterventionReason.CAPTCHA_CHALLENGE,
                                message=f"Verification challenge ({c_type or 'CAPTCHA'}) detected. Please check 'I am human' or solve the puzzle in Chrome.",
                                details={"captcha_type": c_type},
                            )
                            # Cooperative background polling loop while waiting for human resolution
                            poll_task = asyncio.create_task(self.captcha_handler.poll_until_solved(self.browser_agent, timeout_seconds=60))
                            try:
                                wait_res_task = asyncio.create_task(self.intervention_manager.wait_for_resolution())
                                done, pending = await asyncio.wait([poll_task, wait_res_task], return_when=asyncio.FIRST_COMPLETED)
                                for p in pending:
                                    p.cancel()
                                if poll_task in done:
                                    try:
                                        if poll_task.result():
                                            self.intervention_manager.resolve_resume({"action": "CAPTCHA_RESOLVED"})
                                    except Exception as p_err:
                                        logger.warning("Error checking pre-submission CAPTCHA poll result: %s", p_err)
                            except Exception as ex:
                                logger.warning("Error during pre-submission CAPTCHA wait: %s", ex)

                    # 2. Pre-Submission Consent Sweep & Field Reconciliation
                    try:
                        await self.form_filler.ensure_mandatory_consent_accepted(self.browser_agent)
                    except Exception as e:
                        logger.warning("Error during pre-submission consent sweep: %s", e)

                    # Re-reconcile all fields (text, textarea, email, tel, select, radio_group) to prevent late ATS resume parser overwrites
                    try:
                        reconciled_cnt = await self.form_filler.reconcile_fields(self.browser_agent, mapping_result.mappings)
                        if reconciled_cnt > 0:
                            logger.info("Pre-submission reconciliation verified/restored %d fields.", reconciled_cnt)
                    except Exception as e:
                        logger.warning("Error during pre-submission reconciliation: %s", e)

                    # 3. HTML5 Constraint Validation Check & Rescue before click
                    js_fix_invalids = """(() => {
                        const invalids = Array.from(document.querySelectorAll('input:invalid, select:invalid, textarea:invalid'));
                        let fixed = 0;
                        for (const inv of invalids) {
                            if (inv.type === 'checkbox') {
                                const proto = window.HTMLInputElement.prototype;
                                const setter = Object.getOwnPropertyDescriptor(proto, 'checked')?.set;
                                if (setter) setter.call(inv, true); else inv.checked = true;
                                inv.dispatchEvent(new Event('input', { bubbles: true }));
                                inv.dispatchEvent(new Event('change', { bubbles: true }));
                                const lbl = inv.id ? document.querySelector('label[for="' + CSS.escape(inv.id) + '"]') : inv.closest('label');
                                if (lbl && !inv.checked) try { lbl.click(); } catch(e) {}
                                fixed++;
                            }
                        }
                        return fixed;
                    })()"""
                    try:
                        res_fix = self.browser_agent.evaluate(js_fix_invalids)
                        fixed_cnt = await res_fix if asyncio.iscoroutine(res_fix) else res_fix
                        if fixed_cnt and fixed_cnt > 0:
                            logger.info("Pre-submit validation rescue auto-resolved %s invalid fields.", fixed_cnt)
                    except Exception:
                        pass

                    # 4. Smooth scroll to submit button & anti-bot humanic dwell pause
                    submit_sel = analysis.submit_buttons[0].get("selector", "button[type='submit']") if analysis.submit_buttons else "button[type='submit']"
                    try:
                        scroll_r = self.browser_agent.evaluate(f"""(() => {{
                            const btn = document.querySelector({json.dumps(submit_sel)});
                            if (btn) btn.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }})()""")
                        if asyncio.iscoroutine(scroll_r):
                            await scroll_r
                    except Exception:
                        pass
                    # Ensure any in-flight direct file uploads have finalized before submission
                    js_wait_uploads = """(() => {
                        const progress = document.querySelector('.file-field__progress:not([style*="width: 100%"]), [role="progressbar"], .upload-progress, .uploading, .spinner');
                        return progress && window.getComputedStyle(progress).display !== 'none';
                    })()"""
                    for _ in range(20):
                        try:
                            chk_up = self.browser_agent.evaluate(js_wait_uploads)
                            in_flight = await chk_up if asyncio.iscoroutine(chk_up) else chk_up
                            if not in_flight:
                                break
                            await asyncio.sleep(0.5)
                        except Exception:
                            break

                    await asyncio.sleep(random.uniform(1.2, 2.0))
                    # BUG-10: Dismiss any delayed popup overlays before clicking submit
                    try:
                        await PopupManager.scan_and_dismiss_popups(self.browser_agent)
                    except Exception:
                        pass
                    await self.browser_agent.click(submit_sel)
                    await asyncio.sleep(1.5)

                    # Post-click submission check: Did browser HTML5 validation stop the submit?
                    js_recheck_blocked = """(() => {
                        const invalids = Array.from(document.querySelectorAll('input:invalid, select:invalid, textarea:invalid'));
                        if (invalids.length > 0) {
                            for (const inv of invalids) {
                                if (inv.type === 'checkbox') {
                                    const proto = window.HTMLInputElement.prototype;
                                    const setter = Object.getOwnPropertyDescriptor(proto, 'checked')?.set;
                                    if (setter) setter.call(inv, true); else inv.checked = true;
                                    inv.dispatchEvent(new Event('input', { bubbles: true }));
                                    inv.dispatchEvent(new Event('change', { bubbles: true }));
                                    const lbl = inv.id ? document.querySelector('label[for="' + CSS.escape(inv.id) + '"]') : inv.closest('label');
                                    if (lbl && !inv.checked) try { lbl.click(); } catch(e) {}
                                }
                            }
                            return invalids.length;
                        }
                        return 0;
                    })()"""
                    try:
                        res_chk = self.browser_agent.evaluate(js_recheck_blocked)
                        blocked_cnt = await res_chk if asyncio.iscoroutine(res_chk) else res_chk
                        if blocked_cnt and blocked_cnt > 0:
                            logger.warning("Form submission was blocked by %d HTML5 invalid inputs. Rescued and re-submitting...", blocked_cnt)
                            await asyncio.sleep(0.5)
                            await self.browser_agent.click(submit_sel)
                            await asyncio.sleep(2.0)
                    except Exception:
                        pass

                    # 5. Scanning post-submission page for confirmation signals
                    self.state_machine.transition_to(
                        AgentExecutionState.VERIFYING_SUBMISSION,
                        message="Scanning post-submission page for confirmation signals.",
                    )
                    verification = await self.result_verifier.verify_submission(self.browser_agent)

                    # GAP-03: Retry with backoff if status is UNKNOWN (delayed redirect/rendering)
                    # Real portals use AJAX, SPAs, Webflow, Wix — confirmation may take 2-6 seconds
                    if verification.status == "UNKNOWN":
                        for backoff_sec in [1.5, 3.0, 5.0]:
                            logger.info("Verification status UNKNOWN, retrying after %.1fs backoff...", backoff_sec)
                            await asyncio.sleep(backoff_sec)
                            retry_verification = await self.result_verifier.verify_submission(self.browser_agent)
                            if retry_verification.status != "UNKNOWN":
                                verification = retry_verification
                                break

                    # GAP-03b: Webflow / Wix / custom CMS success state detection
                    # These platforms replace the form with a success div after AJAX submit
                    if verification.status == "UNKNOWN":
                        try:
                            cms_success_js = """(() => {
                                // Webflow: .w-form-done becomes visible after submit
                                const wfDone = document.querySelector('.w-form-done');
                                if (wfDone) {
                                    const s = window.getComputedStyle(wfDone);
                                    if (s.display !== 'none' && s.visibility !== 'hidden') {
                                        return { found: true, text: (wfDone.innerText || '').trim().slice(0, 200), source: 'webflow' };
                                    }
                                }
                                // Wix: .formSubmitted, .thankYouMessage
                                const wixDone = document.querySelector('.formSubmitted, .thankYouMessage, [data-hook="thank-you-message"]');
                                if (wixDone) {
                                    const s = window.getComputedStyle(wixDone);
                                    if (s.display !== 'none') {
                                        return { found: true, text: (wixDone.innerText || '').trim().slice(0, 200), source: 'wix' };
                                    }
                                }
                                // Generic: form hidden + success sibling visible
                                const forms = document.querySelectorAll('form');
                                for (const f of forms) {
                                    const fStyle = window.getComputedStyle(f);
                                    if (fStyle.display === 'none' || fStyle.visibility === 'hidden') {
                                        const sibling = f.nextElementSibling;
                                        if (sibling && window.getComputedStyle(sibling).display !== 'none') {
                                            const txt = (sibling.innerText || '').trim();
                                            if (txt.length > 5 && /thank|success|received|submitted|sent/i.test(txt)) {
                                                return { found: true, text: txt.slice(0, 200), source: 'form-sibling' };
                                            }
                                        }
                                    }
                                }
                                return { found: false };
                            })()"""
                            cms_res = self.browser_agent.evaluate(cms_success_js)
                            cms_data = await cms_res if asyncio.iscoroutine(cms_res) else cms_res
                            if cms_data and isinstance(cms_data, dict) and cms_data.get("found"):
                                logger.info("CMS success state detected via %s: %s", cms_data.get("source"), cms_data.get("text", "")[:80])
                                from app.services.automation.universal_agent.result_verifier import VerificationResult
                                verification = VerificationResult(
                                    status="SUCCESS",
                                    is_success=True,
                                    confirmation_text=cms_data.get("text", "Form submitted successfully."),
                                    matched_signals=[f"cms_{cms_data.get('source', 'unknown')}_success_state"],
                                )
                        except Exception as cms_err:
                            logger.debug("CMS success state check error: %s", cms_err)

                    # 6. Post-Submission OTP / Identity Verification Handling
                    if verification.status == "OTP_REQUIRED":
                        logger.info("One-time verification code (OTP) required post-submit. Triggering HITL resolution...")
                        self.intervention_manager.trigger_intervention(
                            self.state_machine,
                            reason=InterventionReason.TWO_FACTOR_AUTH,
                            message="One-time verification code (OTP) required: A verification code was sent to your email. Please type the code into the browser and click 'I've Solved It / Continue'.",
                            details={"url": current_url, "type": "OTP_VERIFICATION"},
                        )
                        res = await self.intervention_manager.wait_for_resolution()
                        if res.resolution_action != "RESUME":
                            return self._build_result(current_url, job_title, company)

                        await self._handle_otp_resolution(res)

                        # Return to step loop to continue application form
                        continue

                    # 6b. Post-Submission Validation Error Handling
                    if verification.status == "VALIDATION_ERROR":
                        logger.warning("Post-submission validation error: %s", verification.error_messages)
                        self.intervention_manager.trigger_intervention(
                            self.state_machine,
                            reason=InterventionReason.POST_SUBMIT_VALIDATION_ERROR,
                            message=f"Post-submission validation error: {'; '.join(verification.error_messages)}. Please resolve in browser.",
                            details={"error_messages": verification.error_messages},
                        )
                        res = await self.intervention_manager.wait_for_resolution()
                        if res.resolution_action != "RESUME":
                            return self._build_result(current_url, job_title, company, fill_result=latest_fill_result)
                        continue

                    # 6c. Post-Submission CAPTCHA Handling (e.g. CatsOne "Verification is required before submitting")
                    if verification.status == "CHALLENGE_DETECTED":
                        logger.warning("Submission blocked by security verification challenge post-submit. Triggering HITL resolution...")
                        auto_ok = await self.captcha_handler.attempt_auto_click(self.browser_agent)
                        if not auto_ok:
                            self.intervention_manager.trigger_intervention(
                                self.state_machine,
                                reason=InterventionReason.CAPTCHA_CHALLENGE,
                                message="Verification is required before submitting. Please check 'I am human' or solve the puzzle in Chrome.",
                            )
                            poll_task = asyncio.create_task(self.captcha_handler.poll_until_solved(self.browser_agent, timeout_seconds=60))
                            try:
                                wait_res_task = asyncio.create_task(self.intervention_manager.wait_for_resolution())
                                done, pending = await asyncio.wait([poll_task, wait_res_task], return_when=asyncio.FIRST_COMPLETED)
                                for p in pending:
                                    p.cancel()
                                if poll_task in done:
                                    try:
                                        if poll_task.result():
                                            self.intervention_manager.resolve_resume({"action": "CAPTCHA_RESOLVED"})
                                    except Exception as p_err:
                                        logger.warning("Error checking post-submit CAPTCHA poll result: %s", p_err)
                            except Exception as ex:
                                logger.warning("Error during post-submit CAPTCHA wait: %s", ex)

                        # Once resolved, re-click submit
                        logger.info("Resuming submission after CAPTCHA resolution...")
                        await asyncio.sleep(1.0)
                        await self.browser_agent.click(submit_sel)
                        await asyncio.sleep(2.5)
                        verification = await self.result_verifier.verify_submission(self.browser_agent)

                    latest_verification = verification
                    self.result_verifier.verify_and_update_state(self.state_machine, verification)

                    # Clear execution checkpoint on completion (Section 24)
                    if job_id and self.state_machine.terminal_result in (TerminalResult.SUCCESS_SUBMITTED, TerminalResult.SUBMISSION_STATUS_UNKNOWN):
                        self.checkpoint_manager.clear_checkpoint(str(job_id))

                    # 6. Capture Cryptographic Audit Snapshot
                    snapshot = await self.snapshot_recorder.capture_snapshot(
                        agent=self.browser_agent,
                        verification=verification,
                        terminal_result=self.state_machine.terminal_result,
                        filled_fields={k: v.get("value") for k, v in fill_res.field_details.items()},
                        job_title=job_title,
                        company=company,
                    )
                    latest_snapshot = snapshot

                    return self._build_result(
                        current_url=await self.browser_agent.get_url(),
                        job_title=job_title,
                        company=company,
                        verification=latest_verification,
                        snapshot=latest_snapshot,
                        fill_result=latest_fill_result,
                    )

            # If loop exceeded max_wizard_steps
            self.state_machine.complete(
                terminal_result=TerminalResult.FAILED_UNRECOVERABLE,
                message=f"Wizard exceeded maximum limit of {max_wizard_steps} steps.",
            )
            return self._build_result(current_url, job_title, company, error="Exceeded max wizard steps.")

        except Exception as e:
            logger.error("Unexpected error in UniversalApplicationOrchestrator: %s", e, exc_info=True)
            # BUG-03: Classify exception and record diagnostic attempt via RecoveryManager
            try:
                cat = self.recovery_manager.classify_exception(e, context_hint=f"url={current_url} step={step_idx}")
                self.recovery_manager.record_attempt(
                    operation_key=f"orchestrator_step_{step_idx}",
                    category=cat,
                    url=current_url,
                    title=f"{job_title or ''} at {company or ''}",
                    state=self.state_machine.state.value if hasattr(self.state_machine.state, "value") else str(self.state_machine.state),
                    exc=e,
                    recovery_action="terminal_failure_record",
                    job_id=str(job_id) if job_id else None,
                )
            except Exception as rm_err:
                logger.warning("Error recording failure in RecoveryManager: %s", rm_err)

            if self.state_machine.state != AgentExecutionState.COMPLETED:
                self.state_machine.complete(
                    terminal_result=TerminalResult.FAILED_UNRECOVERABLE,
                    message=f"Fatal exception: {e}",
                )
            return self._build_result(current_url, job_title, company, error=str(e))

    def _build_result(
        self,
        current_url: str,
        job_title: Optional[str] = None,
        company: Optional[str] = None,
        verification: Optional[VerificationResult] = None,
        snapshot: Optional[ApplicationSubmissionSnapshot] = None,
        fill_result: Optional[FormFillResult] = None,
        error: Optional[str] = None,
    ) -> OrchestrationResult:
        # LOW-05: Ensure terminal_result is not left at NONE if an error occurred or verification completed
        term_res = self.state_machine.terminal_result
        if term_res == TerminalResult.NONE:
            if error:
                term_res = TerminalResult.FAILED_UNRECOVERABLE
            elif verification:
                if verification.is_success:
                    term_res = TerminalResult.SUCCESS_SUBMITTED
                elif verification.status == "UNKNOWN":
                    term_res = TerminalResult.SUBMISSION_STATUS_UNKNOWN

        is_success = (term_res == TerminalResult.SUCCESS_SUBMITTED)
        ref_num = verification.reference_number if verification else (snapshot.reference_number if snapshot else None)

        return OrchestrationResult(
            terminal_result=term_res,
            is_success=is_success,
            state=self.state_machine.state,
            current_url=current_url,
            job_title=job_title,
            company=company,
            reference_number=ref_num,
            snapshot=snapshot,
            verification=verification,
            fill_result=fill_result,
            timeline=self.timeline,
            error_message=error,
        )
