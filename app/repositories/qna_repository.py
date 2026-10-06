"""Repository for Screening Q&A repository with provenance rules and atomic updates."""

import re
from typing import List, Optional
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import QnAEntry
from app.repositories.base import BaseRepository
from app.repositories.dto import QnACreateDTO


def normalize_question_text(text: str) -> str:
    """Normalizes a screening question for consistent lookup."""
    if not text:
        return ""
    cleaned = text.strip().lower()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


class QnARepository(BaseRepository):
    """Data access operations for screening questions and answers."""

    def find_answer(
        self,
        question: str,
        platform: Optional[str] = None,
    ) -> Optional[QnAEntry]:
        """Looks up an active, verified screening answer for a question.

        First attempts platform-specific match, then falls back to universal match.
        """
        normalized = normalize_question_text(question)
        if not normalized:
            return None

        # 1. Platform-specific match
        if platform:
            stmt = select(QnAEntry).where(
                QnAEntry.normalized_question == normalized,
                QnAEntry.platform == platform.strip().lower(),
                QnAEntry.is_active == True,  # noqa: E712
            ).order_by(QnAEntry.confidence.desc())
            entry = self.session.execute(stmt).scalar_one_or_none()
            if entry:
                return entry

        # 2. Universal / platform-agnostic match
        stmt = select(QnAEntry).where(
            QnAEntry.normalized_question == normalized,
            QnAEntry.platform == None,  # noqa: E711
            QnAEntry.is_active == True,  # noqa: E712
        ).order_by(QnAEntry.confidence.desc())
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert_answer(self, dto: QnACreateDTO) -> QnAEntry:
        """Creates or updates a screening Q&A entry enforcing provenance trust rules.

        Trust Rule:
            If source is 'LLM' and validation_status is not explicitly provided,
            validation_status defaults to 'NEEDS_REVIEW'.
            Profile and manual entries default to 'VERIFIED'.
        """
        normalized = normalize_question_text(dto.question_text)
        src = dto.source.strip().upper()

        if dto.validation_status:
            status = dto.validation_status.strip().upper()
        else:
            status = "NEEDS_REVIEW" if src == "LLM" else "VERIFIED"

        plat = dto.platform.strip().lower() if dto.platform else None

        # Check existing
        stmt = select(QnAEntry).where(
            QnAEntry.normalized_question == normalized,
            QnAEntry.platform == plat,
        )
        existing = self.session.execute(stmt).scalar_one_or_none()

        if existing:
            existing.question_text = dto.question_text.strip()
            existing.answer_text = dto.answer_text.strip()
            existing.answer_type = dto.answer_type
            existing.category = dto.category.strip().lower()
            existing.source = src
            existing.confidence = dto.confidence
            existing.validation_status = status
            self.session.flush()
            return existing

        entry = QnAEntry(
            question_text=dto.question_text.strip(),
            normalized_question=normalized,
            answer_text=dto.answer_text.strip(),
            answer_type=dto.answer_type,
            category=dto.category.strip().lower(),
            platform=plat,
            source=src,
            confidence=dto.confidence,
            validation_status=status,
            usage_count=0,
            is_active=True,
        )
        self.session.add(entry)
        self.session.flush()
        return entry

    def increment_usage(self, qna_id: int) -> None:
        """Atomically increments the usage counter and updates last_used_at in the database."""
        self.session.execute(
            update(QnAEntry)
            .where(QnAEntry.id == qna_id)
            .values(
                usage_count=QnAEntry.usage_count + 1,
                last_used_at=utc_now(),
            )
        )
        self.session.flush()

    def list_unreviewed(self, limit: int = 50, offset: int = 0) -> List[QnAEntry]:
        """Lists screening answers awaiting human review and verification."""
        stmt = (
            select(QnAEntry)
            .where(QnAEntry.validation_status == "NEEDS_REVIEW")
            .order_by(QnAEntry.created_at.desc())
        )
        stmt = self.apply_pagination(stmt, limit=limit, offset=offset)
        return list(self.session.execute(stmt).scalars().all())

    def approve_answer(self, qna_id: int) -> bool:
        """Approves a question answer, changing its status to VERIFIED."""
        entry = self.session.execute(
            select(QnAEntry).where(QnAEntry.id == qna_id)
        ).scalar_one_or_none()
        if not entry:
            return False
        entry.validation_status = "VERIFIED"
        self.session.flush()
        return True

    def get_by_id(self, qna_id: int) -> Optional[QnAEntry]:
        """Fetches a QnA entry by internal primary key."""
        return self.session.execute(
            select(QnAEntry).where(QnAEntry.id == qna_id)
        ).scalar_one_or_none()

    def list_entries(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        platform: Optional[str] = None,
        only_active: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> List[QnAEntry]:
        """Lists Q&A entries with optional filtering by category, search term, and platform."""
        stmt = select(QnAEntry)
        if category and category.strip().lower() not in ["all", "all categories", ""]:
            stmt = stmt.where(QnAEntry.category == category.strip().lower())
        if platform and platform.strip().lower() not in ["all", "all platforms", ""]:
            if platform.strip().lower() == "universal":
                stmt = stmt.where(QnAEntry.platform == None)  # noqa: E711
            else:
                stmt = stmt.where(QnAEntry.platform == platform.strip().lower())
        if only_active:
            stmt = stmt.where(QnAEntry.is_active == True)  # noqa: E712
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                (func.lower(QnAEntry.question_text).like(term))
                | (func.lower(QnAEntry.answer_text).like(term))
            )

        stmt = stmt.order_by(QnAEntry.category.asc(), QnAEntry.created_at.desc())
        stmt = self.apply_pagination(stmt, limit=limit, offset=offset)
        return list(self.session.execute(stmt).scalars().all())

    def delete_entry(self, qna_id: int) -> bool:
        """Deletes a screening Q&A entry."""
        entry = self.get_by_id(qna_id)
        if not entry:
            return False
        self.session.delete(entry)
        self.session.flush()
        return True

    def count_entries(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        only_active: bool = False,
    ) -> int:
        """Returns total count of Q&A entries matching filters."""
        stmt = select(func.count(QnAEntry.id))
        if category and category.strip().lower() not in ["all", "all categories", ""]:
            stmt = stmt.where(QnAEntry.category == category.strip().lower())
        if only_active:
            stmt = stmt.where(QnAEntry.is_active == True)  # noqa: E712
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                (func.lower(QnAEntry.question_text).like(term))
                | (func.lower(QnAEntry.answer_text).like(term))
            )
        return self.session.scalar(stmt) or 0
