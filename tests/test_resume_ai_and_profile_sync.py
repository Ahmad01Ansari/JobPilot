"""Unit tests for AI Skill Extraction Layer and Resume-to-Profile Synchronization."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import ProfessionalProfile, Resume, User
from app.repositories.user_repository import UserRepository
from app.services.resume_parser import DetectedSkill, ResumeParserService
from app.services.resume_service import ResumeService


class TestResumeAiAndProfileSync(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        self.storage_dir = os.path.join(self.temp_dir, "storage")
        os.makedirs(self.storage_dir, exist_ok=True)
        self.service = ResumeService(storage_dir=self.storage_dir, session_factory=self.session_factory)

        # Create primary test user
        with self.session_factory() as session:
            user = User(email="candidate@test.local", name="Candidate Test")
            session.add(user)
            session.commit()
            self.user_id = user.id

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_skills_with_ai_merges_new_skills(self):
        """AI extraction layer should identify new skills and merge with regex catalog matches."""
        base_skills = [
            DetectedSkill(canonical="Python", matched_alias="python", category="Languages"),
            DetectedSkill(canonical="SQL", matched_alias="sql", category="Databases"),
        ]

        sample_resume_text = (
            "Experienced Senior Software Engineer with strong background in Python, SQL, "
            "FastAPI microservices, Redis caching, Apache Kafka event streaming, and PyTorch."
        )

        mock_ai_service = MagicMock()
        mock_ai_service.get_config.return_value = {"enabled": True}
        mock_ai_service.extract_structured_json.return_value = {
            "skills": [
                {"name": "Python", "category": "Languages"},  # Already in base skills, should deduplicate
                {"name": "FastAPI", "category": "Web & APIs"},
                {"name": "Redis", "category": "Databases"},
                {"name": "Apache Kafka", "category": "Cloud & DevOps"},
                {"name": "PyTorch", "category": "AI / ML"},
            ]
        }

        merged = ResumeParserService.extract_skills_with_ai(
            text=sample_resume_text,
            existing_skills=base_skills,
            ai_service=mock_ai_service,
        )

        canonicals = [s.canonical for s in merged]
        self.assertIn("Python", canonicals)
        self.assertIn("SQL", canonicals)
        self.assertIn("FastAPI", canonicals)
        self.assertIn("Redis", canonicals)
        self.assertIn("Apache Kafka", canonicals)
        self.assertIn("PyTorch", canonicals)
        # Python should not be duplicated
        self.assertEqual(canonicals.count("Python"), 1)

    def test_extract_skills_with_ai_graceful_fallback_when_disabled_or_error(self):
        """When AI is disabled or raises an exception, regex skills are preserved intact."""
        base_skills = [
            DetectedSkill(canonical="UiPath", matched_alias="uipath", category="RPA")
        ]

        # Case 1: AI disabled
        mock_ai_disabled = MagicMock()
        mock_ai_disabled.get_config.return_value = {"enabled": False}
        result1 = ResumeParserService.extract_skills_with_ai(
            text="Long resume text with many words...",
            existing_skills=base_skills,
            ai_service=mock_ai_disabled,
        )
        self.assertEqual(len(result1), 1)
        self.assertEqual(result1[0].canonical, "UiPath")

        # Case 2: AI call throws exception
        mock_ai_error = MagicMock()
        mock_ai_error.get_config.return_value = {"enabled": True}
        mock_ai_error.extract_structured_json.side_effect = RuntimeError("Network timeout to Ollama")
        result2 = ResumeParserService.extract_skills_with_ai(
            text="Long resume text with many words...",
            existing_skills=base_skills,
            ai_service=mock_ai_error,
        )
        self.assertEqual(len(result2), 1)
        self.assertEqual(result2[0].canonical, "UiPath")

    def test_sync_resume_to_profile(self):
        """Parsed resume skills and target role should automatically update candidate profile."""
        detected_skills = [
            {"canonical": "Python", "category": "Languages"},
            {"canonical": "Automation Anywhere", "category": "RPA"},
            {"canonical": "PostgreSQL", "category": "Databases"},
            {"canonical": "Docker", "category": "DevOps"},
            {"canonical": "FastAPI", "category": "Frameworks"},
            {"canonical": "Redis", "category": "Databases"},
        ]

        self.service.sync_resume_to_profile(
            user_id=self.user_id,
            detected_skills=detected_skills,
            role_target="RPA & AI Automation Lead",
        )

        with self.session_factory() as session:
            repo = UserRepository(session)
            pro = repo.get_professional_profile(self.user_id)
            self.assertIsNotNone(pro)
            self.assertEqual(pro.current_title, "RPA & AI Automation Lead")
            self.assertIn("Python", pro.skills)
            self.assertIn("Automation Anywhere", pro.skills)
            self.assertIn("PostgreSQL", pro.skills)
            self.assertIn("FastAPI", pro.skills)
            # Primary skills should have top 5 skills
            self.assertEqual(len(pro.primary_skills), 5)
            self.assertIn("Python", pro.primary_skills)


if __name__ == "__main__":
    unittest.main()
