"""Cross-platform Job and Application Deduplication Package."""

from app.services.dedup.application_policy import ApplicationPolicy, PolicyEvaluationResult
from app.services.dedup.entity_normalizer import EntityNormalizer
from app.services.dedup.job_dedup_service import JobDeduplicationService
from app.services.dedup.matching_engine import MatchResult, MultiSignalMatchingEngine
from app.services.dedup.url_normalizer import URLNormalizer

__all__ = [
    "URLNormalizer",
    "EntityNormalizer",
    "MultiSignalMatchingEngine",
    "MatchResult",
    "ApplicationPolicy",
    "PolicyEvaluationResult",
    "JobDeduplicationService",
]
