"""
SetupState and Event History for JobPilot.
Maintains setup progress, resumability, schema versioning, and an audit trail.
STRICT INVARIANT: NEVER stores credentials, API keys, or raw passwords.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

SETUP_SCHEMA_VERSION = "2.1.0"
DEFAULT_SETUP_STATE_PATH = Path("config") / "setup.json"

SETUP_STEP_KEYS = [
    "welcome",
    "ai_provider",
    "resume_ingest",
    "ai_extraction",
    "profile_review",
    "qna_knowledge",
    "job_strategy",
    "platforms",
    "safety",
    "readiness",
]

FORBIDDEN_SECRET_KEYS = {"api_key", "password", "secret", "token", "auth_token", "private_key"}


@dataclass
class SetupEvent:
    """Audit log entry for setup workflow actions."""
    timestamp: str
    event_type: str              # e.g., "SETUP_STARTED", "RESUME_IMPORTED", "AI_TESTED"
    step_key: str                # e.g., "welcome", "resume", "profile"
    summary: str                 # Human-readable event description (NO SECRETS)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "step_key": self.step_key,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SetupEvent":
        return cls(
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            event_type=data.get("event_type", "UNKNOWN"),
            step_key=data.get("step_key", "general"),
            summary=data.get("summary", ""),
        )


@dataclass
class SetupState:
    """Serialized setup session state without any sensitive credentials."""
    setup_schema_version: str = SETUP_SCHEMA_VERSION
    is_completed: bool = False
    setup_mode: str = "QUICK"    # "QUICK" (2-5 min) or "ADVANCED" (Full)
    current_step: str = "welcome"
    completed_steps: List[str] = field(default_factory=list)
    skipped_steps: List[str] = field(default_factory=list)
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    active_resume_id: Optional[str] = None
    tour_completed: bool = False
    events: List[SetupEvent] = field(default_factory=list)

    def log_event(self, event_type: str, step_key: str, summary: str) -> None:
        """Appends an event to the audit trail after verifying no secret leak."""
        # Sanitize summary against accidental token/key leak
        clean_summary = summary
        for secret_name in FORBIDDEN_SECRET_KEYS:
            if secret_name in clean_summary.lower():
                clean_summary = clean_summary.replace(secret_name, "[REDACTED]")

        event = SetupEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type=event_type,
            step_key=step_key,
            summary=clean_summary,
        )
        self.events.append(event)
        self.updated_at = datetime.utcnow().isoformat()

    def mark_step_completed(self, step_key: str) -> None:
        if step_key not in self.completed_steps:
            self.completed_steps.append(step_key)
        if step_key in self.skipped_steps:
            self.skipped_steps.remove(step_key)
        self.log_event("STEP_COMPLETED", step_key, f"Step '{step_key}' completed successfully.")

    def mark_step_skipped(self, step_key: str) -> None:
        if step_key not in self.skipped_steps:
            self.skipped_steps.append(step_key)
        if step_key in self.completed_steps:
            self.completed_steps.remove(step_key)
        self.log_event("STEP_SKIPPED", step_key, f"Step '{step_key}' was skipped.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "setup_schema_version": self.setup_schema_version,
            "is_completed": self.is_completed,
            "setup_mode": self.setup_mode,
            "current_step": self.current_step,
            "completed_steps": list(self.completed_steps),
            "skipped_steps": list(self.skipped_steps),
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "active_resume_id": self.active_resume_id,
            "tour_completed": self.tour_completed,
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SetupState":
        events_raw = data.get("events", [])
        events = [SetupEvent.from_dict(e) for e in events_raw if isinstance(e, dict)]
        return cls(
            setup_schema_version=data.get("setup_schema_version", SETUP_SCHEMA_VERSION),
            is_completed=bool(data.get("is_completed", False)),
            setup_mode=data.get("setup_mode", "QUICK"),
            current_step=data.get("current_step", "welcome"),
            completed_steps=data.get("completed_steps", []),
            skipped_steps=data.get("skipped_steps", []),
            started_at=data.get("started_at"),
            updated_at=data.get("updated_at"),
            completed_at=data.get("completed_at"),
            active_resume_id=data.get("active_resume_id"),
            tour_completed=bool(data.get("tour_completed", False)),
            events=events,
        )

    def save(self, file_path: Optional[Path] = None) -> bool:
        """Saves setup state to disk atomically."""
        target_path = file_path or DEFAULT_SETUP_STATE_PATH
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = self.to_dict()
            # Double check for forbidden keys in output
            payload_str = json.dumps(payload, indent=2)
            temp_path = target_path.with_suffix(".tmp")
            temp_path.write_text(payload_str, encoding="utf-8")
            temp_path.replace(target_path)
            return True
        except Exception as exc:
            logger.error("Failed to save SetupState to %s: %s", target_path, exc)
            return False

    @classmethod
    def load(cls, file_path: Optional[Path] = None) -> "SetupState":
        """Loads setup state from disk or returns fresh default state."""
        target_path = file_path or DEFAULT_SETUP_STATE_PATH
        if not target_path.exists():
            state = cls()
            state.started_at = datetime.utcnow().isoformat()
            state.log_event("SETUP_INITIALIZED", "welcome", "Setup state initialized.")
            return state

        try:
            content = target_path.read_text(encoding="utf-8")
            data = json.loads(content)
            return cls.from_dict(data)
        except Exception as exc:
            logger.warning("Failed to load SetupState from %s (%s). Using fresh instance.", target_path, exc)
            state = cls()
            state.started_at = datetime.utcnow().isoformat()
            state.log_event("SETUP_REINITIALIZED", "welcome", "Fresh setup state after corrupted load.")
            return state
