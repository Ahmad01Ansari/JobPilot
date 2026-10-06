"""Repository for Company entity operations."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Company
from app.repositories.base import BaseRepository
from app.repositories.validators import normalize_company_name


class CompanyRepository(BaseRepository):
    """Data access operations for companies."""

    def get_by_id(self, company_id: int) -> Optional[Company]:
        """Fetches a company by its internal primary key."""
        return self.session.execute(
            select(Company).where(Company.id == company_id)
        ).scalar_one_or_none()

    def get_by_normalized_name(self, normalized_name: str) -> Optional[Company]:
        """Fetches a company by its normalized name."""
        return self.session.execute(
            select(Company).where(Company.normalized_name == normalized_name)
        ).scalar_one_or_none()

    def get_or_create_by_name(
        self,
        name: str,
        location: Optional[str] = None,
        website: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> Company:
        """Finds an existing company using deterministic normalization or creates a new one."""
        norm_name = normalize_company_name(name)
        existing = self.get_by_normalized_name(norm_name)
        if existing:
            # Update location or website if previously missing
            if location and not existing.location:
                existing.location = location
            if website and not existing.website:
                existing.website = website
            if industry and not existing.industry:
                existing.industry = industry
            return existing

        company = Company(
            name=name.strip(),
            normalized_name=norm_name,
            location=location,
            website=website,
            industry=industry,
        )
        self.session.add(company)
        self.session.flush()
        return company

    def search(self, query: str, limit: int = 20) -> List[Company]:
        """Searches companies by name using wildcard match."""
        q = f"%{query.strip()}%"
        stmt = (
            select(Company)
            .where(Company.name.ilike(q) | Company.normalized_name.ilike(q))
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_all(self, limit: int = 50, offset: int = 0) -> List[Company]:
        """Lists companies with pagination."""
        stmt = select(Company).order_by(Company.name.asc())
        stmt = self.apply_pagination(stmt, limit=limit, offset=offset)
        return list(self.session.execute(stmt).scalars().all())
