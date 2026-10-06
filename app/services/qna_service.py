"""Screening Q&A Knowledge Base Service.

Encapsulates business logic, search filtering, provenance tagging,
and real-time question matching diagnostics for candidate screening Q&A.
"""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import QnAEntry
from app.db.session import SessionLocal, get_db_session
from app.repositories.dto import QnACreateDTO
from app.repositories.qna_repository import QnARepository, normalize_question_text


class QnAService:
    """Service layer for Screening Q&A management, testing, and lifecycle operations."""

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal

    def list_entries(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        platform: Optional[str] = None,
        only_active: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> List[QnAEntry]:
        """Lists Q&A entries with optional filtering by category, search text, or platform."""
        with get_db_session(self._session_factory) as session:
            repo = QnARepository(session)
            return repo.list_entries(
                category=category,
                search=search,
                platform=platform,
                only_active=only_active,
                limit=limit,
                offset=offset,
            )

    def add_entry(
        self,
        question: str,
        answer: str,
        category: str = "general",
        answer_type: str = "text",
        platform: Optional[str] = None,
        source: str = "MANUAL",
        confidence: float = 1.0,
    ) -> Tuple[Optional[QnAEntry], Optional[str]]:
        """Adds or updates a screening question-answer entry."""
        q_text = str(question or "").strip()
        a_text = str(answer or "").strip()

        if not q_text:
            return None, "Question prompt cannot be empty."
        if not a_text:
            return None, "Answer value cannot be empty."

        plat = platform.strip().lower() if platform and platform.strip().lower() not in ["all", "universal", ""] else None

        dto = QnACreateDTO(
            question_text=q_text,
            answer_text=a_text,
            category=category.strip().lower() if category else "general",
            answer_type=answer_type.strip().lower() if answer_type else "text",
            platform=plat,
            source=source.strip().upper() if source else "MANUAL",
            confidence=confidence,
            validation_status="VERIFIED",
        )

        try:
            with get_db_session(self._session_factory) as session:
                repo = QnARepository(session)
                entry = repo.upsert_answer(dto)
                session.commit()
                return entry, None
        except Exception as e:
            return None, f"Database error creating QnA entry: {e}"

    def update_entry(
        self,
        entry_id: int,
        question: Optional[str] = None,
        answer: Optional[str] = None,
        category: Optional[str] = None,
        answer_type: Optional[str] = None,
        platform: Optional[str] = None,
        is_active: Optional[bool] = None,
        validation_status: Optional[str] = None,
    ) -> Tuple[Optional[QnAEntry], Optional[str]]:
        """Updates specific fields on an existing QnA entry."""
        try:
            with get_db_session(self._session_factory) as session:
                repo = QnARepository(session)
                entry = repo.get_by_id(entry_id)
                if not entry:
                    return None, f"Q&A Entry {entry_id} not found."

                if question is not None:
                    q_clean = question.strip()
                    if not q_clean:
                        return None, "Question text cannot be empty."
                    entry.question_text = q_clean
                    entry.normalized_question = normalize_question_text(q_clean)

                if answer is not None:
                    a_clean = answer.strip()
                    if not a_clean:
                        return None, "Answer text cannot be empty."
                    entry.answer_text = a_clean

                if category is not None:
                    entry.category = category.strip().lower()

                if answer_type is not None:
                    entry.answer_type = answer_type.strip().lower()

                if platform is not None:
                    plat = platform.strip().lower()
                    entry.platform = None if plat in ["all", "universal", ""] else plat

                if is_active is not None:
                    entry.is_active = bool(is_active)

                if validation_status is not None:
                    entry.validation_status = validation_status.strip().upper()

                session.commit()
                return entry, None
        except Exception as e:
            return None, f"Database error updating QnA entry: {e}"

    def delete_entry(self, entry_id: int) -> Tuple[bool, Optional[str]]:
        """Deletes an entry by ID."""
        try:
            with get_db_session(self._session_factory) as session:
                repo = QnARepository(session)
                success = repo.delete_entry(entry_id)
                if not success:
                    return False, f"Entry {entry_id} not found."
                session.commit()
                return True, None
        except Exception as e:
            return False, f"Error deleting QnA entry: {e}"

    def toggle_active(self, entry_id: int) -> Tuple[bool, Optional[str]]:
        """Toggles the is_active status of a QnA entry."""
        try:
            with get_db_session(self._session_factory) as session:
                repo = QnARepository(session)
                entry = repo.get_by_id(entry_id)
                if not entry:
                    return False, f"Entry {entry_id} not found."
                entry.is_active = not entry.is_active
                new_state = entry.is_active
                session.commit()
                return new_state, None
        except Exception as e:
            return False, f"Error toggling QnA entry: {e}"

    def test_question_match(
        self, test_question: str, platform: Optional[str] = None
    ) -> Dict[str, Any]:
        """Simulates question matching to verify what answer JobPilot will submit."""
        q_clean = str(test_question or "").strip()
        if not q_clean:
            return {
                "matched": False,
                "message": "Please provide a question to test.",
            }

        plat = platform.strip().lower() if platform and platform.strip().lower() not in ["all", "universal", ""] else None

        with get_db_session(self._session_factory) as session:
            repo = QnARepository(session)
            entry = repo.find_answer(q_clean, platform=plat)

            if not entry:
                return {
                    "matched": False,
                    "normalized_query": normalize_question_text(q_clean),
                    "message": "No matching knowledge base entry found. The bot would fall back to candidate profile or local LLM.",
                }

            return {
                "matched": True,
                "entry_id": entry.id,
                "question": entry.question_text,
                "answer": entry.answer_text,
                "category": entry.category,
                "answer_type": entry.answer_type,
                "source": entry.source,
                "confidence": entry.confidence,
                "validation_status": entry.validation_status,
                "platform": entry.platform or "Universal",
                "usage_count": entry.usage_count,
            }

    def get_stats(self) -> Dict[str, Any]:
        """Retrieves summary metrics for the Q&A knowledge base."""
        with get_db_session(self._session_factory) as session:
            total = session.scalar(select(func.count(QnAEntry.id))) or 0
            active = session.scalar(
                select(func.count(QnAEntry.id)).where(QnAEntry.is_active == True)  # noqa: E712
            ) or 0
            verified = session.scalar(
                select(func.count(QnAEntry.id)).where(QnAEntry.validation_status == "VERIFIED")
            ) or 0
            unreviewed = session.scalar(
                select(func.count(QnAEntry.id)).where(QnAEntry.validation_status == "NEEDS_REVIEW")
            ) or 0

            # Category counts
            cat_rows = session.execute(
                select(QnAEntry.category, func.count(QnAEntry.id)).group_by(QnAEntry.category)
            ).all()
            category_counts = {cat: count for cat, count in cat_rows}

            return {
                "total_entries": total,
                "total_pairs": total,
                "active_entries": active,
                "verified_entries": verified,
                "unreviewed_entries": unreviewed,
                "categories": category_counts,
            }

    def seed_canonical_bank(
        self,
        user_id: int = 1,
        ai_service: Optional[Any] = None,
        force: bool = False,
    ) -> Tuple[int, int]:
        """Seeds or updates the QnA knowledge base using the canonical question catalog."""
        from app.services.qna_seed_service import QnASeedService
        seeder = QnASeedService(session_factory=self._session_factory)
        return seeder.seed_for_user(user_id=user_id, ai_service=ai_service, force=force)

    def resync_profile_answers(self, user_id: int = 1) -> int:
        """Refreshes all profile-dependent answers (CTC, notice period, location) for a candidate."""
        from app.services.qna_seed_service import QnASeedService
        seeder = QnASeedService(session_factory=self._session_factory)
        return seeder.resync_user_profile_answers(user_id=user_id)

    def export_qna_to_dict(self) -> Dict[str, Any]:
        """Exports all active QnA entries into a portable dictionary."""
        with get_db_session(self._session_factory) as session:
            repo = QnARepository(session)
            entries = repo.list_entries(limit=2000)
            items = []
            for e in entries:
                items.append({
                    "id": e.id,
                    "question": e.question_text,
                    "normalized_question": e.normalized_question,
                    "answer": e.answer_text,
                    "type": e.answer_type,
                    "category": e.category,
                    "platform": e.platform,
                    "source": e.source,
                    "confidence": e.confidence,
                    "validation_status": e.validation_status,
                    "is_active": e.is_active,
                })
            return {"count": len(items), "entries": items}

    def import_qna_from_dict(self, data: Dict[str, Any]) -> Tuple[int, int]:
        """Imports QnA entries from a dictionary into SQLite. Returns (created_count, updated_count)."""
        entries = data.get("entries", []) if isinstance(data, dict) else []
        created = 0
        updated = 0
        for item in entries:
            q = item.get("question")
            a = item.get("answer")
            if not q or not a:
                continue
            entry, err = self.add_entry(
                question=q,
                answer=a,
                category=item.get("category", "general"),
                answer_type=item.get("type", "text"),
                platform=item.get("platform"),
                source=item.get("source", "IMPORT"),
                confidence=float(item.get("confidence", 1.0)),
            )
            if entry:
                created += 1
        return created, updated

    def export_canonical_catalog(self) -> Dict[str, Any]:
        """Exports the active canonical catalog definition."""
        from app.services.qna_seed_service import QnASeedService
        return QnASeedService().export_catalog()

    def import_canonical_catalog(self, catalog_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Imports updated canonical question catalog definition to disk."""
        from app.services.qna_seed_service import QnASeedService
        return QnASeedService().import_catalog(catalog_data)

