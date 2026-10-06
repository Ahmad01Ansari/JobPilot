"""Job offer model."""

from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, IntIdMixin, UTCDateTime, utc_now


class Offer(Base, IntIdMixin, TimestampMixin):
    """Tracks received employment offers and details."""

    __tablename__ = "offers"

    application_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    offered_ctc: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    joining_date: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    offer_date: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="RECEIVED"
    )  # RECEIVED, ACCEPTED, DECLINED, NEGOTIATING, EXPIRED
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    application: Mapped["Application"] = relationship("Application", back_populates="offer")

    def __repr__(self) -> str:
        return f"<Offer(id={self.id}, app_id={self.application_id}, ctc={self.offered_ctc}, status='{self.status}')>"
