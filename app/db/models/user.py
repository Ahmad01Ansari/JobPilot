"""User, Candidate Personal Profile, and Professional Profile models."""

from typing import Any, Dict, List, Optional
from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, IntIdMixin, JsonType


class User(Base, IntIdMixin, TimestampMixin):
    """Primary user entity for JobPilot."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    profile: Mapped[Optional["Profile"]] = relationship(
        "Profile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    professional_profile: Mapped[Optional["ProfessionalProfile"]] = relationship(
        "ProfessionalProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    resumes: Mapped[List["Resume"]] = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', name='{self.name}')>"


class Profile(Base, TimestampMixin):
    """Candidate personal details (sensitive demographic fields omitted)."""

    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    current_city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)
    zipcode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preferred_locations: Mapped[Optional[List[str]]] = mapped_column(JsonType, nullable=True)
    willing_to_relocate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="profile")

    def __repr__(self) -> str:
        return f"<Profile(user_id={self.user_id}, name='{self.first_name} {self.last_name}')>"


class ProfessionalProfile(Base, TimestampMixin):
    """Candidate career, compensation, and technical background details."""

    __tablename__ = "professional_profiles"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    current_title: Mapped[str] = mapped_column(String(255), nullable=False)
    current_employer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    years_of_experience: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_ctc: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    expected_ctc: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    notice_period_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    skills: Mapped[Optional[List[str]]] = mapped_column(JsonType, nullable=True)
    primary_skills: Mapped[Optional[List[str]]] = mapped_column(JsonType, nullable=True)
    secondary_skills: Mapped[Optional[List[str]]] = mapped_column(JsonType, nullable=True)

    linkedin_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    portfolio_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    headline: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_letter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="professional_profile")

    def __repr__(self) -> str:
        return f"<ProfessionalProfile(user_id={self.user_id}, title='{self.current_title}')>"
