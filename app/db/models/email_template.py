"""Email template entity model for Outreach Center."""

from typing import Optional
from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntIdMixin, TimestampMixin


class EmailTemplate(Base, IntIdMixin, TimestampMixin):
    """Reusable email template supporting category, variables, and versioning."""

    __tablename__ = "email_templates"

    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(
        String(64), nullable=False, default="JOB_APPLICATION"
    )  # JOB_APPLICATION, FOLLOW_UP, RECRUITER_REPLY, INTERVIEW_CONFIRMATION, THANK_YOU, OTHER
    subject_template: Mapped[str] = mapped_column(String(512), nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    variables_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<EmailTemplate(id={self.id}, key='{self.key}', category='{self.category}')>"
