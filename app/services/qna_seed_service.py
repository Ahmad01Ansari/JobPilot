"""Screening Q&A Canonical Seed Bank & Dynamic Hydration Service.

Loads the universal screening question catalog, interpolates candidate profile
variables, matches candidate skill matrices, generates behavioral answers via LLM/rules,
and persists verified entries directly into the SQLite knowledge base.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import sessionmaker

from app.db.models import QnAEntry
from app.db.session import SessionLocal, get_db_session
from app.repositories.dto import QnACreateDTO
from app.repositories.qna_repository import QnARepository, normalize_question_text
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "canonical_qna_catalog.json"


class QnASeedService:
    """Manages universal screening questions, user-specific hydration, and auto-sync."""

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        catalog_path: Optional[Path] = None,
    ):
        self._session_factory = session_factory or SessionLocal
        self.catalog_path = catalog_path or DEFAULT_CATALOG_PATH

    def load_catalog(self) -> Dict[str, Any]:
        """Loads canonical question definitions from disk."""
        if not self.catalog_path.exists():
            logger.warning("Canonical QnA catalog not found at %s", self.catalog_path)
            return {"questions": []}
        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("Failed to load canonical QnA catalog: %s", exc)
            return {"questions": []}

    def get_candidate_context(self, user_id: int = 1) -> Dict[str, Any]:
        """Extracts candidate profile and professional data for dynamic hydration."""
        with get_db_session(self._session_factory) as session:
            repo = UserRepository(session)
            user = repo.get_by_id(user_id) or repo.get_primary_user()
            prof = repo.get_profile(user.id if user else user_id)
            pro_prof = repo.get_professional_profile(user.id if user else user_id)

            # Fallback to config_loader if DB records are sparse
            import modules.config_loader as cfg
            fallback_pers = cfg.get_personal(user_id)
            fallback_prof = cfg.get_professional(user_id)

            first_name = (prof.first_name if prof else "") or fallback_pers.get("first_name", "Candidate")
            last_name = (prof.last_name if prof else "") or fallback_pers.get("last_name", "User")
            full_name = f"{first_name} {last_name}".strip()

            title = (pro_prof.current_title if pro_prof else "") or fallback_prof.get("title", "Software Engineer")
            exp_years = float((pro_prof.years_of_experience if pro_prof else 0) or fallback_prof.get("years_of_experience", 2.0))
            cur_ctc = (pro_prof.current_ctc if pro_prof else None) or fallback_prof.get("current_ctc", 350000)
            exp_ctc = (pro_prof.expected_ctc if pro_prof else None) or fallback_prof.get("desired_salary", 550000)
            notice = (pro_prof.notice_period_days if pro_prof else 30) or fallback_prof.get("notice_period_days", 30)
            skills = (pro_prof.skills if pro_prof else []) or fallback_prof.get("skills", [])
            if isinstance(skills, str):
                skills = [s.strip() for s in re.split(r"[,;\n]", skills) if s.strip()]

            city = (prof.current_city if prof else "") or fallback_pers.get("current_city", "Delhi")
            country = (prof.country if prof else "") or fallback_pers.get("country", "India")
            reloc = (prof.willing_to_relocate if prof else True)
            if reloc is None:
                reloc = fallback_pers.get("willing_to_relocate", True)

            dob = fallback_pers.get("dob") or fallback_pers.get("date_of_birth", "15/05/2002")
            highest_degree = fallback_prof.get("highest_qualification") or fallback_prof.get("degree", "Bachelor of Technology")
            field_of_study = fallback_prof.get("field_of_study") or fallback_prof.get("major", "Computer Science & Engineering")
            college = fallback_prof.get("university") or fallback_prof.get("college", "University")
            gpa = fallback_prof.get("cgpa") or fallback_prof.get("gpa", "8.0")
            grad_year = fallback_prof.get("graduation_year") or fallback_prof.get("year_of_completion", "2025")

            return {
                "name": full_name,
                "title": title,
                "years_of_experience": exp_years,
                "current_ctc": cur_ctc,
                "expected_ctc": exp_ctc,
                "notice_period_days": notice,
                "skills": [str(s).lower() for s in skills],
                "skills_raw": skills,
                "current_city": city,
                "country": country,
                "willing_to_relocate": "Yes" if reloc else "No",
                "dob": dob,
                "highest_degree": highest_degree,
                "field_of_study": field_of_study,
                "college": college,
                "gpa": str(gpa),
                "graduation_year": str(grad_year),
            }

    def resolve_question_answer(
        self,
        q_item: Dict[str, Any],
        context: Dict[str, Any],
        ai_service: Optional[Any] = None,
    ) -> str:
        """Resolves the answer for a single canonical question based on its defined strategy."""
        strategy = q_item.get("strategy", "CONSTANT").upper()
        template = q_item.get("template", "")

        if strategy == "CONSTANT":
            return template

        if strategy == "PROFILE_VAR":
            res = template
            for k, v in context.items():
                res = res.replace(f"{{{k}}}", str(v))
            return res

        if strategy == "SKILL_MATCH":
            target = str(q_item.get("target_skill", "")).strip().lower()
            candidate_skills = context.get("skills", [])
            # Check direct or partial match
            matched = any(target in s or s in target for s in candidate_skills)
            if matched:
                exp = context.get("years_of_experience", 2.0)
                return str(int(exp)) if float(exp).is_integer() else str(exp)
            return "0"

        if strategy == "BEHAVIORAL_LLM":
            fallback = q_item.get("fallback_template", "")
            skills_summary = ", ".join(context.get("skills_raw", [])[:5]) or "modern technology workflows"
            fallback_resolved = fallback.replace("{title}", str(context.get("title", "Software Engineer")))
            fallback_resolved = fallback_resolved.replace("{years_of_experience}", str(context.get("years_of_experience", 2)))
            fallback_resolved = fallback_resolved.replace("{skills_summary}", skills_summary)

            if ai_service and hasattr(ai_service, "generate"):
                try:
                    prompt = (
                        f"{q_item.get('llm_prompt', '')}\n\n"
                        f"Candidate Context:\n"
                        f"- Title: {context.get('title')}\n"
                        f"- Experience: {context.get('years_of_experience')} years\n"
                        f"- Core Skills: {skills_summary}\n\n"
                        f"Provide a natural, direct answer without conversational filler."
                    )
                    ans = ai_service.generate(prompt)
                    if ans and len(ans.strip()) > 15:
                        return ans.strip()
                except Exception as exc:
                    logger.debug("AI behavioral generation fallback triggered: %s", exc)

            return fallback_resolved

        return template or "Yes"

    def seed_for_user(
        self,
        user_id: int = 1,
        ai_service: Optional[Any] = None,
        force: bool = False,
    ) -> Tuple[int, int]:
        """Hydrates all canonical questions for the target user into SQLite QnAEntry records.

        Returns:
            Tuple of (created_count, updated_count).
        """
        catalog = self.load_catalog()
        questions = catalog.get("questions", [])
        if not questions:
            return 0, 0

        context = self.get_candidate_context(user_id)
        created = 0
        updated = 0

        with get_db_session(self._session_factory) as session:
            repo = QnARepository(session)

            for q_def in questions:
                q_text = q_def.get("question_text", "").strip()
                ans = self.resolve_question_answer(q_def, context, ai_service=ai_service)
                cat = q_def.get("category", "general")
                a_type = q_def.get("answer_type", "text")

                # Upsert primary question prompt
                dto = QnACreateDTO(
                    question_text=q_text,
                    answer_text=ans,
                    category=cat,
                    answer_type=a_type,
                    platform=None,
                    source="CANONICAL",
                    confidence=1.0,
                    validation_status="VERIFIED",
                )
                entry = repo.upsert_answer(dto)
                if entry:
                    created += 1

                # Also seed normalized variations so pattern matching is 100% instant
                patterns = q_def.get("normalized_patterns", [])
                for pat in patterns:
                    norm = normalize_question_text(pat)
                    existing = session.query(QnAEntry).filter_by(normalized_question=norm).first()
                    if not existing:
                        var_dto = QnACreateDTO(
                            question_text=pat,
                            answer_text=ans,
                            category=cat,
                            answer_type=a_type,
                            platform=None,
                            source="CANONICAL",
                            confidence=1.0,
                            validation_status="VERIFIED",
                        )
                        repo.upsert_answer(var_dto)
                        created += 1
                    elif force:
                        existing.answer_text = ans
                        existing.source = "CANONICAL"
                        existing.validation_status = "VERIFIED"
                        updated += 1

            session.commit()

        logger.info(
            "Seeded canonical QnA catalog for user %s: %d created, %d updated.",
            user_id,
            created,
            updated,
        )
        return created, updated

    def resync_user_profile_answers(self, user_id: int = 1) -> int:
        """Re-evaluates and updates all PROFILE_VAR answers in the database when user changes profile."""
        catalog = self.load_catalog()
        questions = catalog.get("questions", [])
        var_questions = [q for q in questions if q.get("strategy", "").upper() == "PROFILE_VAR"]

        if not var_questions:
            return 0

        context = self.get_candidate_context(user_id)
        updated = 0

        with get_db_session(self._session_factory) as session:
            for q_def in var_questions:
                new_ans = self.resolve_question_answer(q_def, context)
                patterns = [q_def.get("question_text", "")] + q_def.get("normalized_patterns", [])

                for pat in patterns:
                    if not pat:
                        continue
                    norm = normalize_question_text(pat)
                    entries = session.query(QnAEntry).filter_by(normalized_question=norm).all()
                    for entry in entries:
                        if entry.answer_text != new_ans:
                            entry.answer_text = new_ans
                            updated += 1

            session.commit()

        logger.info("Resynced %d profile-dependent QnA entries for user %s.", updated, user_id)
        return updated

    def export_catalog(self) -> Dict[str, Any]:
        """Exports the active canonical catalog definition."""
        return self.load_catalog()

    def import_catalog(self, catalog_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Imports an updated canonical question catalog definition to disk."""
        if not catalog_data or not isinstance(catalog_data, dict):
            return False, "Invalid catalog payload. Expected JSON object."
        if "questions" not in catalog_data or not isinstance(catalog_data["questions"], list):
            return False, "Catalog payload must contain a 'questions' list."

        try:
            with open(self.catalog_path, "w", encoding="utf-8") as f:
                json.dump(catalog_data, f, indent=2, ensure_ascii=False)
            return True, None
        except Exception as exc:
            return False, f"Failed to save catalog: {exc}"
