"""Logs and automation observability service package."""

from app.services.logs.automation_event import (
    AutomationEvent,
    AutomationEventType,
    EventSource,
    LogFileReference,
)
from app.services.logs.automation_log_bridge import AutomationLogBridge
from app.services.logs.event_correlator import EventCorrelator
from app.services.logs.log_normalizer import LogNormalizer
from app.services.logs.run_context import RunObservabilityContext, RunRegistry
from app.services.logs.run_persistence_bridge import RunPersistenceBridge

__all__ = [
    "AutomationEvent",
    "AutomationEventType",
    "EventSource",
    "LogFileReference",
    "EventCorrelator",
    "LogNormalizer",
    "AutomationLogBridge",
    "RunObservabilityContext",
    "RunRegistry",
    "RunPersistenceBridge",
]
