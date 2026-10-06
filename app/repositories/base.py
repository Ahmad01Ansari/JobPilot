"""Lightweight BaseRepository holding session context and query helpers."""

from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select


class BaseRepository:
    """Base repository providing injected session handling and common pagination."""

    def __init__(self, session: Session):
        self.session = session

    def apply_pagination(
        self,
        query: Select,
        limit: Optional[int] = 50,
        offset: Optional[int] = 0,
    ) -> Select:
        """Applies limit and offset to a SQLAlchemy Select statement."""
        if offset is not None and offset > 0:
            query = query.offset(offset)
        if limit is not None and limit > 0:
            query = query.limit(limit)
        return query

    def flush(self) -> None:
        """Flushes pending changes to the database within the current transaction."""
        self.session.flush()
