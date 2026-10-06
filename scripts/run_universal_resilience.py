#!/usr/bin/env python3
"""JobPilot Universal AI Application Agent — Real-World Resilience Runner.

Executes controlled resilience, recovery, popup, iframe, validation, and multi-tab scenarios
against local fixtures and records structured audit reports.

Usage:
    .venv/bin/python scripts/run_universal_resilience.py
    .venv/bin/python scripts/run_universal_resilience.py --scenario popup
    .venv/bin/python scripts/run_universal_resilience.py --scenario validation
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.automation.universal_agent.checkpoint_manager import CheckpointManager, ExecutionCheckpoint
from app.services.automation.universal_agent.frame_resolver import FrameResolver
from app.services.automation.universal_agent.page_classifier import PageClassifier, PageHealthChecker, PageClass
from app.services.automation.universal_agent.popup_manager import PopupManager, PopupClassification
from app.services.automation.universal_agent.recovery_manager import RecoveryManager, FailureCategory
from app.services.automation.universal_agent.validation_resolver import ValidationResolver
from app.services.automation.universal_agent.result_verifier import ResultVerifier, VerificationResult
from app.services.automation.universal_agent.state_machine import (
    AgentExecutionState,
    InterventionReason,
    TerminalResult,
    UniversalApplicationStateMachine,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ResilienceRunner")


@dataclass
class ScenarioResult:
    scenario_name: str
    status: str  # PASS / FAIL
    duration_seconds: float
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class UniversalAgentResilienceRunner:
    """Orchestrates comprehensive resilience and failure-recovery benchmark scenarios."""

    def __init__(self, report_dir: Optional[str] = None) -> None:
        self.report_dir = report_dir or os.path.join("debug", "resilience_reports")
        os.makedirs(self.report_dir, exist_ok=True)
        self.results: List[ScenarioResult] = []

    async def run_all(self) -> Dict[str, Any]:
        print("\n" + "=" * 70)
        print("🛡️  UNIVERSAL AGENT REAL-WORLD RESILIENCE BENCHMARK")
        print("=" * 70 + "\n")

        scenarios = [
            ("Happy Path Recovery Setup", self.scenario_happy_path),
            ("Cookie Consent & Popup Interception", self.scenario_popup_dismissal),
            ("Destructive Modal Protection", self.scenario_destructive_modal),
            ("Page 404 / 500 Classification", self.scenario_page_error_classification),
            ("Security Gate / CAPTCHA Classification", self.scenario_captcha_classification),
            ("Login Wall Detection", self.scenario_login_detection),
            ("Form Validation Error Extraction", self.scenario_validation_detection),
            ("Iframe Application Form Discovery", self.scenario_iframe_discovery),
            ("Execution Checkpoint & Resume Cycle", self.scenario_checkpoint_cycle),
            ("Duplicate Application Prevention", self.scenario_duplicate_prevention),
            ("Ambiguous Submission Uncertainty", self.scenario_submission_uncertainty),
            ("Recovery Manager Retry Exhaustion", self.scenario_retry_exhaustion),
        ]

        for name, fn in scenarios:
            t0 = time.time()
            try:
                res_details = await fn() if asyncio.iscoroutinefunction(fn) else fn()
                dur = time.time() - t0
                self.results.append(ScenarioResult(name, "PASS", dur, res_details))
                print(f"  ✅ [PASS] {name} ({dur:.3f}s)")
            except Exception as e:
                dur = time.time() - t0
                self.results.append(ScenarioResult(name, "FAIL", dur, {}, str(e)))
                print(f"  ❌ [FAIL] {name} ({dur:.3f}s): {e}")

        summary = self._generate_report()
        return summary

    def scenario_happy_path(self) -> Dict[str, Any]:
        sm = UniversalApplicationStateMachine()
        sm.transition_to(AgentExecutionState.INITIALIZING)
        sm.transition_to(AgentExecutionState.NAVIGATING)
        sm.transition_to(AgentExecutionState.ANALYZING_PAGE)
        sm.transition_to(AgentExecutionState.MAPPING_FIELDS)
        sm.transition_to(AgentExecutionState.FILLING_FORM)
        sm.transition_to(AgentExecutionState.PENDING_HUMAN_REVIEW)
        sm.transition_to(AgentExecutionState.SUBMITTING)
        sm.complete(TerminalResult.SUCCESS_SUBMITTED)
        return {"terminal_result": sm.terminal_result.value, "is_success": sm.is_success}

    def scenario_popup_dismissal(self) -> Dict[str, Any]:
        classification = PopupManager.classify_popup("We use cookies to enhance your experience. Accept All Cookies.")
        assert classification == PopupClassification.BENIGN, f"Expected BENIGN got {classification}"
        return {"classification": classification.value}

    def scenario_destructive_modal(self) -> Dict[str, Any]:
        classification = PopupManager.classify_popup("Are you sure you want to discard your application? All data will be deleted.")
        assert classification == PopupClassification.DESTRUCTIVE, f"Expected DESTRUCTIVE got {classification}"
        return {"classification": classification.value}

    def scenario_page_error_classification(self) -> Dict[str, Any]:
        p_class = PageClassifier.classify("https://example.com/job/404", "404 Not Found", "Page is unavailable.")
        assert p_class == PageClass.ERROR, f"Expected ERROR got {p_class}"
        return {"page_class": p_class.value}

    def scenario_captcha_classification(self) -> Dict[str, Any]:
        p_class = PageClassifier.classify("https://example.com/verify", "Security Check", "Please verify you are human to proceed.")
        assert p_class == PageClass.CAPTCHA, f"Expected CAPTCHA got {p_class}"
        return {"page_class": p_class.value}

    def scenario_login_detection(self) -> Dict[str, Any]:
        p_class = PageClassifier.classify("https://example.com/login", "Sign In", "Sign in to apply to your account.", input_count=2)
        assert p_class == PageClass.LOGIN, f"Expected LOGIN got {p_class}"
        return {"page_class": p_class.value}

    async def scenario_validation_detection(self) -> Dict[str, Any]:
        from unittest.mock import AsyncMock, MagicMock
        agent = MagicMock()
        agent.evaluate = AsyncMock(return_value={
            "field_errors": [{"field_identifier": "email", "error_text": "Invalid email address format"}],
            "summary_banners": ["Please correct highlighted errors"],
        })
        rep = await ValidationResolver.inspect_validation_errors(agent)
        assert rep.has_errors, "Expected validation errors"
        assert len(rep.field_errors) == 1
        return {"errors_count": len(rep.field_errors)}

    async def scenario_iframe_discovery(self) -> Dict[str, Any]:
        from unittest.mock import AsyncMock, MagicMock
        agent = MagicMock()
        agent.evaluate = AsyncMock(return_value=[
            {"frame_index": 0, "name": "app_iframe", "frame_id": "app_frame", "src": "https://boards.greenhouse.io/embed", "input_count": 5, "has_form": True, "is_accessible": True, "selector": "#app_frame"}
        ])
        frame = await FrameResolver.find_application_frame(agent)
        assert frame is not None, "Expected application frame"
        assert frame.input_count == 5
        return {"frame_id": frame.frame_id, "inputs": frame.input_count}

    def scenario_checkpoint_cycle(self) -> Dict[str, Any]:
        cm = CheckpointManager(storage_dir=os.path.join(self.report_dir, "test_checkpoints"))
        cp = ExecutionCheckpoint(
            application_id=101,
            job_id="job_resilience_test",
            current_url="https://jobs.example.com/apply",
            page_role="APPLICATION_STEP",
            execution_state="FILLING_FORM",
            current_step=1,
            completed_steps=[],
            facts_used={"user.email": "candidate@example.com"},
        )
        cm.save_checkpoint(cp)
        loaded = cm.load_checkpoint("job_resilience_test")
        assert loaded is not None and loaded.job_id == "job_resilience_test"
        cm.clear_checkpoint("job_resilience_test")
        assert cm.load_checkpoint("job_resilience_test") is None
        return {"saved_and_restored": True}

    async def scenario_duplicate_prevention(self) -> Dict[str, Any]:
        from unittest.mock import MagicMock, patch
        from app.services.automation.universal_agent.orchestrator import UniversalApplicationOrchestrator
        mock_app = MagicMock()
        mock_app.status = "SUBMITTED"
        with patch("app.services.application_service.ApplicationService.get_by_job_id", return_value=mock_app):
            orch = UniversalApplicationOrchestrator(browser_agent=MagicMock())
            res = await orch.run(portal_url="https://example.com/job/1", job_id=1)
            assert res.terminal_result == TerminalResult.SKIPPED_DISQUALIFIED
            return {"duplicate_prevented": True, "terminal_result": res.terminal_result.value}

    def scenario_submission_uncertainty(self) -> Dict[str, Any]:
        sm = UniversalApplicationStateMachine()
        verifier = ResultVerifier()
        verifier.verify_and_update_state(sm, VerificationResult(status="UNKNOWN", is_success=False))
        assert sm.terminal_result == TerminalResult.SUBMISSION_STATUS_UNKNOWN
        return {"terminal_result": sm.terminal_result.value}

    def scenario_retry_exhaustion(self) -> Dict[str, Any]:
        rm = RecoveryManager(run_id="bench_run")
        op = "navigate_step"
        for _ in range(3):
            assert rm.can_retry(op, FailureCategory.TRANSIENT)
            rm.record_attempt(op, FailureCategory.TRANSIENT)
        assert not rm.can_retry(op, FailureCategory.TRANSIENT), "Expected retry budget exhaustion"
        return {"exhausted_after": 3}

    def _generate_report(self) -> Dict[str, Any]:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")

        summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_scenarios": total,
            "passed": passed,
            "failed": failed,
            "pass_rate_percent": (passed / total) * 100 if total > 0 else 0,
            "scenarios": [asdict(r) for r in self.results],
        }

        report_file = os.path.join(self.report_dir, "resilience_summary.json")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        print("\n" + "-" * 70)
        print(f"📊 SUMMARY: {passed}/{total} Scenarios Passed ({summary['pass_rate_percent']:.1f}%)")
        print(f"📄 Detailed Report: {report_file}")
        print("-" * 70 + "\n")
        return summary


if __name__ == "__main__":
    runner = UniversalAgentResilienceRunner()
    loop = asyncio.get_event_loop()
    summary = loop.run_until_complete(runner.run_all())
    sys.exit(0 if summary["failed"] == 0 else 1)
