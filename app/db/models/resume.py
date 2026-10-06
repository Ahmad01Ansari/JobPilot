"""Resume entity model and file hash calculation."""

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntIdMixin, JsonType, TimestampMixin


def calculate_file_sha256(file_path: str) -> str:
    """Calculates the SHA-256 hash of a file for integrity verification."""
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return hashlib.sha256(str(file_path).encode("utf-8")).hexdigest()
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class Resume(Base, IntIdMixin, TimestampMixin):
    """Resume metadata record."""

    __tablename__ = "resumes"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), default="1.0")
    role_target: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Lineage, lifecycle, and cached intelligence metadata
    lineage_id: Mapped[str] = mapped_column(
        String(64),
        default=lambda: uuid.uuid4().hex,
        nullable=False,
        index=True,
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    parsed_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JsonType, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="resumes")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="resume")

    def __repr__(self) -> str:
        return f"<Resume(id={self.id}, name='{self.name}', role='{self.role_target}', v='{self.version}', default={self.is_default}, archived={self.is_archived})>"
