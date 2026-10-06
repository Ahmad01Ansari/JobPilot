"""Unit tests for FakeATSServer and ground truth harness."""

import io
import json
import os
import unittest
import urllib.request
import urllib.parse

from tests.fixtures.harness.fake_ats_server import FakeATSServer


class TestFakeATSServer(unittest.TestCase):
    """Verifies fake ATS server endpoints, multipart handling, and validation."""

    def setUp(self) -> None:
        self.server = FakeATSServer()
        self.base_url = self.server.start()

    def tearDown(self) -> None:
        self.server.stop()

    def test_server_starts_and_allocates_port(self) -> None:
        self.assertTrue(self.server.port > 0)
        self.assertTrue(self.base_url.startswith("http://127.0.0.1:"))

    def test_get_index_page(self) -> None:
        req = urllib.request.Request(f"{self.base_url}/")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode("utf-8")
            self.assertIn("JobPilot Fake ATS Test Harness", body)
            self.assertIn("/standard-job", body)

    def test_get_standard_job_form(self) -> None:
        req = urllib.request.Request(f"{self.base_url}/standard-job")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode("utf-8")
            # Verify core form fields are rendered
            self.assertIn('id="first_name"', body)
            self.assertIn('id="last_name"', body)
            self.assertIn('id="email"', body)
            self.assertIn('id="phone"', body)
            self.assertIn('id="resume_upload"', body)
            self.assertIn('name="work_auth"', body)
            self.assertIn('name="visa_sponsorship"', body)
            self.assertIn('id="years_experience"', body)
            self.assertIn('id="submit-application"', body)

    def test_post_missing_required_fields_fails(self) -> None:
        data = urllib.parse.urlencode({"first_name": "Jane"}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/standard-job/submit",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                self.fail("Expected HTTP 400 for incomplete submission")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            body = e.read().decode("utf-8")
            self.assertIn('id="form-errors"', body)
            self.assertIn("Submission Error", body)

    def test_post_multipart_valid_submission_succeeds(self) -> None:
        boundary = "----WebKitFormBoundaryFakeATSTest12345"
        body = io.BytesIO()

        fields = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@example.com",
            "phone": "+1 555-0199",
            "work_auth": "yes",
            "visa_sponsorship": "no",
            "years_experience": "5-8",
            "notice_period": "30",
            "expected_salary": "$140,000",
        }
        for k, v in fields.items():
            body.write(f"--{boundary}\r\n".encode("utf-8"))
            body.write(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
            body.write(f"{v}\r\n".encode("utf-8"))

        # Add mock resume file
        body.write(f"--{boundary}\r\n".encode("utf-8"))
        body.write('Content-Disposition: form-data; name="resume"; filename="Jane_Doe_Resume.pdf"\r\n'.encode("utf-8"))
        body.write("Content-Type: application/pdf\r\n\r\n".encode("utf-8"))
        body.write(b"%PDF-1.4 Mock PDF Content For Testing\r\n")
        body.write(f"--{boundary}--\r\n".encode("utf-8"))

        content_bytes = body.getvalue()

        req = urllib.request.Request(
            f"{self.base_url}/standard-job/submit",
            data=content_bytes,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(content_bytes)),
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            # 303 redirect followed automatically by urllib to /thank-you
            self.assertEqual(resp.status, 200)
            final_body = resp.read().decode("utf-8")
            self.assertIn("Thank you for your application!", final_body)
            self.assertIn("APP-JP-98765", final_body)

        # Inspect captured state via last_submission
        last = self.server.last_submission
        self.assertIsNotNone(last)
        self.assertEqual(last["fields"]["first_name"], "Jane")
        self.assertEqual(last["fields"]["last_name"], "Doe")
        self.assertEqual(last["fields"]["email"], "jane.doe@example.com")
        self.assertEqual(last["fields"]["work_auth"], "yes")
        self.assertIn("resume", last["files"])
        self.assertEqual(last["files"]["resume"]["filename"], "Jane_Doe_Resume.pdf")

    def test_multi_step_wizard_routes(self) -> None:
        # Step 1
        with urllib.request.urlopen(f"{self.base_url}/wizard/step1") as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("Step 1 of 3", resp.read().decode("utf-8"))

        # Step 2
        with urllib.request.urlopen(f"{self.base_url}/wizard/step2") as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("Step 2 of 3", resp.read().decode("utf-8"))

        # Step 3
        with urllib.request.urlopen(f"{self.base_url}/wizard/step3") as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("Step 3 of 3", resp.read().decode("utf-8"))

    def test_security_challenge_routes(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/challenge/captcha") as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("Verifying you are human", resp.read().decode("utf-8"))

        with urllib.request.urlopen(f"{self.base_url}/challenge/login") as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("Sign in to Apply", resp.read().decode("utf-8"))

    def test_ground_truth_json_schema(self) -> None:
        gt_path = os.path.join(os.path.dirname(__file__), "fixtures", "harness", "ground_truth.json")
        self.assertTrue(os.path.exists(gt_path), f"Ground truth file missing at {gt_path}")
        with open(gt_path) as f:
            data = json.load(f)

        self.assertIn("portal_metadata", data)
        self.assertIn("fields", data)
        self.assertIn("verification_signals", data)

        fields = data["fields"]
        self.assertEqual(len(fields), 12)
        required_count = sum(1 for f in fields if f["required"])
        self.assertEqual(required_count, 8)

        # Check required fields exist
        field_ids = {f["id"] for f in fields}
        self.assertIn("first_name", field_ids)
        self.assertIn("last_name", field_ids)
        self.assertIn("email", field_ids)
        self.assertIn("phone", field_ids)
        self.assertIn("resume_upload", field_ids)
        self.assertIn("work_auth", field_ids)
        self.assertIn("visa_sponsorship", field_ids)


    def test_ats_archetype_routes_get(self) -> None:
        """Verifies GET responses for all 4 ATS archetypes."""
        archetypes = [
            ("/greenhouse", "Senior Backend Engineer", "Greenhouse"),
            ("/lever", "Apply for Product Engineer", "Lever"),
            ("/workday/step1", "Candidate Information", "Workday"),
            ("/workday/step2", "Experience & Resume", "Workday"),
            ("/workday/step3", "Review Application", "Workday"),
            ("/ashby", "Staff Software Engineer", "Ashby"),
        ]
        for path, exp_text, exp_name in archetypes:
            with urllib.request.urlopen(f"{self.base_url}{path}") as resp:
                self.assertEqual(resp.status, 200, f"Failed GET for {path}")
                content = resp.read().decode("utf-8")
                self.assertIn(exp_text, content)
                self.assertIn(exp_name, content)


if __name__ == "__main__":
    unittest.main()
