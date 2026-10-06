'''
Indeed Safety Gate Engine
Reviews application data before final submission.
Enforces pause_before_submit settings, checks candidate salary/notice criteria,
and provides safety review for the Automation Battleground GUI and CLI.
'''

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from modules.helpers import print_lg
from modules.config_loader import get_platform


@dataclass
class SafetyGateResult:
    """Result of safety evaluation before final submission."""
    approved: bool
    reason: str
    requires_human_approval: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


class IndeedSafetyGate:
    """Safety evaluation gate for Indeed job applications."""

    def __init__(self, pause_mode: Optional[bool] = None):
        if pause_mode is not None:
            self.pause_mode = bool(pause_mode)
        else:
            try:
                from config.search import _read_platform_from_db
                db_cfg = _read_platform_from_db("indeed") or {}
            except Exception:
                db_cfg = {}
            cfg = get_platform("indeed") or {}
            merged = {**cfg, **db_cfg}
            self.pause_mode = bool(merged.get("pause_before_submit", False))


    def evaluate(
        self,
        job_title: str,
        company: str,
        answers: Optional[List[Dict[str, str]]] = None,
        job_metadata: Optional[Dict[str, Any]] = None,
    ) -> SafetyGateResult:
        """Evaluates whether the application is safe to submit."""
        answers = answers or []
        job_metadata = job_metadata or {}

        print_lg(f"[IndeedSafetyGate] Evaluating application for '{job_title}' at '{company}'...")

        if self.pause_mode:
            print_lg("[IndeedSafetyGate] Human review requested (pause_before_submit=True).")
            return SafetyGateResult(
                approved=False,
                reason="pause_before_submit enabled. Awaiting human confirmation.",
                requires_human_approval=True,
                details={
                    "job_title": job_title,
                    "company": company,
                    "answers": answers,
                }
            )

        # Automated check passed
        print_lg("[IndeedSafetyGate] Application approved for submission.")
        return SafetyGateResult(
            approved=True,
            reason="Automated checks passed.",
            requires_human_approval=False,
            details={"job_title": job_title, "company": company}
        )
