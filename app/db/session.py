"""SQLAlchemy engine, connection events (WAL mode, foreign keys), and session management."""

import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.config import get_db_url


def configure_sqlite_pragmas(dbapi_connection, connection_record):
    """Sets SQLite PRAGMAs for performance, data integrity, and concurrency."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA busy_timeout = 30000;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.close()


def ensure_sqlite_schema(eng: Engine) -> None:
    """Ensures newly added columns exist in existing SQLite databases."""
    if eng.dialect.name != "sqlite":
        return
    try:
        from sqlalchemy import text
        with eng.connect() as conn:
            tables = [r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
            if "platform_accounts" in tables:
                res = conn.execute(text("PRAGMA table_info(platform_accounts)")).fetchall()
                cols = [r[1] for r in res]
                if "daily_application_goal" not in cols:
                    conn.execute(text("ALTER TABLE platform_accounts ADD COLUMN daily_application_goal INTEGER NOT NULL DEFAULT 50"))
                    conn.commit()
            if "jobs" in tables:
                res = conn.execute(text("PRAGMA table_info(jobs)")).fetchall()
                cols = [r[1] for r in res]
                if "application_method" not in cols:
                    conn.execute(text("ALTER TABLE jobs ADD COLUMN application_method VARCHAR(50) DEFAULT 'EASY_APPLY'"))
                    conn.execute(text("UPDATE jobs SET application_method = CASE WHEN apply_type = 'EXTERNAL' THEN 'COMPANY_PORTAL' ELSE 'EASY_APPLY' END WHERE application_method IS NULL"))
                    conn.commit()
                if "application_url" not in cols:
                    conn.execute(text("ALTER TABLE jobs ADD COLUMN application_url VARCHAR(1024)"))
                    conn.commit()
            if "applications" in tables:
                res = conn.execute(text("PRAGMA table_info(applications)")).fetchall()
                cols = [r[1] for r in res]
                if "automation_status" not in cols:
                    conn.execute(text("ALTER TABLE applications ADD COLUMN automation_status VARCHAR(50) DEFAULT 'NOT_STARTED'"))
                    conn.execute(text("UPDATE applications SET automation_status = CASE WHEN status = 'SUBMITTED' THEN 'SUCCESS' WHEN status = 'APPLYING' THEN 'RUNNING' WHEN status IN ('FAILED', 'UNKNOWN', 'MANUAL_REQUIRED') THEN status ELSE 'NOT_STARTED' END WHERE automation_status IS NULL"))
                    conn.commit()
                if "is_unread" not in cols:
                    conn.execute(text("ALTER TABLE applications ADD COLUMN is_unread BOOLEAN DEFAULT 0"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_applications_is_unread ON applications (is_unread)"))
                    conn.commit()
                if "is_priority" not in cols:
                    conn.execute(text("ALTER TABLE applications ADD COLUMN is_priority BOOLEAN DEFAULT 0"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_applications_is_priority ON applications (is_priority)"))
                    conn.commit()
            if "resumes" in tables:
                res = conn.execute(text("PRAGMA table_info(resumes)")).fetchall()
                cols = [r[1] for r in res]
                if "lineage_id" not in cols:
                    conn.execute(text("ALTER TABLE resumes ADD COLUMN lineage_id VARCHAR(64)"))
                    conn.execute(text("UPDATE resumes SET lineage_id = 'lin_' || hex(randomblob(16)) WHERE lineage_id IS NULL"))
                    conn.commit()
                if "is_archived" not in cols:
                    conn.execute(text("ALTER TABLE resumes ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT 0"))
                    conn.commit()
                if "notes" not in cols:
                    conn.execute(text("ALTER TABLE resumes ADD COLUMN notes VARCHAR(512)"))
                    conn.commit()
                if "parsed_metadata" not in cols:
                    conn.execute(text("ALTER TABLE resumes ADD COLUMN parsed_metadata TEXT"))
                    conn.commit()

            # Outreach Center: Email Templates Table
            if "email_templates" not in tables:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS email_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key VARCHAR(64) UNIQUE NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        category VARCHAR(64) NOT NULL DEFAULT 'JOB_APPLICATION',
                        subject_template VARCHAR(512) NOT NULL,
                        body_template TEXT NOT NULL,
                        variables_json TEXT,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_email_templates_key ON email_templates (key)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_email_templates_category ON email_templates (category)"))
                conn.commit()

            # Outreach Center: Sync Checkpoints Table
            if "email_sync_checkpoints" not in tables:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS email_sync_checkpoints (
                        account_id VARCHAR(64) PRIMARY KEY,
                        last_sync_at DATETIME,
                        last_history_id VARCHAR(255),
                        cursor_token VARCHAR(512)
                    )
                """))
                conn.commit()

            # Outreach Center: Communications Table Columns
            if "communications" in tables:
                res = conn.execute(text("PRAGMA table_info(communications)")).fetchall()
                cols = [r[1] for r in res]
                if "status" not in cols:
                    conn.execute(text("ALTER TABLE communications ADD COLUMN status VARCHAR(50) DEFAULT 'SENT'"))
                if "account_id" not in cols:
                    conn.execute(text("ALTER TABLE communications ADD COLUMN account_id VARCHAR(64) DEFAULT 'default'"))
                if "send_token" not in cols:
                    conn.execute(text("ALTER TABLE communications ADD COLUMN send_token VARCHAR(64)"))
                if "provider_message_id" not in cols:
                    conn.execute(text("ALTER TABLE communications ADD COLUMN provider_message_id VARCHAR(255)"))
                if "provider_thread_id" not in cols:
                    conn.execute(text("ALTER TABLE communications ADD COLUMN provider_thread_id VARCHAR(255)"))
                if "sender_email" not in cols:
                    conn.execute(text("ALTER TABLE communications ADD COLUMN sender_email VARCHAR(255)"))
                if "recipient_email" not in cols:
                    conn.execute(text("ALTER TABLE communications ADD COLUMN recipient_email VARCHAR(255)"))
                if "template_id" not in cols:
                    conn.execute(text("ALTER TABLE communications ADD COLUMN template_id INTEGER"))
                if "template_version" not in cols:
                    conn.execute(text("ALTER TABLE communications ADD COLUMN template_version VARCHAR(32)"))
                if "attachment_snapshot_path" not in cols:
                    conn.execute(text("ALTER TABLE communications ADD COLUMN attachment_snapshot_path VARCHAR(1024)"))
                if "body_snippet" not in cols:
                    conn.execute(text("ALTER TABLE communications ADD COLUMN body_snippet VARCHAR(512)"))
                if "error_message" not in cols:
                    conn.execute(text("ALTER TABLE communications ADD COLUMN error_message VARCHAR(512)"))
                if "ai_classification" not in cols:
                    conn.execute(text("ALTER TABLE communications ADD COLUMN ai_classification VARCHAR(50)"))

                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_comm_provider_msg_id ON communications (provider_message_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_comm_provider_thread_id ON communications (provider_thread_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_comm_send_token ON communications (send_token)"))
                conn.commit()

            # Outreach Center: Follow-ups Table Columns
            if "follow_ups" in tables:
                res = conn.execute(text("PRAGMA table_info(follow_ups)")).fetchall()
                cols = [r[1] for r in res]
                if "sequence_id" not in cols:
                    conn.execute(text("ALTER TABLE follow_ups ADD COLUMN sequence_id VARCHAR(64)"))
                if "step_number" not in cols:
                    conn.execute(text("ALTER TABLE follow_ups ADD COLUMN step_number INTEGER NOT NULL DEFAULT 1"))
                if "paused_reason" not in cols:
                    conn.execute(text("ALTER TABLE follow_ups ADD COLUMN paused_reason VARCHAR(255)"))

                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_follow_ups_seq_id ON follow_ups (sequence_id)"))
                conn.commit()

            # Job Qualification Engine: Job Evaluations Table Columns
            if "job_evaluations" in tables:
                res = conn.execute(text("PRAGMA table_info(job_evaluations)")).fetchall()
                cols = [r[1] for r in res]
                if "score" not in cols:
                    conn.execute(text("ALTER TABLE job_evaluations ADD COLUMN score INTEGER NOT NULL DEFAULT 0"))
                if "decision" not in cols:
                    conn.execute(text("ALTER TABLE job_evaluations ADD COLUMN decision VARCHAR(50) NOT NULL DEFAULT 'REVIEW_REQUIRED'"))
                if "confidence" not in cols:
                    conn.execute(text("ALTER TABLE job_evaluations ADD COLUMN confidence FLOAT"))
                if "evaluation_status" not in cols:
                    conn.execute(text("ALTER TABLE job_evaluations ADD COLUMN evaluation_status VARCHAR(50) NOT NULL DEFAULT 'SUCCESS'"))
                if "ai_status" not in cols:
                    conn.execute(text("ALTER TABLE job_evaluations ADD COLUMN ai_status VARCHAR(50) NOT NULL DEFAULT 'NOT_REQUESTED'"))
                if "matched_skills" not in cols:
                    conn.execute(text("ALTER TABLE job_evaluations ADD COLUMN matched_skills TEXT"))
                if "missing_skills" not in cols:
                    conn.execute(text("ALTER TABLE job_evaluations ADD COLUMN missing_skills TEXT"))
                if "hard_filter_failures" not in cols:
                    conn.execute(text("ALTER TABLE job_evaluations ADD COLUMN hard_filter_failures TEXT"))
                if "positive_reasons" not in cols:
                    conn.execute(text("ALTER TABLE job_evaluations ADD COLUMN positive_reasons TEXT"))
                if "negative_reasons" not in cols:
                    conn.execute(text("ALTER TABLE job_evaluations ADD COLUMN negative_reasons TEXT"))
                if "component_scores" not in cols:
                    conn.execute(text("ALTER TABLE job_evaluations ADD COLUMN component_scores TEXT"))
                if "recommendation" not in cols:
                    conn.execute(text("ALTER TABLE job_evaluations ADD COLUMN recommendation VARCHAR(512)"))
                if "engine_version" not in cols:
                    conn.execute(text("ALTER TABLE job_evaluations ADD COLUMN engine_version VARCHAR(50) NOT NULL DEFAULT '1.0.0'"))
                if "ai_model_version" not in cols:
                    conn.execute(text("ALTER TABLE job_evaluations ADD COLUMN ai_model_version VARCHAR(50)"))

                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_eval_score ON job_evaluations (score)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_eval_decision ON job_evaluations (decision)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_eval_job_evaluated ON job_evaluations (job_id, evaluated_at)"))
                conn.commit()

            # Cross-Platform Deduplication: Job Opportunities Table
            if "job_opportunities" not in tables:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS job_opportunities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        canonical_company_id INTEGER,
                        canonical_company_name VARCHAR(255) NOT NULL,
                        canonical_title VARCHAR(255) NOT NULL,
                        canonical_application_url VARCHAR(1024),
                        canonical_url_hash VARCHAR(64),
                        ats_provider VARCHAR(50),
                        ats_job_id VARCHAR(100),
                        primary_location VARCHAR(255),
                        work_style VARCHAR(50),
                        status VARCHAR(50) NOT NULL DEFAULT 'DISCOVERED',
                        applied_job_id INTEGER,
                        applied_platform VARCHAR(50),
                        applied_at DATETIME,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_opp_company_title ON job_opportunities (canonical_company_name, canonical_title)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_opp_app_url ON job_opportunities (canonical_application_url)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_opp_url_hash ON job_opportunities (canonical_url_hash)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_opp_ats ON job_opportunities (ats_provider, ats_job_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_opp_status ON job_opportunities (status)"))
                conn.commit()

            # Cross-Platform Deduplication: Evidence Audit Trail Table
            if "job_deduplication_evidence" not in tables:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS job_deduplication_evidence (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        incoming_job_id INTEGER NOT NULL,
                        matched_opportunity_id INTEGER,
                        matched_job_id INTEGER,
                        confidence_level VARCHAR(20) NOT NULL,
                        decision VARCHAR(50) NOT NULL,
                        evidence_json TEXT NOT NULL,
                        decision_reason VARCHAR(512) NOT NULL,
                        evaluated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_dedup_evidence_job ON job_deduplication_evidence (incoming_job_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_dedup_evidence_opp ON job_deduplication_evidence (matched_opportunity_id)"))
                conn.commit()
            else:
                res = conn.execute(text("PRAGMA table_info(job_deduplication_evidence)")).fetchall()
                cols = [r[1] for r in res]
                if "created_at" not in cols:
                    conn.execute(text("ALTER TABLE job_deduplication_evidence ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"))
                    conn.commit()
                if "updated_at" not in cols:
                    conn.execute(text("ALTER TABLE job_deduplication_evidence ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"))
                    conn.commit()

            # Jobs Table: Link to Opportunity
            if "jobs" in tables:
                res = conn.execute(text("PRAGMA table_info(jobs)")).fetchall()
                cols = [r[1] for r in res]
                if "opportunity_id" not in cols:
                    conn.execute(text("ALTER TABLE jobs ADD COLUMN opportunity_id INTEGER REFERENCES job_opportunities(id) ON DELETE SET NULL"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_opportunity_id ON jobs (opportunity_id)"))
                    conn.commit()
                if "canonical_url_hash" not in cols:
                    conn.execute(text("ALTER TABLE jobs ADD COLUMN canonical_url_hash VARCHAR(64)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_canonical_url_hash ON jobs (canonical_url_hash)"))
                    conn.commit()

            # Applications Table: Link to Opportunity & Unique Active Index
            if "applications" in tables:
                res = conn.execute(text("PRAGMA table_info(applications)")).fetchall()
                cols = [r[1] for r in res]
                if "opportunity_id" not in cols:
                    conn.execute(text("ALTER TABLE applications ADD COLUMN opportunity_id INTEGER REFERENCES job_opportunities(id) ON DELETE SET NULL"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_applications_opportunity_id ON applications (opportunity_id)"))
                    conn.commit()
                # Partial unique index guaranteeing no duplicate active applications for same opportunity
                conn.execute(text("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_applications_active_opp
                    ON applications (opportunity_id)
                    WHERE status IN ('SUBMITTED', 'APPLYING') AND opportunity_id IS NOT NULL
                """))
                conn.commit()
    except Exception:
        pass


def create_db_engine(url: Optional[str] = None, echo: bool = False) -> Engine:
    """Creates an engine configured with SQLite pragmas."""
    db_url = url or get_db_url()
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        db_url,
        echo=echo,
        connect_args=connect_args,
        future=True,
    )

    if db_url.startswith("sqlite"):
        event.listen(engine, "connect", configure_sqlite_pragmas)
        ensure_sqlite_schema(engine)

    return engine


# Default application-wide engine and sessionmaker
engine = create_db_engine()
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
    future=True,
)


@contextmanager
def get_db_session(session_factory: Optional[sessionmaker] = None) -> Generator[Session, None, None]:
    """Provides a transactional database session context with automatic commit/rollback."""
    factory = session_factory or SessionLocal
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_engine() -> None:
    """Disposes application-wide SQLAlchemy engine and closes all connection pools."""
    global engine
    if engine is not None:
        try:
            engine.dispose()
        except Exception:
            pass

