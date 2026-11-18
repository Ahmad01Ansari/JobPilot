"""Data models and value objects for the JobPilot AI Pilot subsystem.

Defines messages, timeline steps, human-in-the-loop interventions,
rule modifications with undo support, and operational telemetry.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class PilotAuthor(str, Enum):
    USER = "user"
    PILOT = "pilot"
    SYSTEM = "system"


class PilotActionType(str, Enum):
    CHAT = "chat"
    START_AUTOMATION = "start_automation"
    STOP_AUTOMATION = "stop_automation"
    PAUSE_AUTOMATION = "pause_automation"
    RESUME_AUTOMATION = "resume_automation"
    GET_APPLICATIONS_REPORT = "get_applications_report"
    GET_TOP_JOBS = "get_top_jobs"
    SEARCH_JOBS = "search_jobs"
    APPLY_JOBS = "apply_jobs"
    CHECK_PLATFORMS = "check_platforms"
    EXTRACT_RESUME = "extract_resume"
    GET_RESUME_SKILLS = "get_resume_skills"
    LIST_RESUMES = "list_resumes"
    TAILOR_RESUME = "tailor_resume"
    ADD_QNA = "add_qna"
    TEST_QNA = "test_qna"
    LIST_QNA = "list_qna"
    UPDATE_RULES = "update_rules"
    GET_STATUS = "get_status"
    GET_OFFERS = "get_offers"
    UPDATE_APPLICATION_STATUS = "update_application_status"
    QUERY_APPLICATION_STATUS = "query_application_status"
    DELETE_APPLICATION = "delete_application"
    UPDATE_PROFILE = "update_profile"
    GET_INTERVIEWS_REPORT = "get_interviews_report"
    GET_RULES = "get_rules"
    ANSWER_INTERVENTION = "answer_intervention"
    UNKNOWN = "unknown"


class InterventionKind(str, Enum):
    TWO_FACTOR = "two_factor"
    QUESTION = "question"
    CHOICE = "choice"
    APPROVAL = "approval"
    CAPTCHA = "captcha"


class InterventionStatus(str, Enum):
    OPEN = "open"
    ANSWERED = "answered"
    DISMISSED = "dismissed"


@dataclass
class PilotStep:
    """Represents a low-level milestone step emitted during automation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    status: str = "running"  # running, done, failed
    timestamp: datetime = field(default_factory=datetime.utcnow)
    detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PilotStep":
        ts = datetime.utcnow()
        if "timestamp" in data and data["timestamp"]:
            try:
                ts = datetime.fromisoformat(data["timestamp"])
            except Exception:
                pass
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""),
            status=data.get("status", "running"),
            timestamp=ts,
            detail=data.get("detail"),
        )


@dataclass
class PilotRuleChange:
    """Represents a configuration rule modified via natural language."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rule_key: str = ""
    description: str = ""
    previous_value: Any = None
    new_value: Any = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    can_undo: bool = True
    undone: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rule_key": self.rule_key,
            "description": self.description,
            "previous_value": self.previous_value,
            "new_value": self.new_value,
            "timestamp": self.timestamp.isoformat(),
            "can_undo": self.can_undo,
            "undone": self.undone,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PilotRuleChange":
        ts = datetime.utcnow()
        if "timestamp" in data and data["timestamp"]:
            try:
                ts = datetime.fromisoformat(data["timestamp"])
            except Exception:
                pass
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            rule_key=data.get("rule_key", ""),
            description=data.get("description", ""),
            previous_value=data.get("previous_value"),
            new_value=data.get("new_value"),
            timestamp=ts,
            can_undo=data.get("can_undo", True),
            undone=data.get("undone", False),
        )


@dataclass
class PilotIntervention:
    """Represents a human-in-the-loop interruption waiting for candidate input."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    kind: InterventionKind = InterventionKind.QUESTION
    prompt: str = ""
    options: List[str] = field(default_factory=list)
    status: InterventionStatus = InterventionStatus.OPEN
    platform: Optional[str] = None
    job_title: Optional[str] = None
    answer: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    answered_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "prompt": self.prompt,
            "options": self.options,
            "status": self.status.value,
            "platform": self.platform,
            "job_title": self.job_title,
            "answer": self.answer,
            "created_at": self.created_at.isoformat(),
            "answered_at": self.answered_at.isoformat() if self.answered_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PilotIntervention":
        ca = datetime.utcnow()
        if "created_at" in data and data["created_at"]:
            try:
                ca = datetime.fromisoformat(data["created_at"])
            except Exception:
                pass
        aa = None
        if "answered_at" in data and data["answered_at"]:
            try:
                aa = datetime.fromisoformat(data["answered_at"])
            except Exception:
                pass
        try:
            k = InterventionKind(data.get("kind", "question"))
        except Exception:
            k = InterventionKind.QUESTION
        try:
            st = InterventionStatus(data.get("status", "open"))
        except Exception:
            st = InterventionStatus.OPEN
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            kind=k,
            prompt=data.get("prompt", ""),
            options=data.get("options", []),
            status=st,
            platform=data.get("platform"),
            job_title=data.get("job_title"),
            answer=data.get("answer"),
            created_at=ca,
            answered_at=aa,
        )


@dataclass
class PilotMessage:
    """Represents a message or event in the AI Pilot conversation timeline."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    author: PilotAuthor = PilotAuthor.PILOT
    body: str = ""
    action_type: PilotActionType = PilotActionType.CHAT
    payload: Dict[str, Any] = field(default_factory=dict)
    steps: List[PilotStep] = field(default_factory=list)
    rule_change: Optional[PilotRuleChange] = None
    intervention: Optional[PilotIntervention] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "author": self.author.value,
            "body": self.body,
            "action_type": self.action_type.value,
            "payload": self.payload,
            "steps": [s.to_dict() for s in self.steps],
            "rule_change": self.rule_change.to_dict() if self.rule_change else None,
            "intervention": self.intervention.to_dict() if self.intervention else None,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PilotMessage":
        ca = datetime.utcnow()
        if "created_at" in data and data["created_at"]:
            try:
                ca = datetime.fromisoformat(data["created_at"])
            except Exception:
                pass
        try:
            auth = PilotAuthor(data.get("author", "pilot"))
        except Exception:
            auth = PilotAuthor.PILOT
        try:
            act = PilotActionType(data.get("action_type", "chat"))
        except Exception:
            act = PilotActionType.CHAT

        steps = [PilotStep.from_dict(s) for s in data.get("steps", []) if isinstance(s, dict)]
        rc = PilotRuleChange.from_dict(data["rule_change"]) if data.get("rule_change") else None
        inv = PilotIntervention.from_dict(data["intervention"]) if data.get("intervention") else None

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            author=auth,
            body=data.get("body", ""),
            action_type=act,
            payload=data.get("payload", {}),
            steps=steps,
            rule_change=rc,
            intervention=inv,
            created_at=ca,
        )


@dataclass
class PilotTelemetry:
    """Real-time operational snapshot of application intelligence."""
    status: str = "idle"  # idle, working, paused, intervention_required
    active_task: Optional[str] = None
    daily_applies: int = 0
    daily_limit: int = 25
    jobs_analyzed_today: int = 0
    avg_match_score: int = 0
    autopilot_enabled: bool = False
    open_interventions_count: int = 0
