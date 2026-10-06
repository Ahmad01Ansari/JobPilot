"""
Setup Readiness Engine for JobPilot.
Evaluates workspace configuration across CORE, RECOMMENDED, and OPTIONAL requirements.
Provides authoritative readiness judgments for Wizard, Dashboard, Settings, and Automation Pre-flight.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.services.setup.setup_requirements import (
    SetupRequirement,
    RequirementCriticality,
    RequirementStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class PlatformPreflightReport:
    """Pre-flight validation report for executing automation on a specific platform."""
    platform: str
    can_run_automation: bool
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommended_fix_route: str = "settings"


@dataclass
class ReadinessEvaluation:
    """Complete readiness evaluation report."""
    is_core_ready: bool
    is_automation_ready: bool
    core_completed_count: int
    core_total_count: int
    recommended_completed_count: int
    recommended_total_count: int
    requirements: Dict[str, SetupRequirement]
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    change_summary: List[str] = field(default_factory=list)

    @property
    def core_summary(self) -> str:
        return f"{self.core_completed_count}/{self.core_total_count} Core Requirements Complete"

    @property
    def recommended_summary(self) -> str:
        return f"{self.recommended_completed_count}/{self.recommended_total_count} Recommended Complete"


class SetupReadinessService:
    """Authoritative evaluation service for JobPilot setup readiness."""

    def __init__(
        self,
        profile_service=None,
        resume_service=None,
        settings_service=None,
        secrets_service=None,
        qna_service=None,
        platform_service=None,
    ):
        self._profile_service = profile_service
        self._resume_service = resume_service
        self._settings_service = settings_service
        self._secrets_service = secrets_service
        self._qna_service = qna_service
        self._platform_service = platform_service

    # Lazy loaders to avoid circular imports during app startup
    def _get_profile_service(self):
        if not self._profile_service:
            from app.services.profile_service import ProfileService
            self._profile_service = ProfileService()
        return self._profile_service

    def _get_resume_service(self):
        if not self._resume_service:
            from app.services.resume_service import ResumeService
            self._resume_service = ResumeService()
        return self._resume_service

    def _get_settings_service(self):
        if not self._settings_service:
            from app.services.settings_service import SettingsService
            self._settings_service = SettingsService()
        return self._settings_service

    def _get_secrets_service(self):
        if not self._secrets_service:
            from app.services.secrets_service import SecretsService
            self._secrets_service = SecretsService()
        return self._secrets_service

    def _get_qna_service(self):
        if not self._qna_service:
            from app.services.qna_service import QnAService
            self._qna_service = QnAService()
        return self._qna_service

    def _get_platform_service(self):
        if not self._platform_service:
            from app.services.platform_service import PlatformService
            self._platform_service = PlatformService()
        return self._platform_service

    def evaluate(self, user_id: int = 1) -> ReadinessEvaluation:
        """Evaluates all setup requirements and returns an authoritative evaluation report."""
        if user_id == 1:
            try:
                from app.db.session import SessionLocal, get_db_session
                from app.repositories.user_repository import UserRepository
                with get_db_session(SessionLocal) as session:
                    primary = UserRepository(session).get_primary_user()
                    if primary:
                        user_id = primary.id
            except Exception:
                pass

        requirements: Dict[str, SetupRequirement] = {}
        blockers: List[str] = []
        warnings: List[str] = []

        # 1. Candidate Profile (CORE)
        profile_req = self._evaluate_profile(user_id)
        requirements["candidate_profile"] = profile_req
        if profile_req.status != RequirementStatus.READY:
            blockers.append("Candidate profile is incomplete (Name, Email, Phone, or Skills missing).")

        # 2. Primary Resume (CORE)
        resume_req = self._evaluate_resume(user_id)
        requirements["primary_resume"] = resume_req
        if resume_req.status != RequirementStatus.READY:
            blockers.append("No active primary resume file uploaded.")

        # 3. Job Search Preferences (CORE)
        pref_req = self._evaluate_preferences()
        requirements["job_preferences"] = pref_req
        if pref_req.status != RequirementStatus.READY:
            blockers.append("Target job titles and locations are not defined.")

        # 4. AI Provider (RECOMMENDED)
        ai_req = self._evaluate_ai_provider()
        requirements["ai_provider"] = ai_req
        if ai_req.status != RequirementStatus.READY:
            warnings.append("AI Provider is not configured (manual screening Q&A fallback active).")

        # 5. Screening Q&A (RECOMMENDED)
        qna_req = self._evaluate_qna(user_id)
        requirements["screening_qna"] = qna_req
        if qna_req.status != RequirementStatus.READY:
            warnings.append("Screening Q&A knowledge base has unverified answers.")

        # 6. Platform Credentials (OPTIONAL)
        plat_req = self._evaluate_platforms()
        requirements["platform_credentials"] = plat_req
        if plat_req.status != RequirementStatus.READY:
            warnings.append("No job portal credentials or active browser sessions configured.")

        # 7. Automation Safety (OPTIONAL)
        safety_req = self._evaluate_safety()
        requirements["automation_safety"] = safety_req

        # Aggregate counts
        core_reqs = [r for r in requirements.values() if r.criticality == RequirementCriticality.CORE]
        rec_reqs = [r for r in requirements.values() if r.criticality == RequirementCriticality.RECOMMENDED]

        core_completed = sum(1 for r in core_reqs if r.status == RequirementStatus.READY)
        rec_completed = sum(1 for r in rec_reqs if r.status == RequirementStatus.READY)

        is_core_ready = (core_completed == len(core_reqs))

        # Automation requires Core Ready + AI Provider + Screening Q&A + Platform + Safety
        is_automation_ready = (
            is_core_ready
            and ai_req.status == RequirementStatus.READY
            and qna_req.status == RequirementStatus.READY
            and plat_req.status == RequirementStatus.READY
            and safety_req.status == RequirementStatus.READY
        )

        return ReadinessEvaluation(
            is_core_ready=is_core_ready,
            is_automation_ready=is_automation_ready,
            core_completed_count=core_completed,
            core_total_count=len(core_reqs),
            recommended_completed_count=rec_completed,
            recommended_total_count=len(rec_reqs),
            requirements=requirements,
            blockers=blockers,
            warnings=warnings,
        )

    def evaluate_for_platform(self, platform_name: str, user_id: int = 1) -> PlatformPreflightReport:
        """Pre-flight check specifically tailored for launching a platform bot or Universal ATS."""
        base_eval = self.evaluate(user_id)
        blockers = list(base_eval.blockers)
        warnings = list(base_eval.warnings)

        # Check platform-specific session/credentials
        try:
            plat_service = self._get_platform_service()
            platform = plat_service.get_platform_by_name(platform_name)
            is_active = getattr(platform, "is_enabled", getattr(platform, "is_active", False))
            if not platform:
                blockers.append(f"Platform '{platform_name}' is not registered.")
            elif not is_active:
                blockers.append(f"Platform '{platform_name}' is disabled in settings.")
        except Exception as exc:
            logger.warning("Could not query platform service for %s: %s", platform_name, exc)
            warnings.append(f"Could not verify {platform_name} status.")

        # Check if AI provider is responsive if AI-enabled
        settings = self._get_settings_service()
        ai_enabled = settings.get("ai.enabled", True)
        if ai_enabled and base_eval.requirements["ai_provider"].status != RequirementStatus.READY:
            warnings.append("AI assistance is enabled but AI Provider has not passed connectivity tests.")

        can_run = (len(blockers) == 0 and base_eval.is_core_ready)
        recommended_route = "profile" if not base_eval.is_core_ready else "platforms"

        return PlatformPreflightReport(
            platform=platform_name,
            can_run_automation=can_run,
            blockers=blockers,
            warnings=warnings,
            recommended_fix_route=recommended_route,
        )

    # Internal Evaluators

    def _evaluate_profile(self, user_id: int) -> SetupRequirement:
        try:
            ps = self._get_profile_service()
            profile = {}
            if hasattr(ps, "get_primary_user_profile"):
                raw = ps.get_primary_user_profile()
                if isinstance(raw, tuple):
                    user_obj = raw[0] if len(raw) > 0 else None
                    prof_obj = raw[1] if len(raw) > 1 else None
                    pro_prof_obj = raw[2] if len(raw) > 2 else None
                    skills_list = getattr(pro_prof_obj, "skills", []) if pro_prof_obj else []
                    if not skills_list and hasattr(user_obj, "professional_profile") and user_obj.professional_profile:
                        skills_list = getattr(user_obj.professional_profile, "skills", []) or []
                    profile = {
                        "personal_info": {
                            "name": getattr(user_obj, "name", ""),
                            "email": getattr(user_obj, "email", ""),
                            "phone": getattr(user_obj, "phone", ""),
                        },
                        "skills": skills_list,
                    }
                elif isinstance(raw, dict):
                    profile = raw

            if not profile and hasattr(ps, "export_profile_to_dict"):
                exp = ps.export_profile_to_dict(user_id=user_id)
                if isinstance(exp, dict):
                    profile = exp

            personal = profile.get("personal_info") or profile.get("personal") or {}
            if not isinstance(personal, dict):
                personal = {}

            skills = profile.get("skills") or []
            if not isinstance(skills, list):
                skills = []

            def _clean(val):
                return val.strip() if isinstance(val, str) else ""

            name_val = _clean(personal.get("name") or personal.get("full_name") or personal.get("first_name"))
            email_val = _clean(personal.get("email"))
            phone_val = _clean(personal.get("phone") or personal.get("phone_number"))

            has_name = bool(name_val)
            has_email = bool(email_val)
            has_phone = bool(phone_val)
            has_skills = len(skills) >= 3

            missing = []
            if not has_name: missing.append("Full Name")
            if not has_email: missing.append("Email")
            if not has_phone: missing.append("Phone")
            if not has_skills: missing.append("At least 3 Skills")

            if has_name and has_email and has_phone and has_skills:
                status = RequirementStatus.READY
            elif has_name or has_email:
                status = RequirementStatus.NEEDS_REVIEW
            else:
                status = RequirementStatus.NOT_STARTED

            return SetupRequirement(
                key="candidate_profile",
                title="Candidate Profile",
                description="Personal identity, contact details, and top skills.",
                criticality=RequirementCriticality.CORE,
                status=status,
                blocking=(status != RequirementStatus.READY),
                route="profile",
                fix_action="edit_profile",
                details={"name": name_val, "missing": missing},
            )
        except Exception as exc:
            logger.warning("Error evaluating candidate profile: %s", exc)
            return SetupRequirement(
                key="candidate_profile",
                title="Candidate Profile",
                description="Personal identity, contact details, and top skills.",
                criticality=RequirementCriticality.CORE,
                status=RequirementStatus.NOT_STARTED,
                blocking=True,
                route="profile",
                fix_action="edit_profile",
            )

    def _evaluate_resume(self, user_id: int) -> SetupRequirement:
        try:
            rs = self._get_resume_service()
            resumes = rs.list_resumes(user_id=user_id) or []
            if not resumes:
                return SetupRequirement(
                    key="primary_resume",
                    title="Primary Resume Document",
                    description="Active PDF or Word resume uploaded and stored.",
                    criticality=RequirementCriticality.CORE,
                    status=RequirementStatus.NOT_STARTED,
                    blocking=True,
                    route="resumes",
                    fix_action="upload_resume",
                )

            # Check if default resume file actually exists
            default_resume = rs.get_default_resume(user_id=user_id) or resumes[0]
            file_path = Path(default_resume.file_path) if hasattr(default_resume, "file_path") else None
            is_valid_file = file_path and file_path.exists() and file_path.stat().st_size > 0

            status = RequirementStatus.READY if is_valid_file else RequirementStatus.NEEDS_REVIEW
            return SetupRequirement(
                key="primary_resume",
                title="Primary Resume Document",
                description="Active PDF or Word resume uploaded and stored.",
                criticality=RequirementCriticality.CORE,
                status=status,
                blocking=(status != RequirementStatus.READY),
                route="resumes",
                fix_action="upload_resume",
                details={
                    "filename": default_resume.original_filename if hasattr(default_resume, "original_filename") else "Resume",
                    "file_exists": is_valid_file,
                },
            )
        except Exception as exc:
            logger.warning("Error evaluating resume: %s", exc)
            return SetupRequirement(
                key="primary_resume",
                title="Primary Resume Document",
                description="Active PDF or Word resume uploaded and stored.",
                criticality=RequirementCriticality.CORE,
                status=RequirementStatus.NOT_STARTED,
                blocking=True,
                route="resumes",
                fix_action="upload_resume",
            )

    def _evaluate_preferences(self) -> SetupRequirement:
        try:
            ss = self._get_settings_service()
            prefs = ss.get("search_preferences", {})
            if not isinstance(prefs, dict):
                prefs = {}

            titles = prefs.get("titles") or prefs.get("target_roles") or []
            locations = prefs.get("locations") or []

            # If empty in SettingsService, check config_loader as fallback
            if not titles or not locations:
                try:
                    from modules.config_loader import get_search
                    cfg_search = get_search() or {}
                    if not titles:
                        titles = cfg_search.get("roles") or cfg_search.get("titles") or []
                    if not locations:
                        locations = cfg_search.get("locations") or []
                except Exception:
                    pass

            has_titles = len(titles) > 0
            has_locations = len(locations) > 0

            if has_titles and has_locations:
                status = RequirementStatus.READY
            elif has_titles or has_locations:
                status = RequirementStatus.NEEDS_REVIEW
            else:
                status = RequirementStatus.NOT_STARTED

            return SetupRequirement(
                key="job_preferences",
                title="Job Search Preferences",
                description="Target role titles, preferred locations, and work arrangement.",
                criticality=RequirementCriticality.CORE,
                status=status,
                blocking=(status != RequirementStatus.READY),
                route="search",
                fix_action="edit_preferences",
                details={"titles": titles, "locations": locations},
            )
        except Exception as exc:
            logger.warning("Error evaluating preferences: %s", exc)
            return SetupRequirement(
                key="job_preferences",
                title="Job Search Preferences",
                description="Target role titles, preferred locations, and work arrangement.",
                criticality=RequirementCriticality.CORE,
                status=RequirementStatus.NOT_STARTED,
                blocking=True,
                route="search",
                fix_action="edit_preferences",
            )

    def _evaluate_ai_provider(self) -> SetupRequirement:
        try:
            ss = self._get_settings_service()
            sec = self._get_secrets_service()

            provider = ss.get("ai_provider") or ss.get("ai.provider", "groq")
            if not isinstance(provider, str):
                provider = "groq"
            provider_key_name = f"ai_api_key_{provider}"
            has_key = bool(sec.get_secret(provider_key_name))

            # Local Ollama doesn't require an API key
            if provider == "ollama":
                status = RequirementStatus.READY
            elif has_key:
                status = RequirementStatus.READY
            else:
                status = RequirementStatus.NOT_STARTED

            return SetupRequirement(
                key="ai_provider",
                title="AI Reasoning Provider",
                description="LLM provider for structured Q&A answering and tailoring.",
                criticality=RequirementCriticality.RECOMMENDED,
                status=status,
                blocking=False,
                route="settings",
                fix_action="configure_ai",
                details={"provider": provider, "has_key": has_key},
            )
        except Exception as exc:
            logger.warning("Error evaluating AI provider: %s", exc)
            return SetupRequirement(
                key="ai_provider",
                title="AI Reasoning Provider",
                description="LLM provider for structured Q&A answering and tailoring.",
                criticality=RequirementCriticality.RECOMMENDED,
                status=RequirementStatus.NOT_STARTED,
                blocking=False,
                route="settings",
                fix_action="configure_ai",
            )

    def _evaluate_qna(self, user_id: int) -> SetupRequirement:
        try:
            qs = self._get_qna_service()
            stats = qs.get_stats() if hasattr(qs, "get_stats") else {}
            total = 0
            if isinstance(stats, dict):
                val = stats.get("total_entries", 0)
                if isinstance(val, (int, float)):
                    total = int(val)

            if total >= 4:
                status = RequirementStatus.READY
            elif total > 0:
                status = RequirementStatus.NEEDS_REVIEW
            else:
                status = RequirementStatus.NOT_STARTED

            return SetupRequirement(
                key="screening_qna",
                title="Screening Q&A Knowledge Base",
                description="Verified candidate answers for sponsorship, notice, and work authorization.",
                criticality=RequirementCriticality.RECOMMENDED,
                status=status,
                blocking=False,
                route="profile",
                fix_action="review_qna",
                details={"total_rules": total},
            )
        except Exception as exc:
            logger.warning("Error evaluating Q&A: %s", exc)
            return SetupRequirement(
                key="screening_qna",
                title="Screening Q&A Knowledge Base",
                description="Verified candidate answers for sponsorship, notice, and work authorization.",
                criticality=RequirementCriticality.RECOMMENDED,
                status=RequirementStatus.NOT_STARTED,
                blocking=False,
                route="profile",
                fix_action="review_qna",
            )

    def _evaluate_platforms(self) -> SetupRequirement:
        try:
            ps = self._get_platform_service()
            platforms = ps.list_platforms() if hasattr(ps, "list_platforms") else []
            active = [p for p in platforms if getattr(p, "is_enabled", getattr(p, "is_active", False))]
            status = RequirementStatus.READY if active else RequirementStatus.NOT_STARTED

            return SetupRequirement(
                key="platform_credentials",
                title="Supported Job Platforms",
                description="Active platform accounts (LinkedIn, Naukri, Indeed, Foundit, Glassdoor, Email, Universal ATS).",
                criticality=RequirementCriticality.OPTIONAL,
                status=status,
                blocking=False,
                route="platforms",
                fix_action="configure_platforms",
                details={"active_count": len(active), "total_count": len(platforms)},
            )
        except Exception as exc:
            logger.warning("Error evaluating platforms: %s", exc)
            return SetupRequirement(
                key="platform_credentials",
                title="Supported Job Platforms",
                description="Active platform accounts (LinkedIn, Naukri, Indeed).",
                criticality=RequirementCriticality.OPTIONAL,
                status=RequirementStatus.NOT_STARTED,
                blocking=False,
                route="platforms",
                fix_action="configure_platforms",
            )

    def _evaluate_safety(self) -> SetupRequirement:
        try:
            ss = self._get_settings_service()
            automation = ss.get("automation", {})
            if not isinstance(automation, dict):
                automation = {}
            daily_limit = automation.get("daily_limit", 25)
            status = RequirementStatus.READY if daily_limit > 0 else RequirementStatus.NEEDS_REVIEW

            return SetupRequirement(
                key="automation_safety",
                title="Automation Safety & Limits",
                description="Daily application thresholds and pacing delays.",
                criticality=RequirementCriticality.OPTIONAL,
                status=status,
                blocking=False,
                route="settings",
                fix_action="configure_safety",
                details={"daily_limit": daily_limit},
            )
        except Exception as exc:
            logger.warning("Error evaluating safety: %s", exc)
            return SetupRequirement(
                key="automation_safety",
                title="Automation Safety & Limits",
                description="Daily application thresholds and pacing delays.",
                criticality=RequirementCriticality.OPTIONAL,
                status=RequirementStatus.READY,
                blocking=False,
                route="settings",
                fix_action="configure_safety",
            )
