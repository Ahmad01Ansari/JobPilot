import unittest
from modules.models import Job, job_from_linkedin, job_from_naukri


class TestNormalizedJobModel(unittest.TestCase):
    def test_job_model_optional_experience(self):
        # Verify experience is Optional[int] and not defaulted to rigid 0..99
        job = Job(
            platform="naukri",
            job_id="123456",
            title="RPA Developer",
            company="Tech Corp",
            location="Delhi, India",
        )
        self.assertIsNone(job.required_experience_min)
        self.assertIsNone(job.required_experience_max)
        self.assertEqual(job.experience_range_str(), "Not specified")
        self.assertTrue(job.matches_candidate_experience(candidate_experience=2))

    def test_job_model_experience_bounds(self):
        job = Job(
            platform="naukri",
            job_id="123456",
            title="RPA Developer",
            company="Tech Corp",
            location="Noida",
            required_experience_min=1,
            required_experience_max=3,
            salary_min=400000,
            salary_max=700000,
        )
        self.assertEqual(job.required_experience_min, 1)
        self.assertEqual(job.required_experience_max, 3)
        self.assertEqual(job.experience_range_str(), "1-3 years")

        # Candidate with 2 years matches
        self.assertTrue(job.matches_candidate_experience(candidate_experience=2))
        # Candidate with 0 years does not match
        self.assertFalse(job.matches_candidate_experience(candidate_experience=0))
        # Candidate with 0 years + 2 allowance matches
        self.assertTrue(job.matches_candidate_experience(candidate_experience=0, allowance=2))

    def test_job_from_linkedin_adapter(self):
        ln_job = job_from_linkedin(
            job_id="4123456789",
            title="Automation Anywhere Developer",
            company="Global Logistics",
            location="Delhi, India",
            work_style="Hybrid",
            description="Looking for an RPA Developer with 2+ years experience.",
            experience_required=3,
        )
        self.assertEqual(ln_job.platform, "linkedin")
        self.assertEqual(ln_job.job_id, "4123456789")
        self.assertEqual(ln_job.title, "Automation Anywhere Developer")
        self.assertEqual(ln_job.required_experience_min, 3)
        self.assertIsNone(ln_job.required_experience_max)
        self.assertEqual(ln_job.source_url, "https://www.linkedin.com/jobs/view/4123456789")
        self.assertEqual(ln_job.apply_type, "DIRECT")

    def test_job_from_naukri_adapter(self):
        naukri_job = job_from_naukri(
            job_id="naukri_998877",
            title="Python Automation Engineer",
            company="AventIQ AI",
            location="Noida",
            work_style="Remote",
            description="Seeking Python automation engineer with A360 knowledge.",
            required_experience_min=1,
            required_experience_max=4,
            salary_min=500000,
            salary_max=800000,
            source_url="https://www.naukri.com/job-listings-998877",
        )
        self.assertEqual(naukri_job.platform, "naukri")
        self.assertEqual(naukri_job.job_id, "naukri_998877")
        self.assertEqual(naukri_job.required_experience_min, 1)
        self.assertEqual(naukri_job.required_experience_max, 4)
        self.assertEqual(naukri_job.salary_min, 500000)
        self.assertEqual(naukri_job.salary_max, 800000)
        self.assertEqual(naukri_job.source_url, "https://www.naukri.com/job-listings-998877")

    def test_structural_parity_between_platforms(self):
        # Deliverable check: Both produce the exact same internal Job schema
        ln = job_from_linkedin("1", "Dev", "Co", "Loc")
        nk = job_from_naukri("2", "Dev", "Co", "Loc")

        self.assertEqual(type(ln), type(nk))
        self.assertEqual(set(ln.to_dict().keys()), set(nk.to_dict().keys()))


if __name__ == "__main__":
    unittest.main()
