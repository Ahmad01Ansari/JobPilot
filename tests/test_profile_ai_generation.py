"""Unit test suite for AI narrative generation (cover letter, headline, summary).

Validates ProfileService.generate_narrative_content, onboarding persistence,
worker execution, and UI component integration across Onboarding and Profile views.
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import ProfessionalProfile, Profile, User
from app.db.session import configure_sqlite_pragmas
from app.services.profile_service import ProfileService


class TestProfileAIGeneration(unittest.TestCase):
    """Unit tests for AI narrative generation across service and UI layers."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_ai_gen.db")
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
        self.service = ProfileService(session_factory=self.Session)

        # Create candidate user & profile via service
        user, profile, pro = self.service.get_primary_user_profile()
        self.service.save_profile(
            user_id=user.id,
            personal_data={
                "first_name": "Alex",
                "last_name": "Mercer",
                "email": "test.candidate@example.com",
                "current_city": "Bengaluru",
                "country": "India",
            },
            professional_data={
                "title": "Senior Automation Engineer",
                "current_employer": "TechCorp Global",
                "years_of_experience": 6.5,
                "skills": "Python, Selenium, PySide6, Docker, FastApi",
            },
        )
        self.user_id = user.id

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_narrative_all_with_mock_ai(self):
        """Verifies generating headline, summary, and cover letter in a single AI pass."""
        mock_ai = MagicMock()
        mock_ai.get_config.return_value = {"enabled": True, "provider": "gemini"}
        mock_ai.generate_text.return_value = (
            '{\n'
            '  "headline": "Senior Automation Engineer | Python & Selenium Expert",\n'
            '  "summary": "Experienced Automation Engineer specializing in building scalable frameworks.",\n'
            '  "cover_letter": "Dear Hiring Team,\\n\\nI am writing to express my strong interest..."\n'
            '}'
        )

        res = self.service.generate_narrative_content(
            field_type="all",
            user_id=self.user_id,
            ai_service=mock_ai,
        )

        self.assertIn("headline", res)
        self.assertIn("summary", res)
        self.assertIn("cover_letter", res)
        self.assertEqual(res["headline"], "Senior Automation Engineer | Python & Selenium Expert")
        self.assertIn("Experienced Automation Engineer", res["summary"])
        self.assertIn("Dear Hiring Team", res["cover_letter"])

    def test_generate_narrative_single_fields(self):
        """Verifies generating individual fields (headline, summary, cover_letter)."""
        mock_ai = MagicMock()
        mock_ai.get_config.return_value = {"enabled": True, "provider": "gemini"}
        
        # Test headline
        mock_ai.generate_text.return_value = "Staff Software Engineer | Python & Cloud"
        hl_res = self.service.generate_narrative_content(
            field_type="headline",
            context={"target_role": "Staff Software Engineer", "skills": "Python, Cloud"},
            ai_service=mock_ai,
        )
        self.assertIn("headline", hl_res)
        self.assertEqual(hl_res["headline"], "Staff Software Engineer | Python & Cloud")

        # Test summary
        mock_ai.generate_text.return_value = "Results-driven engineer with 8 years of experience."
        sum_res = self.service.generate_narrative_content(
            field_type="summary",
            context={"title": "Staff Engineer"},
            ai_service=mock_ai,
        )
        self.assertIn("summary", sum_res)
        self.assertEqual(sum_res["summary"], "Results-driven engineer with 8 years of experience.")

        # Test cover letter
        mock_ai.generate_text.return_value = "Dear Hiring Manager,\n\nI am eager to apply for this role."
        cl_res = self.service.generate_narrative_content(
            field_type="cover_letter",
            context={"title": "Staff Engineer", "name": "Alex Mercer"},
            ai_service=mock_ai,
        )
        self.assertIn("cover_letter", cl_res)
        self.assertIn("Dear Hiring Manager", cl_res["cover_letter"])

    def test_generate_narrative_ai_unavailable_raises_clean_error(self):
        """Verifies clean, non-crashing exception when AI is disabled or not configured."""
        mock_ai = MagicMock()
        mock_ai.get_config.return_value = {"enabled": False}

        with self.assertRaises(RuntimeError) as ctx:
            self.service.generate_narrative_content(
                field_type="all",
                user_id=self.user_id,
                ai_service=mock_ai,
            )
        self.assertIn("AI Engine is disabled", str(ctx.exception))

    def test_apply_onboarding_data_persists_cover_letter(self):
        """Verifies that onboarding data persistence saves cover letter into ProfessionalProfile."""
        onboarding_payload = {
            "personal": {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane.doe@example.com",
            },
            "professional": {
                "title": "Lead QA Engineer",
                "headline": "Lead QA Engineer | Test Automation Specialist",
                "summary": "10 years of QA automation experience.",
                "cover_letter": "I am passionate about quality assurance and continuous delivery.",
            },
            "skills": ["Selenium", "Cypress", "Python"],
        }

        ok, err = self.service.apply_onboarding_data(self.user_id, onboarding_payload)
        self.assertTrue(ok, f"apply_onboarding_data failed: {err}")

        with self.Session() as session:
            pro = session.query(ProfessionalProfile).filter_by(user_id=self.user_id).first()
            self.assertIsNotNone(pro)
            self.assertEqual(pro.headline, "Lead QA Engineer | Test Automation Specialist")
            self.assertEqual(pro.summary, "10 years of QA automation experience.")
            self.assertEqual(pro.cover_letter, "I am passionate about quality assurance and continuous delivery.")


if __name__ == "__main__":
    unittest.main()


class TestProfileAIGenerationUI(unittest.TestCase):
    """UI integration tests for StepProfileWidget and ProfileView AI generation."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_ui_ai_gen.db")
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
        self.service = ProfileService(session_factory=self.Session)
        user, _, _ = self.service.get_primary_user_profile()
        self.user_id = user.id

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_step_profile_widget_ai_button_and_population(self):
        """Verifies StepProfileWidget has AI button and populates headline, summary, cover letter."""
        from app.ui.widgets.onboarding_steps.step_profile import StepProfileWidget

        mock_setup = MagicMock()
        widget = StepProfileWidget(setup_service=mock_setup)
        widget.show()
        self.assertTrue(hasattr(widget, "btn_ai_gen_narrative"))
        self.assertTrue(hasattr(widget, "txt_cover_letter"))
        self.assertTrue(hasattr(widget, "txt_headline"))
        self.assertTrue(hasattr(widget, "txt_summary"))

        # Simulate worker finish signal
        fake_results = {
            "headline": "Lead RPA Developer | Python & AI Automation",
            "summary": "Proven track record in intelligent process automation.",
            "cover_letter": "I am thrilled to apply for this opening and contribute...",
        }
        widget._on_ai_gen_finished(True, "", fake_results)

        self.assertEqual(widget.txt_headline.text(), fake_results["headline"])
        self.assertEqual(widget.txt_summary.toPlainText(), fake_results["summary"])
        self.assertEqual(widget.txt_cover_letter.toPlainText(), fake_results["cover_letter"])
        self.assertTrue(widget.lbl_ai_status.isVisible())
        self.assertIn("Successfully generated", widget.lbl_ai_status.text())

    def test_profile_view_ai_buttons_and_population(self):
        """Verifies ProfileView has AI buttons on Skills and Professional cards and updates inputs."""
        from app.ui.views.profile_view import ProfileView

        view = ProfileView(service=self.service)
        self.assertTrue(hasattr(view, "btn_ai_gen_skills"))
        self.assertTrue(hasattr(view, "btn_ai_headline"))
        self.assertTrue(hasattr(view, "txt_cover_letter"))

        # Verify context collection
        view.txt_title.setText("Staff Automation Engineer")
        view.txt_skills.setText("Python, Playwright, CI/CD")
        ctx = view._collect_ai_context()
        self.assertEqual(ctx["target_role"], "Staff Automation Engineer")
        self.assertEqual(ctx["technical_skills"], "Python, Playwright, CI/CD")

        # Simulate completion of AI generation
        fake_results = {
            "headline": "Staff Automation Engineer | Python & Playwright",
            "summary": "Architecting enterprise automated test frameworks.",
            "cover_letter": "I am eager to bring my automation expertise to your team.",
        }
        view._on_ai_generate_finished(True, "", fake_results, "all")

        self.assertEqual(view.txt_headline.text(), fake_results["headline"])
        self.assertEqual(view.txt_summary.toPlainText(), fake_results["summary"])
        self.assertEqual(view.txt_cover_letter.toPlainText(), fake_results["cover_letter"])
        self.assertTrue(view.card_skills.is_editing)
        self.assertTrue(view.card_professional.is_editing)
        self.assertIn("Generated Headline, Summary, Cover Letter with AI", view.notification_bar.message_label.text())

    def test_workers_execution(self):
        """Verifies NarrativeGenWorker and ProfileNarrativeGenWorker invoke profile service cleanly."""
        from app.ui.widgets.onboarding_steps.step_profile import NarrativeGenWorker
        from app.ui.views.profile_view import ProfileNarrativeGenWorker

        mock_service = MagicMock()
        mock_service.generate_narrative_content.return_value = {"headline": "AI Headline"}

        # Step worker
        step_worker = NarrativeGenWorker(mock_service, field_type="headline", context={"title": "Dev"})
        step_worker.run()
        mock_service.generate_narrative_content.assert_called_with(field_type="headline", context={"title": "Dev"})

        # Profile view worker
        view_worker = ProfileNarrativeGenWorker(mock_service, field_type="all", context={"title": "Dev"}, user_id=123)
        view_worker.run()
        mock_service.generate_narrative_content.assert_called_with(field_type="all", context={"title": "Dev"}, user_id=123)


class TestCoverLetterRuntimeRendering(unittest.TestCase):
    """Verifies runtime replacement of [Target Position], [Company Name], and candidate details."""

    def setUp(self):
        self.sample_template = (
            "Dear [Hiring Manager Name],\n\n"
            "I am writing to express my interest in the [Target Position] at [Company Name]. "
            "I am excited to bring my skills to [Company Name]. "
            "I look forward to discussing how my skills support [Company Name].\n\n"
            "Sincerely,\n"
            "[Candidate Name]"
        )

    def test_render_cover_letter_full_replacement(self):
        """Verifies clean substitution of position, all company occurrences, and candidate signature."""
        rendered = ProfileService.render_cover_letter(
            template=self.sample_template,
            company="Accenture",
            job_title="RPA Developer",
            candidate_name="Mohd Ahmad Raza Ansari",
        )

        self.assertNotIn("[Target Position]", rendered)
        self.assertNotIn("[Company Name]", rendered)
        self.assertNotIn("[Candidate Name]", rendered)
        self.assertNotIn("[Hiring Manager Name]", rendered)

        self.assertIn("RPA Developer position at Accenture", rendered)
        self.assertIn("skills to Accenture", rendered)
        self.assertIn("support Accenture", rendered)
        self.assertIn("Mohd Ahmad Raza Ansari", rendered)
        self.assertIn("Dear Hiring Team", rendered)

    def test_render_cover_letter_unlisted_company_and_role_fallbacks(self):
        """Verifies natural grammatical fallbacks when company and title are missing or confidential."""
        rendered = ProfileService.render_cover_letter(
            template=self.sample_template,
            company="Confidential",
            job_title="",
            candidate_name="Alex Mercer",
        )

        self.assertNotIn("[Target Position]", rendered)
        self.assertNotIn("[Company Name]", rendered)
        self.assertIn("for this opening with your organization", rendered)
        self.assertIn("skills to your organization", rendered)
        self.assertIn("Alex Mercer", rendered)

    def test_qna_engine_renders_cover_letter_at_runtime(self):
        """Verifies QnAEngine dynamically replaces placeholders when answering cover letter questions."""
        from modules.qna_engine import QnAEngine

        engine = QnAEngine()
        engine.prof["cover_letter"] = self.sample_template
        engine.full_name = "Mohd Ahmad Raza Ansari"

        # Resolve through answer_question with job_context
        ans = engine.answer_question(
            question="Please provide your cover letter or note to the hiring team",
            field_type="textarea",
            job_context={"company": "Google", "title": "AI Automation Engineer"},
        )

        res_val = str(ans.value)
        self.assertNotIn("[Company Name]", res_val)
        self.assertNotIn("[Target Position]", res_val)
        self.assertIn("AI Automation Engineer position at Google", res_val)
        self.assertIn("skills to Google", res_val)
        self.assertIn("Mohd Ahmad Raza Ansari", res_val)
