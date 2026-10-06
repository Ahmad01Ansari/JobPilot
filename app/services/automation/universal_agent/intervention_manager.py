"""Human-in-the-Loop Intervention Manager & Manual Takeover Workflow.

Coordinates async synchronization (asyncio.Event) between background automation
workers and human operators. Handles security challenges (CAPTCHA, Login),
unknown required fields, and first-class manual application handover.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Optional

from app.services.automation.universal_agent.browser_agent.base import BrowserAgent
from app.services.automation.universal_agent.state_machine import (
    AgentExecutionState,
    InterventionReason,
    TerminalResult,
    UniversalApplicationStateMachine,
)

logger = logging.getLogger(__name__)


@dataclass
class InterventionRequest:
    """Represents an active human-in-the-loop intervention requirement."""

    reason: InterventionReason
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_resolved: bool = False
    resolution_action: Optional[str] = None  # "RESUME", "MANUAL_TAKEOVER", "CANCEL", "TIMEOUT"
    resolution_data: Optional[Dict[str, Any]] = None
    resolved_at: Optional[str] = None


@dataclass
class ManualTakeoverResult:
    """Outcome of transferring control of an active application session to the human operator."""

    success: bool
    browser_kept_open: bool
    current_url: str
    terminal_result: TerminalResult
    notes: Optional[str] = None


class InterventionManager:
    """Coordinates pause, resume, and manual takeover for universal portal automation."""

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self._loop = loop
        self._current_request: Optional[InterventionRequest] = None
        self._resolution_event: Optional[asyncio.Event] = None
        self._listeners: List[Callable[[InterventionRequest], None]] = []

    @property
    def current_request(self) -> Optional[InterventionRequest]:
        return self._current_request

    @property
    def is_paused(self) -> bool:
        return self._current_request is not None and not self._current_request.is_resolved

    def add_listener(self, callback: Callable[[InterventionRequest], None]) -> None:
        """Registers a listener notified when an intervention is triggered."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[InterventionRequest], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def trigger_intervention(
        self,
        state_machine: UniversalApplicationStateMachine,
        reason: InterventionReason,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> InterventionRequest:
        """Pauses state machine execution and creates an active intervention request."""
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        self._resolution_event = asyncio.Event()

        req = InterventionRequest(
            reason=reason,
            message=message,
            details=details or {},
        )
        self._current_request = req

        # Transition state machine to PAUSED_FOR_INTERVENTION
        if state_machine.state != AgentExecutionState.PAUSED_FOR_INTERVENTION:
            state_machine.pause_for_intervention(
                reason=reason,
                message=message,
                metadata={"message": message, **(details or {})},
            )

        # Notify registered UI / worker listeners
        for listener in self._listeners:
            try:
                listener(req)
            except Exception as e:
                logger.error("Error in intervention listener: %s", e)

        return req

    async def wait_for_resolution(self, timeout_seconds: Optional[float] = None) -> InterventionRequest:
        """Asynchronously blocks until a human operator resolves, takes over, or cancels."""
        if not self._resolution_event:
            raise RuntimeError("No active intervention event to wait on.")

        if timeout_seconds:
            try:
                await asyncio.wait_for(self._resolution_event.wait(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                if self._current_request:
                    self._current_request.is_resolved = True
                    self._current_request.resolution_action = "TIMEOUT"
                    self._current_request.resolved_at = datetime.now(timezone.utc).isoformat()
                return self._current_request
        else:
            await self._resolution_event.wait()

        return self._current_request

    def resolve_resume(self, resolution_data: Optional[Dict[str, Any]] = None) -> None:
        """Signals that the challenge is solved or missing data provided, and automation may proceed."""
        if not self._current_request or self._current_request.is_resolved:
            return

        self._current_request.is_resolved = True
        self._current_request.resolution_action = "RESUME"
        self._current_request.resolution_data = resolution_data or {}
        self._current_request.resolved_at = datetime.now(timezone.utc).isoformat()

        self._set_event_safely()

    def resolve_manual_takeover(
        self,
        state_machine: UniversalApplicationStateMachine,
        agent: Optional[BrowserAgent] = None,
        notes: Optional[str] = None,
    ) -> ManualTakeoverResult:
        """Transfers control directly to the user, leaving the browser session open."""
        if not self._current_request:
            req = InterventionRequest(
                reason=InterventionReason.MANUAL_ACTION_REQUIRED,
                message="User requested manual takeover.",
            )
            self._current_request = req

        self._current_request.is_resolved = True
        self._current_request.resolution_action = "MANUAL_TAKEOVER"
        self._current_request.resolved_at = datetime.now(timezone.utc).isoformat()

        current_url = ""
        # Keep browser open and active (do NOT call agent.close())
        if agent and agent.is_initialized:
            try:
                current_url = agent.page.url if getattr(agent, "page", None) else ""
            except Exception:
                pass

        # Transition state machine to COMPLETED with MANUAL_REQUIRED
        if state_machine.state != AgentExecutionState.COMPLETED:
            state_machine.complete(
                terminal_result=TerminalResult.MANUAL_REQUIRED,
                message=notes or "Application transferred to user for manual completion.",
                metadata={
                    "manual_takeover": True,
                    "notes": notes or "Application transferred to user for manual completion.",
                    "url": current_url,
                },
            )

        self._set_event_safely()

        return ManualTakeoverResult(
            success=True,
            browser_kept_open=True,
            current_url=current_url,
            terminal_result=TerminalResult.MANUAL_REQUIRED,
            notes=notes,
        )

    def resolve_cancel(
        self,
        state_machine: UniversalApplicationStateMachine,
        reason: str = "User cancelled application.",
    ) -> None:
        """Aborts the application process per user request."""
        if self._current_request:
            self._current_request.is_resolved = True
            self._current_request.resolution_action = "CANCEL"
            self._current_request.resolved_at = datetime.now(timezone.utc).isoformat()

        if state_machine.state != AgentExecutionState.COMPLETED:
            state_machine.complete(
                terminal_result=TerminalResult.USER_CANCELLED,
                message=reason,
                metadata={"cancellation_reason": reason},
            )

        self._set_event_safely()

    def _set_event_safely(self) -> None:
        """Thread-safe and loop-safe resolution event setter."""
        if not self._resolution_event:
            return

        if self._loop and self._loop.is_running():
            try:
                running_loop = asyncio.get_running_loop()
                if running_loop == self._loop:
                    self._resolution_event.set()
                else:
                    self._loop.call_soon_threadsafe(self._resolution_event.set)
            except RuntimeError:
                self._loop.call_soon_threadsafe(self._resolution_event.set)
        else:
            self._resolution_event.set()
