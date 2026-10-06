"""Unit and integration test suite for Universal Global Search Engine and Providers."""

import os
import shutil
import tempfile
import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, utc_now
from app.db.models import Application, Company, Contact, FollowUp, Interview, Job, QnAEntry, Resume, User
from app.db.session import configure_sqlite_pragmas
from app.services.search.global_search_service import GlobalSearchService, build_default_provider_registry
from app.services.search.providers.application_provider import ApplicationSearchProvider
from app.services.search.providers.company_provider import CompanySearchProvider
from app.services.search.providers.contact_provider import ContactSearchProvider
from app.services.search.providers.job_provider import JobSearchProvider
from app.services.search.ranking import calculate_relevance_score, normalize_query
from app.services.search.search_provider import SearchProviderRegistry
from app.services.search.search_result import NavigationAction, SearchResult


class TestUniversalSearchRanking(unittest.TestCase):
    """Verifies deterministic search ranking and token normalization."""

    def test_normalize_query_strips_punctuation_and_lowercases(self):
        lowered, tokens = normalize_query("  Senior, Python/Go Developer! #123  ")
        self.assertEqual(lowered, "senior, python/go developer! #123")
        self.assertIn("senior", tokens)
        self.assertIn("python", tokens)
        self.assertIn("go", tokens)
        self.assertIn("developer", tokens)
        self.assertIn("123", tokens)

    def test_ranking_exact_id_scores_highest(self):
        score, matches = calculate_relevance_score(
            raw_query="JOB-42",
            tokens=["job", "42"],
            entity_id=42,
            primary_text="Software Engineer",
            secondary_text="Acme Corp",
            prefix_tags=["job"],
        )
        self.assertEqual(score, 100.0)
        self.assertIn("id_prefix", matches)

    def test_ranking_exact_title_match(self):
        score, matches = calculate_relevance_score(
            raw_query="Staff Python Engineer",
            tokens=["staff", "python", "engineer"],
            entity_id=1,
            primary_text="Staff Python Engineer",
            secondary_text="Google",
        )
        self.assertGreaterEqual(score, 95.0)
        self.assertIn("primary_exact", matches)

    def test_ranking_title_prefix_match(self):
        score, matches = calculate_relevance_score(
            raw_query="Senior",
            tokens=["senior"],
            entity_id=2,
            primary_text="Senior Frontend Developer",
            secondary_text="Meta",
        )
        self.assertGreaterEqual(score, 85.0)
        self.assertIn("primary_prefix", matches)

    def test_ranking_company_secondary_match(self):
        score, matches = calculate_relevance_score(
            raw_query="Stripe",
            tokens=["stripe"],
            entity_id=3,
            primary_text="Backend Architect",
            secondary_text="Stripe",
        )
        self.assertGreaterEqual(score, 65.0)
        self.assertIn("secondary_exact", matches)


class TestProviderRegistry(unittest.TestCase):
    """Verifies registry registration, aliases, and lookups."""

    def test_default_registry_has_all_10_providers(self):
        reg = build_default_provider_registry()
        providers = reg.list_providers()
        keys = [p.category_key for p in providers]
        self.assertIn("jobs", keys)
        self.assertIn("applications", keys)
        self.assertIn("companies", keys)
        self.assertIn("contacts", keys)
        self.assertIn("interviews", keys)
        self.assertIn("followups", keys)
        self.assertIn("outreach", keys)
        self.assertIn("resumes", keys)
        self.assertIn("qna", keys)
        self.assertIn("platforms", keys)

    def test_registry_case_insensitive_lookup(self):
        reg = build_default_provider_registry()
        p1 = reg.get_provider("JOBS")
        p2 = reg.get_provider("jobs")
        self.assertIsNotNone(p1)
        self.assertEqual(p1, p2)


class TestGlobalSearchServiceIntegration(unittest.TestCase):
    """Integration test suite executing multi-entity queries against SQLite."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "search_test.db")
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
        self._seed_test_data()
        self.service = GlobalSearchService(session_factory=self.Session)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _seed_test_data(self):
        with self.Session() as session:
            # Seed User
            user = User(name="Alex Candidate", email="alex@apply-and-pray.local")
            session.add(user)
            session.flush()

            # Seed Jobs
            job1 = Job(
                title="Staff Backend Engineer (Python)",
                company_raw="Netflix",
                platform="linkedin",
                source_url="https://linkedin.com/jobs/view/101",
                location="Los Gatos, CA",
                job_fingerprint="fp1",
            )
            job2 = Job(
                title="React Frontend Specialist",
                company_raw="Airbnb",
                platform="naukri",
                source_url="https://naukri.com/job/202",
                location="Remote",
                job_fingerprint="fp2",
            )
            session.add_all([job1, job2])
            session.flush()

            # Seed Application
            app1 = Application(
                job_id=job1.id,
                status="INTERVIEWING",
            )
            session.add(app1)
            session.flush()

            # Seed Company
            comp1 = Company(
                name="Netflix",
                normalized_name="netflix",
                website="https://netflix.com",
                industry="Entertainment",
            )
            session.add(comp1)
            session.flush()

            # Seed Contact
            contact1 = Contact(
                company_id=comp1.id,
                name="Sarah Recruiter",
                email="sarah@netflix.com",
                designation="Talent Lead",
            )
            session.add(contact1)

            # Seed Interview
            iv1 = Interview(
                application_id=app1.id,
                round_number=1,
                round_name="Technical Screen",
                scheduled_at=utc_now(),
                interviewer="Jane Architect",
                status="SCHEDULED",
                mode="GOOGLE_MEET",
                meeting_link="https://meet.google.com/abc-defg-hij",
            )
            session.add(iv1)

            # Seed FollowUp
            fu1 = FollowUp(
                application_id=app1.id,
                due_at=utc_now(),
                status="PENDING",
                notes="Check in with Sarah regarding take-home feedback",
            )
            session.add(fu1)

            # Seed Resume
            res1 = Resume(
                user_id=user.id,
                name="Python Backend 2026",
                role_target="Backend Engineer",
                file_path="/tmp/resume.pdf",
                file_hash="dummyhash12345",
                version="2.0",
                is_default=True,
            )
            session.add(res1)

            # Seed QnA
            qna1 = QnAEntry(
                question_text="Why do you want to work at Netflix?",
                normalized_question="why do you want to work at netflix?",
                answer_text="I love high-scale streaming architectures and the Freedom & Responsibility culture.",
                category="culture",
                source="USER_CURATED",
                is_active=True,
            )
            session.add(qna1)

            session.commit()

    def test_search_exact_job_id_prefix(self):
        batch = self.service.search("JOB-1")
        self.assertGreaterEqual(batch.total_count, 1)
        top = batch.items[0]
        self.assertEqual(top.entity_type, "job")
        self.assertEqual(top.entity_id, 1)
        self.assertEqual(top.score, 100.0)

    def test_search_company_name_across_multiple_entities(self):
        batch = self.service.search("Netflix")
        self.assertGreater(batch.total_count, 1)
        # Should match Job, Company, Contact, QnA
        types = {item.entity_type for item in batch.items}
        self.assertIn("job", types)
        self.assertIn("company", types)

    def test_search_category_filter_isolation(self):
        batch = self.service.search("Netflix", category="companies")
        self.assertEqual(batch.total_count, 1)
        self.assertEqual(batch.items[0].entity_type, "company")
        self.assertEqual(batch.items[0].title, "Netflix")

    def test_search_resume_by_role_target(self):
        batch = self.service.search("Backend Engineer", category="resumes")
        self.assertGreaterEqual(batch.total_count, 1)
        res = batch.items[0]
        self.assertEqual(res.entity_type, "resume")
        self.assertIn("Backend", res.title)

    def test_search_empty_query_returns_zero_items(self):
        batch = self.service.search("   ")
        self.assertEqual(batch.total_count, 0)
        self.assertEqual(len(batch.items), 0)

    def test_search_request_id_passed_through(self):
        batch = self.service.search("Python", request_id=42)
        self.assertEqual(batch.request_id, 42)


class TestGlobalSearchDialogUI(unittest.TestCase):
    """Verifies GlobalSearchDialog sizing, category chips, and multi-category grouping."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_dimensions_and_chips(self):
        from app.ui.widgets.search_dialog import GlobalSearchDialog
        dialog = GlobalSearchDialog()
        self.assertGreaterEqual(dialog.width(), 800)
        self.assertGreaterEqual(dialog.height(), 480)
        self.assertEqual(len(dialog.cat_buttons), 10)
        self.assertIn("all", dialog.cat_buttons)
        self.assertIn("jobs", dialog.cat_buttons)
        self.assertIn("applications", dialog.cat_buttons)

    def test_all_category_results_rendering_without_crash(self):
        from app.ui.widgets.search_dialog import GlobalSearchDialog
        from app.services.search.search_result import GlobalSearchBatch, SearchResult

        dialog = GlobalSearchDialog()
        dialog.active_category = "all"

        item1 = SearchResult(
            entity_type="job",
            entity_id=1,
            category="Jobs",
            title="Software Engineer",
            subtitle="Acme • Remote",
            route="jobs",
            action="filter",
        )
        item2 = SearchResult(
            entity_type="application",
            entity_id=2,
            category="Applications",
            title="Product Manager",
            subtitle="Google • Submitted",
            route="applications",
            action="filter",
        )

        batch = GlobalSearchBatch(
            query="engineer",
            total_count=2,
            items=[item1, item2],
            categories={"jobs": 1, "applications": 1},
            request_id=1,
        )

        # Should render 2 section headers + 2 items without raising TypeError
        dialog._current_request_id = 1
        dialog._on_results_ready(1, batch)
        self.assertGreaterEqual(dialog.results_list.count(), 2)


if __name__ == "__main__":
    unittest.main()
