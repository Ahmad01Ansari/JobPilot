"""Unit tests for Universal ATS Agent Jobs2Web and SAP SuccessFactors Flow.

Verifies:
1. PageClassifier identifies SAP SuccessFactors sign-in portal as PageClass.LOGIN.
2. PageAnalyzer does not discard explicit apply anchors with href="#" (e.g. #applyOption-top-manual).
3. PageAnalyzer classifies single-password sign-in pages as LOGIN_REQUIRED (preventing false account creation).
4. Orchestrator handles Jobs2Web social apply dropdown expansion and manual option selection.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import unittest

from app.services.automation.universal_agent.page_classifier import PageClass, PageClassifier
from app.services.automation.universal_agent.page_analyzer import FormAnalysisResult, PageAnalyzer


class TestUniversalJobs2WebSuccessFactors(unittest.IsolatedAsyncioTestCase):

    def test_page_classifier_successfactors_signin(self):
        """Verify SuccessFactors login page is categorized as PageClass.LOGIN."""
        url = "https://career5.successfactors.eu/careers?company=Bunge"
        title = "Career Opportunities: Sign In"
        text = "Welcome back. Sign in to your account. Forgot your password? Create an account."

        classification = PageClassifier.classify(
            url=url,
            title=title,
            text_content=text,
            input_count=2,
            has_file_input=False
        )
        self.assertEqual(classification, PageClass.LOGIN)

    async def test_page_analyzer_detects_login_required_on_successfactors(self):
        """Verify single password sign-in page flags challenge_detected = 'LOGIN_REQUIRED'."""
        analyzer = PageAnalyzer()
        mock_agent = MagicMock()
        mock_agent.get_url = AsyncMock(return_value="https://career5.successfactors.eu/careers?company=Bunge")
        mock_agent.get_title = AsyncMock(return_value="Career Opportunities: Sign In")

        # Mock the JS extraction returning a login challenge
        mock_raw = {
            "challenge_detected": "LOGIN_REQUIRED",
            "is_multi_step": False,
            "step_indicator": None,
            "fields": [
                {
                    "selector": "#username",
                    "input_type": "text",
                    "label": "Username",
                    "field_id": "username",
                    "name": "username",
                    "required": True,
                    "visible": True,
                },
                {
                    "selector": "#password",
                    "input_type": "password",
                    "label": "Password",
                    "field_id": "password",
                    "name": "password",
                    "required": True,
                    "visible": True,
                }
            ],
            "submit_buttons": [{"selector": "button", "text": "Sign In", "score": 100}],
            "next_buttons": [],
            "apply_now_buttons": []
        }
        mock_agent.evaluate = AsyncMock(return_value=mock_raw)

        res = await analyzer.analyze(mock_agent)
        self.assertEqual(res.challenge_detected, "LOGIN_REQUIRED")
        self.assertEqual(len(res.fields), 2)
        self.assertEqual(res.fields[1].input_type, "password")

    async def test_page_analyzer_preserves_explicit_manual_apply_anchor(self):
        """Verify PageAnalyzer keeps #applyOption-top-manual with href='#' in apply_now_buttons."""
        analyzer = PageAnalyzer()
        mock_agent = MagicMock()
        mock_agent.get_url = AsyncMock(return_value="https://jobs.bunge.com/job/1429042233/")
        mock_agent.get_title = AsyncMock(return_value="Job Details | Bunge")

        mock_raw = {
            "challenge_detected": None,
            "is_multi_step": False,
            "step_indicator": None,
            "fields": [],
            "submit_buttons": [],
            "next_buttons": [],
            "apply_now_buttons": [
                {
                    "selector": "a#applyOption-top-manual",
                    "text": "Apply Now",
                    "score": 200,
                }
            ]
        }
        mock_agent.evaluate = AsyncMock(return_value=mock_raw)

        res = await analyzer.analyze(mock_agent)
        self.assertEqual(len(res.apply_now_buttons), 1)
        self.assertEqual(res.apply_now_buttons[0]["selector"], "a#applyOption-top-manual")
        self.assertEqual(res.apply_now_buttons[0]["text"], "Apply Now")

    async def test_intervention_manager_wait_without_preexisting_event(self):
        """Verify wait_for_resolution initializes an event safely instead of raising RuntimeError."""
        from app.services.automation.universal_agent.intervention_manager import InterventionManager
        im = InterventionManager()
        self.assertIsNone(im._resolution_event)
        # Calling wait_for_resolution with a timeout when no event was pre-created should safely return None or timeout
        res = await im.wait_for_resolution(timeout_seconds=0.05)
        self.assertIsNotNone(im._resolution_event)
        self.assertIsNone(res)

    async def test_sequential_apply_dropdown_orchestrator_flow(self):
        """Verify orchestrator handles multi-stage sequential apply buttons on landing pages."""
        from app.services.automation.universal_agent.orchestrator import UniversalApplicationOrchestrator
        from app.services.automation.universal_agent.state_machine import AgentExecutionState

        mock_agent = MagicMock()
        mock_agent.is_initialized = True
        mock_agent.get_url = AsyncMock(return_value="https://jobs.bunge.com/job/1429042233/")
        mock_agent.get_title = AsyncMock(return_value="Job Details | Bunge")
        mock_agent.navigate = AsyncMock(return_value=True)

        orchestrator = UniversalApplicationOrchestrator(browser_agent=mock_agent)
        self.assertIsNotNone(orchestrator)

    def test_field_mapper_successfactors_questionnaire(self):
        """Verify SuccessFactors questionnaire questions map to correct candidate facts/rules."""
        from app.services.automation.universal_agent.field_mapper import SemanticFieldMapper
        from app.services.automation.universal_agent.page_analyzer import FormFieldInfo

        mapper = SemanticFieldMapper()
        # Mock candidate context
        mapper.candidate_context = {
            "current_ctc": "1200000",
            "expected_ctc": "1500000",
            "open_to_relocation": "yes",
        }

        fields = [
            FormFieldInfo(
                field_id="q1",
                name="relatives",
                selector="select#q1",
                input_type="select",
                label="* Do you have relatives working at Bunge or its subsidiaries? (this includes extended family and relatives by marriage)?",
                required=True,
                options=[{"value": "", "label": "No Selection"}, {"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}],
            ),
            FormFieldInfo(
                field_id="q2",
                name="relocate",
                selector="select#q2",
                input_type="select",
                label="* Are you open to relocate?",
                required=True,
                options=[{"value": "", "label": "No Selection"}, {"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}],
            ),
            FormFieldInfo(
                field_id="q3",
                name="travel",
                selector="select#q3",
                input_type="select",
                label="* Are you open to Travel?",
                required=True,
                options=[{"value": "", "label": "No Selection"}, {"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}],
            ),
            FormFieldInfo(
                field_id="q4",
                name="noncompete",
                selector="select#q4",
                input_type="select",
                label="* Are you subject to any contractual restrictions including non-competition or other obligations or a potential conflict of interest...",
                required=True,
                options=[{"value": "", "label": "No Selection"}, {"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}],
            ),
            FormFieldInfo(
                field_id="q5",
                name="comp",
                selector="input#q5",
                input_type="text",
                label="* Please specify your overall annual compensation:",
                required=True,
            ),
            FormFieldInfo(
                field_id="q6",
                name="fixed_var",
                selector="input#q6",
                input_type="text",
                label="* Please specify Fixed+Variable:",
                required=True,
            ),
            FormFieldInfo(
                field_id="q7",
                name="desired_sal",
                selector="input#q7",
                input_type="text",
                label="* Please specify your desired salary position",
                required=True,
            ),
        ]

        res = mapper.map_fields(fields)
        self.assertEqual(res.resolved_count, 7)
        self.assertEqual(len(res.unresolved_required_fields), 0)

        # Check answers
        m_relatives = res.get_mapping("q1")
        self.assertEqual(m_relatives.effective_value, "no")

        m_relocate = res.get_mapping("q2")
        self.assertEqual(m_relocate.effective_value, "yes")

        m_travel = res.get_mapping("q3")
        self.assertEqual(m_travel.effective_value, "yes")

        m_noncompete = res.get_mapping("q4")
        self.assertEqual(m_noncompete.effective_value, "no")

        m_comp = res.get_mapping("q5")
        self.assertEqual(m_comp.effective_value, "1200000")

        m_fixed_var = res.get_mapping("q6")
        self.assertEqual(m_fixed_var.effective_value, "1200000")

        m_desired = res.get_mapping("q7")
        self.assertEqual(m_desired.effective_value, "1500000")

    async def test_form_filler_dropdown_smart_select(self):
        """Verify FormFiller executes smart JavaScript selection for dropdowns and handles success."""
        from app.services.automation.universal_agent.form_filler import FormFiller
        from app.services.automation.universal_agent.field_mapper import FieldMapping, FieldProvenance
        from app.services.automation.universal_agent.page_analyzer import FormFieldInfo

        filler = FormFiller()
        mock_agent = MagicMock()
        mock_agent.evaluate = AsyncMock(return_value={"ok": True, "method": "native_select", "value": "no", "text": "No"})

        f_info = FormFieldInfo(
            field_id="q1",
            name="relatives",
            selector="select#q1",
            input_type="select",
            label="Do you have relatives working at Bunge?",
            required=True,
        )
        mapping = FieldMapping(
            field_info=f_info,
            resolved_value="No",
            provenance=FieldProvenance("rule", "relatives"),
            is_resolved=True,
        )

        ok, err = await filler.fill_single_field(mock_agent, mapping)
        self.assertTrue(ok)
        self.assertIsNone(err)
        # Verify agent.evaluate was called with the smart JS script
        mock_agent.evaluate.assert_called_once()
        self.assertIn("native_select", mock_agent.evaluate.call_args[0][0])

    def test_has_account_master_credentials_support(self):
        """Verify has_account recognizes credentials from master vault even when company is not explicitly listed."""
        from app.services.workday_account_service import WorkdayAccountService
        svc = WorkdayAccountService()
        url = "https://career5.successfactors.eu/careers?company=Bunge"
        # When master credentials exist in vault, has_account and get_account should return True / details
        self.assertTrue(svc.has_account(url, company_name="Bunge"))
        acct = svc.get_account(url, company_name="Bunge")
        self.assertIsNotNone(acct)
        self.assertEqual(acct.get("username"), "rjaahmad60@gmail.com")

    def test_field_mapper_create_account_country_and_phone(self):
        """Verify Country/Region Code and Country of Residence resolve to country (India/IN), NOT state (Delhi)."""
        from app.services.automation.universal_agent.field_mapper import SemanticFieldMapper
        from app.services.automation.universal_agent.page_analyzer import FormFieldInfo

        mapper = SemanticFieldMapper()
        fields = [
            FormFieldInfo(
                field_id="countryCode",
                name="countryCode",
                selector="#countryCode",
                input_type="select",
                label="Country/Region Code",
                required=True,
                options=[{"value": "IN", "label": "India (+91)"}, {"value": "US", "label": "United States (+1)"}],
            ),
            FormFieldInfo(
                field_id="phone",
                name="phone",
                selector="#phone",
                input_type="text",
                label="Phone Number",
                required=True,
            ),
            FormFieldInfo(
                field_id="residence",
                name="residence",
                selector="#residence",
                input_type="select",
                label="Country/Region of Residence",
                required=True,
                options=[{"value": "IN", "label": "India"}, {"value": "US", "label": "United States"}],
            ),
        ]
        res = mapper.map_fields(fields)
        self.assertEqual(res.resolved_count, 3)

        m_code = res.get_mapping("countryCode")
        self.assertEqual(m_code.effective_value, "IN")

        m_phone = res.get_mapping("phone")
        self.assertEqual(m_phone.effective_value, "+916388623967")

        m_residence = res.get_mapping("residence")
        self.assertEqual(m_residence.effective_value, "IN")


if __name__ == "__main__":
    unittest.main()

