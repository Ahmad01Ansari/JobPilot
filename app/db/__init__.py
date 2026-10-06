"""JobPilot Database Layer Package."""

from app.db.base import Base
from app.db.config import DatabaseConfig, get_db_path, get_db_url
from app.db.models import (
    Application,
    ApplicationStatusHistory,
    AppSetting,
    Company,
    Contact,
    Communication,
    FollowUp,
    Interview,
    Job,
    JobEvaluation,
    Offer,
    Platform,
    PlatformAccount,
    Profile,
    ProfessionalProfile,
    QnAEntry,
    Resume,
    User,
    generate_job_fingerprint,
    calculate_file_sha256,
)
from app.db.service import check_connection, get_summary_stats, init_db
from app.db.session import SessionLocal, create_db_engine, engine, get_db_session

__all__ = [
    "Base",
    "DatabaseConfig",
    "get_db_path",
    "get_db_url",
    "engine",
    "create_db_engine",
    "SessionLocal",
    "get_db_session",
    "init_db",
    "check_connection",
    "get_summary_stats",
    # Models
    "Company",
    "Contact",
    "Job",
    "generate_job_fingerprint",
    "JobEvaluation",
    "Application",
    "ApplicationStatusHistory",
    "Communication",
    "Interview",
    "FollowUp",
    "Offer",
    "User",
    "Profile",
    "ProfessionalProfile",
    "Resume",
    "calculate_file_sha256",
    "Platform",
    "PlatformAccount",
    "QnAEntry",
    "AppSetting",
]
