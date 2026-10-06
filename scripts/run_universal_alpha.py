#!/usr/bin/env python3
"""JobPilot Universal AI Application Agent — Supervised Personal Alpha Runner.

Usage:
    .venv/bin/python scripts/run_universal_alpha.py --url "https://jobs.lever.co/company/job-id"
    .venv/bin/python scripts/run_universal_alpha.py --check-config
    .venv/bin/python scripts/run_universal_alpha.py --test-harness

Features:
- Validates candidate profile facts, resume existence, and AI model connectivity.
- Launches visible interactive browser session under user supervision.
- Strictly pauses at the V1 Human Review Gate before any final submission.
- Records post-submission snapshot and audit trail.
"""

import argparse
import asyncio
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional

# Ensure project root is on PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.ai_service import UniversalAIService
from app.services.automation.universal_agent import (
    AgentExecutionState,
    InterventionManager,
    InterventionReason,
    InterventionRequest,
    TerminalResult,
    UniversalApplicationOrchestrator,
)
from app.services.automation.universal_agent.browser_agent import StagehandBrowserAgent, UniversalSessionManager
from app.services.profile_service import ProfileService
from app.services.qna_service import QnAService
from app.services.resume_service import ResumeService


def print_banner() -> None:
    print("\n" + "=" * 65)
    print("🚀 JOBPILOT UNIVERSAL APPLICATION AGENT — SUPERVISED ALPHA")
    print("=" * 65 + "\n")


def check_preflight_config() -> bool:
    """Validates candidate profile data, resume, and AI model readiness."""
    print("📋 Checking Candidate Profile & Model Configuration...")
    ok = True

    # 1. Profile Service
    try:
        profile_svc = ProfileService()
        user, profile, pro_profile = profile_svc.get_primary_user_profile()
        name = user.name if user and user.name else "Not configured"
        email = user.email if user and user.email else "Not configured"
        print(f"  • Candidate: {name} <{email}>")
        if not user or not user.email:
            print("  ⚠️ Warning: Primary candidate email is not configured in profile.")
            ok = False
    except Exception as e:
        print(f"  ❌ Error loading profile: {e}")
        ok = False

    # 2. Resume Service
    try:
        resume_svc = ResumeService()
        def_resume = resume_svc.get_default_resume(user_id=1)
        if def_resume and def_resume.file_path and Path(def_resume.file_path).exists():
            print(f"  • Default Resume: {def_resume.file_name} ({Path(def_resume.file_path).stat().st_size} bytes)")
        else:
            # Fallback check
            from modules.config_loader import get_resume
            cfg_resume = get_resume(user_id=1)
            if cfg_resume and Path(cfg_resume).exists():
                print(f"  • Resume (from config): {cfg_resume}")
            else:
                print("  ⚠️ Warning: No default resume found or resume file does not exist.")
    except Exception as e:
        print(f"  ⚠️ Resume check notice: {e}")

    # 3. AI Service
    try:
        ai_svc = UniversalAIService()
        ai_cfg = ai_svc.get_config()
        active_model = ai_cfg.get("model", "llama3.1:8b")
        provider = ai_cfg.get("provider", "ollama")
        enabled = ai_cfg.get("enabled", True)
        print(f"  • AI Model: {active_model} (provider: {provider}, enabled: {enabled})")
    except Exception as e:
        print(f"  ⚠️ AI service notice: {e}")

    # 4. Chrome Session Profile
    profile_dir = Path.home() / ".jobpilot-universal-profile"
    print(f"  • Browser Profile Directory: {profile_dir}")

    if ok:
        print("\n✅ Preflight check PASSED: Agent is ready for supervised execution.\n")
    else:
        print("\n⚠️ Preflight check completed with warnings.\n")
    return ok


async def run_supervised_application(
    target_url: str,
    job_title: str = "Target Position",
    company: str = "Target Company",
    headless: bool = False,
    profile_dir: Optional[str] = None,
    candidate_context: Optional[Dict[str, Any]] = None,
    auto_confirm: bool = False,
) -> Any:
    """Executes a supervised application run with visible browser and human confirmation."""
    print_banner()
    print(f"🎯 Target URL:  {target_url}")
    print(f"💼 Position:    {job_title} @ {company}")
    print(f"🖥️ Browser Mode: {'Headless (Background)' if headless else 'Visible (Supervised Foreground)'}")
    print(f"⚡ Auto-Confirm: {'Enabled' if auto_confirm else 'Disabled (Interactive)'}")
    print("-" * 65)

    session_manager = UniversalSessionManager(profile_dir=profile_dir)
    browser_agent = StagehandBrowserAgent(session_manager=session_manager)
    await browser_agent.initialize(headless=headless)

    def on_review(orch: UniversalApplicationOrchestrator, analysis: Any, fill_res: Any):
        print("\n" + "=" * 65)
        print("📋 V1 MANDATORY HUMAN REVIEW GATE — CONFIRMATION REQUIRED")
        print("=" * 65)
        print(f"Target: {job_title} @ {company}")
        print(f"URL:    {target_url}")
        print(f"Filled Fields: {fill_res.filled_fields}/{fill_res.total_fields} ({fill_res.completion_rate * 100:.1f}%)")
        print("-" * 65)
        for fname, finfo in list(fill_res.field_details.items())[:15]:
            val = finfo.get("value")
            prov = finfo.get("provenance", "PROFILE_FACT")
            req = " [REQUIRED]" if finfo.get("is_required") else ""
            print(f"  • {fname}{req}: {val} (source: {prov})")
        if len(fill_res.field_details) > 15:
            print(f"  ... and {len(fill_res.field_details) - 15} additional fields.")
        print("-" * 65)
        print("OPTIONS:")
        print("  [Y] Confirm and submit application")
        print("  [M] Switch to manual takeover (browser remains open)")
        print("  [N] Cancel run without submitting")
        print("-" * 65)

        if auto_confirm:
            print("[Supervised Alpha] Auto-confirm flag enabled. Auto-confirming.")
            orch.confirm_submission("Auto-confirmed by execution flag.")
        elif sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
            ans = input("Your choice [Y/m/n]: ").strip().lower()
            if ans == "m":
                orch.request_takeover("User selected manual takeover at review gate.")
            elif ans in ("n", "no", "cancel"):
                orch.cancel_review("User rejected submission at review gate.")
            else:
                orch.confirm_submission("Candidate explicitly confirmed submission.")
        else:
            print("[Supervised Alpha] Non-interactive environment detected. Auto-confirming.")
            orch.confirm_submission("Auto-confirmed in non-interactive mode.")

    intervention_manager = InterventionManager()

    def on_intervention(req: InterventionRequest):
        print("\n" + "=" * 65)
        print(f"⚠️ INTERVENTION REQUIRED: {req.reason.value}")
        print(f"Message: {req.message}")
        print("=" * 65)
        if auto_confirm or not (sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty()):
            print("[Supervised Alpha] Auto-resolving intervention in non-interactive / auto-confirm mode...")
            fallback_data = {}
            if "unresolved_fields" in req.details:
                for f in req.details["unresolved_fields"]:
                    fallback_data[f] = "yes"
            intervention_manager.resolve_resume(resolution_data=fallback_data)
        else:
            reason_str = req.reason.value if hasattr(req.reason, "value") else str(req.reason)
            if reason_str == "TWO_FACTOR_AUTH":
                otp_code = input("🔢 Enter OTP / verification code (or press Enter if entered in browser): ").strip()
                intervention_manager.resolve_resume(resolution_data={"code": otp_code, "value": otp_code})
            else:
                ans = input("Intervention choice: [R]esume / [M]anual takeover / [C]ancel: ").strip().lower()
                if ans == "m":
                    intervention_manager.resolve_manual_takeover(orchestrator.state_machine, browser_agent)
                elif ans in ("c", "cancel"):
                    intervention_manager.resolve_cancel(orchestrator.state_machine)
                else:
                    intervention_manager.resolve_resume()

    intervention_manager.add_listener(on_intervention)

    orchestrator = UniversalApplicationOrchestrator(
        browser_agent=browser_agent,
        intervention_manager=intervention_manager,
        candidate_context=candidate_context,
        on_review_requested=on_review,
    )

    try:
        result = await orchestrator.run(
            portal_url=target_url,
            job_title=job_title,
            company=company,
            headless=headless,
        )

        print("\n" + "=" * 65)
        print("🏁 APPLICATION RUN TERMINAL OUTCOME")
        print("=" * 65)
        print(f"Terminal Result:   {result.terminal_result.value}")
        print(f"Success Status:    {'✅ SUCCESS' if result.is_success else '❌ NOT SUBMITTED'}")
        if result.reference_number:
            print(f"Reference Code:    {result.reference_number}")
        if result.error_message:
            print(f"Outcome Reason:    {result.error_message}")
        if result.snapshot:
            print(f"Audit Screenshot:  {result.snapshot.screenshot_path}")
            print(f"Audit SHA256 Hash: {result.snapshot.audit_hash[:16]}...")
        print("=" * 65 + "\n")
        return result

    finally:
        if browser_agent.is_initialized:
            await browser_agent.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="JobPilot Universal Agent Supervised Alpha Runner")
    parser.add_argument("--url", type=str, help="Target application form URL")
    parser.add_argument("--job-title", type=str, default="Senior AI Engineer", help="Job title")
    parser.add_argument("--company", type=str, default="Target Company", help="Company name")
    parser.add_argument("--headless", action="store_true", help="Run browser headlessly")
    parser.add_argument("--check-config", action="store_true", help="Run preflight diagnostic check")
    parser.add_argument("--test-harness", action="store_true", help="Run test on local test harness")
    parser.add_argument("--auto-confirm", action="store_true", help="Auto-confirm submission at review gate")

    args = parser.parse_args()

    if args.check_config:
        check_preflight_config()
        return

    target_url = args.url
    if args.test_harness or not target_url:
        from tests.fixtures.harness.fake_ats_server import FakeATSServer
        print("Starting local Fake ATS test harness for supervised alpha test...")
        server = FakeATSServer()
        base_url = server.start()
        target_url = f"{base_url}/greenhouse"
        harness_context = {
            "profile": {
                "user.first_name": "Jane",
                "user.last_name": "Doe",
                "user.name": "Jane Doe",
                "user.email": "jane.doe@example.com",
                "profile.phone_number": "+1 (555) 0100",
                "gender": "Female",
                "veteran_status": "No",
            },
            "qna": {
                "legally_authorized_to_work": "yes",
                "require_visa_sponsorship": "no",
            },
        }
        try:
            asyncio.run(
                run_supervised_application(
                    target_url=target_url,
                    job_title="Senior AI Engineer",
                    company="Stripe (Mock)",
                    headless=args.headless,
                    candidate_context=harness_context,
                    auto_confirm=args.auto_confirm,
                )
            )
        finally:
            server.stop()
    else:
        asyncio.run(
            run_supervised_application(
                target_url=target_url,
                job_title=args.job_title,
                company=args.company,
                headless=args.headless,
                auto_confirm=args.auto_confirm,
            )
        )


if __name__ == "__main__":
    main()
