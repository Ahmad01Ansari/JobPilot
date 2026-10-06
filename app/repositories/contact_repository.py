"""Repository for Contact (recruiter and hiring personnel) operations."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Contact
from app.repositories.base import BaseRepository


class ContactRepository(BaseRepository):
    """Data access operations for contacts and recruiters."""

    def get_by_id(self, contact_id: int) -> Optional[Contact]:
        """Fetches a contact by internal primary key."""
        return self.session.execute(
            select(Contact).where(Contact.id == contact_id)
        ).scalar_one_or_none()

    def list_by_company(self, company_id: int) -> List[Contact]:
        """Lists all contacts associated with a specific company."""
        stmt = (
            select(Contact)
            .where(Contact.company_id == company_id)
            .order_by(Contact.name.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def find_by_email(self, email: str) -> Optional[Contact]:
        """Looks up a contact by email address."""
        if not email:
            return None
        return self.session.execute(
            select(Contact).where(Contact.email == email.strip().lower())
        ).scalar_one_or_none()

    def create_contact(
        self,
        name: str,
        company_id: Optional[int] = None,
        designation: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Contact:
        """Creates and flushes a new contact entity."""
        contact = Contact(
            name=name.strip(),
            company_id=company_id,
            designation=designation.strip() if designation else None,
            email=email.strip().lower() if email else None,
            phone=phone.strip() if phone else None,
            linkedin_url=linkedin_url.strip() if linkedin_url else None,
            notes=notes,
        )
        self.session.add(contact)
        self.session.flush()
        return contact
