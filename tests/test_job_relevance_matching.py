import unittest
from modules.qualification_engine import QualificationEngine, is_job_relevant
from modules.models import Job


class TestJobRelevanceMatching(unittest.TestCase):
    """Verifies architectural job qualification and domain relevance matching."""

    def test_developer_searching_rejects_testing_titles(self):
        """A user searching for developer or engineering roles must not qualify testing/QA jobs."""
        testing_titles = [
            "Automation Tester_2 To 3 years _PAN India_SD",
            "Automation Tester",
            "QA Automation Engineer",
            "Senior SDET",
            "Quality Assurance Engineer",
            "Test Engineer - Automation",
            "Test Automation Engineer",
            "Senior Test Automation Engineer",
        ]
        dev_search_terms = [
            "Automation Anywhere Developer",
            "RPA Developer",
            "Automation Engineer",
            "Python Automation",
        ]
        for term in dev_search_terms:
            for title in testing_titles:
                self.assertFalse(
                    is_job_relevant(title, term),
                    f"Search term '{term}' should reject testing title '{title}'",
                )

    def test_qa_user_searching_accepts_testing_titles(self):
        """A QA/testing candidate searching for testing roles must successfully qualify testing jobs."""
        qa_core = ["qa", "tester", "selenium", "automation testing"]
        self.assertTrue(
            is_job_relevant(
                "Automation Tester_2 To 3 years _PAN India_SD",
                "Automation Tester",
                core_skills=qa_core,
            )
        )
        self.assertTrue(
            is_job_relevant(
                "Senior QA Automation Engineer",
                "QA Automation",
                core_skills=qa_core,
            )
        )
        self.assertTrue(
            is_job_relevant(
                "SDET - Software Development Engineer in Test",
                "SDET",
                core_skills=qa_core,
            )
        )

    def test_delimiter_tolerance_in_job_titles(self):
        """Titles with underscores, slashes, or hyphens must respect word boundaries."""
        neg_words = ["tester", "qa", "android"]
        # Underscore delimited
        self.assertFalse(
            is_job_relevant(
                "Automation Tester_2 To 3 years _PAN India_SD",
                "Automation Anywhere Developer",
                negative_words=neg_words,
            )
        )
        # Slash delimited
        self.assertFalse(
            is_job_relevant(
                "Automation/Tester/Pune",
                "Automation Anywhere Developer",
                negative_words=neg_words,
            )
        )

    def test_rpa_developer_valid_relevance(self):
        """Legitimate RPA and software engineering titles must match target search terms."""
        core_skills = ["rpa", "automation anywhere", "python", "automation"]
        self.assertTrue(
            is_job_relevant(
                "RPA Developer - Automation Anywhere",
                "Automation Anywhere Developer",
                core_skills=core_skills,
            )
        )
        self.assertTrue(
            is_job_relevant(
                "Senior RPA Developer (UiPath / Automation Anywhere)",
                "Automation Anywhere Developer",
                core_skills=core_skills,
            )
        )
        self.assertTrue(
            is_job_relevant(
                "Python Automation Engineer",
                "Automation Engineer",
                core_skills=core_skills,
            )
        )

    def test_qualification_engine_negative_title_filtering(self):
        """QualificationEngine fast filter rejects negative title words even with underscore delimiters."""
        engine = QualificationEngine(
            core_skills=["rpa", "python"],
            negative_title_words=["tester", "qa", "sdet"],
        )
        res = engine.qualify_title(
            title="Automation Tester_2 To 3 years _PAN India_SD",
            company="Infosys",
        )
        self.assertFalse(res.accepted)
        self.assertEqual(res.stage, "TITLE_FILTER")
        self.assertIn("tester", res.reason)


    def test_hardware_and_cad_rejection(self):
        """Industrial, CAD, PLC, and SPM machine automation roles must be rejected for software candidates."""
        engine = QualificationEngine(
            core_skills=["rpa", "automation", "python", "automation anywhere"],
            negative_title_words=["plc", "cad", "spm", "scada"],
        )
        cad_res = engine.qualify_title("Cad Automation Engineer", "Sunbrilo Technology")
        self.assertFalse(cad_res.accepted)

        plc_res = engine.qualify_title("Automation Engineer (PLC Programming _ SPM Machines)", "Prodesta")
        self.assertFalse(plc_res.accepted)

        self.assertFalse(
            is_job_relevant(
                "Cad Automation Engineer",
                "Automation Engineer",
                core_skills=engine.core_skills,
                negative_words=engine.negative_title_words,
            )
        )
        self.assertFalse(
            is_job_relevant(
                "Automation Engineer (PLC Programming _ SPM Machines)",
                "Automation Engineer",
                core_skills=engine.core_skills,
                negative_words=engine.negative_title_words,
            )
        )


if __name__ == "__main__":
    unittest.main()

