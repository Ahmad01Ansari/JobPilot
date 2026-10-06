"""Structured execution timeline for Universal AI Application Agent runs."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TimelineEvent:
    """Discrete, ordered event occurring during an agent execution run."""

    state: str
    event_type: str
    message: str
    timestamp: datetime = field(default_factory=_now_utc)
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "state": self.state,
            "event_type": self.event_type,
            "message": self.message,
            "metadata": self.metadata or {},
        }


class AgentRunTimeline:
    """In-memory chronological timeline tracking agent execution steps and events."""

    def __init__(self, run_id: Optional[str] = None) -> None:
        self.run_id = run_id or "default"
        self._events: List[TimelineEvent] = []

    @property
    def events(self) -> List[TimelineEvent]:
        return list(self._events)

    def add_event(
        self,
        state: str,
        event_type: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TimelineEvent:
        """Appends a new discrete event to the timeline."""
        evt = TimelineEvent(
            state=str(state),
            event_type=event_type,
            message=message,
            metadata=metadata,
        )
        self._events.append(evt)
        return evt

    def get_events_by_state(self, state: str) -> List[TimelineEvent]:
        """Filters events matching a specific execution state."""
        target = str(state)
        return [e for e in self._events if e.state == target]

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Serializes all timeline events into JSON-compatible dictionary records."""
        return [e.to_dict() for e in self._events]

    def clear(self) -> None:
        """Clears all timeline events."""
        self._events.clear()
