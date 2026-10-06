'''
Unit Tests for Naukri Search Rotation & Pagination (Phase 14)
Validates multi-term keyword rotation, multi-page progression,
early exit on zero results or missing next button, max evaluated jobs limit,
relevance decay (consecutive skips stopping rule), reset on qualification,
global application cap, and statistics tracking.
'''

import unittest
from unittest.mock import MagicMock, patch

from modules.models import Job
from modules.qualification_engine import QualificationResult
from platforms.naukri.rotator import (
    SearchRotationConfig,
    SearchRotationEngine,
    RotationStats,
    TermStats,
    RotationJobItem,
)


class TestNaukriPaginationAndRotation(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock()
        self.mock_search = MagicMock()
        self.mock_parser = MagicMock()
        self.mock_qualifier = MagicMock()
        self.mock_tracker = MagicMock()
        self.mock_applier = MagicMock()

        # Default search behavior: has next page, not zero results
        self.mock_search._is_zero_results.return_value = False
        self.mock_search.has_next_page.return_value = True

    def _create_mock_card(self, title: str, company: str, job_id: str) -> MagicMock:
        card = MagicMock()
        card.get_attribute.return_value = job_id
        return card

    def _create_mock_job(self, title: str, company: str, job_id: str) -> Job:
        return Job(
            platform="naukri",
            job_id=job_id,
            title=title,
            company=company,
            location="India",
            source_url=f"https://www.naukri.com/job-listings-{job_id}",
        )

    def test_config_from_profile(self):
        with patch("platforms.naukri.rotator.get_platform") as mock_get_plat, \
             patch("config.search._read_platform_from_db", return_value={}):
            mock_get_plat.return_value = {
                "search_terms": ["RPA Developer", "Automation Anywhere"],
                "search_location": "Delhi",
                "experience_years": 2,
                "freshness_days": 7,
                "max_pages_per_search": 2,
                "max_jobs_evaluated_per_search": 25,
                "consecutive_skips_limit": 5,
                "max_applications": 10,
                "apply_mode": "direct_only",
            }
            cfg = SearchRotationConfig.from_profile()
            self.assertEqual(cfg.search_terms, ["RPA Developer", "Automation Anywhere"])
            self.assertEqual(cfg.location, "Delhi")
            self.assertEqual(cfg.max_pages_per_search, 2)
            self.assertEqual(cfg.max_jobs_evaluated_per_search, 25)
            self.assertEqual(cfg.consecutive_skips_limit, 5)
            self.assertEqual(cfg.max_applications, 10)

    def test_multi_term_rotation(self):
        config = SearchRotationConfig(
            search_terms=["Term A", "Term B"],
            max_pages_per_search=1,
            max_jobs_evaluated_per_search=10,
            consecutive_skips_limit=10,
        )

        card_a = self._create_mock_card("Dev A", "Comp A", "id_a")
        card_b = self._create_mock_card("Dev B", "Comp B", "id_b")

        job_a = self._create_mock_job("Dev A", "Comp A", "id_a")
        job_b = self._create_mock_job("Dev B", "Comp B", "id_b")

        def search_side_effect(keyword, **kwargs):
            if keyword == "Term A":
                return [card_a]
            return [card_b]

        self.mock_search.search.side_effect = search_side_effect
        self.mock_parser.parse_card.side_effect = lambda c: job_a if c == card_a else job_b
        self.mock_qualifier.qualify.return_value = QualificationResult(accepted=True)

        engine = SearchRotationEngine(
            browser=self.mock_browser,
            config=config,
            search=self.mock_search,
            parser=self.mock_parser,
            qualification_engine=self.mock_qualifier,
            tracker=self.mock_tracker,
        )

        stats = engine.run()
        self.assertEqual(stats.terms_searched, 2)
        self.assertEqual(stats.pages_processed, 2)
        self.assertEqual(stats.jobs_evaluated, 2)
        self.assertEqual(stats.jobs_qualified, 2)
        self.assertIn("Term A", stats.term_stats)
        self.assertIn("Term B", stats.term_stats)

    def test_multi_page_progression(self):
        config = SearchRotationConfig(
            search_terms=["RPA Developer"],
            max_pages_per_search=3,
            max_jobs_evaluated_per_search=50,
            consecutive_skips_limit=10,
        )

        pages_requested = []

        def search_side_effect(keyword, page=1, **kwargs):
            pages_requested.append(page)
            card = self._create_mock_card(f"Dev {page}", f"Comp {page}", f"id_{page}")
            return [card]

        self.mock_search.search.side_effect = search_side_effect
        self.mock_parser.parse_card.side_effect = lambda c: self._create_mock_job("Dev", "Comp", "id_1")
        self.mock_qualifier.qualify.return_value = QualificationResult(accepted=True)

        engine = SearchRotationEngine(
            config=config,
            search=self.mock_search,
            parser=self.mock_parser,
            qualification_engine=self.mock_qualifier,
            tracker=self.mock_tracker,
        )

        stats = engine.run()
        self.assertEqual(pages_requested, [1, 2, 3])
        self.assertEqual(stats.pages_processed, 3)
        self.assertEqual(stats.jobs_evaluated, 3)

    def test_early_exit_zero_results(self):
        config = SearchRotationConfig(
            search_terms=["ObscureKeyword"],
            max_pages_per_search=3,
        )
        self.mock_search.search.return_value = []
        self.mock_search._is_zero_results.return_value = True

        engine = SearchRotationEngine(
            config=config,
            search=self.mock_search,
            parser=self.mock_parser,
            qualification_engine=self.mock_qualifier,
            tracker=self.mock_tracker,
        )

        stats = engine.run()
        self.assertEqual(stats.terms_searched, 1)
        self.assertEqual(stats.pages_processed, 0)
        self.assertEqual(stats.jobs_evaluated, 0)
        # Verify it stopped after page 1 attempt and didn't request pages 2 or 3
        self.assertEqual(self.mock_search.search.call_count, 1)

    def test_early_exit_no_next_page(self):
        config = SearchRotationConfig(
            search_terms=["SinglePageKeyword"],
            max_pages_per_search=5,
        )
        card = self._create_mock_card("Dev", "Comp", "id_1")
        job = self._create_mock_job("Dev", "Comp", "id_1")
        self.mock_search.search.return_value = [card]
        self.mock_parser.parse_card.return_value = job
        self.mock_qualifier.qualify.return_value = QualificationResult(accepted=True)
        # No next page button present
        self.mock_search.has_next_page.return_value = False

        engine = SearchRotationEngine(
            config=config,
            search=self.mock_search,
            parser=self.mock_parser,
            qualification_engine=self.mock_qualifier,
            tracker=self.mock_tracker,
        )

        stats = engine.run()
        self.assertEqual(stats.pages_processed, 1)
        self.assertEqual(self.mock_search.search.call_count, 1)

    def test_max_jobs_evaluated_per_search_limit(self):
        config = SearchRotationConfig(
            search_terms=["KeywordA", "KeywordB"],
            max_pages_per_search=2,
            max_jobs_evaluated_per_search=3,
        )

        # Generate 5 cards per page
        cards_a = [self._create_mock_card(f"Dev A{i}", "Comp", f"id_a_{i}") for i in range(5)]
        cards_b = [self._create_mock_card(f"Dev B{i}", "Comp", f"id_b_{i}") for i in range(5)]

        def search_side_effect(keyword, **kwargs):
            return cards_a if keyword == "KeywordA" else cards_b

        self.mock_search.search.side_effect = search_side_effect
        self.mock_parser.parse_card.side_effect = lambda c: self._create_mock_job("Dev", "Comp", "id_x")
        self.mock_qualifier.qualify.return_value = QualificationResult(accepted=True)

        engine = SearchRotationEngine(
            config=config,
            search=self.mock_search,
            parser=self.mock_parser,
            qualification_engine=self.mock_qualifier,
            tracker=self.mock_tracker,
        )

        stats = engine.run()
        self.assertEqual(stats.terms_searched, 2)
        # Both terms should halt at 3 evaluated jobs
        self.assertEqual(stats.term_stats["KeywordA"].jobs_evaluated, 3)
        self.assertTrue(stats.term_stats["KeywordA"].max_eval_triggered)
        self.assertEqual(stats.term_stats["KeywordB"].jobs_evaluated, 3)
        self.assertTrue(stats.term_stats["KeywordB"].max_eval_triggered)
        self.assertEqual(stats.jobs_evaluated, 6)

    def test_consecutive_skips_relevance_decay(self):
        config = SearchRotationConfig(
            search_terms=["KeywordWithDecay", "NextKeyword"],
            max_pages_per_search=2,
            consecutive_skips_limit=3,
        )

        cards = [self._create_mock_card(f"Dev {i}", "Comp", f"id_{i}") for i in range(6)]
        self.mock_search.search.return_value = cards
        self.mock_parser.parse_card.side_effect = lambda c: self._create_mock_job("Dev", "Comp", "id_x")

        # First keyword: all jobs fail qualification
        def qualify_side_effect(job):
            return QualificationResult(accepted=False, reason="Experience too high")

        self.mock_qualifier.qualify.side_effect = qualify_side_effect

        engine = SearchRotationEngine(
            config=config,
            search=self.mock_search,
            parser=self.mock_parser,
            qualification_engine=self.mock_qualifier,
            tracker=self.mock_tracker,
        )

        stats = engine.run()
        # For KeywordWithDecay: evaluates exactly 3 jobs, skips 3 jobs, triggers skip limit
        self.assertEqual(stats.term_stats["KeywordWithDecay"].jobs_evaluated, 3)
        self.assertEqual(stats.term_stats["KeywordWithDecay"].jobs_skipped, 3)
        self.assertTrue(stats.term_stats["KeywordWithDecay"].skip_limit_triggered)
        self.assertEqual(stats.consecutive_skips_triggered, 2)  # both terms hit skip limit

    def test_consecutive_skips_resets_on_qualification(self):
        config = SearchRotationConfig(
            search_terms=["HealthyKeyword"],
            max_pages_per_search=1,
            consecutive_skips_limit=3,
        )

        # 5 cards: Fail, Fail, Pass (reset!), Fail, Fail -> Total 4 skips, 1 qualified, never triggers 3 consecutive
        cards = [self._create_mock_card(f"Dev {i}", "Comp", f"id_{i}") for i in range(5)]
        jobs = [self._create_mock_job(f"Dev {i}", "Comp", f"id_{i}") for i in range(5)]

        self.mock_search.search.return_value = cards
        self.mock_parser.parse_card.side_effect = lambda c: jobs[cards.index(c)]

        qualification_results = [
            QualificationResult(accepted=False, reason="Bad company"),
            QualificationResult(accepted=False, reason="Bad title"),
            QualificationResult(accepted=True),  # Reset!
            QualificationResult(accepted=False, reason="Bad exp"),
            QualificationResult(accepted=False, reason="Bad location"),
        ]
        self.mock_qualifier.qualify.side_effect = qualification_results

        engine = SearchRotationEngine(
            config=config,
            search=self.mock_search,
            parser=self.mock_parser,
            qualification_engine=self.mock_qualifier,
            tracker=self.mock_tracker,
        )

        stats = engine.run()
        term_stat = stats.term_stats["HealthyKeyword"]
        self.assertEqual(term_stat.jobs_evaluated, 5)
        self.assertEqual(term_stat.jobs_skipped, 4)
        self.assertEqual(term_stat.jobs_qualified, 1)
        self.assertFalse(term_stat.skip_limit_triggered)
        self.assertEqual(stats.consecutive_skips_triggered, 0)

    def test_global_max_applications_cap(self):
        config = SearchRotationConfig(
            search_terms=["KeywordA", "KeywordB"],
            max_pages_per_search=3,
            max_applications=2,
        )

        cards = [self._create_mock_card(f"Dev {i}", "Comp", f"id_{i}") for i in range(5)]
        self.mock_search.search.return_value = cards
        self.mock_parser.parse_card.return_value = self._create_mock_job("Dev", "Comp", "id_1")
        self.mock_qualifier.qualify.return_value = QualificationResult(accepted=True)

        engine = SearchRotationEngine(
            config=config,
            search=self.mock_search,
            parser=self.mock_parser,
            qualification_engine=self.mock_qualifier,
            tracker=self.mock_tracker,
        )

        # Callback simulates successful submission
        stats = engine.run(on_qualified_job=lambda job, card: "SUBMITTED")
        self.assertEqual(stats.jobs_applied, 2)
        # Should stop before evaluating all jobs or proceeding to KeywordB
        self.assertNotIn("KeywordB", stats.term_stats)

    def test_iter_qualified_jobs_generator(self):
        config = SearchRotationConfig(
            search_terms=["Term1"],
            max_pages_per_search=1,
            consecutive_skips_limit=5,
        )

        card1 = self._create_mock_card("Dev1", "Comp1", "id_1")
        card2 = self._create_mock_card("Dev2", "Comp2", "id_2")
        job1 = self._create_mock_job("Dev1", "Comp1", "id_1")
        job2 = self._create_mock_job("Dev2", "Comp2", "id_2")

        self.mock_search.search.return_value = [card1, card2]
        self.mock_parser.parse_card.side_effect = lambda c: job1 if c == card1 else job2
        self.mock_qualifier.qualify.side_effect = [
            QualificationResult(accepted=False, reason="Unqualified title"),
            QualificationResult(accepted=True),
        ]

        engine = SearchRotationEngine(
            config=config,
            search=self.mock_search,
            parser=self.mock_parser,
            qualification_engine=self.mock_qualifier,
            tracker=self.mock_tracker,
        )

        qualified_items = list(engine.iter_qualified_jobs())
        self.assertEqual(len(qualified_items), 1)
        item = qualified_items[0]
        self.assertIsInstance(item, RotationJobItem)
        self.assertEqual(item.term, "Term1")
        self.assertEqual(item.page, 1)
        self.assertEqual(item.job.job_id, "id_2")
        self.assertEqual(item.card_element, card2)
        self.assertTrue(item.qualification.accepted)
        # Tracker should have recorded SKIPPED for job1 and QUALIFIED for job2
        self.mock_tracker.record_evaluation.assert_called_once_with(job1, "SKIPPED", skip_reason="Unqualified title")
        self.mock_tracker.record_state.assert_called_once_with(job2, "QUALIFIED")

    def test_run_with_applier_safe_apply(self):
        config = SearchRotationConfig(
            search_terms=["TermApplier"],
            max_pages_per_search=1,
        )
        card1 = self._create_mock_card("Dev1", "Comp1", "id_1")
        card2 = self._create_mock_card("Dev2", "Comp2", "id_2")
        job1 = self._create_mock_job("Dev1", "Comp1", "id_1")
        job2 = self._create_mock_job("Dev2", "Comp2", "id_2")

        self.mock_search.search.return_value = [card1, card2]
        self.mock_parser.parse_card.side_effect = lambda c: job1 if c == card1 else job2
        self.mock_qualifier.qualify.return_value = QualificationResult(accepted=True)

        engine = SearchRotationEngine(
            config=config,
            search=self.mock_search,
            parser=self.mock_parser,
            qualification_engine=self.mock_qualifier,
            tracker=self.mock_tracker,
            applier=self.mock_applier,
        )

        with patch("platforms.naukri.rotator.safe_apply_job") as mock_safe_apply:
            mock_safe_apply.side_effect = [
                {"status": "SUBMITTED", "reason": "Confirmed"},
                {"status": "MANUAL_REQUIRED", "reason": "CAPTCHA challenge"},
            ]

            stats = engine.run()
            self.assertEqual(stats.jobs_applied, 1)
            self.assertEqual(stats.jobs_manual_required, 1)
            self.assertEqual(stats.jobs_qualified, 2)
            self.assertEqual(mock_safe_apply.call_count, 2)

    def test_empty_search_terms(self):
        config = SearchRotationConfig(search_terms=[])
        engine = SearchRotationEngine(
            config=config,
            search=self.mock_search,
        )
        stats = engine.run()
        self.assertEqual(stats.terms_searched, 0)
        self.assertEqual(stats.pages_processed, 0)
        self.assertEqual(stats.jobs_evaluated, 0)


if __name__ == "__main__":
    unittest.main()
