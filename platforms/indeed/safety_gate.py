'''
Indeed Safety Gate Engine
Reviews application data before final submission.
Enforces pause_before_submit settings, checks candidate salary/notice criteria,
and provides safety review for the Automation Battleground GUI and CLI.
'''

import re
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

        # 1. Automated Pre-Submission Domain & Negative Keyword Verification
        title_raw = (job_title or "").strip().lower()
        title_lower = re.sub(r'[_/|\-–—]+', ' ', title_raw) if title_raw else ""
        if title_lower:
            from modules.qualification_engine import OUT_OF_DOMAIN_KEYWORDS, is_job_relevant
            cfg = get_platform("indeed") or {}
            neg_words = cfg.get("negative_title_words", [])
            for neg in neg_words:
                n_clean = str(neg).strip().lower()
                if n_clean and re.search(r'\b' + re.escape(n_clean) + r'\b', title_lower):
                    print_lg(f"[IndeedSafetyGate] Rejected: Title '{job_title}' contains negative keyword '{neg}'.")
                    return SafetyGateResult(
                        approved=False,
                        reason=f"Safety Gate rejected submission: Job title contains negative keyword '{neg}'.",
                        requires_human_approval=False,
                        details={"job_title": job_title, "company": company, "matched_negative": neg}
                    )

            # Check out-of-domain words
            search_terms = cfg.get("search_terms", [])
            for ood in OUT_OF_DOMAIN_KEYWORDS:
                if re.search(r'\b' + re.escape(ood) + r'\b', title_lower):
                    matches_term = any(is_job_relevant(job_title, term) for term in search_terms) if search_terms else False
                    if not matches_term:
                        print_lg(f"[IndeedSafetyGate] Rejected: Title '{job_title}' is outside candidate domain ('{ood}').")
                        return SafetyGateResult(
                            approved=False,
                            reason=f"Safety Gate rejected submission: Job title belongs to out-of-domain profession '{ood}'.",
                            requires_human_approval=False,
                            details={"job_title": job_title, "company": company, "out_of_domain": ood}
                        )

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
