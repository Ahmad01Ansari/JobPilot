"""Normalized domain events and data transfer objects for automation observability."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
from typing import Any, Dict, Optional
import uuid

from app.services.sanitizer_service import LogSanitizer


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class EventSource(str, Enum):
    """Precedence origin of the incoming event."""

    SIGNAL = "SIGNAL"                     # Tier 1 (Primary): Typed Qt signal from AutomationWorker
    STRUCTURED_LOG = "STRUCTURED_LOG"     # Tier 2: Structured JSON or engine payload
    PARSED_LOG = "PARSED_LOG"             # Tier 3 (Fallback): Deterministic regex from engine tags
    RAW = "RAW"                           # Tier 4: Unparsed forensic log line


class AutomationEventType(str, Enum):
    """Normalized semantic lifecycle and operational event types."""

    # Run Lifecycle
    RUN_STARTED = "RUN_STARTED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_STOPPED = "RUN_STOPPED"
    RUN_PAUSED = "RUN_PAUSED"

    # Search & Discovery
    SEARCH_STARTED = "SEARCH_STARTED"
    SEARCH_COMPLETED = "SEARCH_COMPLETED"
    JOB_DISCOVERED = "JOB_DISCOVERED"
    JOB_QUALIFIED = "JOB_QUALIFIED"
    JOB_SKIPPED = "JOB_SKIPPED"

    # Application & Execution Stages
    APPLICATION_STARTED = "APPLICATION_STARTED"
    STAGE_TRANSITION = "STAGE_TRANSITION"
    QUESTION_DETECTED = "QUESTION_DETECTED"
    QUESTION_ANSWERED = "QUESTION_ANSWERED"
    RESUME_ATTACHED = "RESUME_ATTACHED"
    APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
    APPLICATION_FAILED = "APPLICATION_FAILED"

    # Interventions & Recovery
    CAPTCHA_DETECTED = "CAPTCHA_DETECTED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"
    RETRY_ATTEMPT = "RETRY_ATTEMPT"
    RATE_LIMITED = "RATE_LIMITED"
    ERROR = "ERROR"
    RAW_LOG = "RAW_LOG"


@dataclass
class LogFileReference:
    """Stable reference to a specific location in a log file."""

    log_file: str                       # e.g. "logs/log.txt"
    file_mtime: float                   # File mtime at recording
    line_number: int                    # 1-indexed line number at recording
    byte_offset: int                    # Byte seek offset in file
    line_fingerprint: str               # SHA256 prefix of raw line
    is_valid: bool = True               # Flagged False if file was truncated/rotated

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogFileReference":
        return cls(**data)


@dataclass
class AutomationEvent:
    """Normalized, deduplicated domain event representing an automation occurrence."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = "default"
    timestamp: datetime = field(default_factory=_now_utc)
    sequence: int = 0
    source: EventSource = EventSource.SIGNAL
    level: str = "INFO"                 # INFO, WARNING, ERROR, CRITICAL
    event_type: AutomationEventType = AutomationEventType.RAW_LOG

    # Execution Context
    platform: str = "unknown"
    engine: Optional[str] = None
    stage: Optional[str] = None         # SEARCH, DISCOVER, QUALIFY, APPLICATION, etc.

    # Entity Identity (Non-secret correlation identifiers)
    job_id: Optional[int] = None
    application_id: Optional[int] = None
    company: Optional[str] = None
    job_title: Optional[str] = None

    # Step & Progress Details
    action: Optional[str] = None
    status: Optional[str] = None        # SUCCESS, FAILED, PENDING, INTERVENTION
    duration_ms: Optional[int] = None
    attempt_number: int = 1

    # Forensic & Diagnostic Payload (Always sanitized)
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_reference: Optional[LogFileReference] = None

    def __post_init__(self) -> None:
        """Enforces sanitization on human-readable message and string metadata."""
        if self.message:
            self.message = LogSanitizer.sanitize_text(self.message)
        if self.metadata and isinstance(self.metadata, dict):
            sanitized_meta = {}
            for k, v in self.metadata.items():
                if isinstance(v, str):
                    sanitized_meta[k] = LogSanitizer.sanitize_text(v)
                elif isinstance(v, dict):
                    sanitized_meta[k] = {
                        sub_k: LogSanitizer.sanitize_text(str(sub_v)) if isinstance(sub_v, str) else sub_v
                        for sub_k, sub_v in v.items()
                    }
                else:
                    sanitized_meta[k] = v
            self.metadata = sanitized_meta

    def get_fingerprint(self) -> str:
        """Calculates a deterministic identity hash used for deduplication."""
        e_type = self.event_type.value if hasattr(self.event_type, "value") else str(self.event_type)
        components = [
            str(self.run_id or ""),
            e_type,
            str(self.job_id or ""),
            str(self.application_id or ""),
            str(self.action or ""),
            str(self.status or ""),
        ]
        raw_key = ":".join(components)
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the event to a JSON-compatible dictionary."""
        d = {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
            "source": self.source.value if hasattr(self.source, "value") else str(self.source),
            "level": self.level,
            "event_type": self.event_type.value if hasattr(self.event_type, "value") else str(self.event_type),
            "platform": self.platform,
            "engine": self.engine,
            "stage": self.stage,
            "job_id": self.job_id,
            "application_id": self.application_id,
            "company": self.company,
            "job_title": self.job_title,
            "action": self.action,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "attempt_number": self.attempt_number,
            "message": self.message,
            "metadata": self.metadata,
            "raw_reference": self.raw_reference.to_dict() if self.raw_reference else None,
        }
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutomationEvent":
        """Deserializes event from dictionary."""
        raw_ref_data = data.get("raw_reference")
        raw_ref = LogFileReference.from_dict(raw_ref_data) if raw_ref_data else None

        ts_raw = data.get("timestamp")
        if isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw)
            except Exception:
                ts = _now_utc()
        elif isinstance(ts_raw, datetime):
            ts = ts_raw
        else:
            ts = _now_utc()

        src_val = data.get("source", EventSource.SIGNAL.value)
        try:
            source = EventSource(src_val)
        except ValueError:
            source = EventSource.SIGNAL

        type_val = data.get("event_type", AutomationEventType.RAW_LOG.value)
        try:
            event_type = AutomationEventType(type_val)
        except ValueError:
            event_type = AutomationEventType.RAW_LOG

        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            run_id=data.get("run_id", "default"),
            timestamp=ts,
            sequence=data.get("sequence", 0),
            source=source,
            level=data.get("level", "INFO"),
            event_type=event_type,
            platform=data.get("platform", "unknown"),
            engine=data.get("engine"),
            stage=data.get("stage"),
            job_id=data.get("job_id"),
            application_id=data.get("application_id"),
            company=data.get("company"),
            job_title=data.get("job_title"),
            action=data.get("action"),
            status=data.get("status"),
            duration_ms=data.get("duration_ms"),
            attempt_number=data.get("attempt_number", 1),
            message=data.get("message", ""),
            metadata=data.get("metadata", {}),
            raw_reference=raw_ref,
        )
