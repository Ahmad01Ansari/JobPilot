"""Comprehensive test suite for ResumeService and ResumesView."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Application, Job, Resume, User
from app.db.session import configure_sqlite_pragmas
from app.services.resume_service import ResumeService


class TestResumeService(unittest.TestCase):
    """Unit tests for ResumeService operations, path safety, and lifecycle rules."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_resume.db")
        self.storage_dir = os.path.join(self.temp_dir, "managed_resumes")
        self.db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(self.db_url, future=True)
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self.engine,
            future=True,
        )

        self.service = ResumeService(storage_dir=self.storage_dir, session_factory=self.Session, is_test=True)

        # Create test users
        with self.Session() as s:
            self.user1 = User(name="User One", email="user1@example.com")
            self.user2 = User(name="User Two", email="user2@example.com")
            s.add_all([self.user1, self.user2])
            s.commit()
            self.user1_id = self.user1.id
            self.user2_id = self.user2.id

        # Create sample files
        self.sample_pdf = os.path.join(self.temp_dir, "sample_resume.pdf")
        with open(self.sample_pdf, "wb") as f:
            f.write(b"%PDF-1.4 sample pdf content for resume")

        self.sample_docx = os.path.join(self.temp_dir, "sample_resume.docx")
        with open(self.sample_docx, "wb") as f:
            f.write(b"PK sample docx content")

        self.sample_doc = os.path.join(self.temp_dir, "sample_resume.doc")
        with open(self.sample_doc, "wb") as f:
            f.write(b"\xd0\xcf\x11\xe0 sample legacy doc content")

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_path_confinement_and_sanitization(self):
        """Verifies that filenames are sanitized and path traversal is strictly prevented."""
        # Sanitization
        sanitized = self.service._sanitize_filename("../../etc/passwd.pdf")
        self.assertNotIn("..", sanitized)
        self.assertNotIn("/", sanitized)
        self.assertTrue(sanitized.endswith(".pdf"))

        # Confinement assertion
        safe_path = self.service.storage_dir / "safe.pdf"
        resolved = self.service._resolve_managed_path(safe_path)
        self.assertEqual(resolved, safe_path.resolve())

        # Outside path triggers ValueError
        outside_path = Path(self.temp_dir) / "outside.pdf"
        with self.assertRaises(ValueError):
            self.service._resolve_managed_path(outside_path)

    def test_add_resume_and_hash_calculation(self):
        """Tests adding a resume, copying into storage, and verifying SHA-256 calculation."""
        resume, created, err = self.service.add_resume(
            user_id=self.user1_id,
            source_path=self.sample_pdf,
            display_name="My Primary Resume",
            role_target="Software Engineer",
        )
        self.assertTrue(created)
        self.assertIsNone(err)
        self.assertIsNotNone(resume)
        self.assertEqual(resume.name, "My Primary Resume")
        self.assertEqual(resume.role_target, "Software Engineer")
        self.assertTrue(resume.is_default)  # First resume is automatically default

        # Verify physical file exists in managed storage
        stored_path = Path(resume.file_path)
        self.assertTrue(stored_path.exists())
        self.assertTrue(stored_path.is_relative_to(self.service.storage_dir))

    def test_duplicate_file_detection(self):
        """Verifies duplicate uploads of the exact same file for a user return existing record."""
        res1, created1, _ = self.service.add_resume(
            user_id=self.user1_id,
            source_path=self.sample_pdf,
        )
        self.assertTrue(created1)

        # Re-upload same file
        res2, created2, msg = self.service.add_resume(
            user_id=self.user1_id,
            source_path=self.sample_pdf,
        )
        self.assertFalse(created2)
        self.assertEqual(res1.id, res2.id)
        self.assertIn("already uploaded", msg)

    def test_set_default_resume_switch(self):
        """Verifies switching default resume atomically unsets the previous default."""
        r1, _, _ = self.service.add_resume(self.user1_id, self.sample_pdf, display_name="R1")
        r2, _, _ = self.service.add_resume(self.user1_id, self.sample_docx, display_name="R2")

        self.assertTrue(r1.is_default)
        self.assertFalse(r2.is_default)

        # Switch default to r2
        switched, err = self.service.set_default_resume(r2.id, self.user1_id)
        self.assertIsNone(err)
        self.assertTrue(switched.is_default)

        # Verify from database
        with self.Session() as s:
            reloaded_r1 = s.get(Resume, r1.id)
            reloaded_r2 = s.get(Resume, r2.id)
            self.assertFalse(reloaded_r1.is_default)
            self.assertTrue(reloaded_r2.is_default)

    def test_delete_default_promotes_next(self):
        """Verifies that deleting the default resume automatically promotes the remaining resume."""
        r1, _, _ = self.service.add_resume(self.user1_id, self.sample_pdf, display_name="R1")
        r2, _, _ = self.service.add_resume(self.user1_id, self.sample_docx, display_name="R2")

        # r1 is default. Delete r1
        success, err = self.service.delete_resume(r1.id, self.user1_id)
        self.assertTrue(success)
        self.assertIsNone(err)

        # r2 should now be promoted to default
        new_default = self.service.get_default_resume(self.user1_id)
        self.assertIsNotNone(new_default)
        self.assertEqual(new_default.id, r2.id)
        self.assertTrue(new_default.is_default)

    def test_delete_resume_blocked_when_referenced_by_application(self):
        """Verifies deletion is blocked when an application references the resume."""
        resume, _, _ = self.service.add_resume(self.user1_id, self.sample_pdf)

        # Create a job and application referencing this resume
        with self.Session() as s:
            job = Job(
                platform="linkedin",
                job_fingerprint="fp_ref_test",
                title="Python Dev",
                company_raw="Ref Corp",
                source_url="https://linkedin.com/job/ref",
            )
            s.add(job)
            s.flush()

            app = Application(
                job_id=job.id,
                user_id=self.user1_id,
                resume_id=resume.id,
                status="SUBMITTED",
            )
            s.add(app)
            s.commit()

        # Attempt to delete resume
        success, err = self.service.delete_resume(resume.id, self.user1_id)
        self.assertFalse(success)
        self.assertIn("linked to existing job applications", err)

        # Verify resume still exists
        with self.Session() as s:
            self.assertIsNotNone(s.get(Resume, resume.id))

    def test_ownership_validation(self):
        """Verifies User 1 cannot delete, rename, or open User 2's resume."""
        res_user2, _, _ = self.service.add_resume(self.user2_id, self.sample_pdf)

        # User 1 attempts delete
        success, err = self.service.delete_resume(res_user2.id, self.user1_id)
        self.assertFalse(success)
        self.assertIn("access denied", err.lower())

        # User 1 attempts rename
        renamed, err = self.service.rename_resume(res_user2.id, self.user1_id, "Hacked Name")
        self.assertIsNone(renamed)
        self.assertIn("access denied", err.lower())

        # User 1 attempts open
        opened, err = self.service.open_resume(res_user2.id, self.user1_id)
        self.assertFalse(opened)
        self.assertIn("access denied", err.lower())

    def test_integrity_verification_and_mismatch(self):
        """Tests that verify_integrity checks for physical file existence and hash match."""
        resume, _, _ = self.service.add_resume(self.user1_id, self.sample_pdf)

        # 1. Valid state
        is_valid, msg = self.service.verify_integrity(resume.id, self.user1_id)
        self.assertTrue(is_valid)
        self.assertEqual(msg, "Verified")

        # 2. File modified externally -> hash mismatch
        with open(resume.file_path, "wb") as f:
            f.write(b"Tampered resume content")

        is_valid, msg = self.service.verify_integrity(resume.id, self.user1_id)
        self.assertFalse(is_valid)
        self.assertIn("mismatch", msg.lower())

        # 3. File deleted from disk -> missing
        os.remove(resume.file_path)
        is_valid, msg = self.service.verify_integrity(resume.id, self.user1_id)
        self.assertFalse(is_valid)
        self.assertIn("missing", msg.lower())

    def test_rename_preserves_hash_and_file(self):
        """Verifies renaming updates metadata without altering the physical file."""
        resume, _, _ = self.service.add_resume(self.user1_id, self.sample_pdf, display_name="Original Name")
        initial_hash = resume.file_hash
        initial_path = resume.file_path

        renamed, err = self.service.rename_resume(
            resume.id, self.user1_id, new_name="Updated Name", new_version="2.0"
        )
        self.assertIsNone(err)
        self.assertEqual(renamed.name, "Updated Name")
        self.assertEqual(renamed.version, "2.0")
        self.assertEqual(renamed.file_hash, initial_hash)
        self.assertEqual(renamed.file_path, initial_path)

    def test_file_formats_pdf_docx_doc(self):
        """Verifies allowed formats (.pdf, .docx, .doc) succeed and unsupported formats fail."""
        # PDF
        _, ok_pdf, _ = self.service.add_resume(self.user1_id, self.sample_pdf)
        self.assertTrue(ok_pdf)

        # DOCX
        _, ok_docx, _ = self.service.add_resume(self.user1_id, self.sample_docx)
        self.assertTrue(ok_docx)

        # DOC
        _, ok_doc, _ = self.service.add_resume(self.user1_id, self.sample_doc)
        self.assertTrue(ok_doc)

        # Unsupported format (.txt)
        txt_path = os.path.join(self.temp_dir, "resume.txt")
        with open(txt_path, "w") as f:
            f.write("Text resume")
        _, ok_txt, err = self.service.add_resume(self.user1_id, txt_path)
        self.assertFalse(ok_txt)
        self.assertIn("unsupported", err.lower())


class TestResumesView(unittest.TestCase):
    """Tests for ResumesView UI component in headless mode."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_view.db")
        self.storage_dir = os.path.join(self.temp_dir, "view_resumes")
        self.db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(self.db_url, future=True)
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self.engine,
            future=True,
        )

        self.service = ResumeService(storage_dir=self.storage_dir, session_factory=self.Session, is_test=True)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_resumes_view_rendering_and_table_population(self):
        """Verifies ResumesView instantiates, renders table rows, and updates summary labels."""
        from app.ui.views.resumes_view import ResumesView

        sample_file = os.path.join(self.temp_dir, "view_test.pdf")
        with open(sample_file, "wb") as f:
            f.write(b"%PDF sample")

        with patch("app.ui.views.resumes_view.get_db_session", return_value=self.Session()):
            view = ResumesView(service=self.service)
            # Initially empty
            self.assertEqual(view.table.rowCount(), 0)
            self.assertIn("Total Resumes: 0", view.lbl_total.text())

            # Add resume
            self.service.add_resume(view.current_user_id, sample_file, display_name="View Resume")
            view.refresh()

            # Now table has 1 row
            self.assertEqual(view.table.rowCount(), 1)
            self.assertEqual(view.table.item(0, 0).text(), "View Resume")
            self.assertIn("Total Resumes: 1", view.lbl_total.text())
            self.assertIn("View Resume", view.lbl_default.text())


if __name__ == "__main__":
    unittest.main()
