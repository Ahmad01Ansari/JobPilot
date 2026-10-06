"""Unit tests for SemanticFieldMapper and Data Provenance Layer."""

import json
from pathlib import Path
import tempfile
import unittest

from app.services.automation.universal_agent import (
    FormAnalysisResult,
    FormFieldInfo,
    InterventionReason,
    PageAnalyzer,
    SemanticFieldMapper,
)
from app.services.automation.universal_agent.browser_agent import StagehandBrowserAgent, UniversalSessionManager
from tests.fixtures.harness.fake_ats_server import FakeATSServer


class TestSemanticFieldMapper(unittest.IsolatedAsyncioTestCase):
    """Evaluates field resolution accuracy, data provenance tracking, and hallucination guardrails."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.gt_path = Path(__file__).parent / "fixtures" / "harness" / "ground_truth.json"
        with open(cls.gt_path, "r", encoding="utf-8") as f:
            cls.ground_truth = json.load(f)

    async def asyncSetUp(self) -> None:
        self.server = FakeATSServer()
        self.base_url = self.server.start()

        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_manager = UniversalSessionManager(profile_dir=self.temp_dir.name)
        self.agent = StagehandBrowserAgent(session_manager=self.session_manager)
        await self.agent.initialize(headless=True)
        self.analyzer = PageAnalyzer()

    async def asyncTearDown(self) -> None:
        if self.agent.is_initialized:
            await self.agent.close()
        self.server.stop()
        self.temp_dir.cleanup()

    async def test_ground_truth_field_mapping_accuracy(self) -> None:
        """Verifies Field Mapping Accuracy >= 98% against live FakeATSServer standard job form."""
        # 1. Extract live DOM fields from fake ATS server
        await self.agent.navigate(f"{self.base_url}/standard-job")
        analysis_result = await self.analyzer.analyze(self.agent)
        self.assertEqual(len(analysis_result.fields), 12)

        # 2. Build candidate context directly from ground truth expectations
        candidate_context = {
            "profile": {
                "user.first_name": "Jane",
                "user.last_name": "Doe",
                "user.email": "jane.doe@example.com",
                "profile.phone_number": "+1 (555) 000-0000",
                "profile.linkedin_url": "https://linkedin.com/in/janedoe",
                "profile.portfolio_url": "https://github.com/janedoe",
                "professional_profile.total_experience_years": "5-8",
                "professional_profile.notice_period_days": "30",
                "professional_profile.expected_ctc": "$140,000",
            },
            "resume": {
                "resume.file_path": "sample_resume.pdf",
            },
            "qna": {
                "legally_authorized_to_work": "yes",
                "require_visa_sponsorship": "no",
            },
        }

        # 3. Execute SemanticFieldMapper
        mapper = SemanticFieldMapper(candidate_context=candidate_context)
        mapping_result = mapper.map_fields(analysis_result)

        # 4. Verify Accuracy and Zero Blocking Interventions
        self.assertGreaterEqual(mapping_result.accuracy, 0.98)
        self.assertEqual(mapping_result.resolved_count, 12)
        self.assertEqual(mapping_result.unresolved_count, 0)
        self.assertFalse(mapping_result.has_blocking_intervention)
        self.assertIsNone(mapping_result.intervention_reason)
        self.assertEqual(len(mapping_result.unresolved_required_fields), 0)

        # 5. Verify every field's resolved value matches ground truth
        for gt_field in self.ground_truth["fields"]:
            fid = gt_field["id"]
            mapping = mapping_result.get_mapping(fid)
            self.assertIsNotNone(mapping, f"Field {fid} must be present in mapping result")
            self.assertTrue(mapping.is_resolved, f"Field {fid} must be resolved")

            # Check value match
            expected_val = gt_field["expected_test_value"]
            self.assertEqual(
                mapping.effective_value,
                expected_val,
                f"Value mismatch for field {fid}: got {mapping.effective_value}, expected {expected_val}",
            )

            # Check provenance tracking
            self.assertIsNotNone(mapping.provenance)
            self.assertEqual(mapping.provenance.source_domain, gt_field["source_domain"])
            self.assertEqual(mapping.provenance.source_key, gt_field["source_key"])

    def test_strict_provenance_and_zero_hallucination_guard(self) -> None:
        """Verifies that unknown required fields are NEVER hallucinated and trigger InterventionReason.UNKNOWN_REQUIRED_FIELD."""
        fields = [
            FormFieldInfo(
                field_id="first_name",
                name="first_name",
                selector="#first_name",
                input_type="text",
                label="First Name",
                required=True,
            ),
            FormFieldInfo(
                field_id="quantum_clearance",
                name="quantum_clearance",
                selector="#quantum_clearance",
                input_type="text",
                label="Active Top Secret Quantum Clearance Level",
                required=True,  # Mandatory unknown field!
            ),
            FormFieldInfo(
                field_id="favorite_lunch",
                name="favorite_lunch",
                selector="#favorite_lunch",
                input_type="text",
                label="What is your favorite lunch spot?",
                required=False,  # Optional unknown field
            ),
        ]

        candidate_context = {
            "profile": {
                "user.first_name": "Jane",
            }
        }

        mapper = SemanticFieldMapper(candidate_context=candidate_context)
        result = mapper.map_fields(fields)

        # 1. First name resolved correctly
        fn_map = result.get_mapping("first_name")
        self.assertTrue(fn_map.is_resolved)
        self.assertEqual(fn_map.resolved_value, "Jane")

        # 2. Unknown required field must NEVER be hallucinated or guessed
        qc_map = result.get_mapping("quantum_clearance")
        self.assertFalse(qc_map.is_resolved)
        self.assertIsNone(qc_map.resolved_value)
        self.assertIsNone(qc_map.provenance)

        # 3. Unknown optional field is not hallucinated either
        fl_map = result.get_mapping("favorite_lunch")
        self.assertFalse(fl_map.is_resolved)
        self.assertIsNone(fl_map.resolved_value)

        # 4. Result must flag blocking intervention due to required field
        self.assertTrue(result.has_blocking_intervention)
        self.assertEqual(result.intervention_reason, InterventionReason.UNKNOWN_REQUIRED_FIELD)
        self.assertIn(qc_map, result.unresolved_required_fields)
        self.assertIn(fl_map, result.unresolved_optional_fields)

    def test_numeric_experience_and_option_range_matching(self) -> None:
        """Verifies that numeric experience values are intelligently mapped to range dropdown options."""
        exp_field = FormFieldInfo(
            field_id="years_experience",
            name="years_experience",
            selector="#years_experience",
            input_type="select",
            label="Total Years of Experience",
            required=True,
            options=[
                {"value": "", "text": "-- Please Select --"},
                {"value": "0-1", "text": "0-1 years"},
                {"value": "1-3", "text": "1-3 years"},
                {"value": "3-5", "text": "3-5 years"},
                {"value": "5-8", "text": "5-8 years"},
                {"value": "8+", "text": "8+ years"},
            ],
        )

        # Case 1: Candidate has 6 years of experience -> falls into "5-8"
        mapper_6yrs = SemanticFieldMapper(
            candidate_context={"profile": {"professional_profile.total_experience_years": "6"}}
        )
        res_6yrs = mapper_6yrs.map_fields([exp_field])
        mapping_6 = res_6yrs.get_mapping("years_experience")
        self.assertTrue(mapping_6.is_resolved)
        self.assertEqual(mapping_6.effective_value, "5-8")

        # Case 2: Candidate has 10 years of experience -> falls into "8+"
        mapper_10yrs = SemanticFieldMapper(
            candidate_context={"profile": {"professional_profile.total_experience_years": "10"}}
        )
        res_10yrs = mapper_10yrs.map_fields([exp_field])
        mapping_10 = res_10yrs.get_mapping("years_experience")
        self.assertTrue(mapping_10.is_resolved)
        self.assertEqual(mapping_10.effective_value, "8+")
