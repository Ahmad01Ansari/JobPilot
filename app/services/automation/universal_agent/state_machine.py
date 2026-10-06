"""Deterministic application lifecycle state machine with decoupled execution, intervention, and terminal enums."""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.services.automation.universal_agent.timeline import AgentRunTimeline


class AgentExecutionState(str, Enum):
    """Current operational state of the universal application agent."""

    IDLE = "IDLE"
    INITIALIZING = "INITIALIZING"
    NAVIGATING = "NAVIGATING"
    ANALYZING_PAGE = "ANALYZING_PAGE"
    MAPPING_FIELDS = "MAPPING_FIELDS"
    FILLING_FORM = "FILLING_FORM"
    UPLOADING_RESUME = "UPLOADING_RESUME"
    NAVIGATING_NEXT_STEP = "NAVIGATING_NEXT_STEP"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    PAUSED_FOR_INTERVENTION = "PAUSED_FOR_INTERVENTION"
    SUBMITTING = "SUBMITTING"
    VERIFYING_SUBMISSION = "VERIFYING_SUBMISSION"
    COMPLETED = "COMPLETED"


class InterventionReason(str, Enum):
    """Explicit justification for pausing automation and requesting human attention."""

    NONE = "NONE"
    CAPTCHA_CHALLENGE = "CAPTCHA_CHALLENGE"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    TWO_FACTOR_AUTH = "TWO_FACTOR_AUTH"
    UNKNOWN_REQUIRED_FIELD = "UNKNOWN_REQUIRED_FIELD"
    AMBIGUOUS_OPTIONS = "AMBIGUOUS_OPTIONS"
    COMPLEX_CUSTOM_WIDGET = "COMPLEX_CUSTOM_WIDGET"
    PRE_SUBMISSION_REVIEW = "PRE_SUBMISSION_REVIEW"
    POST_SUBMIT_VALIDATION_ERROR = "POST_SUBMIT_VALIDATION_ERROR"
    MANUAL_ACTION_REQUIRED = "MANUAL_ACTION_REQUIRED"
    NAVIGATION_OR_NETWORK_STALL = "NAVIGATION_OR_NETWORK_STALL"
    SUBMISSION_UNCERTAIN = "SUBMISSION_UNCERTAIN"


class TerminalResult(str, Enum):
    """Final session outcome upon completion or termination."""

    NONE = "NONE"
    SUCCESS_SUBMITTED = "SUCCESS_SUBMITTED"
    FAILED_UNRECOVERABLE = "FAILED_UNRECOVERABLE"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"
    SKIPPED_DISQUALIFIED = "SKIPPED_DISQUALIFIED"
    USER_CANCELLED = "USER_CANCELLED"
    SUBMISSION_STATUS_UNKNOWN = "SUBMISSION_STATUS_UNKNOWN"


class IllegalStateTransitionError(Exception):
    """Raised when an illegal or unsafe state machine transition is attempted."""

    def __init__(self, from_state: AgentExecutionState, to_state: AgentExecutionState, message: str) -> None:
        super().__init__(f"Illegal transition from {from_state.value} to {to_state.value}: {message}")
        self.from_state = from_state
        self.to_state = to_state


class UniversalApplicationStateMachine:
    """Manages deterministic agent execution states, intervention pauses, and timeline emission."""

    # Explicit whitelist of valid state transitions:
    _VALID_TRANSITIONS = {
        AgentExecutionState.IDLE: {
            AgentExecutionState.INITIALIZING,
            AgentExecutionState.COMPLETED,
        },
        AgentExecutionState.INITIALIZING: {
            AgentExecutionState.NAVIGATING,
            AgentExecutionState.PAUSED_FOR_INTERVENTION,
            AgentExecutionState.COMPLETED,
        },
        AgentExecutionState.NAVIGATING: {
            AgentExecutionState.ANALYZING_PAGE,
            AgentExecutionState.PAUSED_FOR_INTERVENTION,
            AgentExecutionState.COMPLETED,
        },
        AgentExecutionState.ANALYZING_PAGE: {
            AgentExecutionState.MAPPING_FIELDS,
            AgentExecutionState.NAVIGATING,
            AgentExecutionState.PAUSED_FOR_INTERVENTION,
            AgentExecutionState.COMPLETED,
        },
        AgentExecutionState.MAPPING_FIELDS: {
            AgentExecutionState.FILLING_FORM,
            AgentExecutionState.PAUSED_FOR_INTERVENTION,
            AgentExecutionState.COMPLETED,
        },
        AgentExecutionState.FILLING_FORM: {
            AgentExecutionState.UPLOADING_RESUME,
            AgentExecutionState.NAVIGATING,
            AgentExecutionState.NAVIGATING_NEXT_STEP,
            AgentExecutionState.PENDING_HUMAN_REVIEW,
            AgentExecutionState.PAUSED_FOR_INTERVENTION,
            AgentExecutionState.COMPLETED,
        },
        AgentExecutionState.UPLOADING_RESUME: {
            AgentExecutionState.NAVIGATING_NEXT_STEP,
            AgentExecutionState.PENDING_HUMAN_REVIEW,
            AgentExecutionState.PAUSED_FOR_INTERVENTION,
            AgentExecutionState.COMPLETED,
        },
        AgentExecutionState.NAVIGATING_NEXT_STEP: {
            AgentExecutionState.ANALYZING_PAGE,
            AgentExecutionState.MAPPING_FIELDS,
            AgentExecutionState.FILLING_FORM,
            AgentExecutionState.PENDING_HUMAN_REVIEW,
            AgentExecutionState.PAUSED_FOR_INTERVENTION,
            AgentExecutionState.COMPLETED,
        },
        AgentExecutionState.PENDING_HUMAN_REVIEW: {
            # In V1, submission MUST originate from human review confirmation
            AgentExecutionState.SUBMITTING,
            AgentExecutionState.PAUSED_FOR_INTERVENTION,
            AgentExecutionState.COMPLETED,
        },
        AgentExecutionState.PAUSED_FOR_INTERVENTION: {
            # Can resume back to any active operational state, or complete/cancel
            AgentExecutionState.INITIALIZING,
            AgentExecutionState.NAVIGATING,
            AgentExecutionState.ANALYZING_PAGE,
            AgentExecutionState.MAPPING_FIELDS,
            AgentExecutionState.FILLING_FORM,
            AgentExecutionState.UPLOADING_RESUME,
            AgentExecutionState.NAVIGATING_NEXT_STEP,
            AgentExecutionState.PENDING_HUMAN_REVIEW,
            AgentExecutionState.SUBMITTING,
            AgentExecutionState.VERIFYING_SUBMISSION,
            AgentExecutionState.COMPLETED,
        },
        AgentExecutionState.SUBMITTING: {
            AgentExecutionState.VERIFYING_SUBMISSION,
            AgentExecutionState.PAUSED_FOR_INTERVENTION,
            AgentExecutionState.COMPLETED,
        },
        AgentExecutionState.VERIFYING_SUBMISSION: {
            AgentExecutionState.COMPLETED,
            AgentExecutionState.PAUSED_FOR_INTERVENTION,
        },
        AgentExecutionState.COMPLETED: {
            AgentExecutionState.IDLE,  # Reset
        },
    }

    def __init__(self, timeline: Optional[AgentRunTimeline] = None) -> None:
        self.state: AgentExecutionState = AgentExecutionState.IDLE
        self.previous_active_state: Optional[AgentExecutionState] = None
        self.intervention_reason: InterventionReason = InterventionReason.NONE
        self.terminal_result: TerminalResult = TerminalResult.NONE
        self.timeline: AgentRunTimeline = timeline or AgentRunTimeline()
        self._listeners: List[Callable[[AgentExecutionState, AgentExecutionState, InterventionReason, Optional[str]], None]] = []

    @property
    def current_state(self) -> AgentExecutionState:
        """Alias for self.state representing the current execution state."""
        return self.state

    @property
    def is_success(self) -> bool:
        """Indicates whether the state machine concluded with successful submission."""
        return self.terminal_result == TerminalResult.SUCCESS_SUBMITTED

    @property
    def terminal_message(self) -> str:
        """Returns the final message or last timeline event message."""
        if hasattr(self.timeline, "events") and self.timeline.events:
            return self.timeline.events[-1].message
        return ""

    def add_listener(
        self,
        callback: Callable[[AgentExecutionState, AgentExecutionState, InterventionReason, Optional[str]], None],
    ) -> None:
        """Subscribes an event listener to state machine transitions."""
        self._listeners.append(callback)

    def transition_to(
        self,
        new_state: AgentExecutionState,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Transitions state machine to new_state if valid."""
        if new_state == self.state:
            return

        valid_targets = self._VALID_TRANSITIONS.get(self.state, set())
        if new_state not in valid_targets:
            raise IllegalStateTransitionError(
                self.state,
                new_state,
                f"Transition not permitted. In V1, final submission must pass through PENDING_HUMAN_REVIEW.",
            )

        combined_meta = dict(metadata or {})
        if details:
            combined_meta.update(details)

        old_state = self.state
        self.state = new_state

        # Record timeline event
        self.timeline.add_event(
            state=new_state.value,
            event_type="STATE_CHANGE",
            message=message or f"Transitioned from {old_state.value} to {new_state.value}",
            metadata=combined_meta if combined_meta else None,
        )

        # Notify listeners
        for listener in self._listeners:
            try:
                listener(old_state, new_state, self.intervention_reason, message)
            except Exception:
                pass

    def pause_for_intervention(
        self,
        reason: InterventionReason,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Transitions to PAUSED_FOR_INTERVENTION and preserves current active state for resume."""
        if reason == InterventionReason.NONE:
            raise ValueError("Must specify an explicit InterventionReason when pausing.")

        self.previous_active_state = self.state
        self.intervention_reason = reason

        meta = dict(metadata or {})
        meta["intervention_reason"] = reason.value

        self.transition_to(
            AgentExecutionState.PAUSED_FOR_INTERVENTION,
            message=message,
            metadata=meta,
        )

    def resume_from_intervention(self, message: str = "Resumed after intervention") -> None:
        """Resumes execution returning to the previous operational state."""
        if self.state != AgentExecutionState.PAUSED_FOR_INTERVENTION:
            raise RuntimeError(f"Cannot resume from state {self.state.value}; machine is not paused.")

        target_state = self.previous_active_state or AgentExecutionState.ANALYZING_PAGE
        self.intervention_reason = InterventionReason.NONE
        self.previous_active_state = None

        self.transition_to(target_state, message=message)

    def complete(
        self,
        terminal_result: TerminalResult,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Transitions to COMPLETED and records terminal result outcome."""
        self.terminal_result = terminal_result
        meta = dict(metadata or {})
        meta["terminal_result"] = terminal_result.value

        self.transition_to(
            AgentExecutionState.COMPLETED,
            message=message or f"Execution concluded with result: {terminal_result.value}",
            metadata=meta,
        )

    def reset(self) -> None:
        """Resets the state machine back to IDLE."""
        self.state = AgentExecutionState.IDLE
        self.previous_active_state = None
        self.intervention_reason = InterventionReason.NONE
        self.terminal_result = TerminalResult.NONE
