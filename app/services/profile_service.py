"""Candidate Profile Management Service.

Encapsulates candidate personal, contact, professional background, compensation,
and technical skills management backed by the relational database.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import ProfessionalProfile, Profile, User
from app.db.session import SessionLocal, get_db_session
from app.repositories.dto import ProfessionalProfileUpdateDTO, ProfileUpdateDTO
from app.repositories.user_repository import UserRepository


class ProfileService:
    """Business logic for candidate profile viewing, editing, and readiness scoring."""

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal
        self.is_test = (session_factory is not None and session_factory != SessionLocal)

    def get_primary_user_profile(
        self,
    ) -> Tuple[User, Optional[Profile], Optional[ProfessionalProfile]]:
        """Retrieves or creates the primary candidate user and their profiles."""
        with get_db_session(self._session_factory) as session:
            repo = UserRepository(session)
            user = repo.get_primary_user()

            if not user:
                # Fallback to config_loader or default candidate if database is unseeded
                email = "candidate@jobpilot.local"
                name = "Candidate User"
                phone = None
                try:
                    from modules.config_loader import get_personal

                    pers = get_personal()
                    if pers:
                        email = pers.get("email") or email
                        fname = pers.get("first_name", "")
                        lname = pers.get("last_name", "")
                        name = f"{fname} {lname}".strip() or name
                        phone = pers.get("phone_number")
                except Exception:
                    pass

                user = repo.get_or_create_primary_user(name=name, email=email, phone=phone)

            profile = repo.get_profile(user.id)
            pro_profile = repo.get_professional_profile(user.id)
            return user, profile, pro_profile

    def get_profile_by_user_id(
        self, user_id: int
    ) -> Tuple[Optional[User], Optional[Profile], Optional[ProfessionalProfile]]:
        """Retrieves user and associated profiles by user ID."""
        with get_db_session(self._session_factory) as session:
            repo = UserRepository(session)
            user = repo.get_by_id(user_id)
            if not user:
                return None, None, None
            profile = repo.get_profile(user_id)
            pro_profile = repo.get_professional_profile(user_id)
            return user, profile, pro_profile

    def save_profile(
        self,
        user_id: int,
        personal_data: Dict[str, Any],
        professional_data: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """Validates and persists candidate personal and professional profile details.

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        # 1. Validation
        email = str(personal_data.get("email", "")).strip().lower()
        if not email or "@" not in email or "." not in email.split("@")[-1]:
            return False, "Please provide a valid candidate email address."

        first_name = str(personal_data.get("first_name", "")).strip()
        last_name = str(personal_data.get("last_name", "")).strip()
        if not first_name or not last_name:
            return False, "First name and last name are required."

        title = str(professional_data.get("title", "")).strip()
        if not title:
            return False, "Current job title / designation is required."

        # Numeric validations
        try:
            exp = float(professional_data.get("years_of_experience", 0.0))
            if exp < 0:
                return False, "Years of experience cannot be negative."
        except (ValueError, TypeError):
            return False, "Years of experience must be a valid number."

        cur_ctc = professional_data.get("current_ctc")
        if cur_ctc is not None and str(cur_ctc).strip() != "":
            try:
                cur_ctc = int(cur_ctc)
                if cur_ctc < 0:
                    return False, "Current CTC cannot be negative."
            except (ValueError, TypeError):
                return False, "Current CTC must be an integer (e.g. 500000 for 5 LPA)."
        else:
            cur_ctc = None

        exp_ctc = professional_data.get("expected_ctc")
        if exp_ctc is not None and str(exp_ctc).strip() != "":
            try:
                exp_ctc = int(exp_ctc)
                if exp_ctc < 0:
                    return False, "Expected CTC cannot be negative."
            except (ValueError, TypeError):
                return False, "Expected CTC must be an integer (e.g. 800000 for 8 LPA)."
        else:
            exp_ctc = None

        try:
            notice = int(professional_data.get("notice_period_days", 30))
            if notice < 0:
                return False, "Notice period days cannot be negative."
        except (ValueError, TypeError):
            return False, "Notice period must be an integer number of days."

        # Skills normalization
        raw_skills = professional_data.get("skills", [])
        if isinstance(raw_skills, str):
            skills_list = [s.strip() for s in re.split(r"[,;\n]", raw_skills) if s.strip()]
        elif isinstance(raw_skills, list):
            skills_list = [str(s).strip() for s in raw_skills if str(s).strip()]
        else:
            skills_list = []

        # 2. Database Persistence
        try:
            with get_db_session(self._session_factory) as session:
                repo = UserRepository(session)
                user = repo.get_by_id(user_id)
                if not user:
                    return False, f"User ID {user_id} not found."

                # Update core User fields
                full_name = f"{first_name} {last_name}".strip()
                user.name = full_name
                user.email = email
                phone = personal_data.get("phone_number")
                if phone:
                    user.phone = str(phone).strip()

                # Update Personal Profile
                profile_dto = ProfileUpdateDTO(
                    first_name=first_name,
                    last_name=last_name,
                    middle_name=personal_data.get("middle_name"),
                    current_city=str(personal_data.get("current_city", "India")).strip(),
                    state=personal_data.get("state"),
                    country=str(personal_data.get("country", "India")).strip(),
                    zipcode=personal_data.get("zipcode"),
                    address=personal_data.get("address"),
                    willing_to_relocate=bool(personal_data.get("willing_to_relocate", False)),
                )
                repo.save_profile(user_id, profile_dto)

                # Update Professional Profile
                prof_dto = ProfessionalProfileUpdateDTO(
                    current_title=title,
                    current_employer=professional_data.get("current_employer"),
                    years_of_experience=exp,
                    current_ctc=cur_ctc,
                    expected_ctc=exp_ctc,
                    notice_period_days=notice,
                    skills=skills_list,
                    linkedin_url=professional_data.get("linkedin_url"),
                    github_url=professional_data.get("github_url"),
                    portfolio_url=professional_data.get("portfolio_url"),
                    headline=professional_data.get("headline"),
                    summary=professional_data.get("summary"),
                    cover_letter=professional_data.get("cover_letter"),
                )
                repo.save_professional_profile(user_id, prof_dto)
                session.commit()

            # Synchronize changes back to config/profile.json so automation engines pick them up immediately
            if not self.is_test:
                self._sync_to_profile_json(personal_data, professional_data)

            return True, None
        except Exception as e:
            return False, f"Database error while saving profile: {e}"

    def _sync_to_profile_json(
        self,
        personal_data: Dict[str, Any],
        professional_data: Dict[str, Any],
    ) -> None:
        """Synchronizes updated personal and professional profile details into config/profile.json."""
        try:
            import json
            import logging
            from pathlib import Path

            profile_path = Path(__file__).resolve().parent.parent.parent / "config" / "profile.json"
            if not profile_path.exists():
                return

            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "personal" not in data or not isinstance(data["personal"], dict):
                data["personal"] = {}
            if "professional" not in data or not isinstance(data["professional"], dict):
                data["professional"] = {}

            # Update personal fields
            if "first_name" in personal_data:
                data["personal"]["first_name"] = personal_data["first_name"] or ""
            if "middle_name" in personal_data:
                data["personal"]["middle_name"] = personal_data["middle_name"] or ""
            if "last_name" in personal_data:
                data["personal"]["last_name"] = personal_data["last_name"] or ""
            if "email" in personal_data:
                data["personal"]["email"] = personal_data["email"] or ""
            if "phone_number" in personal_data:
                data["personal"]["phone_number"] = personal_data["phone_number"] or ""
            if "current_city" in personal_data:
                data["personal"]["current_city"] = personal_data["current_city"] or ""
                data["personal"]["street"] = personal_data["current_city"] or ""
            if "state" in personal_data:
                data["personal"]["state"] = personal_data["state"] or ""
            if "country" in personal_data:
                data["personal"]["country"] = personal_data["country"] or "India"
            if "zipcode" in personal_data:
                data["personal"]["zipcode"] = personal_data["zipcode"] or ""
            if "willing_to_relocate" in personal_data:
                data["personal"]["willing_to_relocate"] = bool(personal_data["willing_to_relocate"])

            # Update professional fields
            if "title" in professional_data:
                data["professional"]["title"] = professional_data["title"] or ""
            if "current_employer" in professional_data:
                data["professional"]["current_employer"] = professional_data["current_employer"] or ""
            if "years_of_experience" in professional_data and professional_data["years_of_experience"] is not None:
                data["professional"]["years_of_experience"] = professional_data["years_of_experience"]
            if "current_ctc" in professional_data:
                try:
                    data["professional"]["current_ctc"] = int(professional_data["current_ctc"]) if professional_data["current_ctc"] else None
                except (ValueError, TypeError):
                    data["professional"]["current_ctc"] = None
            if "expected_ctc" in professional_data:
                try:
                    data["professional"]["desired_salary"] = int(professional_data["expected_ctc"]) if professional_data["expected_ctc"] else None
                except (ValueError, TypeError):
                    data["professional"]["desired_salary"] = None
            if "notice_period_days" in professional_data:
                try:
                    data["professional"]["notice_period_days"] = int(professional_data["notice_period_days"]) if professional_data["notice_period_days"] is not None else 30
                except (ValueError, TypeError):
                    data["professional"]["notice_period_days"] = 30
            if "linkedin_url" in professional_data:
                data["professional"]["linkedin_url"] = professional_data["linkedin_url"] or ""
            if "github_url" in professional_data:
                data["professional"]["github_url"] = professional_data["github_url"] or ""
            if "portfolio_url" in professional_data:
                data["professional"]["portfolio_url"] = professional_data["portfolio_url"] or ""
            if "headline" in professional_data:
                data["professional"]["headline"] = professional_data["headline"] or ""
            if "summary" in professional_data:
                data["professional"]["summary"] = professional_data["summary"] or ""
            if "cover_letter" in professional_data:
                data["professional"]["cover_letter"] = professional_data["cover_letter"] or ""

            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Invalidate config cache
            try:
                import modules.config_loader as cfg_ldr
                cfg_ldr._PROFILE_CACHE = None
            except Exception:
                pass
        except Exception as exc:
            logger = logging.getLogger(__name__)
            logger.warning("Failed to synchronize profile.json: %s", exc)

    def validate_completeness(self, user_id: int) -> Dict[str, Any]:
        """Calculates completeness percentage and checks for missing critical fields."""
        with get_db_session(self._session_factory) as session:
            repo = UserRepository(session)
            user = repo.get_by_id(user_id)
            profile = repo.get_profile(user_id)
            pro = repo.get_professional_profile(user_id)

            critical = [
                ("Full Name", bool(user and user.name)),
                ("Email", bool(user and user.email)),
                ("Phone", bool(user and user.phone)),
                ("City", bool(profile and profile.current_city)),
                ("Job Title", bool(pro and pro.current_title)),
                ("Current CTC", bool(pro and pro.current_ctc is not None)),
                ("Expected CTC", bool(pro and pro.expected_ctc is not None)),
                ("Notice Period", bool(pro and pro.notice_period_days is not None)),
            ]

            recommended = [
                ("LinkedIn URL", bool(pro and pro.linkedin_url)),
                ("Skills", bool(pro and pro.skills and len(pro.skills) > 0)),
                ("Summary / Bio", bool(pro and pro.summary)),
                ("Portfolio URL", bool(pro and pro.portfolio_url)),
            ]

            missing_critical = [name for name, present in critical if not present]
            missing_recommended = [name for name, present in recommended if not present]

            total_weights = len(critical) * 2 + len(recommended)
            achieved = (len(critical) - len(missing_critical)) * 2 + (
                len(recommended) - len(missing_recommended)
            )
            score = int((achieved / total_weights) * 100) if total_weights > 0 else 0

            is_ready = len(missing_critical) == 0

            return {
                "score": score,
                "is_ready": is_ready,
                "missing_critical": missing_critical,
                "missing_recommended": missing_recommended,
                "summary": (
                    "Profile is ready for job automation."
                    if is_ready
                    else f"Missing {len(missing_critical)} critical field(s) for automation."
                ),
            }

    def apply_onboarding_data(
        self,
        user_id: int,
        data: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """Applies reviewed onboarding data across User, Profile, ProfessionalProfile, and Q&A."""
        try:
            pers = data.get("personal", {})
            prof = data.get("professional", {})
            skills_list = data.get("skills", [])
            qna_data = data.get("qna", {})

            # Clean skill names
            extracted_skills = []
            for s in skills_list:
                if isinstance(s, dict):
                    name = s.get("name", "").strip()
                else:
                    name = str(s).strip()
                if name and name not in extracted_skills:
                    extracted_skills.append(name)

            first_name = pers.get("first_name", "").strip() or "Candidate"
            last_name = pers.get("last_name", "").strip() or "User"
            email = pers.get("email", "").strip()
            phone = pers.get("phone", "").strip()

            # Build personal_data dict matching save_profile's expected format
            personal_data = {
                "first_name": first_name,
                "last_name": last_name,
                "email": email or "candidate@jobpilot.local",
                "phone_number": phone,
                "current_city": pers.get("current_city", "Delhi").strip() or "Delhi",
                "state": pers.get("state", "Delhi").strip() or "Delhi",
                "country": pers.get("country", "India").strip() or "India",
                "willing_to_relocate": qna_data.get("open_to_relocation", "Yes").strip().lower() == "yes",
            }

            # Build professional_data dict matching save_profile's expected format
            professional_data = {
                "title": prof.get("current_title", "Software Engineer").strip() or "Software Engineer",
                "years_of_experience": float(prof.get("years_of_experience", 2.0)),
                "current_ctc": int(prof.get("current_ctc", 350000)),
                "expected_ctc": int(prof.get("expected_ctc", 550000)),
                "notice_period_days": int(prof.get("notice_period_days", 30)),
                "skills": extracted_skills,
                "linkedin_url": pers.get("linkedin_url", "").strip() or None,
                "github_url": pers.get("github_url", "").strip() or None,
                "portfolio_url": pers.get("portfolio_url", "").strip() or None,
                "headline": prof.get("current_title", "").strip() or None,
                "summary": prof.get("summary", "").strip() or None,
            }

            # Save in database using the Dict-based save_profile
            ok, err = self.save_profile(
                user_id=user_id,
                personal_data=personal_data,
                professional_data=professional_data,
            )
            if not ok:
                return False, err

            # Sync QnA questions into database
            if qna_data:
                self._sync_onboarding_qna(qna_data)

            return True, None
        except Exception as exc:
            return False, f"Failed to apply onboarding data: {exc}"

    def _sync_onboarding_qna(self, qna_dict: Dict[str, Any]) -> None:
        """Syncs standard screening answers to QnAEntry database records."""
        from app.db.models.qna import QnAEntry
        mapping = {
            "authorized_in_india": ("Are you legally authorized to work in India?", "authorization", "boolean"),
            "authorized_in_us": ("Are you legally authorized to work in the United States?", "authorization", "boolean"),
            "require_sponsorship": ("Will you now or in the future require visa sponsorship?", "authorization", "boolean"),
            "open_to_relocation": ("Are you open or willing to relocate for this position?", "relocation", "boolean"),
            "comfortable_with_remote": ("Are you comfortable working in a remote or hybrid environment?", "location", "boolean"),
        }
        with get_db_session(self._session_factory) as session:
            for key, val in qna_dict.items():
                if key in mapping and val:
                    q_text, cat, a_type = mapping[key]
                    norm = q_text.lower().strip()
                    entry = session.query(QnAEntry).filter_by(normalized_question=norm).first()
                    if entry:
                        entry.answer_text = str(val).strip()
                        entry.source = "PROFILE"
                        entry.validation_status = "VERIFIED"
                    else:
                        new_entry = QnAEntry(
                            question_text=q_text,
                            normalized_question=norm,
                            answer_text=str(val).strip(),
                            answer_type=a_type,
                            category=cat,
                            source="PROFILE",
                            confidence=1.0,
                            validation_status="VERIFIED",
                        )
                        session.add(new_entry)
            session.commit()

    def export_profile_to_dict(self, user_id: int = 1) -> Dict[str, Any]:
        """Exports complete candidate profile from SQLite database to standard profile.json structure."""
        with get_db_session(self._session_factory) as session:
            repo = UserRepository(session)
            user = repo.get_by_id(user_id) or repo.get_primary_user()
            if not user:
                return {}

            prof = repo.get_profile(user.id)
            pro_prof = repo.get_professional_profile(user.id)

            first_name = ""
            last_name = ""
            if user.name:
                parts = user.name.split(None, 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ""

            personal = {
                "first_name": first_name,
                "middle_name": "",
                "last_name": last_name,
                "email": user.email or "",
                "phone_number": user.phone or "",
                "current_city": (prof.current_city if prof else "") or "",
                "street": (prof.current_city if prof else "") or "",
                "state": (prof.state if prof else "") or "",
                "zipcode": (prof.zipcode if prof else "") or "",
                "country": (prof.country if prof else "") or "India",
                "ethnicity": "Decline",
                "gender": "Decline",
                "disability_status": "No",
                "veteran_status": "No",
            }

            professional = {
                "title": (pro_prof.current_title if pro_prof else "") or "",
                "current_employer": (pro_prof.current_employer if pro_prof else "") or "",
                "years_of_experience": (pro_prof.years_of_experience if pro_prof else 0) or 0,
                "current_ctc": (pro_prof.current_ctc if pro_prof else None),
                "desired_salary": (pro_prof.expected_ctc if pro_prof else None),
                "notice_period_days": (pro_prof.notice_period_days if pro_prof else 30) or 30,
                "linkedin_url": (pro_prof.linkedin_url if pro_prof else "") or "",
                "portfolio_url": (pro_prof.portfolio_url if pro_prof else "") or "",
                "confidence_level": "9",
                "headline": (pro_prof.headline if pro_prof else "") or "",
                "summary": (pro_prof.summary if pro_prof else "") or "",
                "cover_letter": (pro_prof.cover_letter if pro_prof else "") or "",
            }

            # Resumes
            resumes = {"default": "PersonalData/resume.pdf", "roles": {}}
            try:
                from app.repositories.resume_repository import ResumeRepository
                r_repo = ResumeRepository(session)
                user_resumes = r_repo.get_by_user_id(user.id)
                for r in user_resumes:
                    if r.is_default:
                        resumes["default"] = r.file_path
                    resumes["roles"][r.file_name] = r.file_path
            except Exception:
                pass

            # Platforms
            platforms: Dict[str, Any] = {}
            try:
                from app.repositories.platform_repository import PlatformRepository
                p_repo = PlatformRepository(session)
                all_plats = p_repo.get_all()
                for p in all_plats:
                    plat_dict: Dict[str, Any] = {
                        "search_terms": (p.extra_settings or {}).get("search_terms", []),
                        "search_location": p.default_location or "India",
                        "experience_years": p.experience_years or 2,
                    }
                    if p.name == "linkedin":
                        plat_dict["switch_number"] = p.max_applications or 30
                        plat_dict["easy_apply_only"] = True
                    elif p.name == "naukri":
                        plat_dict["max_pages_per_search"] = (p.extra_settings or {}).get("max_pages_per_search", 3)
                        plat_dict["core_skills"] = (p.extra_settings or {}).get("core_skills", [])
                    platforms[p.name] = plat_dict
            except Exception:
                pass

            return {
                "personal": personal,
                "professional": professional,
                "resumes": resumes,
                "platforms": platforms,
                "qna": {"standard_answers": {}, "custom_qa": {}},
            }

    def import_profile_from_dict(self, user_id: int, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Imports candidate profile data directly into SQLite database for a user."""
        if not data or not isinstance(data, dict):
            return False, "Invalid profile payload. Expected JSON object."

        try:
            pers = dict(data.get("personal", {}))
            prof = dict(data.get("professional", {}))

            first_name = pers.get("first_name", "").strip()
            last_name = pers.get("last_name", "").strip()
            full_name = f"{first_name} {last_name}".strip() or "Candidate User"
            email = pers.get("email", "").strip() or f"user_{user_id}@jobpilot.local"
            phone = pers.get("phone_number", "").strip() or None

            with get_db_session(self._session_factory) as session:
                repo = UserRepository(session)
                user = repo.get_by_id(user_id)
                if not user:
                    user = repo.get_or_create_primary_user(name=full_name, email=email, phone=phone)
                user_pk = user.id

            pers["first_name"] = first_name or "Candidate"
            pers["last_name"] = last_name or "User"
            pers["email"] = email
            if "desired_salary" in prof and "expected_ctc" not in prof:
                prof["expected_ctc"] = prof["desired_salary"]

            if "title" not in prof or not prof["title"]:
                prof["title"] = "Software Engineer"

            ok, err = self.save_profile(user_id=user_pk, personal_data=pers, professional_data=prof)
            if not ok:
                return False, err

            # Sync QnA if present
            qna_sec = data.get("qna", {})
            std_ans = qna_sec.get("standard_answers", {})
            if std_ans:
                self._sync_onboarding_qna(std_ans)

            return True, None
        except Exception as exc:
            return False, f"Failed to import profile: {exc}"

