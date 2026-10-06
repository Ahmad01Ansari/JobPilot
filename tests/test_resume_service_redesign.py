"""Unit and integration tests for the Resume Redesign (Phase 1).

Tests domain rules, boundary-aware skill extraction, privacy guarantees (no raw PII),
cache invalidation, deterministic default promotion, lineage tracking, and usage analytics.
"""

from datetime import datetime, timezone
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Application, Job, Interview, Offer, Resume, User
from app.db.session import configure_sqlite_pragmas
from app.services.resume_parser import CURRENT_PARSER_VERSION, ResumeParserService
from app.services.resume_service import ResumeService


class TestResumeParserService(unittest.TestCase):
    """Direct tests for deterministic parser, boundary skills, and privacy constraints."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_minimal_pdf(self, filename: str, text_content: str) -> str:
        """Generates a real minimal PDF with extractable text using pypdf/reportlab or minimal PDF syntax."""
        import pypdf
        writer = pypdf.PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        # To add actual text easily without extra heavy dependencies, we can use reportlab if available
        # or pypdf annotation, or write a real minimal PDF stream:
        pdf_path = os.path.join(self.temp_dir, filename)
        
        # Build standard valid minimal PDF text stream
        content = f"BT /F1 12 Tf 50 700 Td ({text_content}) Tj ET"
        stream_len = len(content)
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
            b"4 0 obj << /Length " + str(stream_len).encode("ascii") + b" >>\n"
            b"stream\n" + content.encode("latin-1") + b"\nendstream\nendobj\n"
            b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
            b"xref\n0 6\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"0000000244 00000 n \n"
            b"0000000330 00000 n \n"
            b"trailer << /Size 6 /Root 1 0 R >>\n"
            b"startxref\n410\n%%EOF"
        )
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        return pdf_path

    def test_privacy_guarantee_no_raw_text_or_pii_in_metadata(self):
        """CRITICAL: Verifies zero raw resume text and zero contact strings in parsed_metadata."""
        text = "Candidate Name John Doe john.doe@example.com (555) 123-4567 Experienced Python and Docker developer."
        pdf_path = self._create_minimal_pdf("privacy_test.pdf", text)

        res = ResumeParserService.parse_pdf(pdf_path)
        meta = res.to_metadata_dict("dummy_hash")

        # 1. No raw text snippet
        self.assertNotIn("text", meta)
        self.assertNotIn("extracted_text_snippet", meta)
        self.assertNotIn("raw_text", meta)
        self.assertIn("extracted_text_hash", meta)

        # 2. No raw contact strings (phone/email), only boolean presence
        contacts = meta.get("contacts", {})
        self.assertTrue(contacts.get("email_present"))
        self.assertTrue(contacts.get("phone_present"))
        self.assertNotIn("john.doe@example.com", str(meta))
        self.assertNotIn("555", str(meta))
        self.assertNotIn("123-4567", str(meta))

    def test_boundary_aware_skill_matching(self):
        """Verifies skill regex matches words accurately and avoids false positives."""
        # 'c++' and 'Python 3' should match; 'good' should NOT match 'go'; 'restaurant' should NOT match 'rest api'
        text = "Proficient in Python 3, C++, SQL and Docker. Doing good work in restaurant management."
        pdf_path = self._create_minimal_pdf("skills_test.pdf", text)

        res = ResumeParserService.parse_pdf(pdf_path)
        skills = {s.canonical for s in res.detected_skills}

        self.assertIn("Python", skills)
        self.assertIn("C++", skills)
        self.assertIn("SQL", skills)
        self.assertIn("Docker", skills)

        # Negative checks: 'good' must not trigger 'Go'
        self.assertNotIn("Go", skills)
        # 'restaurant' must not trigger 'REST API'
        self.assertNotIn("REST API", skills)

    def test_factual_health_evaluator(self):
        """Verifies factual health status: VALID, NEEDS_ATTENTION, or INVALID."""
        # 1. Fully valid
        state, flags = ResumeParserService.evaluate_health_state(
            file_exists=True,
            hash_valid=True,
            pdf_readable=True,
            text_extractable=True,
            contacts_detected=True,
            role_assigned=True,
        )
        self.assertEqual(state, "VALID")

        # 2. Needs attention (e.g. missing role target or missing contact info)
        state_na, flags_na = ResumeParserService.evaluate_health_state(
            file_exists=True,
            hash_valid=True,
            pdf_readable=True,
            text_extractable=True,
            contacts_detected=False,  # missing contact
            role_assigned=True,
        )
        self.assertEqual(state_na, "NEEDS_ATTENTION")

        # 3. Invalid (corrupt, missing file, or hash mismatch)
        state_inv, flags_inv = ResumeParserService.evaluate_health_state(
            file_exists=True,
            hash_valid=False,  # modified externally
            pdf_readable=True,
            text_extractable=True,
            contacts_detected=True,
            role_assigned=True,
        )
        self.assertEqual(state_inv, "INVALID")


class TestResumeServiceRedesign(unittest.TestCase):
    """End-to-end tests for ResumeService redesign logic."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "redesign.db")
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

        with self.Session() as s:
            self.user = User(name="Test User", email="user@example.com")
            s.add(self.user)
            s.commit()
            self.user_id = self.user.id

        # Create valid test PDF
        self.pdf_file = os.path.join(self.temp_dir, "resume.pdf")
        content = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
            b"4 0 obj << /Length 85 >>\n"
            b"stream\nBT /F1 12 Tf 50 700 Td (Software Engineer test@example.com 1234567890 Python Docker) Tj ET\nendstream\nendobj\n"
            b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
            b"xref\n0 6\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"0000000244 00000 n \n"
            b"0000000381 00000 n \n"
            b"trailer << /Size 6 /Root 1 0 R >>\n"
            b"startxref\n461\n%%EOF"
        )
        with open(self.pdf_file, "wb") as f:
            f.write(content)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_opaque_naming_and_metadata_persistence(self):
        """Verifies opaque file naming (res_{uuid}.pdf) and automatic metadata generation."""
        res, created, err = self.service.add_resume(
            user_id=self.user_id,
            source_path=self.pdf_file,
            display_name="Senior Python Developer",
            role_target="Backend Engineer",
            notes="Initial upload",
        )
        self.assertTrue(created)
        self.assertIsNone(err)
        self.assertIsNotNone(res)

        # Check filename pattern res_{uuid}.pdf
        filename = Path(res.file_path).name
        self.assertTrue(filename.startswith("res_"))
        self.assertTrue(filename.endswith(".pdf"))

        # Check parsed metadata presence
        self.assertIsNotNone(res.parsed_metadata)
        self.assertEqual(res.parsed_metadata.get("parser_version"), CURRENT_PARSER_VERSION)
        self.assertEqual(res.notes, "Initial upload")
        self.assertTrue(res.lineage_id)

    def test_lineage_and_versioning(self):
        """Verifies that create_new_version preserves lineage_id and associates versions."""
        v1, created1, _ = self.service.add_resume(
            user_id=self.user_id,
            source_path=self.pdf_file,
            display_name="Base Resume",
            role_target="Full Stack",
            version="1.0",
        )
        self.assertTrue(created1)

        # Create another file for v2
        v2_source = os.path.join(self.temp_dir, "resume_v2.pdf")
        with open(v2_source, "wb") as f:
            f.write(open(self.pdf_file, "rb").read() + b"\n% v2 difference")

        v2, created2, err2 = self.service.create_new_version(
            source_resume_id=v1.id,
            user_id=self.user_id,
            new_source_path=v2_source,
            new_version="2.0",
            notes="Updated with new certifications",
        )
        self.assertTrue(created2)
        self.assertIsNone(err2)
        self.assertEqual(v2.lineage_id, v1.lineage_id)
        self.assertEqual(v2.version, "2.0")
        self.assertEqual(v2.role_target, "Full Stack")

        lineage_members = self.service.get_lineage_resumes(v1.lineage_id, self.user_id)
        self.assertEqual(len(lineage_members), 2)

    def test_deterministic_default_promotion_on_archive(self):
        """Verifies 4-tier precedence when archiving default resume:
        1. Active in same role -> 2. Active General -> 3. Any active -> 4. None.
        """
        # Upload 3 resumes:
        # A: Backend Engineer (Default)
        # B: Backend Engineer
        # C: General
        srcA = self.pdf_file
        srcB = os.path.join(self.temp_dir, "b.pdf")
        srcC = os.path.join(self.temp_dir, "c.pdf")
        with open(srcB, "wb") as f:
            f.write(open(self.pdf_file, "rb").read() + b"\n% B")
        with open(srcC, "wb") as f:
            f.write(open(self.pdf_file, "rb").read() + b"\n% C")

        resA, _, _ = self.service.add_resume(self.user_id, srcA, "A", role_target="Backend", is_default=True)
        resB, _, _ = self.service.add_resume(self.user_id, srcB, "B", role_target="Backend", is_default=False)
        resC, _, _ = self.service.add_resume(self.user_id, srcC, "C", role_target="General", is_default=False)

        self.assertTrue(resA.is_default)

        # Archive A -> B should become default because B has same role ("Backend")
        ok, err = self.service.archive_resume(resA.id, self.user_id)
        self.assertTrue(ok)

        new_def = self.service.get_default_resume(self.user_id)
        self.assertIsNotNone(new_def)
        self.assertEqual(new_def.id, resB.id)

        # Archive B -> C should become default because C is "General"
        ok, err = self.service.archive_resume(resB.id, self.user_id)
        self.assertTrue(ok)
        new_def2 = self.service.get_default_resume(self.user_id)
        self.assertIsNotNone(new_def2)
        self.assertEqual(new_def2.id, resC.id)

        # Archive C -> None remains
        ok, err = self.service.archive_resume(resC.id, self.user_id)
        self.assertTrue(ok)
        self.assertIsNone(self.service.get_default_resume(self.user_id))

    def test_parser_cache_invalidation(self):
        """Verifies that if parser_version differs, get_resume_health invalidates cache and re-parses."""
        res, _, _ = self.service.add_resume(self.user_id, self.pdf_file, "Test Cache")

        # Manually alter parser_version in DB to simulate old cache
        with self.Session() as s:
            from app.repositories.resume_repository import ResumeRepository
            repo = ResumeRepository(s)
            r = repo.get_by_id(res.id)
            r.parsed_metadata["parser_version"] = "0.0.1"
            s.commit()

        # Calling get_resume_health should detect outdated parser_version and re-parse to CURRENT_PARSER_VERSION
        health = self.service.get_resume_health(res.id, self.user_id)
        self.assertEqual(health["metadata"]["parser_version"], CURRENT_PARSER_VERSION)

    def test_resume_usage_metrics(self):
        """Verifies calculation of applications, interviews, offers, and last_used timestamp."""
        res, _, _ = self.service.add_resume(self.user_id, self.pdf_file, "Usage Test")

        with self.Session() as s:
            # Create a job and applications
            job1 = Job(
                platform="linkedin",
                company_raw="Google",
                title="Staff Engineer",
                job_fingerprint="fp1",
                source_url="https://linkedin.com/jobs/view/1001",
            )
            job2 = Job(
                platform="naukri",
                company_raw="Amazon",
                title="Principal SDE",
                job_fingerprint="fp2",
                source_url="https://naukri.com/job/2002",
            )
            s.add_all([job1, job2])
            s.flush()

            app1 = Application(
                job_id=job1.id,
                user_id=self.user_id,
                resume_id=res.id,
                status="INTERVIEW",
                applied_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
            )
            app2 = Application(
                job_id=job2.id,
                user_id=self.user_id,
                resume_id=res.id,
                status="OFFER",
                applied_at=datetime(2026, 9, 25, 14, 0, tzinfo=timezone.utc),
            )
            s.add_all([app1, app2])
            s.flush()

            interview = Interview(
                application_id=app2.id,
                round_name="Technical",
                scheduled_at=datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc),
                status="COMPLETED",
            )
            s.add(interview)
            s.commit()

        usage = self.service.get_resume_usage(res.id, self.user_id)
        self.assertEqual(usage["total_applications"], 2)
        self.assertEqual(usage["submitted_count"], 2)
        self.assertEqual(usage["interviews_count"], 2)  # app1 (INTERVIEW status) + app2 (Interview record)
        self.assertEqual(usage["offers_count"], 1)
        self.assertIn("Sep 25, 2026", usage["last_used_at"])
        self.assertEqual(usage["platforms"].get("linkedin"), 1)
        self.assertEqual(usage["platforms"].get("naukri"), 1)
        self.assertEqual(len(usage["recent_applications"]), 2)

    def test_library_summary_aggregation(self):
        """Verifies get_library_summary compiles KPIs accurately."""
        res1, _, _ = self.service.add_resume(self.user_id, self.pdf_file, "Active 1", role_target="Software Engineer")
        summary = self.service.get_library_summary(self.user_id)

        self.assertEqual(summary["total_resumes"], 1)
        self.assertEqual(summary["archived_count"], 0)
        self.assertEqual(summary["default_resume_name"], "Active 1")
        self.assertIn("valid", summary["health_summary"])


if __name__ == "__main__":
    unittest.main()
