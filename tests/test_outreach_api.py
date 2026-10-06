"""Unit tests for Flask Outreach REST API endpoints."""

import json
import os
import shutil
import tempfile
import unittest

from sqlalchemy import select

from app import app
from app.db.base import Base
from app.db.models import Application, Communication, Company, Contact, FollowUp, Job, Resume, User
from app.db.session import SessionLocal, get_db_session
from app.services.email.factory import register_email_provider, unregister_email_provider
from app.services.email.mock_provider import MockEmailProvider


class TestOutreachAPI(unittest.TestCase):
    """Verifies REST endpoints for Outreach Center dashboard and composer."""

    def setUp(self):
        self.client = app.test_client()
        self.mock_provider = MockEmailProvider(account_email="tester@jobpilot.local")
        register_email_provider("default", self.mock_provider)

        # Seed candidate user and template
        with get_db_session(SessionLocal) as s:
            user = s.get(User, 1)
            if not user:
                s.add(User(id=1, name="Test User", email="tester@jobpilot.local", is_active=True))
                s.commit()

    def tearDown(self):
        unregister_email_provider("default")
        with get_db_session(SessionLocal) as s:
            test_contacts = select(Contact.id).where(Contact.email.like("%@apitestlabs.org"))
            test_apps = s.query(Application).filter(
                Application.application_type == "EMAIL",
                Application.contact_id.in_(test_contacts),
            ).all()
            for app in test_apps:
                s.query(FollowUp).filter(FollowUp.application_id == app.id).delete(synchronize_session=False)
                s.query(Communication).filter(Communication.application_id == app.id).delete(synchronize_session=False)
                s.delete(app)
            s.query(Contact).filter(Contact.email.like("%@apitestlabs.org")).delete(synchronize_session=False)
            s.query(Company).filter(Company.name.like("API Test Labs%")).delete(synchronize_session=False)
            s.query(User).filter(User.email == "tester@jobpilot.local").delete(synchronize_session=False)
            s.commit()

    def test_outreach_stats_endpoint(self):
        """GET /api/outreach/stats returns metrics payload."""
        response = self.client.get("/api/outreach/stats")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("total_outreached", data)
        self.assertIn("total_sent", data)
        self.assertIn("awaiting_reply", data)
        self.assertIn("recruiter_replied", data)
        self.assertIn("followups_due", data)
        self.assertIn("delivery_success_rate", data)

    def test_templates_and_preview_endpoints(self):
        """GET /api/outreach/templates and POST /api/outreach/templates/preview."""
        # List templates
        res = self.client.get("/api/outreach/templates")
        self.assertEqual(res.status_code, 200)
        templates = res.get_json()
        self.assertGreater(len(templates), 0)

        tmpl_id = templates[0]["id"]
        # Preview
        preview_res = self.client.post(
            "/api/outreach/templates/preview",
            json={
                "template_id": tmpl_id,
                "context": {
                    "recruiter_name": "Marcus",
                    "company_name": "Acme Corp",
                    "job_title": "Lead Architect",
                },
            },
        )
        self.assertEqual(preview_res.status_code, 200)
        preview_data = preview_res.get_json()
        self.assertIn("subject_preview", preview_data)
        self.assertIn("body_preview", preview_data)
        self.assertIn("missing_variables", preview_data)

    def test_send_and_timeline_lifecycle(self):
        """POST /api/outreach/send followed by GET /api/outreach/conversations and timeline."""
        import uuid
        uid = uuid.uuid4().hex[:6]
        # 1. Send outreach
        send_payload = {
            "manual_company_name": f"API Test Labs {uid}",
            "manual_job_title": "Backend Lead",
            "contact_name": "Alice Recruiter",
            "contact_email": f"alice_{uid}@apitestlabs.org",
            "subject": "Application for Backend Lead",
            "body_text": "Hi Alice, I am excited to apply for Backend Lead.",
            "followup_cadence_days": [3, 7],
        }
        res = self.client.post("/api/outreach/send", json=send_payload)
        self.assertEqual(res.status_code, 200)
        send_data = res.get_json()
        self.assertTrue(send_data["success"])
        app_id = send_data["application_id"]
        self.assertIsNotNone(app_id)

        # 2. Check conversation listing
        conv_res = self.client.get("/api/outreach/conversations")
        self.assertEqual(conv_res.status_code, 200)
        conversations = conv_res.get_json()
        matching = [c for c in conversations if c["application_id"] == app_id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["company_name"], f"API Test Labs {uid}")

        # 3. Check conversation timeline
        timeline_res = self.client.get(f"/api/outreach/conversations/{app_id}/timeline")
        self.assertEqual(timeline_res.status_code, 200)
        timeline = timeline_res.get_json()
        self.assertEqual(len(timeline["communications"]), 1)
        self.assertEqual(len(timeline["follow_ups"]), 2)

        # 4. Pause followups
        pause_res = self.client.post(f"/api/outreach/conversations/{app_id}/pause", json={"reason": "User paused"})
        self.assertEqual(pause_res.status_code, 200)
        pause_data = pause_res.get_json()
        self.assertEqual(pause_data["paused_count"], 2)

        # 5. Resume followups
        resume_res = self.client.post(f"/api/outreach/conversations/{app_id}/resume", json={})
        self.assertEqual(resume_res.status_code, 200)
        resume_data = resume_res.get_json()
        self.assertEqual(resume_data["resumed_count"], 2)

    def test_provider_test_endpoint(self):
        """POST /api/outreach/provider/test verifies connectivity check."""
        res = self.client.post("/api/outreach/provider/test", json={"account_id": "default"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["provider_name"], "mock")

    def test_resumes_endpoint_does_not_expose_file_paths(self):
        """GET /api/outreach/resumes returns safe resume metadata."""
        res = self.client.get("/api/outreach/resumes")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)
        for item in data:
            self.assertNotIn("file_path", item)


if __name__ == "__main__":
    unittest.main()
