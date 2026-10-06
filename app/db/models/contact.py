"""Recruiter and hiring contact model."""

from typing import List, Optional
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, IntIdMixin


class Contact(Base, IntIdMixin, TimestampMixin):
    """Recruiter, hiring manager, or professional contact."""

    __tablename__ = "contacts"

    company_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    designation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="contacts")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="contact")
    communications: Mapped[List["Communication"]] = relationship("Communication", back_populates="contact")
    follow_ups: Mapped[List["FollowUp"]] = relationship("FollowUp", back_populates="contact")

    def __repr__(self) -> str:
        return f"<Contact(id={self.id}, name='{self.name}', email='{self.email}')>"
