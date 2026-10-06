"""
Setup Requirements and Criticality Models for JobPilot.
Defines atomic capabilities, their criticality tier (CORE vs RECOMMENDED vs OPTIONAL),
and status lifecycle for the Setup Wizard and Readiness Engine.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


class RequirementCriticality(str, Enum):
    """Criticality levels for setup requirements."""
    CORE = "CORE"                    # Must have to use basic JobPilot (Profile, Resume, Prefs)
    RECOMMENDED = "RECOMMENDED"      # Highly recommended (AI Provider, Screening Q&A)
    OPTIONAL = "OPTIONAL"            # Feature-specific (Platform credentials, Automation limits)


class RequirementStatus(str, Enum):
    """Lifecycle status for a setup requirement."""
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    READY = "READY"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class SetupRequirement:
    """Represents a discrete setup requirement evaluated by ReadinessService."""
    key: str                         # e.g., "candidate_profile", "primary_resume", "ai_provider"
    title: str                       # e.g., "Candidate Profile"
    description: str                 # e.g., "Basic personal info, target role, and key skills"
    criticality: RequirementCriticality
    status: RequirementStatus = RequirementStatus.NOT_STARTED
    blocking: bool = False           # True only if required for current target capability
    route: str = "profile"           # Associated UI navigation route (Ctrl+1..9)
    fix_action: str = "edit_profile" # Wizard step or settings handler
    details: Dict[str, Any] = field(default_factory=dict) # e.g. {"name": "Ahmad", "missing_fields": []}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "description": self.description,
            "criticality": self.criticality.value,
            "status": self.status.value,
            "blocking": self.blocking,
            "route": self.route,
            "fix_action": self.fix_action,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SetupRequirement":
        return cls(
            key=data["key"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            criticality=RequirementCriticality(data.get("criticality", RequirementCriticality.CORE.value)),
            status=RequirementStatus(data.get("status", RequirementStatus.NOT_STARTED.value)),
            blocking=bool(data.get("blocking", False)),
            route=data.get("route", "profile"),
            fix_action=data.get("fix_action", ""),
            details=data.get("details", {}),
        )
