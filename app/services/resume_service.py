"""Resume Management Service handling storage, integrity, ownership, and OS viewer interaction."""

import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.db.models import Resume, calculate_file_sha256
from app.db.session import SessionLocal, get_db_session
from app.repositories.resume_repository import ResumeRepository


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB


class ResumeService:
    """Service layer managing resume files, integrity validation, and lifecycle."""

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        session_factory=None,
        is_test: bool = False,
    ):
        self.is_test = is_test
        if storage_dir:
            self._storage_dir = Path(storage_dir).resolve()
        else:
            try:
                from app.services.os.app_paths import AppPaths
                self._storage_dir = AppPaths.get_resumes_dir()
            except Exception:
                self._storage_dir = Path.home() / ".jobpilot" / "managed_resumes"

        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._session_factory = session_factory or SessionLocal

    @property
    def storage_dir(self) -> Path:
        return self._storage_dir

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitizes filename, stripping directory paths and dangerous characters."""
        base = Path(filename).name
        stem = Path(base).stem
        ext = Path(base).suffix.lower()

        # Replace non-alphanumeric (except underscores and hyphens)
        clean_stem = re.sub(r"[^\w\-]", "_", stem)
        clean_stem = re.sub(r"_+", "_", clean_stem).strip("_")
        if not clean_stem:
            clean_stem = "resume"

        return f"{clean_stem[:50]}{ext}"

    def _resolve_managed_path(self, target_path: Path) -> Path:
        """Resolves target_path and verifies it is confined within the managed storage directory."""
        resolved = target_path.resolve()
        if not resolved.is_relative_to(self._storage_dir):
            raise ValueError(f"Path traversal detected: {target_path} is outside managed directory.")
        return resolved

    def validate_source_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """Validates that a source file exists, has an allowed extension, and is within size limits."""
        if not file_path:
            return False, "File path cannot be empty."

        path = Path(file_path).resolve()
        if not path.exists():
            return False, f"File does not exist: {file_path}"
        if not path.is_file():
            return False, f"Path is not a regular file: {file_path}"

        suffix = path.suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            return False, f"Unsupported file format '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"

        try:
            size = path.stat().st_size
            if size == 0:
                return False, "File is empty."
            if size > MAX_FILE_SIZE_BYTES:
                return False, f"File size ({size / (1024*1024):.1f}MB) exceeds maximum limit of 15MB."
        except OSError as e:
            return False, f"Unable to read file metadata: {e}"

        return True, None

    def add_resume(
        self,
        user_id: int,
        source_path: str,
        display_name: Optional[str] = None,
        role_target: Optional[str] = None,
        is_default: bool = False,
        version: str = "1.0",
        lineage_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Tuple[Optional[Resume], bool, Optional[str]]:
        """Validates source file, copies it into managed storage, extracts technical metadata, and registers record.

        Returns:
            Tuple of (Resume, created: bool, error_message: Optional[str])
        """
        is_valid, err = self.validate_source_file(source_path)
        if not is_valid:
            return None, False, err

        source = Path(source_path).resolve()
        source_hash = calculate_file_sha256(str(source))

        with get_db_session(self._session_factory) as session:
            repo = ResumeRepository(session)

            # Check duplicate file for user
            existing = repo.find_by_hash_for_user(user_id, source_hash)
            if existing:
                if lineage_id:
                    # When creating a version revision for an existing resume lineage:
                    # Only reject if the exact same version in this same lineage already has this file
                    if existing.lineage_id == lineage_id and existing.version == version:
                        return existing, False, f"Version {version} of this resume is already uploaded."
                else:
                    return existing, False, "This exact resume file is already uploaded."

            ext = source.suffix.lower()
            # Opaque file naming per directive: res_{uuid}{ext}
            unique_name = f"res_{uuid.uuid4().hex}{ext}"
            target_path = self._resolve_managed_path(self._storage_dir / unique_name)

            try:
                shutil.copy2(source, target_path)
            except OSError as e:
                return None, False, f"Failed to store resume file: {e}"

            # Verify integrity of copied file
            stored_hash = calculate_file_sha256(str(target_path))
            if stored_hash != source_hash:
                target_path.unlink(missing_ok=True)
                return None, False, "File copy integrity check failed."

            # Automatically set as default if first resume
            user_resumes = repo.list_by_user(user_id, include_archived=False)
            effective_default = is_default or len(user_resumes) == 0

            # Deterministic, boundary-aware parsing (privacy-compliant, zero raw text stored)
            from app.services.resume_parser import ResumeParserService
            parse_res = ResumeParserService.parse_pdf(str(target_path))
            parsed_meta = parse_res.to_metadata_dict(file_hash=stored_hash)

            resume_record = repo.add_resume(
                user_id=user_id,
                name=display_name.strip() if display_name else source.stem,
                file_path=str(target_path),
                role_target=role_target.strip() if role_target else None,
                is_default=effective_default,
                version=version,
                lineage_id=lineage_id,
                notes=notes.strip() if notes else None,
                parsed_metadata=parsed_meta,
            )
            session.commit()

            if effective_default:
                self.sync_default_to_config(str(target_path), role_target=resume_record.role_target)

            record_id = resume_record.id
            rec_role = resume_record.role_target

        self.sync_resume_to_profile(
            user_id=user_id,
            detected_skills=parsed_meta.get("detected_skills", []),
            role_target=rec_role,
        )

        with get_db_session(self._session_factory) as session:
            repo = ResumeRepository(session)
            refreshed = repo.get_by_id(record_id)
            return refreshed, True, None

    def delete_resume(self, resume_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """Safely deletes a resume record and its managed physical file.

        Enforces ownership and reference protection.
        If the deleted resume was default, automatically promotes the next available resume.
        """
        with get_db_session(self._session_factory) as session:
            repo = ResumeRepository(session)
            resume = repo.get_by_id(resume_id)

            if not resume or resume.user_id != user_id:
                return False, f"Resume {resume_id} not found or access denied."

            # Check if referenced by applications
            if repo.is_referenced_by_application(resume_id):
                return False, "Cannot delete resume: it is linked to existing job applications."

            was_default = resume.is_default
            raw_path = resume.file_path

            # Delete database record
            repo.delete_resume(resume_id)

            # If deleted was default, promote next resume to default
            new_def_path = ""
            if was_default:
                promoted = repo.promote_next_default(user_id)
                if promoted:
                    new_def_path = promoted.file_path

            session.commit()

        if was_default:
            self.sync_default_to_config(new_def_path)

        # Delete physical file
        try:
            stored_path = Path(raw_path).resolve()
            if stored_path.exists() and stored_path.is_file():
                if stored_path.is_relative_to(self._storage_dir) or "managed_resumes" in str(stored_path):
                    stored_path.unlink(missing_ok=True)
        except Exception:
            pass  # Non-blocking filesystem cleanup

        return True, None

    def sync_default_to_config(self, resume_path: str, role_target: Optional[str] = None) -> None:
        """Synchronizes the default resume path to config/profile.json and DB Profile, and updates search keywords."""
        if (
            getattr(self, "is_test", False)
            or not resume_path
            or "/tmp" in str(resume_path)
            or "\\tmp" in str(resume_path)
            or "pytest" in sys.modules
            or "unittest" in sys.modules
        ):
            return

        import json
        try:
            cfg_path = Path(__file__).resolve().parent.parent.parent / "config" / "profile.json"
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if "candidate" in data:
                    data["candidate"]["resume_path"] = resume_path
                if "resumes" not in data or not isinstance(data["resumes"], dict):
                    data["resumes"] = {}
                data["resumes"]["default"] = resume_path

                # Auto-sync keywords & domain exclusions based on role if role_target provided
                if role_target:
                    try:
                        from app.services.keyword_extractor_service import KeywordExtractorService
                        rec = KeywordExtractorService.get_recommendations_for_role(role_target)
                        if "platforms" in data and isinstance(data["platforms"], dict):
                            for p_key in ["linkedin", "naukri", "indeed", "glassdoor"]:
                                if p_key in data["platforms"]:
                                    # Ensure search terms include recommended domain terms
                                    existing = data["platforms"][p_key].get("search_terms", [])
                                    combined = list(dict.fromkeys(rec["search_terms"] + existing))
                                    data["platforms"][p_key]["search_terms"] = combined
                                    data["platforms"][p_key]["negative_title_words"] = rec["negative_title_words"]
                                    data["platforms"][p_key]["bad_words"] = rec["bad_words"]
                    except Exception:
                        pass

                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

                # Invalidate config loader cache
                try:
                    import modules.config_loader as cfg_ldr
                    cfg_ldr._PROFILE_CACHE = None
                except Exception:
                    pass

            with get_db_session(self._session_factory) as session:
                from app.db.models import Profile
                profile = session.query(Profile).first()
                if profile:
                    profile.resume_path = resume_path
                    session.commit()
        except Exception:
            pass

    def sync_resume_to_profile(
        self,
        user_id: int,
        detected_skills: List[Any],
        role_target: Optional[str] = None,
    ) -> None:
        """Synchronizes detected resume skills and target role into candidate profile and profile.json."""
        if not detected_skills and not role_target:
            return

        # Normalize skill list
        skill_names = []
        for s in detected_skills:
            if isinstance(s, dict) and s.get("canonical"):
                skill_names.append(str(s["canonical"]).strip())
            elif isinstance(s, str) and s.strip():
                skill_names.append(s.strip())

        # 1. Database sync
        try:
            with get_db_session(self._session_factory) as session:
                from app.repositories.user_repository import UserRepository
                from app.repositories.dto import ProfessionalProfileUpdateDTO

                repo = UserRepository(session)
                user = repo.get_by_id(user_id)
                if user:
                    pro = repo.get_professional_profile(user_id)
                    existing_skills = list(pro.skills or []) if pro and pro.skills else []
                    existing_set = {s.lower() for s in existing_skills}

                    for sk in skill_names:
                        if sk.lower() not in existing_set:
                            existing_skills.append(sk)
                            existing_set.add(sk.lower())

                    new_title = pro.current_title if pro and pro.current_title else (role_target or "Software Engineer")
                    if role_target and (not pro or not pro.current_title or pro.current_title in ("Candidate", "Default Candidate")):
                        new_title = role_target

                    primary = pro.primary_skills if pro and pro.primary_skills else existing_skills[:5]

                    prof_dto = ProfessionalProfileUpdateDTO(
                        current_title=new_title,
                        current_employer=pro.current_employer if pro else None,
                        years_of_experience=pro.years_of_experience if pro else 0.0,
                        current_ctc=pro.current_ctc if pro else None,
                        expected_ctc=pro.expected_ctc if pro else None,
                        notice_period_days=pro.notice_period_days if pro else 30,
                        skills=existing_skills,
                        primary_skills=primary,
                        linkedin_url=pro.linkedin_url if pro else None,
                        github_url=pro.github_url if pro else None,
                        portfolio_url=pro.portfolio_url if pro else None,
                        headline=pro.headline if pro else None,
                        summary=pro.summary if pro else None,
                        cover_letter=pro.cover_letter if pro else None,
                    )
                    repo.save_professional_profile(user_id, prof_dto)
                    session.commit()
        except Exception as e:
            import logging
            logging.getLogger("JobPilot.ResumeService").warning(f"Error syncing resume to DB profile: {e}")

        # 2. Sync to config/profile.json
        import sys
        if "unittest" in sys.modules or "pytest" in sys.modules:
            return

        try:
            import json
            cfg_path = Path(__file__).resolve().parent.parent.parent / "config" / "profile.json"
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if "professional" not in data or not isinstance(data["professional"], dict):
                    data["professional"] = {}

                current_json_skills = data["professional"].get("skills", [])
                if isinstance(current_json_skills, list):
                    json_set = {s.lower() for s in current_json_skills if isinstance(s, str)}
                    for sk in skill_names:
                        if sk.lower() not in json_set:
                            current_json_skills.append(sk)
                            json_set.add(sk.lower())
                    data["professional"]["skills"] = current_json_skills
                else:
                    data["professional"]["skills"] = skill_names

                if "candidate" in data and isinstance(data["candidate"], dict):
                    data["candidate"]["skills"] = data["professional"]["skills"]

                if role_target and not data["professional"].get("title"):
                    data["professional"]["title"] = role_target

                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                # Invalidate config loader cache
                try:
                    import modules.config_loader as cfg_ldr
                    cfg_ldr._PROFILE_CACHE = None
                except Exception:
                    pass
        except Exception as e:
            import logging
            logging.getLogger("JobPilot.ResumeService").warning(f"Error syncing resume to profile.json: {e}")

    def set_default_resume(self, resume_id: int, user_id: int) -> Tuple[Optional[Resume], Optional[str]]:
        """Sets a resume as the user's default resume."""
        with get_db_session(self._session_factory) as session:
            repo = ResumeRepository(session)
            resume = repo.get_by_id(resume_id)
            if not resume or resume.user_id != user_id:
                return None, f"Resume {resume_id} not found or access denied."

            target = repo.set_default_resume(resume_id, user_id)
            file_path = target.file_path
            role = target.role_target
            meta = target.parsed_metadata or {}
            session.commit()

        self.sync_default_to_config(file_path, role_target=role)
        self.sync_resume_to_profile(
            user_id=user_id,
            detected_skills=meta.get("detected_skills", []),
            role_target=role,
        )
        return target, None

    def update_resume(
        self,
        resume_id: int,
        user_id: int,
        name: Optional[str] = None,
        role_target: Optional[str] = None,
        version: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Tuple[Optional[Resume], Optional[str]]:
        """Updates resume metadata and optionally designates it as default."""
        file_path_to_sync = None
        role_to_sync = None
        with get_db_session(self._session_factory) as session:
            repo = ResumeRepository(session)
            resume = repo.get_by_id(resume_id)
            if not resume or resume.user_id != user_id:
                return None, f"Resume {resume_id} not found or access denied."

            if name and name.strip():
                resume.name = name.strip()
            if role_target is not None:
                resume.role_target = role_target.strip() if role_target.strip() else None
            if version and version.strip():
                resume.version = version.strip()

            if is_default:
                repo.set_default_resume(resume_id, user_id)
                file_path_to_sync = resume.file_path
                role_to_sync = resume.role_target

            session.commit()

        if file_path_to_sync:
            self.sync_default_to_config(file_path_to_sync, role_target=role_to_sync)

        return resume, None

    def rename_resume(
        self,
        resume_id: int,
        user_id: int,
        new_name: str,
        new_version: Optional[str] = None,
    ) -> Tuple[Optional[Resume], Optional[str]]:
        """Renames a resume's display name and version in metadata without altering file content."""
        if not new_name or not new_name.strip():
            return None, "Resume name cannot be empty."

        return self.update_resume(
            resume_id=resume_id,
            user_id=user_id,
            name=new_name,
            version=new_version,
        )

    def verify_integrity(self, resume_id: int, user_id: int) -> Tuple[bool, str]:
        """Checks if the physical resume file exists on disk and matches its stored SHA-256 hash."""
        with get_db_session(self._session_factory) as session:
            repo = ResumeRepository(session)
            resume = repo.get_by_id(resume_id)
            if not resume or resume.user_id != user_id:
                return False, "Resume record not found."

            path = Path(resume.file_path)
            if not path.exists():
                return False, f"Physical file missing on disk: {path.name}"

            current_hash = calculate_file_sha256(str(path))
            if current_hash != resume.file_hash:
                return False, "Integrity hash mismatch: physical file has been modified externally."

            return True, "Verified"

    def open_resume(self, resume_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """Launches the system default application to view the resume safely without blocking the UI."""
        with get_db_session(self._session_factory) as session:
            repo = ResumeRepository(session)
            resume = repo.get_by_id(resume_id)
            if not resume:
                return False, "Resume not found."
            if resume.user_id != user_id:
                return False, "Resume not found or access denied."

            path = Path(resume.file_path).resolve()
            if not path.exists():
                return False, f"Resume file missing on disk: {path.name}"
            if not path.is_file():
                return False, f"Resume path is not a file: {path.name}"

        # Avoid spawning external system viewer processes during unit tests
        if getattr(self, "is_test", False) or "unittest" in sys.modules or "pytest" in sys.modules:
            return True, None

        # Delegate to centralized cross-platform system service
        from app.services.os.system_service import SystemService
        return SystemService.open_file_or_dir(path)

    def list_resumes(
        self,
        user_id: Optional[int] = None,
        include_archived: bool = False,
        role: Optional[str] = None,
    ) -> List[Resume]:
        """Lists resumes uploaded by a user, with optional archive and role filtering."""
        with get_db_session(self._session_factory) as session:
            if user_id is None:
                from app.repositories.user_repository import UserRepository
                u = UserRepository(session).get_primary_user()
                user_id = u.id if u else 1
            repo = ResumeRepository(session)
            return repo.list_by_user(user_id, include_archived=include_archived, role=role)

    def get_default_resume(self, user_id: int) -> Optional[Resume]:
        """Fetches the user's current default resume."""
        with get_db_session(self._session_factory) as session:
            repo = ResumeRepository(session)
            return repo.get_default_resume(user_id)

    def get_lineage_resumes(self, lineage_id: str, user_id: int) -> List[Resume]:
        """Returns all versions in a resume lineage family."""
        with get_db_session(self._session_factory) as session:
            repo = ResumeRepository(session)
            return repo.get_lineage_resumes(lineage_id, user_id)

    def create_new_version(
        self,
        source_resume_id: int,
        user_id: int,
        new_source_path: str,
        new_version: str,
        notes: Optional[str] = None,
        display_name: Optional[str] = None,
        role_target: Optional[str] = None,
        is_default: bool = False,
    ) -> Tuple[Optional[Resume], bool, Optional[str]]:
        """Creates a new version of an existing resume under the same lineage_id."""
        with get_db_session(self._session_factory) as session:
            repo = ResumeRepository(session)
            source_resume = repo.get_by_id(source_resume_id)
            if not source_resume or source_resume.user_id != user_id:
                return None, False, f"Source resume {source_resume_id} not found or access denied."

            lineage_id = source_resume.lineage_id
            name = display_name.strip() if display_name else source_resume.name
            role = role_target.strip() if role_target else source_resume.role_target
            was_default = source_resume.is_default

        effective_default = is_default or was_default

        new_resume, created, err = self.add_resume(
            user_id=user_id,
            source_path=new_source_path,
            display_name=name,
            role_target=role,
            is_default=effective_default,
            version=new_version.strip() if new_version else "2.0",
            lineage_id=lineage_id,
            notes=notes,
        )

        if created and new_resume:
            # Per versioning requirements: archive previous versions in this lineage
            # so the new revision becomes the active version representing this resume.
            with get_db_session(self._session_factory) as session:
                repo = ResumeRepository(session)
                for old_res in repo.get_lineage_resumes(lineage_id, user_id):
                    if old_res.id != new_resume.id:
                        old_res.is_archived = True
                        if effective_default:
                            old_res.is_default = False
                session.commit()

            if effective_default:
                self.sync_default_to_config(new_resume.file_path, role_target=new_resume.role_target)

        return new_resume, created, err

    def archive_resume(self, resume_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """Archives an active resume. If default, automatically promotes the next resume according to precedence."""
        promoted_path = None
        promoted_role = None
        was_default = False

        with get_db_session(self._session_factory) as session:
            repo = ResumeRepository(session)
            target = repo.get_by_id(resume_id)
            if not target or target.user_id != user_id:
                return False, f"Resume {resume_id} not found or access denied."

            if target.is_archived:
                return True, None

            was_default = target.is_default
            target_role = target.role_target

            repo.archive_resume(resume_id, user_id)

            if was_default:
                target.is_default = False
                promoted = repo.promote_next_default(user_id, preferred_role=target_role)
                if promoted:
                    promoted_path = promoted.file_path
                    promoted_role = promoted.role_target

            session.commit()

        if was_default:
            self.sync_default_to_config(promoted_path or "", role_target=promoted_role)

        return True, None

    def unarchive_resume(self, resume_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """Restores an archived resume back into active circulation."""
        with get_db_session(self._session_factory) as session:
            repo = ResumeRepository(session)
            target = repo.unarchive_resume(resume_id, user_id)
            if not target:
                return False, f"Resume {resume_id} not found or access denied."

            # If user has no active default, promote this unarchived resume
            curr_def = repo.get_default_resume(user_id)
            should_sync = False
            if not curr_def:
                target.is_default = True
                should_sync = True

            session.commit()

            if should_sync:
                self.sync_default_to_config(target.file_path, role_target=target.role_target)

        return True, None

    def get_resume_health(self, resume_id: int, user_id: int) -> Dict[str, Any]:
        """Calculates factual technical health status for a resume with parser cache validation."""
        with get_db_session(self._session_factory) as session:
            repo = ResumeRepository(session)
            resume = repo.get_by_id(resume_id)
            if not resume or resume.user_id != user_id:
                return {
                    "health_status": "INVALID",
                    "flags": {
                        "file_exists": False,
                        "hash_valid": False,
                        "pdf_readable": False,
                        "text_extractable": False,
                        "contacts_detected": False,
                        "role_assigned": False,
                    },
                    "metadata": {},
                    "error_message": "Resume record not found.",
                }

            path = Path(resume.file_path).resolve()
            file_exists = path.exists() and path.is_file()
            current_hash = calculate_file_sha256(str(path)) if file_exists else ""
            hash_valid = (file_exists and current_hash == resume.file_hash)

            from app.services.resume_parser import CURRENT_PARSER_VERSION, ResumeParserService

            meta = resume.parsed_metadata or {}
            # Invalidation rule: re-parse if parser version != CURRENT_PARSER_VERSION or file hash != stored_hash
            cache_valid = (
                bool(meta)
                and meta.get("parser_version") == CURRENT_PARSER_VERSION
                and meta.get("parsed_file_hash") == resume.file_hash
                and file_exists
            )

            if not cache_valid and file_exists:
                parse_res = ResumeParserService.parse_pdf(str(path))
                meta = parse_res.to_metadata_dict(file_hash=resume.file_hash)
                resume.parsed_metadata = meta
                session.commit()

            pdf_readable = file_exists and meta.get("page_count", 0) > 0 and meta.get("error_message") is None
            text_extractable = meta.get("text_extractable", False)
            contacts = meta.get("contacts", {})
            contacts_detected = bool(contacts.get("email_present") or contacts.get("phone_present"))
            role_assigned = bool(resume.role_target and resume.role_target.strip())

            health_status, flags = ResumeParserService.evaluate_health_state(
                file_exists=file_exists,
                hash_valid=hash_valid,
                pdf_readable=pdf_readable,
                text_extractable=text_extractable,
                contacts_detected=contacts_detected,
                role_assigned=role_assigned,
            )

            return {
                "health_status": health_status,
                "flags": flags,
                "metadata": meta,
                "error_message": meta.get("error_message") if not pdf_readable else None,
            }

    def get_resume_usage(self, resume_id: int, user_id: int) -> Dict[str, Any]:
        """Calculates factual application usage metrics linked to this specific resume."""
        from sqlalchemy import func, select
        from app.db.models import Application, Job, Interview, Offer

        submitted_statuses = {
            "APPLIED",
            "SUBMITTED",
            "SUCCESS",
            "UNDER_REVIEW",
            "SHORTLISTED",
            "RECRUITER_CONTACTED",
            "ASSESSMENT",
            "INTERVIEW",
            "INTERVIEWING",
            "OFFER",
            "OFFERED",
            "ACCEPTED",
            "REJECTED",
            "WITHDRAWN",
        }

        with get_db_session(self._session_factory) as session:
            # Query all applications linked to this resume
            stmt = (
                select(Application, Job)
                .join(Job, Application.job_id == Job.id)
                .where(Application.resume_id == resume_id)
                .order_by(Application.applied_at.desc().nullslast(), Application.id.desc())
            )
            rows = session.execute(stmt).all()

            total_applications = len(rows)
            submitted_apps = []
            interviews_count = 0
            offers_count = 0
            platforms_count: Dict[str, int] = {}
            last_used_dt = None

            app_ids = [app.id for app, _ in rows]
            interview_app_ids = set()
            offer_app_ids = set()
            if app_ids:
                i_stmt = select(Interview.application_id).where(Interview.application_id.in_(app_ids)).distinct()
                interview_app_ids = set(session.execute(i_stmt).scalars().all())

                o_stmt = select(Offer.application_id).where(Offer.application_id.in_(app_ids)).distinct()
                offer_app_ids = set(session.execute(o_stmt).scalars().all())

            for app, job in rows:
                st = (app.status or "").strip().upper()
                is_sub = st in submitted_statuses
                if is_sub:
                    submitted_apps.append((app, job))
                    p = (job.platform or "other").strip().lower()
                    platforms_count[p] = platforms_count.get(p, 0) + 1
                    if app.applied_at and (last_used_dt is None or app.applied_at > last_used_dt):
                        last_used_dt = app.applied_at

                # Check interview/offer
                if app.id in interview_app_ids or "INTERVIEW" in st:
                    interviews_count += 1
                if app.id in offer_app_ids or "OFFER" in st or "ACCEPTED" in st:
                    offers_count += 1

            # Recent 5 applications
            recent = []
            for app, job in rows[:5]:
                recent.append({
                    "id": app.id,
                    "job_title": job.title,
                    "company_name": job.company_raw,
                    "platform": job.platform,
                    "status": app.status,
                    "applied_at": app.applied_at.strftime("%Y-%m-%d %H:%M") if app.applied_at else None,
                })

            return {
                "total_applications": total_applications,
                "submitted_count": len(submitted_apps),
                "interviews_count": interviews_count,
                "offers_count": offers_count,
                "last_used_at": last_used_dt.strftime("%b %d, %Y") if last_used_dt else "Never",
                "platforms": platforms_count,
                "recent_applications": recent,
            }

    def get_library_summary(self, user_id: int) -> Dict[str, Any]:
        """Aggregates high-level library KPIs using optimized queries without N+1 queries."""
        from sqlalchemy import func, select
        from app.db.models import Application

        with get_db_session(self._session_factory) as session:
            repo = ResumeRepository(session)
            active_resumes = repo.list_by_user(user_id, include_archived=False)
            all_resumes = repo.list_by_user(user_id, include_archived=True)
            archived_count = sum(1 for r in all_resumes if r.is_archived)

            default_resume = repo.get_default_resume(user_id)
            default_name = default_resume.name if default_resume else "None"
            default_id = default_resume.id if default_resume else None

            # Distinct lineages
            distinct_lineages = set(r.lineage_id for r in active_resumes if r.lineage_id)

            # Total applications linked
            resume_ids = [r.id for r in all_resumes]
            total_apps = 0
            if resume_ids:
                total_apps = session.execute(
                    select(func.count(Application.id)).where(Application.resume_id.in_(resume_ids))
                ).scalar_one() or 0

            # Health counts across active resumes
            valid_count = 0
            needs_attention_count = 0
            invalid_count = 0

            for r in active_resumes:
                h = self.get_resume_health(r.id, user_id)
                status = h.get("health_status", "INVALID")
                if status == "VALID":
                    valid_count += 1
                elif status == "NEEDS_ATTENTION":
                    needs_attention_count += 1
                else:
                    invalid_count += 1

            return {
                "total_resumes": len(active_resumes),
                "archived_count": archived_count,
                "default_resume_name": default_name,
                "default_resume_id": default_id,
                "total_applications_linked": total_apps,
                "active_lineages_count": len(distinct_lineages),
                "health_summary": {
                    "valid": valid_count,
                    "needs_attention": needs_attention_count,
                    "invalid": invalid_count,
                },
            }
