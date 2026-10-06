"""Tests for Outreach Center schema evolution and backward compatibility."""

import os
import sqlite3
import tempfile
import unittest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Application, Communication, Company, Contact, EmailTemplate, FollowUp, Job
from app.db.session import create_db_engine, ensure_sqlite_schema


class TestOutreachSchemaMigration(unittest.TestCase):
    """Verifies non-destructive SQLite schema migration for Outreach Center."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "legacy_test.db")
        self.db_url = f"sqlite:///{self.db_path}"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_legacy_database_migration_idempotence(self):
        """Simulates an older legacy JobPilot database and proves idempotent migration."""
        # 1. Manually create legacy schema with bare minimum columns
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE communications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER,
                contact_id INTEGER,
                type VARCHAR(50) DEFAULT 'EMAIL',
                direction VARCHAR(20) DEFAULT 'INBOUND',
                occurred_at DATETIME,
                subject VARCHAR(255),
                summary TEXT,
                notes TEXT,
                source VARCHAR(50) DEFAULT 'manual',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE follow_ups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER,
                contact_id INTEGER,
                due_at DATETIME,
                completed_at DATETIME,
                status VARCHAR(50) DEFAULT 'PENDING',
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Insert a legacy communication
        cur.execute("""
            INSERT INTO communications (type, direction, subject, notes)
            VALUES ('EMAIL', 'OUTBOUND', 'Legacy Email Subject', 'Legacy communication note')
        """)
        conn.commit()
        conn.close()

        # 2. Run ensure_sqlite_schema via create_db_engine
        engine = create_db_engine(url=self.db_url)

        # 3. Verify columns were added to legacy database
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Check communications columns
        comm_cols = [r[1] for r in cur.execute("PRAGMA table_info(communications)").fetchall()]
        self.assertIn("status", comm_cols)
        self.assertIn("account_id", comm_cols)
        self.assertIn("send_token", comm_cols)
        self.assertIn("provider_message_id", comm_cols)
        self.assertIn("provider_thread_id", comm_cols)
        self.assertIn("template_id", comm_cols)
        self.assertIn("attachment_snapshot_path", comm_cols)
        self.assertIn("body_snippet", comm_cols)

        # Verify legacy row is preserved intact with defaults
        legacy_row = cur.execute("SELECT id, subject, status, account_id FROM communications WHERE id = 1").fetchone()
        self.assertEqual(legacy_row[0], 1)
        self.assertEqual(legacy_row[1], "Legacy Email Subject")
        self.assertEqual(legacy_row[2], "SENT")
        self.assertEqual(legacy_row[3], "default")

        # Check follow_ups columns
        fu_cols = [r[1] for r in cur.execute("PRAGMA table_info(follow_ups)").fetchall()]
        self.assertIn("sequence_id", fu_cols)
        self.assertIn("step_number", fu_cols)
        self.assertIn("paused_reason", fu_cols)

        # Check new tables exist
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        self.assertIn("email_templates", tables)
        self.assertIn("email_sync_checkpoints", tables)
        conn.close()

        # 4. Run ensure_sqlite_schema a second time to verify complete idempotence
        ensure_sqlite_schema(engine)

        # 5. Verify ORM models map and execute cleanly on migrated DB
        Session = sessionmaker(bind=engine)
        with Session() as session:
            # Create an email template
            tmpl = EmailTemplate(
                key="test_job_app",
                name="Job Application Template",
                category="JOB_APPLICATION",
                subject_template="Application for {{job_title}}",
                body_template="Dear {{recruiter_name}},\n\nI am applying...",
            )
            session.add(tmpl)
            session.commit()

            fetched_tmpl = session.execute(select(EmailTemplate).where(EmailTemplate.key == "test_job_app")).scalar_one()
            self.assertEqual(fetched_tmpl.name, "Job Application Template")

            # Create an outreach communication linked to the template
            comm = Communication(
                type="EMAIL",
                direction="OUTBOUND",
                status="SENDING",
                account_id="acc_main",
                send_token="token_abc_123",
                template_id=fetched_tmpl.id,
                subject="Application for RPA Lead",
            )
            session.add(comm)
            session.commit()

            fetched_comm = session.execute(select(Communication).where(Communication.send_token == "token_abc_123")).scalar_one()
            self.assertEqual(fetched_comm.account_id, "acc_main")
            self.assertEqual(fetched_comm.status, "SENDING")
            self.assertEqual(fetched_comm.template.key, "test_job_app")

            # Create a follow-up with sequence_id
            fu = FollowUp(
                due_at=fetched_comm.occurred_at,
                sequence_id="seq_xyz_789",
                step_number=1,
                status="PENDING",
            )
            session.add(fu)
            session.commit()

            fetched_fu = session.execute(select(FollowUp).where(FollowUp.sequence_id == "seq_xyz_789")).scalar_one()
            self.assertEqual(fetched_fu.step_number, 1)
            self.assertEqual(fetched_fu.status, "PENDING")


if __name__ == "__main__":
    unittest.main()
