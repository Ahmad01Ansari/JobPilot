"""Outreach DTOs and Enums package."""

from app.services.dto.outreach_enums import (
    CANONICAL_APPLICATION_METHOD_EMAIL,
    CANONICAL_PLATFORM_EMAIL,
    CANONICAL_SOURCE_DIRECT_EMAIL,
    ConversationState,
    FollowUpStatus,
    InboundClassification,
    MessageStatus,
)
from app.services.dto.outreach_dto import (
    ConnectionStatusDTO,
    DuplicateMatchResultDTO,
    EmailMessageDTO,
    ExpandedInboundEmailDTO,
    OutreachCreateDTO,
    SendResultDTO,
    SyncCheckpointDTO,
)
from app.services.dto.outreach_viewmodels import (
    ContactViewModel,
    ConversationDetailViewModel,
    FollowUpStepViewModel,
    NextActionRecommendation,
    OutreachConversationViewModel,
    PresentationConversationState,
    ResumeSnapshotViewModel,
    TimelineMessageViewModel,
)

from app.services.dto.qualification_enums import (
    AIStatus,
    EvaluationStatus,
    ExperienceStrength,
    QualificationDecision,
)
from app.services.dto.qualification_dto import (
    CandidateQualificationContext,
    ExperienceEvaluationResult,
    JobQualificationInput,
    QualificationResultDTO,
    ScoringWeights,
    SkillMatchResult,
)

__all__ = [
    "MessageStatus",
    "ConversationState",
    "FollowUpStatus",
    "InboundClassification",
    "CANONICAL_APPLICATION_METHOD_EMAIL",
    "CANONICAL_PLATFORM_EMAIL",
    "CANONICAL_SOURCE_DIRECT_EMAIL",
    "OutreachCreateDTO",
    "EmailMessageDTO",
    "SendResultDTO",
    "ExpandedInboundEmailDTO",
    "SyncCheckpointDTO",
    "DuplicateMatchResultDTO",
    "ConnectionStatusDTO",
    # Presentation ViewModels (Outreach Redesign)
    "PresentationConversationState",
    "NextActionRecommendation",
    "OutreachConversationViewModel",
    "ConversationDetailViewModel",
    "ContactViewModel",
    "ResumeSnapshotViewModel",
    "TimelineMessageViewModel",
    "FollowUpStepViewModel",
    # Qualification Engine DTOs and Enums
    "QualificationDecision",
    "EvaluationStatus",
    "AIStatus",
    "ExperienceStrength",
    "CandidateQualificationContext",
    "JobQualificationInput",
    "ScoringWeights",
    "SkillMatchResult",
    "ExperienceEvaluationResult",
    "QualificationResultDTO",
]
