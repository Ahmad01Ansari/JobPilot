"""Unit tests for template rendering, template repository, and high-level OutreachService."""

import os
from pathlib import Path
import shutil
import tempfile
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Application, Communication, Company, Contact, EmailTemplate, FollowUp, Job, User
from app.repositories.email_template_repository import EmailTemplateRepository
from app.services.dto.outreach_dto import OutreachCreateDTO
from app.services.dto.outreach_enums import FollowUpStatus, MessageStatus
from app.services.email.mock_provider import MockEmailProvider
from app.services.outreach_dispatcher import OutreachDispatcher
from app.services.outreach_service import OutreachService
from app.services.template_renderer import TemplateRenderError, TemplateRenderer


class TestOutreachTemplatesAndService(unittest.TestCase):
    """Verifies template rendering engine, template CRUD, and OutreachService domain methods."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "svc_test.db")
        self.attach_dir = Path(self.temp_dir) / "attachments"
        self.attach_dir.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        with self.Session() as s:
            u = User(id=1, name="Jane Candidate", email="jane@candidate.test", is_active=True)
            s.add(u)
            s.commit()

        self.mock_provider = MockEmailProvider(account_email="jane@candidate.test")
        self.dispatcher = OutreachDispatcher(
            session_factory=self.Session,
            attachments_dir=self.attach_dir,
            default_provider=self.mock_provider,
        )
        self.service = OutreachService(
            session_factory=self.Session,
            dispatcher=self.dispatcher,
            email_provider=self.mock_provider,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_template_renderer_extraction_and_strict_rendering(self):
        """TemplateRenderer extracts placeholder keys and strictly checks missing values."""
        text = "Hello {{recruiter_name}}, applying for {{job_title}} at {{company_name}}."
        vars_found = TemplateRenderer.extract_variables(text)
        self.assertEqual(vars_found, ["company_name", "job_title", "recruiter_name"])

        # Strict rendering with missing variables raises TemplateRenderError
        with self.assertRaises(TemplateRenderError) as ctx:
            TemplateRenderer.render(text, {"recruiter_name": "Dave"}, strict=True)
        self.assertIn("company_name", str(ctx.exception))
        self.assertIn("job_title", str(ctx.exception))

        # Complete context renders successfully
        complete_ctx = {
            "recruiter_name": "Dave",
            "job_title": "Senior AI Architect",
            "company_name": "DeepTech Inc",
        }
        rendered, missing = TemplateRenderer.render(text, complete_ctx, strict=True)
        self.assertEqual(rendered, "Hello Dave, applying for Senior AI Architect at DeepTech Inc.")
        self.assertEqual(len(missing), 0)

    def test_template_renderer_preview_mode(self):
        """Preview mode replaces missing tokens with diagnostic placeholders without raising errors."""
        text = "Hi {{recruiter_name}}, your posting for {{job_title}} looks great."
        res = TemplateRenderer.preview(text, {"recruiter_name": "Sarah"})
        self.assertIn("Hi Sarah", res["preview"])
        self.assertIn("[NOT PROVIDED]", res["preview"])
        self.assertIn("job_title", res["missing_variables"])
        self.assertFalse(res["is_ready_to_send"])

    def test_email_template_repository_seeding_and_crud(self):
        """Repository seeds 4 canonical templates and supports retrieval."""
        with self.Session() as s:
            repo = EmailTemplateRepository(s)
            count = repo.seed_defaults_if_empty()
            self.assertEqual(count, 4)

            # Re-seeding when already populated should be idempotent (0 created)
            count2 = repo.seed_defaults_if_empty()
            self.assertEqual(count2, 0)

            templates = repo.list_all()
            self.assertEqual(len(templates), 4)

            # Check individual template structure
            pitch = repo.get_by_key("direct_application_pitch")
            self.assertIsNotNone(pitch)
            self.assertIn("{{candidate_name}}", pitch.subject_template)
            self.assertIn("{{skills}}", pitch.body_template)

    def test_outreach_service_send_and_timeline(self):
        """OutreachService interpolates template, creates records, and builds timeline."""
        # Seed templates first
        self.service.seed_templates_if_empty()
        templates = self.service.list_templates()
        self.assertGreater(len(templates), 0)
        pitch_tmpl = next(t for t in templates if t["key"] == "direct_application_pitch")

        dto = OutreachCreateDTO(
            template_id=pitch_tmpl["id"],
            manual_company_name="Innovate Corp",
            manual_job_title="Full Stack Lead",
            contact_name="Bob Talent",
            contact_email="bob@innovatecorp.com",
            followup_cadence_days=[3, 7, 14],
        )

        # Dispatch
        send_res = self.service.send_outreach(dto)
        self.assertTrue(send_res["success"])
        app_id = send_res["application_id"]
        self.assertIsNotNone(app_id)

        # Timeline verification
        timeline = self.service.get_conversation_timeline(app_id)
        self.assertEqual(timeline["company_name"], "Innovate Corp")
        self.assertEqual(timeline["job_title"], "Full Stack Lead")
        self.assertEqual(len(timeline["communications"]), 1)
        self.assertEqual(len(timeline["follow_ups"]), 3)
        self.assertIn("Application: Full Stack Lead", timeline["communications"][0]["subject"])

    def test_pause_and_resume_followups(self):
        """Service pauses and resumes scheduled follow-up cadences."""
        dto = OutreachCreateDTO(
            manual_company_name="Horizon Software",
            manual_job_title="Software Architect",
            contact_email="hiring@horizon.io",
            subject="Hello",
            body_text="World",
            followup_cadence_days=[5, 12],
        )
        res = self.service.send_outreach(dto)
        app_id = res["application_id"]

        # Pause followups
        paused_count = self.service.pause_followups(app_id, reason="Recruiter sent reply")
        self.assertEqual(paused_count, 2)

        timeline = self.service.get_conversation_timeline(app_id)
        for fu in timeline["follow_ups"]:
            self.assertEqual(fu["status"], FollowUpStatus.PAUSED.value)
            self.assertEqual(fu["paused_reason"], "Recruiter sent reply")

        # Resume followups
        resumed_count = self.service.resume_followups(app_id)
        self.assertEqual(resumed_count, 2)

        timeline_resumed = self.service.get_conversation_timeline(app_id)
        for fu in timeline_resumed["follow_ups"]:
            self.assertEqual(fu["status"], FollowUpStatus.PENDING.value)
            self.assertIsNone(fu["paused_reason"])


if __name__ == "__main__":
    unittest.main()
