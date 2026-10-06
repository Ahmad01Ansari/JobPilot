"""Immutable Audit Snapshot Recorder for Universal Application Agent.

Captures post-submission visual proof (PNG screenshot), full DOM outerHTML,
and generates cryptographic SHA-256 audit hashes to certify submission authenticity.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.automation.universal_agent.browser_agent.base import BrowserAgent
from app.services.automation.universal_agent.result_verifier import VerificationResult
from app.services.automation.universal_agent.state_machine import TerminalResult


@dataclass
class ApplicationSubmissionSnapshot:
    """Immutable audit record certifying an application attempt and outcome."""

    portal_url: str
    submission_timestamp: str
    status: str
    terminal_result: str
    reference_number: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
    filled_fields_summary: Dict[str, Any] = field(default_factory=dict)
    screenshot_path: Optional[str] = None
    dom_html_path: Optional[str] = None
    metadata_path: Optional[str] = None
    audit_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SnapshotRecorder:
    """Captures and stores immutable audit snapshots of submitted applications."""

    def __init__(self, base_snapshot_dir: Optional[str] = None) -> None:
        if base_snapshot_dir:
            self.base_snapshot_dir = Path(base_snapshot_dir).resolve()
        else:
            try:
                from app.services.os.app_paths import AppPaths
                self.base_snapshot_dir = AppPaths.get_snapshots_dir()
            except Exception:
                self.base_snapshot_dir = Path.home() / ".jobpilot" / "snapshots"
        self.base_snapshot_dir.mkdir(parents=True, exist_ok=True)

    async def capture_snapshot(
        self,
        agent: BrowserAgent,
        verification: VerificationResult,
        terminal_result: TerminalResult,
        output_dir: Optional[str] = None,
        filled_fields: Optional[Dict[str, Any]] = None,
        job_title: Optional[str] = None,
        company: Optional[str] = None,
    ) -> ApplicationSubmissionSnapshot:
        """Captures screenshot, DOM HTML, and writes cryptographic metadata record."""
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        target_dir = Path(output_dir).resolve() if output_dir else (self.base_snapshot_dir / f"snap_{timestamp_str}")
        target_dir.mkdir(parents=True, exist_ok=True)

        url = await agent.get_url()
        screenshot_file = target_dir / "submission_screenshot.png"
        dom_file = target_dir / "submission_dom.html"
        metadata_file = target_dir / "snapshot_metadata.json"

        # 1. Capture visual screenshot proof
        screenshot_bytes = b""
        try:
            screenshot_bytes = await agent.screenshot(path=str(screenshot_file))
        except Exception:
            pass

        # 2. Capture full DOM HTML
        dom_content = ""
        try:
            dom_content = await agent.get_content()
            dom_file.write_text(dom_content, encoding="utf-8")
        except Exception:
            pass

        # 3. Compute Cryptographic SHA-256 Audit Hash
        hasher = hashlib.sha256()
        hasher.update(screenshot_bytes)
        hasher.update(dom_content.encode("utf-8"))
        hasher.update(str(verification.reference_number or "").encode("utf-8"))
        hasher.update(url.encode("utf-8"))
        audit_hash = hasher.hexdigest()

        snapshot = ApplicationSubmissionSnapshot(
            portal_url=url,
            submission_timestamp=datetime.now(timezone.utc).isoformat(),
            status=verification.status,
            terminal_result=terminal_result.value,
            reference_number=verification.reference_number,
            job_title=job_title,
            company=company,
            filled_fields_summary=filled_fields or {},
            screenshot_path=str(screenshot_file) if screenshot_file.exists() else None,
            dom_html_path=str(dom_file) if dom_file.exists() else None,
            metadata_path=str(metadata_file),
            audit_hash=audit_hash,
        )

        # 4. Write immutable metadata JSON
        metadata_file.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")

        return snapshot

    def persist_to_application_record(
        self,
        snapshot: ApplicationSubmissionSnapshot,
        application_id: int,
        session_factory=None,
    ) -> bool:
        """Stores snapshot audit metadata onto the relational Application entity."""
        try:
            from app.db.session import get_db_session
            from app.db.models.application import Application
            from app.db.models.status_history import ApplicationStatusHistory

            with get_db_session(session_factory) as session:
                app = session.get(Application, application_id)
                if not app:
                    return False

                app.notes = json.dumps({
                    "audit_snapshot": snapshot.to_dict(),
                    "reference_number": snapshot.reference_number,
                    "audit_hash": snapshot.audit_hash,
                })

                if snapshot.terminal_result == TerminalResult.SUCCESS_SUBMITTED.value:
                    app.status = "SUBMITTED"
                    app.automation_status = "SUCCESS"
                    app.applied_at = datetime.now(timezone.utc)
                elif snapshot.terminal_result == TerminalResult.MANUAL_REQUIRED.value:
                    app.status = "UNDER_REVIEW"
                    app.automation_status = "MANUAL_REQUIRED"

                session.commit()
                return True
        except Exception:
            return False
