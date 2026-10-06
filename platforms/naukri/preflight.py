'''
Naukri Production Readiness & Pre-Flight Verification Engine (Phase 19)
Performs comprehensive health checks on environment, configurations, credentials,
resume assets, ledger directories, and Chrome compatibility prior to production execution.
'''

import os
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from modules.config_loader import (
    get_platform,
    get_resume,
    validate_naukri_config,
    get_candidate_experience,
    get_salary_preferences,
    get_notice_period,
)
from modules.helpers import print_lg, make_directories
from platforms.naukri.browser import DEFAULT_NAUKRI_PROFILE_DIR
from modules.open_chrome import get_installed_chrome_major_version


@dataclass
class PreflightCheckResult:
    name: str
    passed: bool
    details: str
    is_critical: bool = True


@dataclass
class PreflightReport:
    checks: List[PreflightCheckResult] = field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        """Returns True if all critical checks passed."""
        return all(c.passed for c in self.checks if c.is_critical)

    def summary(self) -> str:
        """Renders an ASCII diagnostic report card."""
        sep = "=" * 70
        sub_sep = "-" * 70
        lines = [
            sep,
            "NAUKRI PRODUCTION PRE-FLIGHT READINESS REPORT",
            sep,
        ]
        for c in self.checks:
            badge = "[PASS]" if c.passed else ("[FAIL]" if c.is_critical else "[WARN]")
            lines.append(f" {badge:<7} {c.name:<30} : {c.details}")

        lines.append(sub_sep)
        if self.is_ready:
            lines.append(" OVERALL STATUS: READY FOR PRODUCTION RUN")
        else:
            lines.append(" OVERALL STATUS: ACTION REQUIRED BEFORE PRODUCTION RUN")
        lines.append(sep)
        return "\n".join(lines)


class NaukriPreflightChecker:
    """Evaluates readiness of all subsystems required for Naukri production execution."""

    def __init__(self):
        self.report = PreflightReport()

    def run_all_checks(self) -> PreflightReport:
        self.report = PreflightReport()
        self._check_configuration()
        self._check_safety_lock()
        self._check_resume_file()
        self._check_tracking_ledger()
        self._check_chrome_environment()
        self._check_credential_wiring()
        return self.report

    def _check_configuration(self) -> None:
        try:
            validate_naukri_config()
            cfg = get_platform("naukri") or {}
            terms = cfg.get("search_terms", [])
            exp = cfg.get("experience_years", 0)
            self.report.checks.append(PreflightCheckResult(
                name="Configuration Validity",
                passed=True,
                details=f"Valid JSON. Search terms: {len(terms)}, Exp filter: {exp} yrs",
                is_critical=True,
            ))
        except Exception as e:
            self.report.checks.append(PreflightCheckResult(
                name="Configuration Validity",
                passed=False,
                details=f"Invalid configuration: {e}",
                is_critical=True,
            ))

    def _check_safety_lock(self) -> None:
        cfg = get_platform("naukri") or {}
        pause = cfg.get("pause_before_submit", True)
        if pause:
            self.report.checks.append(PreflightCheckResult(
                name="Safety Lock (Phase 11)",
                passed=True,
                details="LOCKED (Controlled Human Review before submission)",
                is_critical=False,
            ))
        else:
            self.report.checks.append(PreflightCheckResult(
                name="Safety Lock (Phase 11)",
                passed=True,
                details="UNLOCKED (Autonomous mode enabled)",
                is_critical=False,
            ))

    def _check_resume_file(self) -> None:
        res_path = get_resume()
        if res_path and os.path.exists(res_path) and os.path.getsize(res_path) > 0:
            self.report.checks.append(PreflightCheckResult(
                name="Candidate Resume File",
                passed=True,
                details=f"Found: {os.path.basename(res_path)} ({os.path.getsize(res_path)} bytes)",
                is_critical=True,
            ))
        else:
            self.report.checks.append(PreflightCheckResult(
                name="Candidate Resume File",
                passed=False,
                details=f"Missing or empty at: '{res_path}'",
                is_critical=True,
            ))

    def _check_tracking_ledger(self) -> None:
        ledger_dir = "all excels"
        ledger_file = os.path.join(ledger_dir, "applications.csv")
        screenshots_dir = os.path.join(ledger_dir, "logs", "screenshots")
        try:
            make_directories([ledger_file, screenshots_dir])
            self.report.checks.append(PreflightCheckResult(
                name="History Ledger & Logs",
                passed=True,
                details=f"Directories verified ({ledger_file})",
                is_critical=True,
            ))
        except Exception as e:
            self.report.checks.append(PreflightCheckResult(
                name="History Ledger & Logs",
                passed=False,
                details=f"Directory error: {e}",
                is_critical=True,
            ))

    def _check_chrome_environment(self) -> None:
        chrome_major = get_installed_chrome_major_version()
        if chrome_major and chrome_major > 0:
            self.report.checks.append(PreflightCheckResult(
                name="Google Chrome Binary",
                passed=True,
                details=f"Detected Chrome major version: {chrome_major}",
                is_critical=True,
            ))
        else:
            self.report.checks.append(PreflightCheckResult(
                name="Google Chrome Binary",
                passed=False,
                details="Could not detect installed Google Chrome browser.",
                is_critical=True,
            ))

        profile_dir = DEFAULT_NAUKRI_PROFILE_DIR
        try:
            make_directories([profile_dir])
            self.report.checks.append(PreflightCheckResult(
                name="Isolated Profile Dir",
                passed=True,
                details=f"Accessible: {profile_dir}",
                is_critical=True,
            ))
        except Exception as e:
            self.report.checks.append(PreflightCheckResult(
                name="Isolated Profile Dir",
                passed=False,
                details=f"Profile directory error: {e}",
                is_critical=True,
            ))

    def _check_credential_wiring(self) -> None:
        has_creds = False
        try:
            import config.secrets as secrets
            user = getattr(secrets, "naukri_username", None) or os.environ.get("NAUKRI_USERNAME")
            pwd = getattr(secrets, "naukri_password", None) or os.environ.get("NAUKRI_PASSWORD")
            has_creds = bool(user and pwd)
        except Exception:
            has_creds = bool(os.environ.get("NAUKRI_USERNAME") and os.environ.get("NAUKRI_PASSWORD"))

        if has_creds:
            self.report.checks.append(PreflightCheckResult(
                name="Authentication Wiring",
                passed=True,
                details="Credentials configured (secrets.py / env)",
                is_critical=False,
            ))
        else:
            self.report.checks.append(PreflightCheckResult(
                name="Authentication Wiring",
                passed=True,
                details="No credentials stored; manual browser login will be used",
                is_critical=False,
            ))


def run_preflight() -> bool:
    """Executes pre-flight diagnostics and outputs summary to console."""
    checker = NaukriPreflightChecker()
    report = checker.run_all_checks()
    print_lg(report.summary())
    return report.is_ready


if __name__ == "__main__":
    ready = run_preflight()
    sys.exit(0 if ready else 1)
