"""
Setup Domain Package for JobPilot.
Exposes SetupService, SetupReadinessService, SetupState, and provider metadata.
"""

from app.services.setup.setup_requirements import (
    SetupRequirement,
    RequirementCriticality,
    RequirementStatus,
)
from app.services.setup.setup_state import (
    SetupState,
    SetupEvent,
    SETUP_SCHEMA_VERSION,
)
from app.services.setup.setup_readiness import (
    SetupReadinessService,
    ReadinessEvaluation,
    PlatformPreflightReport,
)
from app.services.setup.setup_service import SetupService
from app.services.setup.provider_definitions import (
    ProviderMetadata,
    get_all_providers,
    get_provider_by_id,
)

__all__ = [
    "SetupRequirement",
    "RequirementCriticality",
    "RequirementStatus",
    "SetupState",
    "SetupEvent",
    "SETUP_SCHEMA_VERSION",
    "SetupReadinessService",
    "ReadinessEvaluation",
    "PlatformPreflightReport",
    "SetupService",
    "ProviderMetadata",
    "get_all_providers",
    "get_provider_by_id",
]
