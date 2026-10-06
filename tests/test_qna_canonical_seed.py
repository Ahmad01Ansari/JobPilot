"""Unit tests for Universal Canonical Q&A Seed Bank, Dynamic Hydration, and Auto-Sync."""

import os
import unittest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import User, Profile, ProfessionalProfile, QnAEntry
from app.repositories.dto import ProfileUpdateDTO, ProfessionalProfileUpdateDTO
from app.repositories.user_repository import UserRepository
from app.services.qna_service import QnAService
from app.services.qna_seed_service import QnASeedService


class TestCanonicalQnASeed(unittest.TestCase):
    """Test suite covering canonical QnA seed catalog, hydration, and re-syncing."""

    def setUp(self):
        # Create an isolated in-memory SQLite database
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionFactory = sessionmaker(bind=self.engine)

        self.seed_service = QnASeedService(session_factory=self.SessionFactory)
        self.qna_service = QnAService(session_factory=self.SessionFactory)

        # Seed sample candidate
        with self.SessionFactory() as session:
            repo = UserRepository(session)
            user = repo.get_or_create_primary_user(name="Jane Doe", email="jane@example.com", phone="+1234567890")
            repo.save_profile(
                user.id,
                ProfileUpdateDTO(
                    first_name="Jane",
                    last_name="Doe",
                    current_city="Bangalore",
                    country="India",
                    willing_to_relocate=True,
                    zipcode="560001",
                ),
            )
            repo.save_professional_profile(
                user.id,
                ProfessionalProfileUpdateDTO(
                    current_title="Lead Automation Architect",
                    years_of_experience=5.0,
                    current_ctc=1200000,
                    expected_ctc=1800000,
                    notice_period_days=15,
                    skills=["python", "fastapi", "docker", "selenium", "postgresql"],
                ),
            )
            session.commit()
            self.user_id = user.id

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_canonical_catalog_schema(self):
        """Verifies that the canonical catalog is well-formed with 30+ questions."""
        catalog = self.seed_service.load_catalog()
        self.assertIn("questions", catalog)
        self.assertGreater(len(catalog["questions"]), 30)

        # Ensure all questions have required fields
        for q in catalog["questions"]:
            self.assertIn("id", q)
            self.assertIn("question_text", q)
            self.assertIn("strategy", q)
            self.assertIn("category", q)
            self.assertIn(q["strategy"], ["CONSTANT", "PROFILE_VAR", "SKILL_MATCH", "BEHAVIORAL_LLM"])

    def test_context_extraction(self):
        """Verifies candidate context extraction maps directly from DB."""
        ctx = self.seed_service.get_candidate_context(self.user_id)
        self.assertEqual(ctx["title"], "Lead Automation Architect")
        self.assertEqual(ctx["years_of_experience"], 5.0)
        self.assertEqual(ctx["notice_period_days"], 15)
        self.assertEqual(ctx["current_city"], "Bangalore")
        self.assertIn("python", ctx["skills"])

    def test_resolve_strategies(self):
        """Tests resolution for CONSTANT, PROFILE_VAR, SKILL_MATCH, and BEHAVIORAL_LLM."""
        ctx = self.seed_service.get_candidate_context(self.user_id)

        # 1. CONSTANT
        const_q = {"strategy": "CONSTANT", "template": "Never served"}
        self.assertEqual(self.seed_service.resolve_question_answer(const_q, ctx), "Never served")

        # 2. PROFILE_VAR
        var_q = {"strategy": "PROFILE_VAR", "template": "Notice is {notice_period_days} days"}
        self.assertEqual(self.seed_service.resolve_question_answer(var_q, ctx), "Notice is 15 days")

        # 3. SKILL_MATCH (Candidate has Python)
        skill_q_has = {"strategy": "SKILL_MATCH", "target_skill": "Python"}
        self.assertEqual(self.seed_service.resolve_question_answer(skill_q_has, ctx), "5")

        # 4. SKILL_MATCH (Candidate DOES NOT have Solidworks)
        skill_q_none = {"strategy": "SKILL_MATCH", "target_skill": "Solidworks"}
        self.assertEqual(self.seed_service.resolve_question_answer(skill_q_none, ctx), "0")

        # 5. BEHAVIORAL_LLM Fallback
        beh_q = {
            "strategy": "BEHAVIORAL_LLM",
            "fallback_template": "Experienced {title} with {years_of_experience} yrs in {skills_summary}.",
        }
        res = self.seed_service.resolve_question_answer(beh_q, ctx)
        self.assertIn("Lead Automation Architect", res)
        self.assertIn("5.0 yrs", res)

    def test_seed_canonical_bank_for_user(self):
        """Verifies bulk canonical seeding populates SQLite QnAEntry records with VERIFIED status."""
        created, updated = self.qna_service.seed_canonical_bank(user_id=self.user_id, force=False)
        self.assertGreater(created, 30)

        # Check in DB
        with self.SessionFactory() as session:
            count = session.query(QnAEntry).count()
            self.assertGreaterEqual(count, 30)

            # Test specific match
            criminal = session.query(QnAEntry).filter_by(normalized_question="criminal record").first()
            self.assertIsNotNone(criminal)
            self.assertEqual(criminal.answer_text, "No")
            self.assertEqual(criminal.validation_status, "VERIFIED")
            self.assertEqual(criminal.source, "CANONICAL")

            notice = session.query(QnAEntry).filter_by(normalized_question="notice period").first()
            self.assertIsNotNone(notice)
            self.assertEqual(notice.answer_text, "15 days")

    def test_resync_profile_answers(self):
        """Verifies resync updates PROFILE_VAR entries when candidate updates compensation or notice."""
        # Seed initial bank
        self.qna_service.seed_canonical_bank(user_id=self.user_id, force=False)

        # Candidate changes notice period from 15 to 45 days and CTC to 2500000
        with self.SessionFactory() as session:
            repo = UserRepository(session)
            prof = repo.get_professional_profile(self.user_id)
            prof.notice_period_days = 45
            prof.expected_ctc = 2500000
            session.commit()

        # Trigger re-sync
        updated_count = self.qna_service.resync_profile_answers(user_id=self.user_id)
        self.assertGreater(updated_count, 0)

        with self.SessionFactory() as session:
            notice = session.query(QnAEntry).filter_by(normalized_question="notice period").first()
            self.assertIsNotNone(notice)
            self.assertEqual(notice.answer_text, "45 days")

    def test_qna_export_import_roundtrip(self):
        """Tests exporting and importing QnA entries."""
        self.qna_service.add_entry(
            question="What is your favorite IDE?",
            answer="VS Code",
            category="custom",
        )
        export_data = self.qna_service.export_qna_to_dict()
        self.assertEqual(export_data["count"], 1)
        self.assertEqual(export_data["entries"][0]["question"], "What is your favorite IDE?")

        # Clear and import
        with self.SessionFactory() as session:
            session.query(QnAEntry).delete()
            session.commit()

        created, _ = self.qna_service.import_qna_from_dict(export_data)
        self.assertEqual(created, 1)

        test_res = self.qna_service.test_question_match("What is your favorite IDE?")
        self.assertTrue(test_res["matched"])
        self.assertEqual(test_res["answer"], "VS Code")


if __name__ == "__main__":
    unittest.main()
