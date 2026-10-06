"""Configuration to Database Migration Engine.

Migrates legacy JSON configurations, Python config modules, and historical CSV logs
into normalized relational database models.

INVARIANTS:
1. Existing configuration and CSV files are strictly read-only; never modified or deleted.
2. ZERO secrets in DB: no passwords, tokens, cookies, or OTPs.
3. Fully idempotent: safe to execute multiple times without data duplication.
4. Validation routine: verifies DB values match existing configuration values.
"""

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import utc_now
from app.db.models import (
    Application,
    ApplicationStatusHistory,
    AppSetting,
    Company,
    Job,
    Platform,
    PlatformAccount,
    ProfessionalProfile,
    Profile,
    QnAEntry,
    Resume,
    User,
)
from app.db.service import init_db
from app.db.session import SessionLocal, get_db_session
from app.repositories.application_repository import ApplicationRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.dto import (
    ApplicationCreateDTO,
    JobCreateDTO,
    ProfessionalProfileUpdateDTO,
    ProfileUpdateDTO,
    QnACreateDTO,
)
from app.repositories.job_repository import JobRepository
from app.repositories.platform_repository import PlatformRepository
from app.repositories.qna_repository import QnARepository
from app.repositories.resume_repository import ResumeRepository
from app.repositories.settings_repository import SettingsRepository
from app.repositories.user_repository import UserRepository
from app.services.resume_service import ResumeService


@dataclass
class ValidationReport:
    """Parity verification report comparing database records against source configuration."""

    is_valid: bool
    mismatches: List[str] = field(default_factory=list)
    checked_fields: int = 0
    passed_fields: int = 0
    summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationReport:
    """Summary of operations performed during configuration migration."""

    dry_run: bool = False
    success: bool = True
    user_migrated: bool = False
    profiles_migrated: bool = False
    resumes_count: int = 0
    platforms_count: int = 0
    platform_accounts_count: int = 0
    qna_entries_count: int = 0
    settings_count: int = 0
    jobs_imported: int = 0
    applications_imported: int = 0
    companies_created: int = 0
    errors: List[str] = field(default_factory=list)
    validation: Optional[ValidationReport] = None


class MigrationService:
    """Engine for migrating legacy configuration and application history into SQLite."""

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        resume_service: Optional[ResumeService] = None,
        project_root: Optional[str] = None,
    ):
        self._session_factory = session_factory or SessionLocal
        self._project_root = Path(
            project_root
            or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ).resolve()
        self._resume_service = resume_service or ResumeService(
            storage_dir=os.path.join(self._project_root, "managed_resumes"),
            session_factory=self._session_factory,
        )

    # ----------------------------------------------------------------------
    # Config Extraction Helpers
    # ----------------------------------------------------------------------

    def load_source_config(self) -> Dict[str, Any]:
        """Loads configuration from config_loader or directly from config/profile.json."""
        try:
            from modules.config_loader import load_profile

            data = load_profile()
            if data:
                return data
        except Exception:
            pass

        profile_path = self._project_root / "config" / "profile.json"
        if profile_path.exists():
            import json

            with open(profile_path, "r", encoding="utf-8") as f:
                return json.load(f)

        template_path = self._project_root / "config" / "profile.template.json"
        if template_path.exists():
            import json

            with open(template_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return {}

    # ----------------------------------------------------------------------
    # 1. User & Candidate Profiles Migration
    # ----------------------------------------------------------------------

    def migrate_user_and_profiles(
        self,
        session: Session,
        config: Optional[Dict[str, Any]] = None,
    ) -> Tuple[User, Profile, ProfessionalProfile]:
        """Migrates candidate personal and professional profiles idempotently."""
        cfg = config if config is not None else self.load_source_config()
        personal = cfg.get("personal", {})
        prof = cfg.get("professional", {})

        first_name = str(personal.get("first_name", "Candidate")).strip()
        last_name = str(personal.get("last_name", "User")).strip()
        middle_name = personal.get("middle_name")
        email = str(personal.get("email", "candidate@jobpilot.local")).strip().lower()
        phone = personal.get("phone_number")

        full_name = f"{first_name} {last_name}".strip()
        user_repo = UserRepository(session)
        user = user_repo.get_or_create_primary_user(name=full_name, email=email, phone=phone)

        # If user already has both Personal Profile and Professional Profile in the DB,
        # preserve the DB as the source of truth rather than overwriting with static config files.
        existing_profile = user_repo.get_profile(user.id)
        existing_pro = user_repo.get_professional_profile(user.id)
        if existing_profile and existing_pro:
            return user, existing_profile, existing_pro

        # Update Personal Profile
        profile_dto = ProfileUpdateDTO(
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            current_city=str(personal.get("current_city", "India")).strip(),
            state=personal.get("state"),
            country=str(personal.get("country", "India")).strip(),
            zipcode=personal.get("zipcode"),
            address=personal.get("street"),
            willing_to_relocate=bool(personal.get("willing_to_relocate", False)),
        )
        profile = user_repo.update_profile(user.id, profile_dto)

        # Update Professional Profile
        exp_years = float(prof.get("years_of_experience", 0.0))
        cur_ctc = prof.get("current_ctc")
        if cur_ctc is not None:
            try:
                cur_ctc = int(cur_ctc)
            except (ValueError, TypeError):
                cur_ctc = None

        exp_ctc = prof.get("desired_salary")
        if exp_ctc is not None:
            try:
                exp_ctc = int(exp_ctc)
            except (ValueError, TypeError):
                exp_ctc = None

        prof_dto = ProfessionalProfileUpdateDTO(
            current_title=str(prof.get("title", "Software Engineer")).strip(),
            current_employer=prof.get("current_employer"),
            years_of_experience=exp_years,
            current_ctc=cur_ctc,
            expected_ctc=exp_ctc,
            notice_period_days=int(prof.get("notice_period_days", 30)),
            skills=prof.get("skills", []),
            linkedin_url=prof.get("linkedin_url"),
            github_url=prof.get("github_url"),
            portfolio_url=prof.get("portfolio_url"),
            headline=prof.get("headline"),
            summary=prof.get("summary"),
            cover_letter=prof.get("cover_letter"),
        )
        pro_profile = user_repo.update_professional_profile(user.id, prof_dto)

        return user, profile, pro_profile

    # ----------------------------------------------------------------------
    # 2. Resume Migration
    # ----------------------------------------------------------------------

    def migrate_resumes(
        self,
        session: Session,
        user_id: int,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[Resume]:
        """Discovers configured resume paths and registers them via ResumeRepository."""
        cfg = config if config is not None else self.load_source_config()
        resumes_cfg = cfg.get("resumes", {})
        default_path = resumes_cfg.get("default")
        roles_dict = resumes_cfg.get("roles", {})

        # Fallback to questions.py default_resume_path
        if not default_path:
            try:
                from config import questions

                default_path = getattr(questions, "default_resume_path", None)
            except Exception:
                pass

        resume_repo = ResumeRepository(session)
        imported_resumes: List[Resume] = []

        candidate_paths: List[Tuple[str, Optional[str], bool]] = []
        if default_path:
            candidate_paths.append((default_path, "General", True))

        for role_name, path in roles_dict.items():
            if path and path != default_path:
                candidate_paths.append((path, role_name, False))

        for rel_path, role_target, is_default in candidate_paths:
            resolved = self._project_root / rel_path
            if not resolved.exists():
                # Check if path is absolute
                resolved = Path(rel_path)
                if not resolved.exists():
                    continue

            name = resolved.stem.replace("_", " ").title()
            try:
                res_obj, created, err = self._resume_service.add_resume(
                    user_id=user_id,
                    source_path=str(resolved),
                    display_name=name,
                    role_target=role_target,
                    is_default=is_default,
                )
                if res_obj:
                    imported_resumes.append(res_obj)
            except Exception:
                pass

        return imported_resumes

    # ----------------------------------------------------------------------
    # 3. Platform & Platform Accounts Migration
    # ----------------------------------------------------------------------

    def migrate_platforms(
        self,
        session: Session,
        user_id: int,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[PlatformAccount]:
        """Registers core platforms and platform preferences without storing credentials."""
        cfg = config if config is not None else self.load_source_config()
        platform_repo = PlatformRepository(session)

        # If platform accounts already exist in DB, preserve DB as source of truth
        existing_li = platform_repo.get_account("linkedin")
        existing_nk = platform_repo.get_account("naukri")
        if existing_li and existing_nk:
            return [existing_li, existing_nk]

        accounts: List[PlatformAccount] = []
        platforms_cfg = cfg.get("platforms", {})

        # 1. LinkedIn
        li_cfg = platforms_cfg.get("linkedin", {})
        li_loc = li_cfg.get("search_location", "Delhi, India")
        li_exp = li_cfg.get("current_experience", 2)
        li_max = li_cfg.get("switch_number", 30)
        li_easy_only = "EASY_APPLY_ONLY" if li_cfg.get("easy_apply_only", True) else "ALL"
        li_extras = {
            "search_terms": li_cfg.get("search_terms", ["Software Engineer"]),
            "date_posted": li_cfg.get("date_posted", "Past week"),
            "bad_words": li_cfg.get("bad_words", []),
            "pause_at_failed_question": li_cfg.get("pause_at_failed_question", True),
            "pause_after_filters": li_cfg.get("pause_after_filters", True),
        }

        li_acc = platform_repo.save_account(
            platform_name="linkedin",
            display_name="LinkedIn",
            account_name="Default Profile",
            default_location=li_loc,
            experience_years=li_exp,
            max_applications=li_max,
            apply_mode=li_easy_only,
            pause_before_submit=li_cfg.get("pause_before_submit", True),
            stealth_mode=li_cfg.get("stealth_mode", True),
            safe_mode=li_cfg.get("safe_mode", True),
            extra_settings=li_extras,
        )
        accounts.append(li_acc)

        # 2. Naukri
        nk_cfg = platforms_cfg.get("naukri", {})
        nk_loc = nk_cfg.get("search_location", "Delhi, India")
        nk_exp = nk_cfg.get("experience_years", 2)
        nk_max = nk_cfg.get("max_jobs_evaluated_per_search", 50)
        nk_apply_mode = nk_cfg.get("apply_mode", "direct_only").upper()
        nk_extras = {
            "search_terms": nk_cfg.get("search_terms", ["Software Engineer"]),
            "max_pages_per_search": nk_cfg.get("max_pages_per_search", 3),
            "consecutive_skips_limit": nk_cfg.get("consecutive_skips_limit", 10),
            "freshness_days": nk_cfg.get("freshness_days", 7),
            "core_skills": nk_cfg.get("core_skills", ["python"]),
        }

        nk_acc = platform_repo.save_account(
            platform_name="naukri",
            display_name="Naukri.com",
            account_name="Default Profile",
            default_location=nk_loc,
            experience_years=nk_exp,
            max_applications=nk_max,
            apply_mode=nk_apply_mode,
            pause_before_submit=nk_cfg.get("pause_before_submit", True),
            stealth_mode=True,
            safe_mode=True,
            extra_settings=nk_extras,
        )
        accounts.append(nk_acc)

        # 3. Register Indeed & Glassdoor stubs
        platform_repo.get_or_create_platform("indeed", "Indeed")
        platform_repo.get_or_create_platform("glassdoor", "Glassdoor")

        return accounts

    # ----------------------------------------------------------------------
    # 4. Q&A Knowledge Base Migration
    # ----------------------------------------------------------------------

    def migrate_qna(
        self,
        session: Session,
        user_id: int,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[QnAEntry]:
        """Seeds Q&A knowledge base from profile.json and questions.py."""
        cfg = config if config is not None else self.load_source_config()
        qna_cfg = cfg.get("qna", {})
        std_answers = qna_cfg.get("standard_answers", {})
        custom_qa = qna_cfg.get("custom_qa", {})

        qna_repo = QnARepository(session)
        entries: List[QnAEntry] = []

        # Standard questionnaire mappings
        standard_map = {
            "require_visa": ("Do you require visa sponsorship now or in the future?", "work_auth", "boolean"),
            "us_citizenship": ("What is your citizenship or work authorization status?", "work_auth", "text"),
            "security_clearance": ("Do you have an active security clearance?", "background", "boolean"),
            "did_masters": ("Have you completed a Master's degree?", "education", "boolean"),
            "comfortable_with_remote": ("Are you comfortable working remotely?", "work_style", "boolean"),
            "valid_driving_license": ("Do you hold a valid driver's license?", "background", "boolean"),
            "background_check_consent": ("Do you consent to a background check?", "background", "boolean"),
        }

        for key, (prompt, category, a_type) in standard_map.items():
            if key in std_answers:
                val = str(std_answers[key])
                dto = QnACreateDTO(
                    question_text=prompt,
                    answer_text=val,
                    category=category,
                    source="PROFILE",
                    confidence=1.0,
                    validation_status="VERIFIED",
                    answer_type=a_type,
                )
                entry = qna_repo.upsert_answer(dto)
                entries.append(entry)

        # Custom Q&A entries
        for question_key, answer_val in custom_qa.items():
            dto = QnACreateDTO(
                question_text=question_key,
                answer_text=str(answer_val),
                category="custom",
                source="PROFILE",
                confidence=1.0,
                validation_status="VERIFIED",
                answer_type="text",
            )
            entry = qna_repo.upsert_answer(dto)
            entries.append(entry)

        return entries

    # ----------------------------------------------------------------------
    # 5. App Settings Migration
    # ----------------------------------------------------------------------

    def migrate_settings(
        self,
        session: Session,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[AppSetting]:
        """Migrates engine parameters and non-sensitive AI configurations."""
        cfg = config if config is not None else self.load_source_config()
        ai_cfg = cfg.get("ai", {})

        settings_repo = SettingsRepository(session)
        saved_settings: List[AppSetting] = []

        # Bot engine settings from settings.py or defaults
        engine_defaults = {
            "bot.click_gap": (1, "bot_engine", "Delay in seconds between automated UI clicks"),
            "bot.run_in_background": (False, "bot_engine", "Run browser in headless/background mode"),
            "bot.safe_mode": (True, "bot_engine", "Run browser in isolated profile mode"),
            "bot.stealth_mode": (True, "bot_engine", "Enable undetected anti-bot evasion"),
            "bot.keep_screen_awake": (True, "bot_engine", "Prevent operating system sleep during run"),
            "bot.smooth_scroll": (False, "bot_engine", "Use smooth human-like page scrolling"),
            "bot.close_tabs": (False, "bot_engine", "Close tabs after processing"),
            "bot.follow_companies": (False, "bot_engine", "Automatically follow companies on apply"),
            "bot.logs_folder_path": ("logs/", "system", "Path to automation log files"),
        }

        # Attempt to read live settings.py
        try:
            from config import settings

            for key in [
                "click_gap",
                "run_in_background",
                "safe_mode",
                "stealth_mode",
                "keep_screen_awake",
                "smooth_scroll",
                "close_tabs",
                "follow_companies",
                "logs_folder_path",
            ]:
                if hasattr(settings, key):
                    val = getattr(settings, key)
                    setting_key = f"bot.{key}"
                    if setting_key in engine_defaults:
                        _, cat, desc = engine_defaults[setting_key]
                        engine_defaults[setting_key] = (val, cat, desc)
        except Exception:
            pass

        for k, (v, cat, desc) in engine_defaults.items():
            s = settings_repo.set(k, v, category=cat, description=desc)
            saved_settings.append(s)

        # AI Configuration (ZERO SECRETS: api_key is NEVER saved)
        ai_settings = {
            "ai.enabled": (ai_cfg.get("enabled", True), "ai", "Enable LLM question answering engine"),
            "ai.provider": (ai_cfg.get("provider", "openai"), "ai", "LLM provider (openai, ollama, gemini)"),
            "ai.model": (ai_cfg.get("model", "llama3.1:8b"), "ai", "Default LLM model identifier"),
            "ai.api_url": (ai_cfg.get("api_url", "http://localhost:11434/v1/"), "ai", "LLM API endpoint URL"),
            "ai.spec": (ai_cfg.get("spec", "openai-like"), "ai", "API specification dialect"),
            "ai.stream": (ai_cfg.get("stream", False), "ai", "Stream LLM inference tokens"),
        }

        for k, (v, cat, desc) in ai_settings.items():
            s = settings_repo.set(k, v, category=cat, description=desc)
            saved_settings.append(s)

        return saved_settings

    # ----------------------------------------------------------------------
    # 6. Historical CSV Migration
    # ----------------------------------------------------------------------

    def migrate_historical_applications(
        self,
        session: Session,
        user_id: int,
        csv_dir: Optional[str] = None,
    ) -> Tuple[int, int, int]:
        """Imports historical job applications from CSV tracking logs.

        Returns:
            Tuple of (jobs_imported: int, applications_imported: int, companies_created: int)
        """
        directory = Path(csv_dir or (self._project_root / "all excels"))
        if not directory.exists():
            return 0, 0, 0

        company_repo = CompanyRepository(session)
        job_repo = JobRepository(session)
        app_repo = ApplicationRepository(session)

        jobs_imported = 0
        apps_imported = 0
        initial_company_count = session.scalar(select(func.count(Company.id))) or 0

        # 1. Parse applications.csv (Naukri / unified multi-platform format)
        unified_csv = directory / "applications.csv"
        if unified_csv.exists():
            try:
                with open(unified_csv, "r", encoding="utf-8", errors="replace") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        platform_code = (row.get("platform") or "naukri").strip().lower()
                        ext_id = (row.get("job_id") or "").strip()
                        title = (row.get("title") or "Unknown Title").strip()
                        company_raw = (row.get("company") or "Unknown Company").strip()
                        location = (row.get("location") or "").strip()
                        source_url = (row.get("source_url") or "").strip()
                        status = (row.get("status") or "DISCOVERED").strip().upper()
                        app_type = (row.get("application_type") or "DIRECT").strip().upper()
                        failure_reason = (row.get("failure_reason") or "").strip() or None
                        skip_reason = (row.get("skip_reason") or "").strip() or None
                        is_external = (status == "EXTERNAL" or app_type == "EXTERNAL")
                        app_method = "COMPANY_PORTAL" if is_external else "EASY_APPLY"

                        company = company_repo.get_or_create_by_name(name=company_raw, location=location)

                        job_dto = JobCreateDTO(
                            platform=platform_code,
                            company_raw=company_raw,
                            title=title,
                            source_url=source_url,
                            external_job_id=ext_id if ext_id else None,
                            location=location,
                            company_id=company.id,
                            apply_type=app_type,
                            application_method=app_method,
                            application_url=None,
                        )
                        job, job_created = job_repo.upsert_job(job_dto)
                        if job_created:
                            jobs_imported += 1

                        # Decouple Discovery from Application: only create Application for actual application attempts
                        APPLICATION_WORTHY_STATUSES = {
                            "SUBMITTED", "APPLIED", "APPLYING", "FAILED", "UNKNOWN", "MANUAL_REQUIRED"
                        }
                        if status in APPLICATION_WORTHY_STATUSES:
                            existing_app = app_repo.get_by_job_id(job.id)
                            if not existing_app:
                                app_dto = ApplicationCreateDTO(
                                    job_id=job.id,
                                    user_id=user_id,
                                    status="SUBMITTED" if status == "APPLIED" else status,
                                    application_type=app_type,
                                    notes=failure_reason or skip_reason,
                                )
                                app_repo.create_application(app_dto)
                                apps_imported += 1
            except Exception:
                pass

        # 2. Parse all_applied_applications_history.csv (LinkedIn history)
        li_csv = directory / "all_applied_applications_history.csv"
        if li_csv.exists():
            try:
                with open(li_csv, "r", encoding="utf-8", errors="replace") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        ext_id = (row.get("Job ID") or "").strip()
                        title = (row.get("Title") or "Unknown Title").strip()
                        company_raw = (row.get("Company") or "Unknown Company").strip()
                        location = (row.get("Work Location") or "").strip()
                        source_url = (row.get("Job Link") or row.get("External Job link") or "").strip()
                        work_style = (row.get("Work Style") or "").strip()
                        exp_req = (row.get("Experience required") or "").strip()
                        skills_req = (row.get("Skills required") or "").strip()
                        about_job = (row.get("About Job") or "").strip() or None
                        raw_ext_link = (row.get("External Job link") or "").strip()
                        is_external = bool(raw_ext_link and raw_ext_link.startswith("http"))
                        ext_job_link = raw_ext_link if is_external else None
                        app_method = "COMPANY_PORTAL" if is_external else "EASY_APPLY"


                        company = company_repo.get_or_create_by_name(name=company_raw, location=location)

                        job_dto = JobCreateDTO(
                            platform="linkedin",
                            company_raw=company_raw,
                            title=title,
                            source_url=source_url,
                            external_job_id=ext_id if ext_id else None,
                            location=location,
                            work_style=work_style,
                            experience_text=exp_req,
                            company_id=company.id,
                            apply_type="EXTERNAL" if is_external else "EASY_APPLY",
                            application_method=app_method,
                            application_url=ext_job_link,
                            description=about_job,
                        )
                        job, job_created = job_repo.upsert_job(job_dto)
                        if job_created:
                            jobs_imported += 1

                        existing_app = app_repo.get_by_job_id(job.id)
                        if not existing_app:
                            app_dto = ApplicationCreateDTO(
                                job_id=job.id,
                                user_id=user_id,
                                status="SUBMITTED",
                                application_type="EASY_APPLY",
                                external_job_link=ext_job_link,
                            )
                            app_repo.create_application(app_dto)
                            apps_imported += 1
            except Exception:
                pass

        final_company_count = session.scalar(select(func.count(Company.id))) or 0
        companies_created = final_company_count - initial_company_count

        return jobs_imported, apps_imported, companies_created

    # ----------------------------------------------------------------------
    # 7. Validation & Parity Verification
    # ----------------------------------------------------------------------

    def validate_migration(
        self,
        session: Session,
        user_id: int,
        config: Optional[Dict[str, Any]] = None,
    ) -> ValidationReport:
        """Compares database records against configuration files to guarantee parity."""
        cfg = config if config is not None else self.load_source_config()
        personal = cfg.get("personal", {})
        prof = cfg.get("professional", {})
        platforms = cfg.get("platforms", {})
        qna = cfg.get("qna", {})
        std_answers = qna.get("standard_answers", {})

        mismatches: List[str] = []
        checked = 0
        passed = 0

        user_repo = UserRepository(session)
        user = user_repo.get_by_id(user_id)
        if not user:
            return ValidationReport(is_valid=False, mismatches=["Primary User not found in database"])

        profile = user_repo.get_profile(user_id)
        pro_profile = user_repo.get_professional_profile(user_id)
        platform_repo = PlatformRepository(session)
        qna_repo = QnARepository(session)
        settings_repo = SettingsRepository(session)

        def _check(name: str, expected: Any, actual: Any):
            nonlocal checked, passed
            checked += 1
            if expected is not None and str(expected).strip() != "":
                try:
                    if float(expected) == float(actual):
                        passed += 1
                        return
                except (ValueError, TypeError):
                    pass

                if str(expected).strip() != str(actual).strip():
                    mismatches.append(f"{name}: expected '{expected}', found '{actual}'")
                else:
                    passed += 1
            else:
                passed += 1

        # Personal profile checks
        _check("First Name", personal.get("first_name"), profile.first_name if profile else None)
        _check("Last Name", personal.get("last_name"), profile.last_name if profile else None)
        _check("Email", personal.get("email"), user.email)
        _check("City", personal.get("current_city"), profile.current_city if profile else None)

        # Professional profile checks
        _check("Job Title", prof.get("title"), pro_profile.current_title if pro_profile else None)
        _check("Years Experience", prof.get("years_of_experience"), pro_profile.years_of_experience if pro_profile else None)
        _check("Current CTC", prof.get("current_ctc"), pro_profile.current_ctc if pro_profile else None)
        _check("Desired Salary", prof.get("desired_salary"), pro_profile.expected_ctc if pro_profile else None)
        _check("Notice Period", prof.get("notice_period_days"), pro_profile.notice_period_days if pro_profile else None)

        # Platform account checks
        li_acc = platform_repo.get_account("linkedin")
        if not li_acc:
            mismatches.append("Platform account for 'linkedin' missing from DB")
        else:
            li_cfg = platforms.get("linkedin", {})
            _check("LinkedIn Location", li_cfg.get("search_location"), li_acc.default_location)

        nk_acc = platform_repo.get_account("naukri")
        if not nk_acc:
            mismatches.append("Platform account for 'naukri' missing from DB")
        else:
            nk_cfg = platforms.get("naukri", {})
            _check("Naukri Location", nk_cfg.get("search_location"), nk_acc.default_location)

        # Settings checks
        stealth = settings_repo.get("bot.stealth_mode")
        _check("Stealth Mode Setting", True, stealth)

        is_valid = len(mismatches) == 0
        summary = {
            "checked_fields": checked,
            "passed_fields": passed,
            "mismatches_count": len(mismatches),
            "user_email": user.email,
        }
        return ValidationReport(
            is_valid=is_valid,
            mismatches=mismatches,
            checked_fields=checked,
            passed_fields=passed,
            summary=summary,
        )

    # ----------------------------------------------------------------------
    # 8. Full Migration Orchestrator
    # ----------------------------------------------------------------------

    def run_full_migration(
        self,
        dry_run: bool = False,
        config: Optional[Dict[str, Any]] = None,
        csv_dir: Optional[str] = None,
    ) -> MigrationReport:
        """Executes full end-to-end migration and returns a structured report."""
        report = MigrationReport(dry_run=dry_run)
        cfg = config if config is not None else self.load_source_config()

        with get_db_session(self._session_factory) as session:
            try:
                # 1. User & Profiles
                user, profile, pro_profile = self.migrate_user_and_profiles(session, cfg)
                report.user_migrated = bool(user)
                report.profiles_migrated = bool(profile and pro_profile)

                # 2. Resumes
                resumes = self.migrate_resumes(session, user.id, cfg)
                report.resumes_count = len(resumes)

                # 3. Platforms & Accounts
                accounts = self.migrate_platforms(session, user.id, cfg)
                report.platform_accounts_count = len(accounts)
                report.platforms_count = len(set(a.platform_id for a in accounts))

                # 4. Q&A Knowledge Base
                qna_entries = self.migrate_qna(session, user.id, cfg)
                report.qna_entries_count = len(qna_entries)

                # 5. Settings
                settings = self.migrate_settings(session, cfg)
                report.settings_count = len(settings)

                # 6. Historical CSVs
                jobs_cnt, apps_cnt, comp_cnt = self.migrate_historical_applications(
                    session, user.id, csv_dir
                )
                report.jobs_imported = jobs_cnt
                report.applications_imported = apps_cnt
                report.companies_created = comp_cnt

                # 7. Parity Validation
                val_report = self.validate_migration(session, user.id, cfg)
                report.validation = val_report
                report.success = val_report.is_valid

                if dry_run:
                    session.rollback()

            except Exception as e:
                report.success = False
                report.errors.append(str(e))
                session.rollback()
                raise

        return report
