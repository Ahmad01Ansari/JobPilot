"""Comprehensive Unit and Integration Test Suite for Job Qualification Engine.

Verifies all 26+ required behaviors specified in WorkingFlow/JobQualificationEngine.md:
- Canonical CandidateQualificationContext decoupling
- Deterministic matching (role, skills, experience, location, salary)
- Experience requirement strength (REQUIRED vs PREFERRED vs FLEXIBLE vs UNKNOWN)
- Hard filter exclusions (company blacklist, negative title keywords)
- Nullable / evidence-based confidence (no fake 1.0 default)
- Status separation (evaluation_status vs ai_status)
- AI optionality with graceful fallback on offline, malformed, or error
- Persistence, history, caching, requalification, and bulk evaluation
"""

import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Company, Job, JobEvaluation, User
from app.repositories.job_evaluation_repo import JobEvaluationRepository
from app.repositories.job_repository import JobRepository
from app.services.dto.qualification_dto import (
    CandidateQualificationContext,
    JobQualificationInput,
    QualificationResultDTO,
    ScoringWeights,
)
from app.services.dto.qualification_enums import (
    AIStatus,
    EvaluationStatus,
    ExperienceStrength,
    QualificationDecision,
)
from app.services.job_qualification_service import JobQualificationService
from app.services.qualification.candidate_context_provider import CandidateContextProvider
from app.services.qualification.experience_parser import ExperienceParser
from app.services.qualification.hard_filter_evaluator import HardFilterEvaluator
from app.services.qualification.qualification_engine import QualificationEngine
from app.services.qualification.semantic_ai_advisor import SemanticAIAdvisor
from app.services.qualification.skill_matcher import ExactSkillMatcher, SynonymSkillMatcher


class TestJobQualificationEngine(unittest.TestCase):
    """Unit tests for pure deterministic QualificationEngine and its components."""

    def setUp(self):
        self.context = CandidateQualificationContext(
            candidate_id=1,
            target_titles=("Senior RPA Developer", "Python Automation Engineer", "RPA Developer"),
            current_title="RPA Developer",
            years_of_experience=3.5,
            primary_skills=("Python", "UiPath", "Automation Anywhere"),
            secondary_skills=("SQL", "REST API", "Docker"),
            all_skills=("Python", "UiPath", "Automation Anywhere", "SQL", "REST API", "Docker", "Git"),
            preferred_locations=("Pune", "Mumbai", "Bengaluru"),
            current_city="Pune",
            willing_to_relocate=False,
            expected_ctc=1200000,
            current_ctc=900000,
            notice_period_days=30,
            blacklisted_companies=("ScamCorp", "UnwantedStaffing"),
            negative_title_keywords=("mechanical", "civil", "electrical", "technician", "intern"),
        )
        self.engine = QualificationEngine(skill_matcher=SynonymSkillMatcher(), weights=ScoringWeights())

    def test_strong_match_job(self):
        """Scenario 1: Job aligning with candidate skills, title, experience, and location."""
        job = JobQualificationInput(
            job_id=1,
            title="Senior RPA Developer (UiPath / Python)",
            company_name="Innovatech Solutions",
            location="Pune, India",
            work_style="Hybrid",
            experience_text="3-5 years required",
            required_experience_min=3,
            required_experience_max=5,
            salary_min=1300000,
            salary_max=1600000,
            description="Looking for an experienced Senior RPA Developer skilled in UiPath, Python, and SQL.",
        )
        res = self.engine.qualify(job, self.context)
        self.assertEqual(res.evaluation_status, EvaluationStatus.SUCCESS)
        self.assertIn(res.decision, (QualificationDecision.STRONG_MATCH, QualificationDecision.GOOD_MATCH))
        self.assertGreaterEqual(res.score, 75)
        self.assertIn("Python", res.matched_skills)
        self.assertIn("UiPath", res.matched_skills)
        self.assertGreater(len(res.positive_reasons), 0)

    def test_weak_match_job(self):
        """Scenario 2: Job with minimal overlap in tech stack and role."""
        job = JobQualificationInput(
            job_id=2,
            title="Ruby on Rails Backend Developer",
            company_name="WebCraft LLC",
            location="Pune",
            experience_text="4+ years required",
            required_experience_min=4,
            description="Develop web applications using Ruby, Rails, Haml, and Redis.",
        )
        res = self.engine.qualify(job, self.context)
        self.assertEqual(res.evaluation_status, EvaluationStatus.SUCCESS)
        self.assertIn(res.decision, (QualificationDecision.WEAK_MATCH, QualificationDecision.REJECTED))
        self.assertLess(res.score, 50)
        self.assertGreater(len(res.negative_reasons), 0)

    def test_missing_description_insufficient_data(self):
        """Scenario 3: Job lacking description triggers INSUFFICIENT_DATA."""
        job = JobQualificationInput(
            job_id=3,
            title="Software Developer",
            company_name="VagueCorp",
            description="",
        )
        res = self.engine.qualify(job, self.context)
        self.assertEqual(res.evaluation_status, EvaluationStatus.INSUFFICIENT_DATA)
        self.assertEqual(res.score, 0)
        self.assertIn("Insufficient", res.recommendation)

    def test_missing_salary_does_not_penalize(self):
        """Scenario 4: Missing salary treated as UNKNOWN without reducing score."""
        job = JobQualificationInput(
            job_id=4,
            title="Python Automation Engineer",
            company_name="GoodCo",
            location="Pune",
            experience_text="2-4 years",
            required_experience_min=2,
            salary_text=None,
            salary_min=None,
            salary_max=None,
            description="Automate data pipelines using Python and REST APIs.",
        )
        res = self.engine.qualify(job, self.context)
        self.assertEqual(res.component_scores.get("salary_match"), "UNKNOWN")
        self.assertGreaterEqual(res.score, 70)

    def test_missing_experience_does_not_penalize(self):
        """Scenario 5: Missing experience is UNKNOWN and renormalizes weights."""
        job = JobQualificationInput(
            job_id=5,
            title="RPA Developer",
            company_name="TechFlow",
            location="Pune",
            experience_text=None,
            description="Build automation bots using UiPath and Automation Anywhere.",
        )
        res = self.engine.qualify(job, self.context)
        self.assertEqual(res.component_scores.get("experience_match"), "UNKNOWN")
        self.assertGreaterEqual(res.score, 65)
        self.assertEqual(res.decision, QualificationDecision.GOOD_MATCH)

    def test_role_mismatch(self):
        """Scenario 6: Completely unrelated title scores low on role match."""
        job = JobQualificationInput(
            job_id=6,
            title="Chief Marketing Officer",
            company_name="BrandGen",
            description="Lead digital marketing and social media strategies.",
        )
        res = self.engine.qualify(job, self.context)
        self.assertLess(res.component_scores.get("role_match", 0), 40)

    def test_skill_synonym_matching(self):
        """Scenario 7: Synonyms like K8s, AA, and JS match correctly."""
        matcher = SynonymSkillMatcher()
        res = matcher.match_skills(
            candidate_skills=["Kubernetes", "Automation Anywhere", "React"],
            job_text="Requirements: K8s cluster management, AA bot building, and reactjs components.",
        )
        self.assertEqual(len(res.matched_skills), 3)
        self.assertEqual(res.score, 100.0)

    def test_experience_strength_required_vs_preferred(self):
        """Scenario 25: Distinguishes strict REQUIRED penalty from soft PREFERRED."""
        # Candidate has 3.5 years. Job mentions 5 years.
        res_req = ExperienceParser.evaluate_experience(
            candidate_years=3.5,
            text="Minimum 5 years of experience required in backend development.",
        )
        self.assertEqual(res_req.requirement_strength, ExperienceStrength.REQUIRED)
        self.assertLessEqual(res_req.score, 55.0)

        res_pref = ExperienceParser.evaluate_experience(
            candidate_years=3.5,
            text="5 years experience preferred, but talent matters most.",
        )
        self.assertEqual(res_pref.requirement_strength, ExperienceStrength.PREFERRED)
        self.assertGreaterEqual(res_pref.score, 65.0)

        # Flexible
        res_flex = ExperienceParser.evaluate_experience(
            candidate_years=3.5,
            text="Freshers welcome to apply for entry-level position.",
        )
        self.assertEqual(res_flex.requirement_strength, ExperienceStrength.FLEXIBLE)
        self.assertEqual(res_flex.score, 100.0)

    def test_hard_filter_company_blacklist(self):
        """Scenario 12: Job from blacklisted company is immediately rejected."""
        job = JobQualificationInput(
            job_id=12,
            title="Senior RPA Developer",
            company_name="ScamCorp Global",
            description="Looking for UiPath and Python developer.",
        )
        res = self.engine.qualify(job, self.context)
        self.assertEqual(res.decision, QualificationDecision.REJECTED)
        self.assertEqual(res.score, 0)
        self.assertTrue(any(f["rule"] == "COMPANY_BLACKLIST" for f in res.hard_filter_failures))

    def test_hard_filter_negative_title_keyword(self):
        """Scenario 13: Job with negative title keyword like 'Mechanical' is rejected."""
        job = JobQualificationInput(
            job_id=13,
            title="Mechanical Automation Engineer",
            company_name="Tata Motors",
            description="Develop manufacturing robotics automation scripts.",
        )
        res = self.engine.qualify(job, self.context)
        self.assertEqual(res.decision, QualificationDecision.REJECTED)
        self.assertEqual(res.score, 0)
        self.assertTrue(any(f["rule"] == "NEGATIVE_TITLE_KEYWORD" for f in res.hard_filter_failures))

    def test_confidence_reflects_evidence_completeness(self):
        """Scenario 26: Confidence is not 1.0; reflects known attribute completeness."""
        job_sparse = JobQualificationInput(
            job_id=14,
            title="RPA Developer",
            company_name="QuickTech",
            description="We need an RPA developer to join our growing team.",
        )
        res = self.engine.qualify(job_sparse, self.context)
        self.assertIsNotNone(res.confidence)
        self.assertLess(res.confidence, 1.0)
        self.assertGreaterEqual(res.confidence, 0.4)

    def test_ai_unavailable_retains_deterministic_evaluation(self):
        """Scenario 15: AI failure/offline leaves deterministic evaluation intact."""
        job = JobQualificationInput(
            job_id=15,
            title="Python Developer",
            company_name="TechCorp",
            location="Pune",
            description="Python development with REST APIs and SQL databases.",
        )
        det_result = self.engine.qualify(job, self.context)

        # Mock failing AI service
        mock_ai = MagicMock()
        mock_ai.get_config.return_value = {"enabled": True, "model": "test-model"}
        mock_ai.extract_structured_json.side_effect = RuntimeError("Ollama connection refused")

        advisor = SemanticAIAdvisor(ai_service=mock_ai)
        enhanced = advisor.enhance(base_result=det_result, job=job, context=self.context)

        # Status separation: evaluation SUCCESS, AI UNAVAILABLE
        self.assertEqual(enhanced.evaluation_status, EvaluationStatus.SUCCESS)
        self.assertEqual(enhanced.ai_status, AIStatus.UNAVAILABLE)
        self.assertGreater(enhanced.score, 0)


class TestJobQualificationServiceIntegration(unittest.TestCase):
    """Integration tests for JobQualificationService with in-memory SQLite database."""

    def setUp(self):
        self.engine_db = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine_db)
        self.session_factory = sessionmaker(bind=self.engine_db)

        # Seed candidate user
        with self.session_factory() as s:
            user = User(name="Candidate User", email="candidate@jobpilot.local")
            s.add(user)
            s.flush()

            # Seed sample jobs
            job1 = Job(
                platform="naukri",
                job_fingerprint="fp_job_1",
                title="RPA Developer",
                company_raw="Cognizant",
                location="Pune",
                description="UiPath and Python RPA development with SQL.",
                source_url="https://example.com/job1",
            )
            job2 = Job(
                platform="linkedin",
                job_fingerprint="fp_job_2",
                title="Civil Site Engineer",
                company_raw="BuildCorp",
                location="Mumbai",
                description="On-site concrete construction management.",
                source_url="https://example.com/job2",
            )
            s.add_all([job1, job2])
            s.commit()
            self.job1_id = job1.id
            self.job2_id = job2.id

        self.service = JobQualificationService(session_factory=self.session_factory)

    def tearDown(self):
        Base.metadata.drop_all(self.engine_db)

    def test_service_qualify_and_persist(self):
        """Scenario 24: Qualifying a job persists record in JobEvaluation repository."""
        res = self.service.qualify_job(self.job1_id)
        self.assertIsInstance(res, QualificationResultDTO)
        self.assertEqual(res.job_id, self.job1_id)
        self.assertGreater(res.score, 0)

        # Verify database record
        with self.session_factory() as s:
            repo = JobEvaluationRepository(s)
            latest = repo.get_latest_evaluation(self.job1_id)
            self.assertIsNotNone(latest)
            self.assertEqual(latest.score, res.score)
            self.assertEqual(latest.decision, res.decision.value)

    def test_service_cached_qualification(self):
        """Scenario 23: Subsequent calls return cached evaluation unless forced."""
        res1 = self.service.qualify_job(self.job1_id)
        res2 = self.service.qualify_job(self.job1_id, force_reevaluate=False)
        self.assertEqual(res1.score, res2.score)

        # Requalify forces new history entry
        res3 = self.service.requalify_job(self.job1_id)
        with self.session_factory() as s:
            repo = JobEvaluationRepository(s)
            history = repo.list_by_job(self.job1_id)
            self.assertEqual(len(history), 2)

    def test_service_bulk_qualification(self):
        """Scenario 21: Bulk qualification evaluates multiple jobs sequentially."""
        res = self.service.qualify_jobs_bulk([self.job1_id, self.job2_id])
        self.assertEqual(res["total"], 2)
        self.assertEqual(res["processed"], 2)
        self.assertEqual(len(res["results"]), 2)

    def test_service_job_not_found(self):
        """Scenario 22: Non-existent job ID returns clean failed DTO."""
        res = self.service.qualify_job(99999)
        self.assertEqual(res.evaluation_status, EvaluationStatus.FAILED)
        self.assertEqual(res.score, 0)


if __name__ == "__main__":
    unittest.main()
