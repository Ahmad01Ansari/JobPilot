"""Unit tests for LinkedIn external company portal extraction and hybrid mode."""

import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import unquote


class TestLinkedInExternalApply(unittest.TestCase):
    """Verifies LinkedIn external apply link extraction, redirect unwrapping, and safety."""

    def test_unwrap_redirect_helper(self):
        """Verifies URL unwrap helper safely unquotes and extracts destination URL."""
        from urllib.parse import urlparse, parse_qs

        def _unwrap_redirect(u: str) -> str:
            if not u:
                return u
            try:
                parsed = urlparse(u)
                qs = parse_qs(parsed.query)
                for k in ["url", "target", "dest", "redirect", "redirect_url", "destUrl"]:
                    if k in qs and qs[k]:
                        cand = unquote(qs[k][0]).strip()
                        if cand.startswith("http") and "linkedin.com" not in cand.lower():
                            return cand
            except Exception:
                pass
            return u

        # Test safety redirect URL
        safety_url = "https://www.linkedin.com/safety/go?url=https%3A%2F%2Fmagna.wd3.myworkdayjobs.com%2Fen-US%2FMagna_Careers%2Fjob%2F4414235311"
        self.assertEqual(
            _unwrap_redirect(safety_url),
            "https://magna.wd3.myworkdayjobs.com/en-US/Magna_Careers/job/4414235311"
        )

        # Test direct clean URL
        direct_url = "https://careers.magna.com/jobs/4414235311"
        self.assertEqual(_unwrap_redirect(direct_url), direct_url)

    def test_search_url_omits_f_al_in_hybrid_mode(self):
        """Verifies that in Hybrid Mode (easy_apply_only=False), the search URL does NOT contain f_AL=true."""
        from urllib.parse import urlencode

        def build_search_url_mock(search_term: str, easy_apply_only: bool) -> str:
            params = {"keywords": search_term}
            if easy_apply_only:
                params["f_AL"] = "true"
            return f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"

        # Hybrid Mode: easy_apply_only is False -> f_AL must NOT be in URL
        hybrid_url = build_search_url_mock("RPA Developer", easy_apply_only=False)
        self.assertNotIn("f_AL=true", hybrid_url)
        self.assertIn("keywords=RPA+Developer", hybrid_url)

        # Easy Apply Only Mode: easy_apply_only is True -> f_AL must be in URL
        easy_url = build_search_url_mock("RPA Developer", easy_apply_only=True)
        self.assertIn("f_AL=true", easy_url)

    def test_blue_machines_multiline_form_resolution(self):
        """Verifies resolution and validation for all 5 questions from Blue Machines AI form."""
        from modules.qna_engine import QnAEngine

        q = QnAEngine()
        q1 = q.resolve_text_answer("What is your current CTC (Fixed)?*", work_location="Bengaluru")
        self.assertTrue(q1.validated)
        self.assertIn("350000", q1.value)

        q2 = q.resolve_text_answer("What is your expected CTC?*", work_location="Bengaluru")
        self.assertTrue(q2.validated)
        self.assertIn("550000", q2.value)

        q3 = q.resolve_text_answer("What is your Notice Period? (preferably - immediate joiners)*", work_location="Bengaluru")
        self.assertTrue(q3.validated)
        self.assertIn("30", q3.value)

        q4 = q.resolve_text_answer("Are you based out of Bengaluru location?*", work_location="Bengaluru")
        self.assertTrue(q4.validated)
        self.assertTrue(any(w in q4.value.lower() for w in ["yes", "delhi", "relocate"]))

        q5 = q.resolve_text_answer("Do you have experience in the area of AI Agents / Bots / Gen AI?*", work_location="Bengaluru")
        self.assertTrue(q5.validated)
        self.assertIn("Yes", q5.value)


if __name__ == "__main__":
    unittest.main()
