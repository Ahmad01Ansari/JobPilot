"""Thin SearchProvider adapter for Candidate Resumes."""

from typing import List
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.resume import Resume
from app.services.search.ranking import calculate_relevance_score
from app.services.search.search_provider import SearchProvider
from app.services.search.search_result import SearchResult


class ResumeSearchProvider(SearchProvider):
    """Searches Candidate Resumes using fast database metadata."""

    @property
    def category_key(self) -> str:
        return "resumes"

    @property
    def display_name(self) -> str:
        return "Resumes"

    @property
    def default_route(self) -> str:
        return "resumes"

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
        elif clean_q.startswith("res-") and clean_q[4:].isdigit():
            exact_id = int(clean_q[4:])

        stmt = select(Resume)
        if exact_id is not None:
            stmt = stmt.where(Resume.id == exact_id)
        else:
            filters = []
            for token in tokens:
                pattern = f"%{token}%"
                filters.append(
                    or_(
                        Resume.name.ilike(pattern),
                        Resume.role_target.ilike(pattern),
                        Resume.version.ilike(pattern),
                    )
                )
            if filters:
                stmt = stmt.where(*filters)

        stmt = stmt.order_by(Resume.id.desc()).limit(limit * 3)
        records = session.execute(stmt).scalars().all()

        results: List[SearchResult] = []
        for resume in records:
            role = resume.role_target or "General Purpose"
            score, matched_fields = calculate_relevance_score(
                raw_query=raw_query,
                tokens=tokens,
                entity_id=resume.id,
                primary_text=resume.name or "",
                secondary_text=role,
                tertiary_text=resume.version or "",
                long_text="",
                prefix_tags=["RES", "RESUME"],
            )

            if score > 0 or exact_id == resume.id:
                badge = "Default" if resume.is_default else f"v{resume.version}"
                results.append(
                    SearchResult(
                        entity_type="resume",
                        entity_id=resume.id,
                        category=self.display_name,
                        title=resume.name,
                        subtitle=f"Target: {role} • Version: {resume.version}",
                        route=self.default_route,
                        action="open",
                        score=score,
                        matched_fields=matched_fields,
                        badge_text=badge,
                        badge_variant="success" if resume.is_default else "neutral",
                        metadata={"file_path": resume.file_path, "is_default": resume.is_default},
                    )
                )

        results.sort(key=lambda r: (r.score, r.entity_id), reverse=True)
        return results[:limit]
