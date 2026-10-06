"""Targeted tests for Naukri chatbot questions, confirmation recognition, and Battleground real-time sync."""

import unittest
from unittest.mock import MagicMock
from modules.qna_engine import QnAEngine
from platforms.naukri.selectors import SUBMISSION_CONFIRMATION_TEXTS, SUBMISSION_SUCCESS_SELECTORS
from platforms.naukri.submitter import NaukriSubmitter
from app.ui.widgets.automation.state import AutomationUIState
from app.services.automation_events import (
    AutomationProgressEvent,
    JobDiscoveredEvent,
    JobEvaluatedEvent,
    ApplicationSubmittedEvent,
)


class TestNaukriChatbotAndMetrics(unittest.TestCase):
    """Verifies chatbot question handling, submission confirmation detection, and UI state sync."""

    def test_military_chatbot_question_matching(self):
        """Verifies military service question resolves to 'Never served' and auto-learns."""
        engine = QnAEngine()
        options = ["Currently serving", "Previously served", "Never served"]
        
        # Test exact query from user screenshot
        ans, matched = engine.resolve_choice_answer(
            "Have you ever served in the military?",
            options
        )
        self.assertEqual(matched, "Never served")
        self.assertEqual(str(ans.value), "Never served")
        self.assertIn(ans.source, ("profile", "rule"))
        self.assertTrue(ans.validated)

        # Test alternative military phrasing
        ans2, matched2 = engine.resolve_choice_answer(
            "Are you a military veteran?",
            options
        )
        self.assertEqual(matched2, "Never served")
        self.assertEqual(str(ans2.value), "Never served")

    def test_naukri_post_apply_confirmation_detection(self):
        """Verifies modern Naukri post-apply confirmation card text and selectors match."""
        # Check that 'applied to' and 'start your interview preparation' are recognized
        body_text_sample = 'applied to "genai engineer | llms, nlp & cloud (mlops)" start your interview preparation'
        
        matched_any = any(phrase in body_text_sample for phrase in SUBMISSION_CONFIRMATION_TEXTS)
        self.assertTrue(matched_any)
        self.assertIn("applied to", SUBMISSION_CONFIRMATION_TEXTS)
        self.assertIn("start your interview preparation", SUBMISSION_CONFIRMATION_TEXTS)
        self.assertIn("div[class*='applied-to']", SUBMISSION_SUCCESS_SELECTORS)

    def test_naukri_submitter_verifies_applied_to_text(self):
        """Verifies NaukriSubmitter confirms application when body contains 'Applied to'."""
        mock_driver = MagicMock()
        mock_body = MagicMock()
        mock_body.text = 'Applied to "GenAI Engineer | LLMs, NLP & Cloud (MLOps)"\nStart your interview preparation'
        mock_driver.driver.find_elements.return_value = []
        mock_driver.driver.find_element.return_value = mock_body

        submitter = NaukriSubmitter(browser=mock_driver)
        confirmed, reason = submitter.verify_submission(timeout=1.0)
        self.assertTrue(confirmed)
        self.assertIn("applied to", reason.lower())

    def test_naukri_chatbot_relocation_question_matching(self):
        """Verifies relocation/residence question from user screenshot resolves to 'Yes'."""
        engine = QnAEngine()
        options = ["Yes", "No"]
        ans, matched = engine.resolve_choice_answer(
            "Are you currently residing in Bengaluru or willing to relocate to Bengaluru?",
            options
        )
        self.assertEqual(matched, "Yes")
        self.assertEqual(str(ans.value), "Yes")
        self.assertTrue(ans.validated)

    def test_naukri_chatbot_drawer_not_treated_as_direct_success(self):
        """Verifies ambiguous apply-message is not in success selectors and thank you phrases are recognized."""
        self.assertNotIn(".apply-message", SUBMISSION_SUCCESS_SELECTORS)
        self.assertNotIn("div[class*='apply-message']", SUBMISSION_SUCCESS_SELECTORS)
        self.assertIn("thank you for your responses", SUBMISSION_CONFIRMATION_TEXTS)
        self.assertIn("thank you for your response", SUBMISSION_CONFIRMATION_TEXTS)

    def test_naukri_form_chatbot_thank_you_confirms_submission(self):
        """Verifies NaukriForm confirms submission when chatbot displays 'Thank you for your responses.'"""
        from platforms.naukri.form import NaukriForm
        mock_driver = MagicMock()
        mock_drawer = MagicMock()
        mock_drawer.text = "Thank you for your responses.\nStart your interview preparation"
        mock_drawer.is_displayed.return_value = True

        form = NaukriForm(browser=mock_driver)
        form.get_container = MagicMock(return_value=mock_drawer)

        confirmed = form._check_submission_confirmed()
        self.assertTrue(confirmed)

    def test_realtime_battleground_metrics_telemetry(self):
        """Verifies telemetry progress and domain events update state and metrics cleanly."""
        state = AutomationUIState()
        state.reset_for_run(platform="naukri")

        # Telemetry progress updates
        prog = AutomationProgressEvent(
            run_id="test-run",
            platform="naukri",
            jobs_discovered=5,
            jobs_evaluated=4,
            jobs_qualified=3,
            jobs_skipped=1,
            applications_submitted=2,
            errors_count=0,
            current_job="GenAI Engineer @ TechCorp",
        )
        state.on_progress(prog)

        self.assertEqual(state.jobs_discovered, 5)
        self.assertEqual(state.jobs_evaluated, 4)
        self.assertEqual(state.jobs_qualified, 3)
        self.assertEqual(state.jobs_skipped, 1)
        self.assertEqual(state.applications_submitted, 2)
        self.assertEqual(state.current_job_title, "GenAI Engineer")
        self.assertEqual(state.current_job_company, "TechCorp")

    def test_naukri_multi_question_chatbot_turn_transition(self):
        """Verifies wait_for_chatbot_turn_transition detects arrival of Question 2 from Screenshot 1."""
        from platforms.naukri.form import NaukriForm, FormField
        mock_driver = MagicMock()
        mock_drawer = MagicMock()
        mock_drawer.text = "Are you ready to learn new technology & deliver training on that?\nYes\nDo you have technical training/classroom training experience?"
        mock_drawer.is_displayed.return_value = True

        form = NaukriForm(browser=mock_driver)
        form.get_container = MagicMock(return_value=mock_drawer)
        form.is_chatbot = MagicMock(return_value=True)
        form._clean_label = lambda x: (x or "").strip()
        
        # When Question 2 arrives, discover_fields returns the new question's field
        q2_field = FormField(
            field_type="radio",
            label="Do you have technical training/classroom training experience?",
            element=MagicMock(),
            options=["Yes", "No"],
        )
        form._get_latest_chatbot_question = MagicMock(return_value="Do you have technical training/classroom training experience?")
        form.discover_fields = MagicMock(return_value=[q2_field])

        status, detail = form.wait_for_chatbot_turn_transition(
            previous_question="Are you ready to learn new technology & deliver training on that?",
            timeout=2.0
        )
        self.assertEqual(status, "NEXT_QUESTION")
        self.assertEqual(detail, "Do you have technical training/classroom training experience?")

    def test_naukri_chatbot_confirmation_and_completion(self):
        """Verifies 'Thank you for your response' triggers CONFIRMED and auto-close."""
        from platforms.naukri.form import NaukriForm
        mock_driver = MagicMock()
        mock_drawer = MagicMock()
        mock_drawer.text = "Thank you for your response"
        mock_drawer.is_displayed.return_value = True

        form = NaukriForm(browser=mock_driver)
        form.get_container = MagicMock(return_value=mock_drawer)
        form.is_chatbot = MagicMock(return_value=True)

        status, detail = form.wait_for_chatbot_turn_transition(
            previous_question="Do you have technical training/classroom training experience?",
            timeout=2.0
        )
        self.assertEqual(status, "CONFIRMED")
        self.assertIn("Thank you for your response", detail)

    def test_naukri_rejection_error_returns_failed_and_closes_modal(self):
        """Verifies rejection due to incomplete information is caught and returns FAILED."""
        from platforms.naukri.form import NaukriForm
        from platforms.naukri.applier import NaukriApplier
        from modules.models import Job

        mock_driver = MagicMock()
        mock_body = MagicMock()
        mock_body.text = "Oops! Your application was not accepted due to incomplete information"
        mock_driver.driver.find_element.return_value = mock_body
        mock_driver.driver.find_elements.return_value = []

        form = NaukriForm(browser=mock_driver)
        form.is_chatbot = MagicMock(return_value=True)
        form.get_container = MagicMock(return_value=mock_body)

        form_result = form.fill_form()
        self.assertEqual(form_result.get("status"), "FAILED")
        self.assertIn("not accepted", form_result.get("reason", "").lower())

        # Test applier closes modal and records FAILED without crashing
        applier = NaukriApplier(browser=mock_driver, form=form)
        mock_btn = MagicMock()
        applier.flow_detector.find_apply_button = MagicMock(return_value=mock_btn)
        applier.flow_detector.detect_apply_button_type = MagicMock(return_value="INTERNAL")
        applier.flow_detector.detect_flow_after_click = MagicMock(return_value=("QUESTIONNAIRE", "Screening questionnaire"))
        applier.flow_detector.close_modal_if_open = MagicMock(return_value=True)
        applier.tracker = MagicMock()

        test_job = Job(job_id="test_rej_123", title="Trainer", company="Valuedx", location="Bengaluru", platform="naukri")
        
        # Test applier handling of failed form result
        app_res = applier.apply_to_job(test_job)
        self.assertEqual(app_res.get("status"), "FAILED")
        applier.flow_detector.close_modal_if_open.assert_called()
        applier.tracker.record_state.assert_called_with(test_job, "FAILED", reason=form_result.get("reason"))

    def test_no_premature_save_in_chatbot(self):
        """Verifies self.next() is never called in chatbot mode after filling field."""
        from platforms.naukri.form import NaukriForm, FormField, Answer
        mock_driver = MagicMock()
        form = NaukriForm(browser=mock_driver)
        form.is_chatbot = MagicMock(return_value=True)
        form.next = MagicMock()  # If next() is called, this will record call_count > 0

        # Simulate form with 1 question that completes on transition
        field1 = FormField(
            field_type="radio",
            label="Are you ready to learn new technology & deliver training on that?",
            element=MagicMock(),
            options=["Yes", "No"],
        )
        form.discover_fields = MagicMock(return_value=[field1])
        form.answer = MagicMock(return_value=Answer(value="Yes", source="rule", confidence=1.0, validated=True))
        form.validate = MagicMock(return_value=True)
        form.fill_field = MagicMock(return_value=True)
        form._check_submission_error = MagicMock(return_value=None)
        form._check_submission_confirmed = MagicMock(return_value=False)
        form.wait_for_chatbot_turn_transition = MagicMock(return_value=("CONFIRMED", "All questions answered"))
        form._handle_chatbot_completion = MagicMock(return_value=True)

        res = form.fill_form()
        self.assertEqual(res.get("status"), "SUBMITTED")
        # Ensure next() was NEVER called in chatbot mode!
        form.next.assert_not_called()

    def test_wfo_question_extraction_and_yes_no_validation(self):
        """Verifies that non-standard questions like 'This is work from office on all 5 days...' are recognized and validated."""
        from platforms.naukri.form import NaukriForm
        from modules.qna_engine import validate_answer, Answer

        # 1. Test validate_answer with boolean options does not require numeric digits
        ans = Answer(value="Yes", source="rule", confidence=1.0)
        validated_ans = validate_answer(ans, "How many years of experience do you have in SQL?", available_options=["Yes", "No"])
        self.assertTrue(validated_ans.validated)
        self.assertIsNone(validated_ans.validation_error)

        # 2. Test chatbot question extraction with multiple prior questions
        mock_driver = MagicMock()
        form = NaukriForm(browser=mock_driver)

        # Mock bot message elements
        msg1 = MagicMock()
        msg1.text = "How many years of experience do you have in Uipath Studio and Orchestrator?"
        msg2 = MagicMock()
        msg2.text = "How many years of experience do you have in SQL?"
        msg3 = MagicMock()
        msg3.text = "This is work from office on all 5 days, pls apply if you are okay"

        mock_drawer = MagicMock()
        mock_drawer.find_elements.return_value = [msg1, msg2, msg3]

        extracted_q = form._get_latest_chatbot_question(container=mock_drawer)
        self.assertEqual(extracted_q, "This is work from office on all 5 days, pls apply if you are okay")

    def test_direct_apply_flow_detector_matches_interview_prep_card(self):
        """Verifies detect_flow_after_click immediately recognizes confirmation card as DIRECT apply."""
        from platforms.naukri.applier import NaukriFlowDetector
        mock_browser = MagicMock()
        mock_driver = MagicMock()
        mock_browser.driver = mock_driver

        mock_driver.window_handles = ["win1"]
        mock_driver.current_window_handle = "win1"
        mock_driver.current_url = "https://www.naukri.com/job-listings-ai-ml-engineer-110725018533"

        # No questionnaire drawer
        mock_driver.find_elements.return_value = []

        mock_body = MagicMock()
        mock_body.text = 'Applied to "AI/ML Engineer"\nStart your interview preparation for Navgurukul Foundation\nAll interview questions for this job View ->'
        mock_driver.find_element.return_value = mock_body

        detector = NaukriFlowDetector(browser=mock_browser)
        detector.is_already_applied = MagicMock(return_value=False)

        flow, reason = detector.detect_flow_after_click(timeout=1.0)
        self.assertEqual(flow, "DIRECT")
        self.assertTrue("applied to" in reason.lower() or "interview preparation" in reason.lower())

    def test_dob_resolution_and_protection(self):
        """Verifies DOB resolves to candidate's real birth date (15/05/2002) and rejects corrupted answers."""
        engine = QnAEngine()
        ans = engine.resolve_text_answer("What is your DOB?")
        self.assertEqual(str(ans.value), "15/05/2002")
        self.assertEqual(ans.source, "profile")
        self.assertEqual(ans.confidence, 1.0)

        ans2 = engine.resolve_text_answer("What is your Date of Birth?")
        self.assertEqual(str(ans2.value), "15/05/2002")

        # Verify save_learned_answer rejects saving '0' or 'Yes' for DOB
        saved = engine.save_learned_answer("What is your DOB", "0", answer_type="radio", source="rule")
        self.assertFalse(saved)

    def test_chatbot_user_answer_bubble_not_mistaken_for_radio(self):
        """Verifies candidate's previous response bubble (e.g. '0') is not discovered as a radio chip."""
        from platforms.naukri.form import NaukriForm
        mock_driver = MagicMock()
        mock_ctx = MagicMock()

        # Mock previous answer bubble with class userItem, userMsg, and edit pencil icon
        user_bubble = MagicMock()
        user_bubble.is_displayed.return_value = True
        user_bubble.text = "0"
        user_bubble.get_attribute.side_effect = lambda attr: "userItem chatbot_ListItem editable-listItem" if attr == "class" else "0"
        
        # Sibling or ancestor pencil icon
        pencil = MagicMock()
        pencil.get_attribute.return_value = "chatBot-edit_pencil_pwa editMsg"
        user_bubble.find_elements.side_effect = lambda by, expr: [pencil] if "pencil" in expr or "userMsg" in expr or "userItem" in expr else []

        mock_ctx.find_elements.side_effect = lambda by, sel: []

        form = NaukriForm(browser=mock_driver)
        form.is_chatbot = MagicMock(return_value=True)
        form._get_latest_chatbot_question = MagicMock(return_value="What is your DOB?")

        # Also mock the contenteditable input present in the drawer
        ce_elem = MagicMock()
        ce_elem.is_displayed.return_value = True
        ce_elem.get_attribute.side_effect = lambda attr: "" if attr == "textContent" else None
        
        def find_elements_mock(by, sel):
            if "contenteditable" in sel or "textArea" in sel:
                return [ce_elem]
            return []

        mock_ctx.find_elements = find_elements_mock
        form.get_container = MagicMock(return_value=mock_ctx)

        fields = form.discover_fields(container=mock_ctx)
        self.assertEqual(len(fields), 1)
        # Must be identified as contenteditable (or text), NOT phantom radio with option ['0']
        self.assertIn(fields[0].field_type, ("contenteditable", "text"))
        self.assertNotEqual(fields[0].field_type, "radio")
        self.assertEqual(fields[0].label, "What is your DOB?")


if __name__ == "__main__":
    unittest.main()



