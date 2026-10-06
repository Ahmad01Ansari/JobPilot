'''
Unified Application Tracker & Deduplication Engine
Tracks lifecycle states of job applications across platforms.
Ensures idempotency and enforces the critical rule: UNKNOWN states are never automatically retried.
'''

import os
import csv
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, Tuple, Set, List, Literal, Union

from modules.models import Job
from modules.helpers import make_directories, print_lg

# Permitted Application Lifecycle States
ApplicationState = Literal[
    "DISCOVERED",
    "QUALIFIED",
    "SKIPPED",
    "APPLYING",
    "SUBMITTED",
    "FAILED",
    "MANUAL_REQUIRED",
    "EXTERNAL",
    "UNKNOWN",
    "JUNK",
]

VALID_STATES: Set[str] = {
    "DISCOVERED",
    "QUALIFIED",
    "SKIPPED",
    "APPLYING",
    "SUBMITTED",
    "FAILED",
    "MANUAL_REQUIRED",
    "EXTERNAL",
    "UNKNOWN",
    "JUNK",
}

# States that strictly block automatic retry to prevent duplicate applications or spam
BLOCKING_STATES: Set[str] = {
    "SUBMITTED",
    "APPLYING",
    "UNKNOWN",          # Critical safety: UNKNOWN must never be automatically retried
    "MANUAL_REQUIRED",  # Requires human intervention
    "JUNK",             # Marked as irrelevant / junk by user
}

DEFAULT_TRACKER_PATH = "all excels/applications.csv"
LEGACY_TRACKER_PATH = "all excels/application_tracking.csv"

# Canonical 12-column unified schema per Phase 15 specification
CSV_FIELDNAMES = [
    "platform",
    "job_id",
    "title",
    "company",
    "location",
    "source_url",
    "status",
    "application_type",
    "discovered_at",
    "applied_at",
    "failure_reason",
    "skip_reason",
]


@dataclass
class ApplicationRecord:
    platform: str
    job_id: str
    title: str
    company: str
    location: str
    source_url: str
    status: ApplicationState
    application_type: str = "DIRECT"
    discovered_at: str = ""
    applied_at: Optional[str] = None
    failure_reason: Optional[str] = None
    skip_reason: Optional[str] = None
    application_url: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def state(self) -> ApplicationState:
        """Alias for status for full backwards compatibility."""
        return self.status

    @property
    def reason(self) -> Optional[str]:
        """Alias returning failure_reason or skip_reason for backwards compatibility."""
        return self.failure_reason or self.skip_reason

    @property
    def updated_at(self) -> str:
        """Alias returning applied_at or discovered_at for backwards compatibility."""
        return self.applied_at or self.discovered_at

    @property
    def applied_date(self) -> Optional[str]:
        """Alias returning applied_at for backwards compatibility."""
        return self.applied_at

    @property
    def created_date(self) -> Optional[str]:
        """Alias returning discovered_at for backwards compatibility."""
        return self.discovered_at

    def to_job_dict(self) -> Dict[str, Any]:
        """Converts ApplicationRecord to structured dictionary for UI/event processing."""
        return {
            "platform": self.platform,
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "source_url": self.source_url,
            "status": self.status,
            "skip_reason": self.skip_reason,
            "failure_reason": self.failure_reason,
        }


class ApplicationTracker:
    """Manages unified application history across LinkedIn, Naukri, and future platforms.
    Enforces deduplication, prevents retrying UNKNOWN states, and maintains applications.csv.
    """

    _listeners: List[Any] = []

    @classmethod
    def add_listener(cls, callback) -> None:
        """Registers a callback to receive ApplicationRecord events on every state transition."""
        if callback not in cls._listeners:
            cls._listeners.append(callback)

    @classmethod
    def remove_listener(cls, callback) -> None:
        """Unregisters a previously added ApplicationTracker listener."""
        if callback in cls._listeners:
            cls._listeners.remove(callback)

    def __init__(
        self,
        file_path: Optional[str] = None,
        user_id: Optional[int] = None,
        enable_db: Optional[bool] = None,
    ):
        self.file_path = file_path or DEFAULT_TRACKER_PATH
        self.user_id = user_id or 1
        self._records: Dict[Tuple[str, str], ApplicationRecord] = {}
        self._db_available: bool = False

        if enable_db is not None:
            self.enable_db = enable_db
        else:
            self.enable_db = (file_path is None or file_path == DEFAULT_TRACKER_PATH)

        make_directories([self.file_path])
        if self.enable_db:
            self._load_from_db()
        self._load_from_csv()

    def _load_from_db(self) -> None:
        """Loads existing application history directly from SQLite database into cache (SSOT)."""
        try:
            from app.db.session import get_db_session
            from app.db.models import Job, Application
            from sqlalchemy import select

            with get_db_session() as session:
                stmt = select(Job, Application).outerjoin(
                    Application, Job.id == Application.job_id
                )
                results = session.execute(stmt).all()
                for job, app in results:
                    plat = (job.platform or "").strip().lower()
                    jid = str(job.external_job_id or job.id).strip()
                    if not plat or not jid:
                        continue

                    st = "DISCOVERED"
                    applied_time = None
                    fail_reason = None
                    skip_rsn = None
                    app_type = "DIRECT"

                    if app:
                        st = app.status
                        applied_time = app.applied_at.strftime("%Y-%m-%d %H:%M:%S") if app.applied_at else None
                        fail_reason = app.failure_reason
                        skip_rsn = app.skip_reason
                        app_type = app.application_type or "DIRECT"
                    elif job.application_method == "COMPANY_PORTAL":
                        st = "EXTERNAL"

                    rec = ApplicationRecord(
                        platform=plat,
                        job_id=jid,
                        title=job.title or "",
                        company=job.company_raw or "",
                        location=job.location or "",
                        source_url=job.source_url or "",
                        status=st,
                        discovered_at=job.first_seen_at.strftime("%Y-%m-%d %H:%M:%S") if job.first_seen_at else "",
                        applied_at=applied_time,
                        failure_reason=fail_reason,
                        skip_reason=skip_rsn,
                        application_type=app_type,
                    )
                    rec.details = {
                        "description": job.description,
                        "salary_text": job.salary_text,
                        "salary_min": job.salary_min,
                        "salary_max": job.salary_max,
                        "required_experience_min": job.required_experience_min,
                        "required_experience_max": job.required_experience_max,
                        "experience_text": job.experience_text,
                        "work_style": job.work_style,
                    }
                    self._records[(plat, jid)] = rec
                self._db_available = True
        except Exception as e:
            self._db_available = False

    def _sync_to_db(self, record: ApplicationRecord, user_id: Optional[int] = None) -> None:
        """Persists application record state directly to SQLite database."""
        if not self.enable_db:
            return
        try:
            from app.db.session import get_db_session
            from app.repositories.job_repository import JobRepository
            from app.repositories.application_repository import ApplicationRepository
            from app.repositories.dto import JobCreateDTO, ApplicationCreateDTO

            uid = user_id or self.user_id or 1
            with get_db_session() as session:
                job_repo = JobRepository(session)
                app_repo = ApplicationRepository(session)

                app_method = "COMPANY_PORTAL" if record.status == "EXTERNAL" else (
                    "EASY_APPLY" if record.platform in ("linkedin", "indeed") else "DIRECT"
                )
                app_url = record.application_url or (record.details.get("application_url") if record.details else None)
                det = record.details or {}
                dto = JobCreateDTO(
                    platform=record.platform,
                    company_raw=record.company,
                    title=record.title,
                    location=record.location,
                    source_url=record.source_url,
                    external_job_id=record.job_id,
                    application_method=app_method,
                    application_url=app_url,
                    apply_type="EXTERNAL" if app_method == "COMPANY_PORTAL" else "DIRECT",
                    description=det.get("description"),
                    salary_text=det.get("salary_text"),
                    salary_min=det.get("salary_min"),
                    salary_max=det.get("salary_max"),
                    required_experience_min=det.get("required_experience_min"),
                    required_experience_max=det.get("required_experience_max"),
                    experience_text=det.get("experience_text"),
                    work_style=det.get("work_style"),
                )
                job, _ = job_repo.upsert_job(dto)

                app = app_repo.get_by_job_id(job.id)
                if not app:
                    app_dto = ApplicationCreateDTO(
                        job_id=job.id,
                        user_id=uid,
                        status=record.status,
                        application_type=record.application_type or app_method,
                        notes=record.skip_reason or record.failure_reason,
                        external_job_link=app_url or record.source_url,
                    )
                    app = app_repo.create_application(app_dto)
                else:
                    if record.status != app.status:
                        try:
                            app_repo.transition_status(
                                application_id=app.id,
                                new_status=record.status,
                                source="automation",
                                notes=record.skip_reason or record.failure_reason,
                                failure_reason=record.failure_reason,
                                allow_override=True,
                            )
                        except Exception:
                            app.status = record.status
                session.commit()
                self._db_available = True
        except Exception:
            pass

    def _load_from_csv(self) -> None:
        """Loads existing application history into cache."""
        # Fallback migration check: if applications.csv does not exist, check legacy tracker path
        target_path = self.file_path
        if not os.path.exists(target_path) and target_path == DEFAULT_TRACKER_PATH and os.path.exists(LEGACY_TRACKER_PATH):
            target_path = LEGACY_TRACKER_PATH

        if not os.path.exists(target_path):
            return

        try:
            with open(target_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    plat = row.get("platform", "").strip().lower()
                    jid = row.get("job_id", "").strip()
                    st = (row.get("status") or row.get("state") or "DISCOVERED").strip()
                    if plat and jid and st in VALID_STATES:
                        applied_time = row.get("applied_at") or (row.get("updated_at") if st == "SUBMITTED" else None)
                        fail_reason = row.get("failure_reason")
                        skip_rsn = row.get("skip_reason")
                        legacy_reason = row.get("reason")
                        if legacy_reason and not (fail_reason or skip_rsn):
                            if st == "SKIPPED":
                                skip_rsn = legacy_reason
                            else:
                                fail_reason = legacy_reason

                        rec = ApplicationRecord(
                            platform=plat,
                            job_id=jid,
                            title=row.get("title", ""),
                            company=row.get("company", ""),
                            location=row.get("location", ""),
                            source_url=row.get("source_url", ""),
                            status=st,  # type: ignore
                            discovered_at=row.get("discovered_at", ""),
                            applied_at=applied_time,
                            failure_reason=fail_reason,
                            skip_reason=skip_rsn,
                            application_type=row.get("application_type", "DIRECT"),
                        )
                        # Only set if not already loaded from DB
                        if (plat, jid) not in self._records:
                            self._records[(plat, jid)] = rec
        except Exception as e:
            print_lg(f"[ApplicationTracker] Notice while loading {target_path}: {e}")

    def is_already_handled(
        self,
        job_id: str,
        platform: str = "naukri",
        skip_if_previously_skipped: bool = True,
        user_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Determines if a job should be skipped because it was already applied, in-progress, or UNKNOWN.
        Returns (should_skip: bool, reason: Optional[str]).
        """
        plat = platform.lower()
        jid = str(job_id).strip()
        key = (plat, jid)
        record = self._records.get(key)

        # Dynamic SQLite lookup if not present in in-memory cache
        if not record and self.enable_db:
            try:
                from app.db.session import get_db_session
                from app.repositories.job_repository import JobRepository
                from app.repositories.application_repository import ApplicationRepository

                with get_db_session() as session:
                    j_repo = JobRepository(session)
                    job = j_repo.get_by_external_id(plat, jid)
                    if job:
                        a_repo = ApplicationRepository(session)
                        app = a_repo.get_by_job_id(job.id)
                        st = app.status if app else ("EXTERNAL" if job.application_method == "COMPANY_PORTAL" else "DISCOVERED")
                        record = ApplicationRecord(
                            platform=plat,
                            job_id=jid,
                            title=job.title or "",
                            company=job.company_raw or "",
                            location=job.location or "",
                            source_url=job.source_url or "",
                            status=st,
                            discovered_at=job.first_seen_at.strftime("%Y-%m-%d %H:%M:%S") if job.first_seen_at else "",
                            applied_at=app.applied_at.strftime("%Y-%m-%d %H:%M:%S") if (app and app.applied_at) else None,
                            failure_reason=app.failure_reason if app else None,
                            skip_reason=app.skip_reason if app else None,
                            application_type=app.application_type if app else "DIRECT",
                        )
                        self._records[key] = record
            except Exception:
                pass

        if not record:
            return (False, None)

        if record.status == "SUBMITTED":
            return (True, f"Already successfully submitted on {record.applied_at or record.discovered_at}")

        if record.status == "UNKNOWN":
            # Hard safety rule: Never blindly retry an UNKNOWN application
            return (True, "Previous attempt resulted in UNKNOWN state — cannot automatically retry without manual confirmation")

        if record.status == "APPLYING":
            return (True, "Application is currently marked as APPLYING in another session")

        if record.status == "MANUAL_REQUIRED":
            return (True, f"Marked as MANUAL_REQUIRED ({record.failure_reason or 'User action required'})")

        if skip_if_previously_skipped and record.status == "SKIPPED":
            return (True, f"Previously skipped: {record.skip_reason or 'Unspecified reason'}")

        if record.status == "JUNK":
            return (True, f"Marked as JUNK: {record.skip_reason or 'Irrelevant job marked by user'}")

        if record.status == "EXTERNAL":
            return (True, "Previously classified as EXTERNAL (skipped per configuration)")

        return (False, None)

    def is_retryable(self, job_id: str, platform: str = "naukri") -> bool:
        """Explicit safety check: confirms if a job can be safely attempted.
        Returns False for SUBMITTED, UNKNOWN, APPLYING, or MANUAL_REQUIRED.
        """
        should_skip, _ = self.is_already_handled(job_id, platform=platform, skip_if_previously_skipped=False)
        return not should_skip

    def get_state(self, job_id: str, platform: str = "naukri") -> Optional[ApplicationState]:
        """Returns the current state/status of a job or None if undiscovered."""
        return self.get_status(job_id, platform=platform)

    def get_status(self, job_id: str, platform: str = "naukri") -> Optional[ApplicationState]:
        """Returns the current status of a job or None if undiscovered."""
        key = (platform.lower(), str(job_id).strip())
        record = self._records.get(key)
        return record.status if record else None

    def get_record(self, job_id: str, platform: str = "naukri") -> Optional[ApplicationRecord]:
        """Returns the complete ApplicationRecord for a given job and platform."""
        key = (platform.lower(), str(job_id).strip())
        return self._records.get(key)

    def is_applied(self, job_id: str, platform: str = "naukri") -> bool:
        """Returns True if the job is in SUBMITTED state."""
        return self.get_status(job_id, platform=platform) == "SUBMITTED"

    def is_already_applied(self, job_id: str, platform: str = "naukri") -> bool:
        """Alias for is_applied to ensure compatibility across all platform drivers."""
        return self.is_applied(job_id, platform=platform)

    def check_cross_platform_opportunity(
        self,
        title: str,
        company: str,
        application_url: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Tuple[bool, Optional[ApplicationRecord], str, str]:
        """Checks if this job opportunity has already been submitted on ANY platform.

        Evaluates safe URL normalization, ATS requisition IDs, and multi-signal heuristics.

        Returns:
            Tuple of (is_already_applied: bool, matched_record: Optional[ApplicationRecord], code: str, reason: str)
        """
        from app.services.dedup.url_normalizer import URLNormalizer
        from app.services.dedup.entity_normalizer import EntityNormalizer

        norm_app_url = URLNormalizer.normalize_application_url(application_url)
        in_ats_provider, in_ats_id = URLNormalizer.extract_ats_metadata(norm_app_url)
        in_company_norm = EntityNormalizer.normalize_company(company)

        for (plat, jid), rec in self._records.items():
            if rec.status != "SUBMITTED":
                continue

            # Signal 1: External application URL match
            rec_app_url = URLNormalizer.normalize_application_url(
                rec.application_url or (rec.details.get("application_url") if rec.details else None)
            )
            if norm_app_url and rec_app_url:
                if norm_app_url == rec_app_url:
                    reason = f"Already applied on {rec.platform.capitalize()} (Matched external application URL)"
                    return True, rec, "EXACT_URL_MATCH", reason

            # Signal 2: ATS Requisition ID match
            if in_ats_provider and in_ats_id and rec_app_url:
                rec_ats_prov, rec_ats_id = URLNormalizer.extract_ats_metadata(rec_app_url)
                if in_ats_provider == rec_ats_prov and in_ats_id == rec_ats_id:
                    reason = f"Already applied on {rec.platform.capitalize()} (Matched {in_ats_provider} requisition #{in_ats_id})"
                    return True, rec, "EXACT_ATS_MATCH", reason

            # Signal 3: Normalized Company + High Title Similarity
            rec_comp_norm = EntityNormalizer.normalize_company(rec.company)
            if in_company_norm and rec_comp_norm and in_company_norm == rec_comp_norm:
                sim = EntityNormalizer.compute_title_similarity(title, rec.title)
                loc_compat = EntityNormalizer.are_locations_compatible(location, rec.location)
                if sim >= 0.85 and loc_compat:
                    reason = f"Already applied on {rec.platform.capitalize()} (Same role '{rec.title}', title similarity {sim:.2f})"
                    return True, rec, "HIGH_CONFIDENCE_MATCH", reason

        return False, None, "UNIQUE", "Opportunity is unapplied."

    def reset_stale_in_flight(self, platform: Optional[str] = None) -> int:
        """Resets any jobs stuck in APPLYING state from crashed or terminated sessions back to DISCOVERED."""
        count = 0
        plat_lower = platform.lower() if platform else None
        for (plat, jid), rec in list(self._records.items()):
            if plat_lower and plat != plat_lower:
                continue
            if rec.status == "APPLYING":
                rec.status = "DISCOVERED"
                count += 1
        if self.enable_db:
            try:
                from app.db.session import get_db_session
                from app.repositories.application_repository import ApplicationRepository
                with get_db_session() as session:
                    a_repo = ApplicationRepository(session)
                    apps = a_repo.list_by_status("APPLYING", limit=500)
                    for app in apps:
                        if not plat_lower or (app.job and app.job.platform == plat_lower):
                            app.status = "DISCOVERED"
                            count += 1
                    session.commit()
            except Exception:
                pass
        return count

    def get_all_records(
        self,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        include_junk: bool = False,
    ) -> List[ApplicationRecord]:
        """Returns all cached application records, optionally filtered by platform and/or status."""
        results = []
        for (plat, _), rec in self._records.items():
            if platform is not None and plat != platform.lower():
                continue
            if status is not None:
                if rec.status != status:
                    continue
            elif not include_junk and rec.status == "JUNK":
                # Hide junk jobs from default listing
                continue
            results.append(rec)
        return results

    def mark_as_junk(
        self,
        job_id: str,
        platform: str = "naukri",
        reason: str = "Marked as junk by user",
    ) -> bool:
        """Marks an existing tracked job or record as JUNK."""
        key = (platform.lower(), str(job_id).strip())
        rec = self._records.get(key)
        job_payload = {
            "platform": platform,
            "job_id": str(job_id).strip(),
            "title": rec.title if rec else "",
            "company": rec.company if rec else "",
            "location": rec.location if rec else "",
            "source_url": rec.source_url if rec else "",
        }
        self.record_state(job_payload, state="JUNK", reason=reason, skip_reason=reason)
        return True

    def restore_from_junk(
        self,
        job_id: str,
        platform: str = "naukri",
        new_status: ApplicationState = "DISCOVERED",
    ) -> bool:
        """Restores a job from JUNK status back to an active state (default: DISCOVERED)."""
        key = (platform.lower(), str(job_id).strip())
        rec = self._records.get(key)
        if not rec:
            return False
        job_payload = {
            "platform": platform,
            "job_id": str(job_id).strip(),
            "title": rec.title,
            "company": rec.company,
            "location": rec.location,
            "source_url": rec.source_url,
        }
        self.record_state(job_payload, state=new_status, reason="Restored from junk")
        return True

    def record_state(
        self,
        job: Union[Job, Dict[str, Any]],
        state: ApplicationState,
        reason: Optional[str] = None,
        skip_reason: Optional[str] = None,
        failure_reason: Optional[str] = None,
        application_type: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> ApplicationRecord:
        """Records a state transition for a job and persists to unified CSV and SQLite DB."""
        if state not in VALID_STATES:
            raise ValueError(f"Invalid state '{state}'. Must be one of {VALID_STATES}")

        if isinstance(job, Job):
            platform = job.platform.lower()
            job_id = str(job.job_id).strip()
            title = job.title
            company = job.company
            location = job.location
            source_url = job.source_url
            app_type = application_type or job.apply_type
            app_url = getattr(job, "application_url", None)
        else:
            platform = str(job.get("platform", "naukri")).lower()
            job_id = str(job.get("job_id", "")).strip()
            title = str(job.get("title", ""))
            company = str(job.get("company", ""))
            location = str(job.get("location", ""))
            source_url = str(job.get("source_url", ""))
            app_type = application_type or str(job.get("apply_type", "DIRECT"))
            app_url = job.get("application_url")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        key = (platform, job_id)

        existing = self._records.get(key)
        discovered_at = existing.discovered_at if existing and existing.discovered_at else now_str

        # Resolve applied_at timestamp
        applied_at = now_str if state == "SUBMITTED" else (existing.applied_at if existing else None)

        # Resolve application_url
        eff_app_url = app_url or (existing.application_url if existing else None)
        if eff_app_url:
            u_str = str(eff_app_url).lower()
            if "/applystart" not in u_str and "/rc/clk" not in u_str:
                if any(d in u_str for d in ["naukri.com", "linkedin.com", "foundit.in"]) or ("indeed.com" in u_str and any(p in u_str for p in ["/viewjob", "/jobs?", "/jobs/"])):
                    eff_app_url = None

        # Resolve skip_reason and failure_reason
        eff_skip_reason = None
        eff_failure_reason = None

        if state in ("SKIPPED", "JUNK"):
            eff_skip_reason = skip_reason or reason or (existing.skip_reason if existing else None)
        elif state in ("FAILED", "UNKNOWN", "MANUAL_REQUIRED"):
            eff_failure_reason = failure_reason or reason or (existing.failure_reason if existing else None)
        elif state == "SUBMITTED":
            eff_skip_reason = None
            eff_failure_reason = None
        else:
            # Preserve existing reasons if available
            eff_skip_reason = existing.skip_reason if existing else None
            eff_failure_reason = existing.failure_reason if existing else None

        # Collect rich metadata details
        details = dict(existing.details) if existing and existing.details else {}
        if isinstance(job, Job):
            if job.description:
                details["description"] = job.description
            # Check top-level attributes first, then fall back to raw_metadata
            raw_md = getattr(job, "raw_metadata", None) or {}
            sal_text = getattr(job, "salary", None) or getattr(job, "salary_text", None) or raw_md.get("salary_text")
            if sal_text:
                details["salary_text"] = sal_text
            if job.salary_min:
                details["salary_min"] = job.salary_min
            if job.salary_max:
                details["salary_max"] = job.salary_max
            if job.required_experience_min is not None:
                details["required_experience_min"] = job.required_experience_min
            if job.required_experience_max is not None:
                details["required_experience_max"] = job.required_experience_max
            if job.work_style:
                details["work_style"] = job.work_style
            # Experience text: check top-level, raw_metadata, then computed range string
            exp_text = raw_md.get("experience_text")
            if not exp_text and hasattr(job, "experience_range_str"):
                exp_str = job.experience_range_str()
                if exp_str and exp_str != "Not specified":
                    exp_text = exp_str
            if exp_text:
                details["experience_text"] = exp_text
            if getattr(job, "application_url", None):
                details["application_url"] = getattr(job, "application_url", None)
        elif isinstance(job, dict):
            if job.get("description"):
                details["description"] = job.get("description")
            if job.get("salary") or job.get("salary_text"):
                details["salary_text"] = job.get("salary") or job.get("salary_text")
            if job.get("salary_min"):
                details["salary_min"] = job.get("salary_min")
            if job.get("salary_max"):
                details["salary_max"] = job.get("salary_max")
            if job.get("required_experience_min") is not None:
                details["required_experience_min"] = job.get("required_experience_min")
            if job.get("required_experience_max") is not None:
                details["required_experience_max"] = job.get("required_experience_max")
            if job.get("work_style"):
                details["work_style"] = job.get("work_style")
            if job.get("experience_text"):
                details["experience_text"] = job.get("experience_text")
            if job.get("application_url"):
                details["application_url"] = job.get("application_url")

        record = ApplicationRecord(
            platform=platform,
            job_id=job_id,
            title=title,
            company=company,
            location=location,
            source_url=source_url,
            status=state,
            discovered_at=discovered_at,
            applied_at=applied_at,
            failure_reason=eff_failure_reason,
            skip_reason=eff_skip_reason,
            application_type=app_type,
            application_url=eff_app_url,
            details=details,
        )

        self._records[key] = record
        self._sync_to_db(record, user_id=user_id)
        self._append_to_csv(record)

        log_msg = f"[ApplicationTracker] [{platform.upper()}] Job {job_id} -> {state}"
        if eff_skip_reason:
            log_msg += f" (Skipped: {eff_skip_reason})"
        elif eff_failure_reason:
            log_msg += f" (Reason: {eff_failure_reason})"
        print_lg(log_msg)

        for listener in list(self._listeners):
            try:
                listener(record)
            except Exception:
                pass

        return record

    def record_evaluation(
        self,
        job: Union[Job, Dict[str, Any]],
        state: ApplicationState,
        skip_reason: Optional[str] = None,
        failure_reason: Optional[str] = None,
        application_type: Optional[str] = None,
    ) -> ApplicationRecord:
        """Records an evaluation decision (e.g. SKIPPED or QUALIFIED) for a job."""
        return self.record_state(
            job=job,
            state=state,
            skip_reason=skip_reason,
            failure_reason=failure_reason,
            application_type=application_type,
        )

    def record_job(self, job: Union[Job, Dict[str, Any]]) -> ApplicationRecord:
        """Records initial discovery of a job."""
        return self.record_state(job, state="DISCOVERED")

    def record_discovered(self, job: Union[Job, Dict[str, Any]]) -> ApplicationRecord:
        """Records initial discovery of a job."""
        return self.record_state(job, state="DISCOVERED")

    def record_qualified(self, job: Union[Job, Dict[str, Any]]) -> ApplicationRecord:
        """Records that a job passed qualification criteria."""
        return self.record_state(job, state="QUALIFIED")

    def record_applying(self, job: Union[Job, Dict[str, Any]]) -> ApplicationRecord:
        """Records that an application submission is in progress."""
        return self.record_state(job, state="APPLYING")

    def record_submitted(self, job: Union[Job, Dict[str, Any]]) -> ApplicationRecord:
        """Records a confirmed successful job submission."""
        return self.record_state(job, state="SUBMITTED")

    def record_skipped(self, job: Union[Job, Dict[str, Any]], reason: Optional[str] = None) -> ApplicationRecord:
        """Records that a job was skipped during qualification or pre-filter."""
        return self.record_state(job, state="SKIPPED", skip_reason=reason)

    def record_external(self, job: Union[Job, Dict[str, Any]], external_url: Optional[str] = None) -> ApplicationRecord:
        """Records that a job redirects to an external company/employer portal."""
        if external_url:
            if isinstance(job, Job):
                job.application_url = external_url
                job.application_method = "COMPANY_PORTAL"
                job.apply_type = "EXTERNAL"
            elif isinstance(job, dict):
                job["application_url"] = external_url
                job["application_method"] = "COMPANY_PORTAL"
                job["apply_type"] = "EXTERNAL"
        return self.record_state(job, state="EXTERNAL", application_type="EXTERNAL", failure_reason=external_url)

    def record_manual_required(self, job: Union[Job, Dict[str, Any]], reason: Optional[str] = None) -> ApplicationRecord:
        """Records that manual intervention (CAPTCHA, 2FA, approval) is required."""
        return self.record_state(job, state="MANUAL_REQUIRED", reason=reason)

    def record_unknown(self, job: Union[Job, Dict[str, Any]], failure_reason: Optional[str] = None) -> ApplicationRecord:
        """Records an unconfirmed submission as UNKNOWN to prevent auto-retrying."""
        return self.record_state(job, state="UNKNOWN", failure_reason=failure_reason)

    def record_failed(self, job: Union[Job, Dict[str, Any]], failure_reason: Optional[str] = None) -> ApplicationRecord:
        """Records a failed application attempt."""
        return self.record_state(job, state="FAILED", failure_reason=failure_reason)

    def record_submission(
        self,
        job: Union[Job, Dict[str, Any]],
        status: ApplicationState = "SUBMITTED",
        failure_reason: Optional[str] = None,
        application_type: Optional[str] = None,
    ) -> ApplicationRecord:
        """Records the final submission result (SUBMITTED, UNKNOWN, MANUAL_REQUIRED, FAILED, EXTERNAL)."""
        return self.record_state(
            job=job,
            state=status,
            failure_reason=failure_reason,
            application_type=application_type,
        )

    def record_application(
        self,
        platform: str,
        job_id: str,
        title: str = "",
        company: str = "",
        location: str = "",
        url: str = "",
        status: str = "SUBMITTED",
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        application_type: Optional[str] = None,
    ) -> ApplicationRecord:
        """Compatibility helper method for recording application events with discrete parameters.

        Maps incoming status (e.g. ALREADY_APPLIED -> SKIPPED with reason='Already applied') to VALID_STATES.
        """
        st = (status or "SUBMITTED").upper()
        eff_reason = reason
        if st == "ALREADY_APPLIED":
            st = "SKIPPED"
            eff_reason = eff_reason or "Already applied"

        job_dict = {
            "platform": (platform or "glassdoor").lower(),
            "job_id": str(job_id).strip(),
            "title": title or "",
            "company": company or "",
            "location": location or "",
            "source_url": url or "",
            "application_url": url or "",
            "details": details or {},
        }
        return self.record_state(
            job=job_dict,
            state=st,
            reason=eff_reason,
            skip_reason=eff_reason if st in ("SKIPPED", "JUNK") else None,
            failure_reason=eff_reason if st in ("FAILED", "UNKNOWN", "MANUAL_REQUIRED") else None,
            application_type=application_type or ("EXTERNAL" if st == "EXTERNAL" else "DIRECT"),
        )

    def update_status(
        self,
        job_id: str,
        status: ApplicationState,
        platform: str = "linkedin",
        reason: Optional[str] = None,
        title: Optional[str] = None,
        company: Optional[str] = None,
        location: Optional[str] = None,
        source_url: Optional[str] = None,
        application_type: Optional[str] = None,
    ) -> ApplicationRecord:
        """Updates or registers a job's status and notifies all registered listeners.
        Guarantees that telemetry from external processes or subprocesses is reliably recorded.
        """
        plat = (platform or "linkedin").lower()
        jid = str(job_id).strip()
        key = (plat, jid)
        existing = self._records.get(key)

        job_data: Dict[str, Any] = {
            "platform": plat,
            "job_id": jid,
            "title": title or (existing.title if existing else "Job"),
            "company": company or (existing.company if existing else "Company"),
            "location": location or (existing.location if existing else ""),
            "source_url": source_url or (existing.source_url if existing else f"https://www.{plat}.com/jobs/view/{jid}"),
            "apply_type": application_type or (existing.application_type if existing else ("EASY_APPLY" if plat == "linkedin" else "DIRECT")),
        }

        skip_rsn = reason if status == "SKIPPED" else None
        fail_rsn = reason if status in ("FAILED", "UNKNOWN", "MANUAL_REQUIRED") else None

        return self.record_state(
            job=job_data,
            state=status,
            reason=reason,
            skip_reason=skip_rsn,
            failure_reason=fail_rsn,
            application_type=job_data["apply_type"],
        )

    def _append_to_csv(self, record: ApplicationRecord) -> None:
        """Appends a record to the canonical 12-column applications CSV."""
        file_exists = os.path.exists(self.file_path) and os.path.getsize(self.file_path) > 0

        try:
            with open(self.file_path, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                if not file_exists:
                    writer.writeheader()
                writer.writerow({
                    "platform": record.platform,
                    "job_id": record.job_id,
                    "title": record.title,
                    "company": record.company,
                    "location": record.location,
                    "source_url": record.source_url,
                    "status": record.status,
                    "application_type": record.application_type,
                    "discovered_at": record.discovered_at,
                    "applied_at": record.applied_at or "",
                    "failure_reason": record.failure_reason or "",
                    "skip_reason": record.skip_reason or "",
                })
        except Exception as e:
            print_lg(f"[ApplicationTracker] Error writing to {self.file_path}: {e}")

    def get_stats(self, platform: Optional[str] = None) -> Dict[str, int]:
        """Returns statistics breakdown by status across all records or for a specific platform."""
        stats: Dict[str, int] = {st: 0 for st in VALID_STATES}
        for (plat, _), rec in self._records.items():
            if platform is None or plat == platform.lower():
                stats[rec.status] = stats.get(rec.status, 0) + 1
        return stats

    def get_daily_submitted_count(self, platform: Optional[str] = None) -> int:
        """Returns the count of applications submitted today for a specific platform or all platforms."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        count = 0
        for (plat, _), rec in self._records.items():
            if platform is None or plat == platform.lower():
                if rec.status == "SUBMITTED":
                    date_val = str(getattr(rec, "applied_at", None) or getattr(rec, "applied_date", None) or getattr(rec, "discovered_at", None) or getattr(rec, "created_date", None) or "")[:10]
                    if date_val == today_str:
                        count += 1
        return count

    def sync_legacy_linkedin_files(
        self,
        applied_csv: str = "all excels/all_applied_applications_history.csv",
        failed_csv: str = "all excels/all_failed_applications_history.csv",
    ) -> int:
        """
        Synchronizes historical LinkedIn applications from legacy CSVs into unified tracker.
        Returns the count of newly ingested records.
        """
        new_count = 0

        # Ingest successful applications
        if os.path.exists(applied_csv):
            try:
                with open(applied_csv, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        jid = str(row.get("Job ID", "")).strip()
                        if not jid:
                            continue
                        key = ("linkedin", jid)
                        if key not in self._records or self._records[key].status != "SUBMITTED":
                            rec = ApplicationRecord(
                                platform="linkedin",
                                job_id=jid,
                                title=row.get("Title", "").strip(),
                                company=row.get("Company", "").strip(),
                                location=row.get("Work Location", "").strip(),
                                source_url=row.get("Job Link", "").strip(),
                                status="SUBMITTED",
                                application_type="EASY_APPLY",
                                discovered_at=row.get("Date Applied", "") or row.get("Date Posted", ""),
                                applied_at=row.get("Date Applied", ""),
                            )
                            self._records[key] = rec
                            self._append_to_csv(rec)
                            new_count += 1
            except Exception as e:
                print_lg(f"[ApplicationTracker] Notice ingesting legacy applied CSV: {e}")

        # Ingest failed/skipped applications
        if os.path.exists(failed_csv):
            try:
                with open(failed_csv, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        jid = str(row.get("Job ID", "")).strip()
                        if not jid:
                            continue
                        key = ("linkedin", jid)
                        if key not in self._records:
                            reason = row.get("Assumed Reason", "").strip()
                            is_skip = "bad word" in reason.lower() or "skip" in reason.lower()
                            st: ApplicationState = "SKIPPED" if is_skip else "FAILED"
                            rec = ApplicationRecord(
                                platform="linkedin",
                                job_id=jid,
                                title="",
                                company="",
                                location="",
                                source_url=row.get("Job Link", "").strip(),
                                status=st,
                                application_type="DIRECT",
                                discovered_at=row.get("Date listed", "") or row.get("Date Tried", ""),
                                failure_reason=reason if not is_skip else None,
                                skip_reason=reason if is_skip else None,
                            )
                            self._records[key] = rec
                            self._append_to_csv(rec)
                            new_count += 1
            except Exception as e:
                print_lg(f"[ApplicationTracker] Notice ingesting legacy failed CSV: {e}")

        return new_count
