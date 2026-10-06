"""Database lifecycle, health diagnostics, and statistics service."""

from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    Application,
    AppSetting,
    Company,
    Contact,
    FollowUp,
    Interview,
    Job,
    JobEvaluation,
    Offer,
    Platform,
    PlatformAccount,
    QnAEntry,
    Resume,
    User,
)
from app.db.session import engine as default_engine, get_db_session


def init_db(target_engine: Optional[Engine] = None) -> Tuple[bool, Optional[str]]:
    """Initializes the database schema idempotently.

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    eng = target_engine or default_engine
    try:
        Base.metadata.create_all(bind=eng)
        from app.db.session import ensure_sqlite_schema
        ensure_sqlite_schema(eng)
        return True, None
    except Exception as exc:
        return False, str(exc)


def check_connection(target_engine: Optional[Engine] = None) -> Dict[str, Any]:
    """Tests database reachability, SQLite PRAGMA configuration, and schema state.

    Returns:
        Dictionary with status, dialect, wal/fk states, and registered tables.
    """
    eng = target_engine or default_engine
    report: Dict[str, Any] = {
        "status": "unknown",
        "dialect": eng.dialect.name,
        "url": str(eng.url),
        "wal_enabled": False,
        "foreign_keys": False,
        "table_count": 0,
        "tables": [],
        "error": None,
    }

    try:
        with eng.connect() as conn:
            # Connectivity check
            conn.execute(text("SELECT 1"))

            # SQLite-specific PRAGMA verification
            if eng.dialect.name == "sqlite":
                journal_res = conn.execute(text("PRAGMA journal_mode")).scalar()
                report["wal_enabled"] = str(journal_res).lower() == "wal"

                fk_res = conn.execute(text("PRAGMA foreign_keys")).scalar()
                report["foreign_keys"] = bool(fk_res)

            # Metadata tables
            table_names = list(Base.metadata.tables.keys())
            report["table_count"] = len(table_names)
            report["tables"] = table_names
            report["status"] = "ok"

    except Exception as exc:
        report["status"] = "error"
        report["error"] = str(exc)

    return report


def get_summary_stats(session: Optional[Session] = None) -> Dict[str, Any]:
    """Retrieves high-level counts for all core entities."""

    def _query_stats(s: Session) -> Dict[str, Any]:
        app_status_counts = dict(
            s.execute(
                select(Application.status, func.count(Application.id)).group_by(Application.status)
            ).all()
        )

        return {
            "users_count": s.scalar(select(func.count(User.id))) or 0,
            "companies_count": s.scalar(select(func.count(Company.id))) or 0,
            "contacts_count": s.scalar(select(func.count(Contact.id))) or 0,
            "jobs_count": s.scalar(select(func.count(Job.id))) or 0,
            "job_evaluations_count": s.scalar(select(func.count(JobEvaluation.id))) or 0,
            "applications_count": s.scalar(select(func.count(Application.id))) or 0,
            "applications_by_status": app_status_counts,
            "interviews_count": s.scalar(select(func.count(Interview.id))) or 0,
            "follow_ups_count": s.scalar(select(func.count(FollowUp.id))) or 0,
            "offers_count": s.scalar(select(func.count(Offer.id))) or 0,
            "resumes_count": s.scalar(select(func.count(Resume.id))) or 0,
            "qna_entries_count": s.scalar(select(func.count(QnAEntry.id))) or 0,
        }

    if session:
        return _query_stats(session)
    else:
        with get_db_session() as s:
            return _query_stats(s)
