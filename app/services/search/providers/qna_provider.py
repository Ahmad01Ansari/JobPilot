"""Thin SearchProvider adapter for Q&A Knowledge Base entries."""

from typing import List
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.qna import QnAEntry
from app.services.search.ranking import calculate_relevance_score
from app.services.search.search_provider import SearchProvider
from app.services.search.search_result import SearchResult


class QnASearchProvider(SearchProvider):
    """Searches Screening Q&A entries, safely truncating answer previews to protect privacy."""

    @property
    def category_key(self) -> str:
        return "qna"

    @property
    def display_name(self) -> str:
        return "Q&A Knowledge"

    @property
    def default_route(self) -> str:
        return "profile"  # Q&A knowledge base is in Profile/Knowledge view

    def search(
        self,
        session: Session,
        tokens: List[str],
        raw_query: str,
        limit: int = 5,
    ) -> List[SearchResult]:
        if not tokens and not raw_query:
            return []

        exact_id = None
        clean_q = raw_query.strip().casefold()
        if clean_q.isdigit():
            exact_id = int(clean_q)
        elif clean_q.startswith("qna-") and clean_q[4:].isdigit():
            exact_id = int(clean_q[4:])

        stmt = select(QnAEntry).where(QnAEntry.is_active == True)
        if exact_id is not None:
            stmt = stmt.where(QnAEntry.id == exact_id)
        else:
            filters = []
            for token in tokens:
                pattern = f"%{token}%"
                filters.append(
                    or_(
                        QnAEntry.question_text.ilike(pattern),
                        QnAEntry.category.ilike(pattern),
                        QnAEntry.answer_text.ilike(pattern),
                    )
                )
            if filters:
                stmt = stmt.where(*filters)

        stmt = stmt.order_by(QnAEntry.id.desc()).limit(limit * 3)
        records = session.execute(stmt).scalars().all()

        results: List[SearchResult] = []
        for qna in records:
            cat_name = (qna.category or "General").replace("_", " ").title()

            score, matched_fields = calculate_relevance_score(
                raw_query=raw_query,
                tokens=tokens,
                entity_id=qna.id,
                primary_text=qna.question_text or "",
                secondary_text=cat_name,
                tertiary_text=qna.platform or "",
                long_text=qna.answer_text or "",
                prefix_tags=["QNA"],
            )

            if score > 0 or exact_id == qna.id:
                # Safe, privacy-preserving preview (max 60 chars)
                ans_preview = (qna.answer_text or "").strip()
                if len(ans_preview) > 60:
                    ans_preview = ans_preview[:57] + "..."
                sub = f"Category: {cat_name} • Preview: {ans_preview}" if ans_preview else f"Category: {cat_name}"

                results.append(
                    SearchResult(
                        entity_type="qna",
                        entity_id=qna.id,
                        category=self.display_name,
                        title=qna.question_text,
                        subtitle=sub,
                        route=self.default_route,
                        action="focus",
                        score=score,
                        matched_fields=matched_fields,
                        badge_text=qna.validation_status or "VERIFIED",
                        badge_variant="success" if qna.validation_status == "VERIFIED" else "warning",
                        metadata={"category": qna.category, "platform": qna.platform},
                    )
                )

        results.sort(key=lambda r: (r.score, r.entity_id), reverse=True)
        return results[:limit]
