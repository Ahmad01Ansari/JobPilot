"""Unit tests for Outreach AI pitch generation, response classification, and status transitions."""

import json
import unittest
from unittest.mock import MagicMock, patch

from app import app
from app.db.base import utc_now
from app.db.models import Application, Company, Contact, Job, User
from app.db.session import SessionLocal, get_db_session
from app.services.outreach_ai_service import OutreachAIService


class TestOutreachAI(unittest.TestCase):
    """Verifies AI pitch generation, response classification, and API endpoints."""

    def setUp(self):
        self.client = app.test_client()
        mock_disabled_ai = MagicMock()
        mock_disabled_ai.get_config.return_value = {"enabled": False}
        self.ai_svc = OutreachAIService(session_factory=SessionLocal, ai_service=mock_disabled_ai)

        with get_db_session(SessionLocal) as s:
            u = s.get(User, 1)
            if not u:
                s.add(User(id=1, name="Dev Candidate", email="dev@jobpilot.local", is_active=True))
                s.commit()

    def test_generate_pitch_ai_success(self):
        """When AI is enabled and returns JSON, generate_pitch returns AI-generated content."""
        mock_ai = MagicMock()
        mock_ai.get_config.return_value = {"enabled": True, "provider": "mock"}
        mock_ai.extract_structured_json.return_value = {
            "subject": "Tailored Application: Lead Python Engineer",
            "body_text": "Hi Jane, I saw Acme Corp's opening for Lead Python Engineer and wanted to introduce myself.",
        }

        svc = OutreachAIService(session_factory=SessionLocal, ai_service=mock_ai)
        res = svc.generate_pitch(
            company_name="Acme Corp",
            job_title="Lead Python Engineer",
            recruiter_name="Jane Doe",
            tone="direct",
        )

        self.assertEqual(res["source"], "ai")
        self.assertEqual(res["subject"], "Tailored Application: Lead Python Engineer")
        self.assertIn("Acme Corp", res["body_text"])

    def test_generate_pitch_template_fallback(self):
        """When AI is disabled or fails, generate_pitch falls back to canonical template."""
        mock_ai = MagicMock()
        mock_ai.get_config.return_value = {"enabled": False}

        svc = OutreachAIService(session_factory=SessionLocal, ai_service=mock_ai)
        res = svc.generate_pitch(
            company_name="Beta Systems",
            job_title="Full Stack Developer",
            recruiter_name="Bob Smith",
        )

        self.assertEqual(res["source"], "template_fallback")
        self.assertIn("Full Stack Developer", res["subject"])
        self.assertIn("Beta Systems", res["body_text"])

    def test_classify_response_interview_heuristic(self):
        """Heuristic classifier accurately detects interview requests."""
        body = "Hi Dev, we reviewed your profile and would love to schedule a call on Zoom this Wednesday."
        subject = "Next Steps at Acme Corp"
        res = self.ai_svc.classify_response(email_body=body, email_subject=subject)

        self.assertEqual(res["category"], "INTERVIEW_REQUEST")
        self.assertEqual(res["suggested_action"], "INTERVIEW")
        self.assertEqual(res["confidence"], "HIGH")

    def test_classify_response_assessment_heuristic(self):
        """Heuristic classifier accurately detects assessment requests."""
        body = "Please complete the technical coding test on HackerRank within the next 48 hours."
        res = self.ai_svc.classify_response(email_body=body)

        self.assertEqual(res["category"], "ASSESSMENT_REQUEST")
        self.assertEqual(res["suggested_action"], "ASSESSMENT")

    def test_classify_response_rejection_heuristic(self):
        """Heuristic classifier accurately detects rejections."""
        body = "Unfortunately, after careful review, we have decided not to proceed with your candidacy at this time."
        res = self.ai_svc.classify_response(email_body=body)

        self.assertEqual(res["category"], "REJECTION")
        self.assertEqual(res["suggested_action"], "REJECTED")

    def test_classify_response_offer_heuristic(self):
        """Heuristic classifier accurately detects job offers."""
        body = "We are pleased to offer you the position of Senior Engineer. Attached is our formal offer letter."
        res = self.ai_svc.classify_response(email_body=body)

        self.assertEqual(res["category"], "OFFER")
        self.assertEqual(res["suggested_action"], "OFFER")

    def test_classify_response_information_request_heuristic(self):
        """Heuristic classifier accurately detects notice period / CTC inquiries."""
        body = "Could you please confirm your notice period and current compensation expectations?"
        res = self.ai_svc.classify_response(email_body=body)

        self.assertEqual(res["category"], "INFORMATION_REQUEST")

    def test_classify_response_other_fallback(self):
        """Generic email text without keywords categorizes as RECRUITER_RESPONSE."""
        body = "Automated system update: server maintenance scheduled for midnight."
        res = self.ai_svc.classify_response(email_body=body)

        self.assertEqual(res["category"], "RECRUITER_RESPONSE")

    def test_api_generate_pitch_endpoint(self):
        """POST /api/outreach/ai/generate-pitch returns generated draft."""
        payload = {
            "company_name": "Stark Industries",
            "job_title": "AI Research Scientist",
            "recruiter_name": "Tony",
        }
        res = self.client.post("/api/outreach/ai/generate-pitch", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("subject", data)
        self.assertIn("body_text", data)
        self.assertIn("AI Research Scientist", data["subject"])

    def test_api_classify_response_endpoint(self):
        """POST /api/outreach/ai/classify-response returns structured classification."""
        payload = {
            "email_body": "We would love to set up an introductory chat on Google Meet this Friday.",
            "email_subject": "Introductory Call - Stark Industries",
        }
        res = self.client.post("/api/outreach/ai/classify-response", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["category"], "INTERVIEW_REQUEST")
        self.assertEqual(data["suggested_action"], "INTERVIEW")

    def test_api_apply_suggested_status_endpoint(self):
        """POST /api/outreach/conversations/<id>/apply-status updates application status."""
        import uuid
        from app.db.models.job import generate_job_fingerprint
        uid = uuid.uuid4().hex[:6]

        with get_db_session(SessionLocal) as s:
            comp = Company(name=f"Gamma Labs {uid}", normalized_name=f"gamma labs {uid}")
            s.add(comp)
            s.flush()
            fp = generate_job_fingerprint("DIRECT_OUTREACH", f"Gamma Labs {uid}", f"Backend Developer {uid}")
            job = Job(
                company_id=comp.id,
                company_raw=f"Gamma Labs {uid}",
                title=f"Backend Developer {uid}",
                platform="DIRECT_OUTREACH",
                source_url=f"https://gamma.test/jobs/{uid}",
                job_fingerprint=fp,
            )
            s.add(job)
            s.flush()
            app_rec = Application(user_id=1, job_id=job.id, status="APPLIED", applied_at=utc_now())
            s.add(app_rec)
            s.commit()
            app_id = app_rec.id

        # Apply INTERVIEW status
        res = self.client.post(
            f"/api/outreach/conversations/{app_id}/apply-status",
            json={
                "status": "INTERVIEW",
                "notes": "Recruiter invited to technical screen",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["new_status"], "INTERVIEW")

        with get_db_session(SessionLocal) as s:
            updated_app = s.get(Application, app_id)
            self.assertEqual(updated_app.status, "INTERVIEW")


if __name__ == "__main__":
    unittest.main()
