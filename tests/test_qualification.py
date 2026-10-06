import unittest
from modules.models import Job, job_from_linkedin, job_from_naukri
from modules.qualification_engine import (
    QualificationEngine,
    QualificationResult,
    extract_experience_bounds,
    extract_years_of_experience,
)


class TestQualificationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = QualificationEngine(
            candidate_experience=2,
            did_masters=False,
            security_clearance=False,
            bad_words=["US Citizen Only", "Polygraph", "CNC Operator"],
            negative_title_words=[
                "electrical", "mechanical", "civil", "hardware", "chemical",
                "structural", "technician", "machinist", "maintenance", "site engineer",
                "eplan", "plc programmer"
            ],
            blacklisted_companies={"ScamCorp", "UnwantedLLC"},
            about_company_bad_words=["Crossover", "Staffing"],
            about_company_good_words=["Robert Half", "Dice"],
            applied_job_ids={"job_applied_1", "job_applied_2"},
        )

    def test_applied_jobs_rejected(self):
        job = job_from_linkedin("job_applied_1", "RPA Developer", "Good Company", "Delhi")
        res = self.engine.qualify(job)
        self.assertFalse(res.accepted)
        self.assertEqual(res.stage, "ALREADY_APPLIED")

    def test_blacklisted_company_rejected(self):
        job = job_from_naukri("job_new_1", "RPA Developer", "ScamCorp", "Noida")
        res = self.engine.qualify(job)
        self.assertFalse(res.accepted)
        self.assertEqual(res.stage, "COMPANY_BLACKLIST")

    def test_negative_title_word_rejected(self):
        # Case 1: Mechanical Engineer
        job1 = job_from_naukri("job_new_2", "Senior Mechanical Automation Engineer", "Tata", "Pune")
        res1 = self.engine.qualify(job1)
        self.assertFalse(res1.accepted)
        self.assertEqual(res1.stage, "TITLE_FILTER")
        self.assertIn("mechanical", res1.reason)

        # Case 2: Eplan Drafter
        job2 = job_from_linkedin("job_new_3", "EPLAN Designer", "ABB", "Bengaluru")
        res2 = self.engine.qualify(job2)
        self.assertFalse(res2.accepted)
        self.assertEqual(res2.stage, "TITLE_FILTER")

        # Case 3: Valid title passes
        job3 = job_from_naukri("job_new_4", "Automation Anywhere RPA Developer", "AventIQ", "Delhi")
        res3 = self.engine.qualify(job3)
        self.assertTrue(res3.accepted)

    def test_irrelevant_tech_stack_rejected(self):
        # Case 1: Java + Angular (like in user screenshot)
        job1 = job_from_naukri("job_java", "Java + Angular. (2-5 years)", "Infosys", "Noida")
        res1 = self.engine.qualify(job1)
        self.assertFalse(res1.accepted)
        self.assertEqual(res1.stage, "TITLE_FILTER")
        self.assertIn("irrelevant tech", res1.reason.lower())

        # Case 2: Fullstack React / Node
        job2 = job_from_naukri("job_react", "React / Node Developer", "TCS", "Bengaluru")
        res2 = self.engine.qualify(job2)
        self.assertFalse(res2.accepted)
        self.assertEqual(res2.stage, "TITLE_FILTER")

        # Case 3: Python Automation Engineer (should NOT be rejected despite any overlap)
        job3 = job_from_naukri("job_py_auto", "Python Automation Engineer", "TechCorp", "Pune")
        res3 = self.engine.qualify(job3)
        self.assertTrue(res3.accepted)

    def test_generic_title_skill_matching(self):
        # Case 1: Generic title with irrelevant description
        job_generic_irrelevant = job_from_naukri(
            job_id="job_gen_1",
            title="Software Engineer",
            company="Global IT",
            location="Gurgaon",
            description="Looking for Java Spring Boot and Hibernate developer with MySQL experience."
        )
        res1 = self.engine.qualify(job_generic_irrelevant)
        self.assertFalse(res1.accepted)
        self.assertEqual(res1.stage, "SKILL_MISMATCH")

        # Case 2: Generic title with matching RPA/Python automation description
        job_generic_relevant = job_from_naukri(
            job_id="job_gen_2",
            title="Software Engineer",
            company="Global IT",
            location="Gurgaon",
            description="Developing RPA bots using UiPath and Python automation scripts."
        )
        res2 = self.engine.qualify(job_generic_relevant)
        self.assertTrue(res2.accepted)

    def test_about_company_good_vs_bad_words(self):
        # Bad company word without exception
        res_bad = self.engine.qualify_company("This is a Crossover remote role.")
        self.assertFalse(res_bad.accepted)
        self.assertEqual(res_bad.stage, "ABOUT_COMPANY")

        # Bad company word with good word exception
        res_good = self.engine.qualify_company("Staffing role managed by Robert Half technology.")
        self.assertTrue(res_good.accepted)
        self.assertIn("robert half", res_good.reason.lower())

    def test_description_bad_words(self):
        job = job_from_naukri(
            job_id="job_bad_1",
            title="Python Developer",
            company="Govt Subcontractor",
            location="Remote",
            description="Must be US Citizen Only. Python and automation tools required.",
        )
        res = self.engine.qualify(job)
        self.assertFalse(res.accepted)
        self.assertEqual(res.stage, "BAD_WORDS")

    def test_security_clearance_requirement(self):
        job = job_from_linkedin(
            job_id="job_clearance_1",
            title="Automation Engineer",
            company="Defense Partner",
            location="Remote",
            description="Candidate must possess active secret clearance.",
        )
        res = self.engine.qualify(job)
        self.assertFalse(res.accepted)
        self.assertEqual(res.stage, "CLEARANCE")

    def test_experience_evaluation_direct_bounds(self):
        # Candidate has 2 years exp
        # Job requires 1-3 years -> Accepted
        job_ok = job_from_naukri(
            job_id="job_exp_1",
            title="RPA Developer",
            company="Tech Corp",
            location="Noida",
            required_experience_min=1,
            required_experience_max=3,
        )
        res_ok = self.engine.qualify(job_ok)
        self.assertTrue(res_ok.accepted)

        # Job requires 5 years -> Rejected
        job_high = job_from_naukri(
            job_id="job_exp_2",
            title="Lead RPA Developer",
            company="Tech Corp",
            location="Noida",
            required_experience_min=5,
            required_experience_max=8,
        )
        res_high = self.engine.qualify(job_high)
        self.assertFalse(res_high.accepted)
        self.assertEqual(res_high.stage, "EXPERIENCE")

    def test_experience_evaluation_masters_allowance(self):
        # Candidate has 2 years exp + Masters degree
        masters_engine = QualificationEngine(
            candidate_experience=2,
            did_masters=True,
            bad_words=[],
            negative_title_words=[],
        )

        # Job requires 4 years and mentions "Master's degree preferred" -> 2 + 2 = 4 -> Accepted
        job_with_master = job_from_linkedin(
            job_id="job_m_1",
            title="AI Automation Engineer",
            company="AventIQ AI",
            location="Delhi",
            experience_required=4,
            description="Requires 4 years experience. Master degree in Computer Science preferred.",
        )
        res1 = masters_engine.qualify(job_with_master)
        self.assertTrue(res1.accepted)

        # Job requires 4 years and does NOT mention master -> 2 + 0 < 4 -> Rejected
        job_without_master = job_from_linkedin(
            job_id="job_m_2",
            title="AI Automation Engineer",
            company="AventIQ AI",
            location="Delhi",
            experience_required=4,
            description="Requires 4 years of Python automation experience.",
        )
        res2 = masters_engine.qualify(job_without_master)
        self.assertFalse(res2.accepted)

    def test_extract_experience_bounds_regex(self):
        # Test range patterns
        self.assertEqual(extract_experience_bounds("Requires 2-5 years experience"), (2, 5))
        self.assertEqual(extract_experience_bounds("Looking for 3 to 6 Years in RPA"), (3, 6))
        self.assertEqual(extract_experience_bounds("1–3 years hands-on work"), (1, 3))

        # Test single patterns
        self.assertEqual(extract_experience_bounds("Must have 4+ years of Python"), (4, None))
        self.assertEqual(extract_experience_bounds("Minimum 2 years experience"), (2, None))

        # Test no match
    def test_qualify_job_pre_and_post_click(self):
        # Stage 1 Pre-click rejects blacklisted company or title
        bad_title_job = Job(
            platform="foundit",
            job_id="f_1",
            title="Civil Site Engineer",
            company="Tata Projects",
            location="Mumbai"
        )
        pre_res = self.engine.qualify_job_pre_click(bad_title_job)
        self.assertFalse(pre_res.accepted)
        self.assertEqual(pre_res.stage, "TITLE_FILTER")

        good_job = Job(
            platform="foundit",
            job_id="f_2",
            title="Senior RPA Developer",
            company="Tata Consulting",
            location="Bengaluru",
            description="Developing RPA bots using Python and Automation Anywhere for 2 years."
        )
        pre_res_good = self.engine.qualify_job_pre_click(good_job)
        self.assertTrue(pre_res_good.accepted)

        # Stage 2 Post-click rejects on bad words
        bad_jd_job = Job(
            platform="foundit",
            job_id="f_3",
            title="Senior RPA Developer",
            company="Tata Consulting",
            location="Bengaluru",
            description="Active Polygraph clearance required. US Citizen Only."
        )
        post_res_bad = self.engine.qualify_job_post_click(bad_jd_job)
        self.assertFalse(post_res_bad.accepted)

        # Stage 2 Post-click accepts matching JD
        post_res_good = self.engine.qualify_job_post_click(good_job)
        self.assertTrue(post_res_good.accepted)


if __name__ == "__main__":
    unittest.main()
