"""Application policy layer decoupled from identity deduplication."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.db.models.job_opportunity import ConfidenceLevel, JobOpportunity, OpportunityStatus


@dataclass
class PolicyEvaluationResult:
    """Outcome of application policy decision."""

    allow_application: bool
    policy_code: str  # PROCEED_NEW, SUPPRESS_ALREADY_APPLIED, SUPPRESS_IN_FLIGHT, HOLD_FOR_REVIEW, ALLOW_RETRY
    reason: str
    matched_opportunity_id: Optional[int] = None


class ApplicationPolicy:
    """Decides whether an application should proceed, be suppressed, or be held for review."""

    def __init__(
        self,
        allow_reapply_after_days: Optional[int] = None,
        review_possible_duplicates: bool = True,
    ):
        self.allow_reapply_after_days = allow_reapply_after_days
        self.review_possible_duplicates = review_possible_duplicates

    def evaluate_opportunity_application(
        self,
        opportunity: Optional[JobOpportunity],
        confidence: ConfidenceLevel,
        current_platform: str,
    ) -> PolicyEvaluationResult:
        """Evaluates policy constraints on a matched or new opportunity.

        Args:
            opportunity: Matched JobOpportunity (or None if unique).
            confidence: Confidence level from matching engine.
            current_platform: Platform name of the current listing (e.g. 'naukri').

        Returns:
            PolicyEvaluationResult with decision and explanation.
        """
        if not opportunity or confidence == ConfidenceLevel.UNIQUE:
            return PolicyEvaluationResult(
                allow_application=True,
                policy_code="PROCEED_NEW",
                reason="Unique new opportunity. Ready for normal application.",
            )

        opp_id = opportunity.id

        # 1. Ambiguous POSSIBLE match -> Escalate to review if configured
        if confidence == ConfidenceLevel.POSSIBLE:
            if self.review_possible_duplicates:
                return PolicyEvaluationResult(
                    allow_application=False,
                    policy_code="HOLD_FOR_REVIEW",
                    reason=(
                        f"Possible duplicate of opportunity #{opp_id} ('{opportunity.canonical_title}' @ "
                        f"'{opportunity.canonical_company_name}'). Flagged for user review."
                    ),
                    matched_opportunity_id=opp_id,
                )
            else:
                return PolicyEvaluationResult(
                    allow_application=True,
                    policy_code="PROCEED_POSSIBLE_UNBLOCKED",
                    reason="Possible duplicate allowed by user policy without review.",
                    matched_opportunity_id=opp_id,
                )

        # 2. Opportunity currently in flight (another worker applying)
        if opportunity.status == OpportunityStatus.APPLYING.value:
            return PolicyEvaluationResult(
                allow_application=False,
                policy_code="SUPPRESS_IN_FLIGHT",
                reason=f"Application currently in progress for opportunity #{opp_id} on {opportunity.applied_platform or 'another platform'}.",
                matched_opportunity_id=opp_id,
            )

        # 3. Opportunity already applied
        if opportunity.status == OpportunityStatus.APPLIED.value:
            # Check reapply cooldown policy
            if self.allow_reapply_after_days is not None and opportunity.applied_at:
                now_utc = datetime.now(timezone.utc)
                applied_utc = opportunity.applied_at
                if applied_utc.tzinfo is None:
                    applied_utc = applied_utc.replace(tzinfo=timezone.utc)
                days_elapsed = (now_utc - applied_utc).days

                if days_elapsed >= self.allow_reapply_after_days:
                    return PolicyEvaluationResult(
                        allow_application=True,
                        policy_code="ALLOW_RETRY_EXPIRED_COOLDOWN",
                        reason=(
                            f"Re-application permitted: {days_elapsed} days elapsed since prior application "
                            f"on {opportunity.applied_platform} (Cooldown: {self.allow_reapply_after_days} days)."
                        ),
                        matched_opportunity_id=opp_id,
                    )

            applied_date_str = opportunity.applied_at.strftime("%Y-%m-%d") if opportunity.applied_at else "prior session"
            plat_str = opportunity.applied_platform or "another platform"
            return PolicyEvaluationResult(
                allow_application=False,
                policy_code="SUPPRESS_ALREADY_APPLIED",
                reason=(
                    f"Already applied to opportunity #{opp_id} via {plat_str} on {applied_date_str}. "
                    "Application suppressed to prevent duplicate submission."
                ),
                matched_opportunity_id=opp_id,
            )

        # 4. Opportunity failed on another platform -> Allow retry on alternative platform
        if opportunity.status in ("FAILED", "TECHNICAL_ERROR"):
            return PolicyEvaluationResult(
                allow_application=True,
                policy_code="ALLOW_RETRY_ALTERNATIVE_PLATFORM",
                reason=(
                    f"Prior attempt on {opportunity.applied_platform} failed. "
                    f"Retrying application on alternative platform '{current_platform}'."
                ),
                matched_opportunity_id=opp_id,
            )

        # Default: Unapplied opportunity
        return PolicyEvaluationResult(
            allow_application=True,
            policy_code="PROCEED_UNAPPLIED",
            reason="Opportunity is unapplied. Proceeding with application.",
            matched_opportunity_id=opp_id,
        )
