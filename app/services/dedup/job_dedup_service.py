"""Comprehensive Job Deduplication & Opportunity Lifecycle Coordinator."""

import logging
import threading
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import utc_now
from app.db.models.job import Job
from app.db.models.job_opportunity import (
    ConfidenceLevel,
    DedupDecision,
    JobDeduplicationEvidence,
    JobOpportunity,
    OpportunityStatus,
)
from app.db.session import SessionLocal, get_db_session
from app.services.dedup.application_policy import ApplicationPolicy, PolicyEvaluationResult
from app.services.dedup.entity_normalizer import EntityNormalizer
from app.services.dedup.matching_engine import MatchResult, MultiSignalMatchingEngine
from app.services.dedup.url_normalizer import URLNormalizer

logger = logging.getLogger(__name__)


class JobDeduplicationService:
    """Orchestrates multi-signal deduplication, canonical opportunity creation, and concurrency locking."""

    _process_lock = threading.Lock()

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        policy: Optional[ApplicationPolicy] = None,
    ):
        self._session_factory = session_factory or SessionLocal
        self.policy = policy or ApplicationPolicy()

    def process_incoming_job(self, job_id: int) -> Tuple[JobOpportunity, DedupDecision, PolicyEvaluationResult]:
        """Processes a discovered Job listing, links or creates JobOpportunity, and records evidence.

        Args:
            job_id: Database ID of the Job listing.

        Returns:
            Tuple of (JobOpportunity, DedupDecision, PolicyEvaluationResult).
        """
        with self._process_lock:
            with get_db_session(self._session_factory) as session:
                job = session.get(Job, job_id)
                if not job:
                    raise ValueError(f"Job with ID {job_id} not found.")

                # 1. Normalize application URL and extract ATS metadata
                norm_app_url = URLNormalizer.normalize_application_url(job.application_url)
                url_hash = URLNormalizer.compute_canonical_url_hash(norm_app_url)
                ats_provider, ats_job_id = URLNormalizer.extract_ats_metadata(norm_app_url)

                # Update listing's canonical hash if available
                if url_hash and not job.canonical_url_hash:
                    job.canonical_url_hash = url_hash

                # 2. Retrieve candidate opportunities
                candidates = self._find_candidate_opportunities(
                    session=session,
                    company_name=job.company_raw,
                    url_hash=url_hash,
                    ats_provider=ats_provider,
                    ats_job_id=ats_job_id,
                )

                # 3. Evaluate multi-signal match
                match = MultiSignalMatchingEngine.evaluate_match(
                    incoming_title=job.title,
                    incoming_company=job.company_raw,
                    incoming_application_url=job.application_url,
                    incoming_location=job.location,
                    incoming_work_style=job.work_style,
                    incoming_description=job.description,
                    candidate_opportunities=candidates,
                )

                opportunity: JobOpportunity
                decision: DedupDecision

                if match.confidence in (ConfidenceLevel.EXACT, ConfidenceLevel.HIGH):
                    # Safe automatic linking
                    opportunity = match.matched_opportunity  # type: ignore[assignment]
                    job.opportunity_id = opportunity.id
                    decision = DedupDecision.LINKED_EXISTING

                    # Enrich opportunity if incoming listing has better data
                    if not opportunity.canonical_application_url and norm_app_url:
                        opportunity.canonical_application_url = norm_app_url
                        opportunity.canonical_url_hash = url_hash
                        opportunity.ats_provider = ats_provider
                        opportunity.ats_job_id = ats_job_id
                    if not opportunity.primary_location and job.location:
                        opportunity.primary_location = job.location

                elif match.confidence == ConfidenceLevel.POSSIBLE:
                    # Ambiguous match: link but flag for review
                    opportunity = match.matched_opportunity  # type: ignore[assignment]
                    job.opportunity_id = opportunity.id
                    decision = DedupDecision.NEEDS_REVIEW

                else:
                    # UNIQUE: create new JobOpportunity
                    opportunity = JobOpportunity(
                        canonical_company_id=job.company_id,
                        canonical_company_name=job.company_raw,
                        canonical_title=job.title,
                        canonical_application_url=norm_app_url,
                        canonical_url_hash=url_hash,
                        ats_provider=ats_provider,
                        ats_job_id=ats_job_id,
                        primary_location=job.location,
                        work_style=job.work_style,
                        status=OpportunityStatus.DISCOVERED.value,
                    )
                    session.add(opportunity)
                    session.flush()  # populate opportunity.id

                    job.opportunity_id = opportunity.id
                    decision = DedupDecision.CREATED_NEW

                # 4. Evaluate Application Policy
                policy_result = self.policy.evaluate_opportunity_application(
                    opportunity=opportunity,
                    confidence=match.confidence,
                    current_platform=job.platform,
                )

                # 5. Record immutable deduplication evidence
                evidence = JobDeduplicationEvidence(
                    incoming_job_id=job.id,
                    matched_opportunity_id=opportunity.id,
                    matched_job_id=match.matched_opportunity.applied_job_id if match.matched_opportunity else None,
                    confidence_level=match.confidence.value,
                    decision=decision.value,
                    evidence_json=match.evidence,
                    decision_reason=match.reason,
                )
                session.add(evidence)
                session.commit()

                logger.info(
                    "[JobDedupService] Processed Job #%s (%s @ %s) -> Opp #%s | Confidence: %s | Decision: %s | Policy: %s",
                    job.id,
                    job.title,
                    job.company_raw,
                    opportunity.id,
                    match.confidence.value,
                    decision.value,
                    policy_result.policy_code,
                )
                return opportunity, decision, policy_result

    def claim_opportunity_for_application(
        self,
        opportunity_id: int,
        job_id: int,
        platform: str,
    ) -> bool:
        """Atomically claims an opportunity for in-flight application (Compare-and-Swap).

        Guarantees that two concurrent workers cannot both claim the same opportunity.

        Returns:
            True if claim was secured; False if opportunity is already in-flight or applied.
        """
        with get_db_session(self._session_factory) as session:
            stmt = text("""
                UPDATE job_opportunities
                SET status = 'APPLYING',
                    applied_job_id = :jid,
                    applied_platform = :plat,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :opp_id
                  AND status NOT IN ('APPLIED', 'APPLYING')
            """)
            result = session.execute(
                stmt,
                {"opp_id": opportunity_id, "jid": job_id, "plat": platform.lower()},
            )
            session.commit()
            return result.rowcount > 0

    def mark_opportunity_applied(
        self,
        opportunity_id: int,
        job_id: int,
        platform: str,
    ) -> None:
        """Finalizes an opportunity as APPLIED upon verified application submission."""
        with get_db_session(self._session_factory) as session:
            opp = session.get(JobOpportunity, opportunity_id)
            if opp:
                opp.status = OpportunityStatus.APPLIED.value
                opp.applied_job_id = job_id
                opp.applied_platform = platform.lower()
                opp.applied_at = utc_now()
                session.commit()
                logger.info("[JobDedupService] Opportunity #%s marked APPLIED via %s", opportunity_id, platform)

    def _find_candidate_opportunities(
        self,
        session: Session,
        company_name: str,
        url_hash: Optional[str] = None,
        ats_provider: Optional[str] = None,
        ats_job_id: Optional[str] = None,
    ) -> List[JobOpportunity]:
        """Queries database for potential matching opportunities using indexed lookup filters."""
        conditions = []

        # 1. Exact URL hash match
        if url_hash:
            conditions.append(JobOpportunity.canonical_url_hash == url_hash)

        # 2. Exact ATS Requisition ID match
        if ats_provider and ats_job_id:
            conditions.append(
                (JobOpportunity.ats_provider == ats_provider) & (JobOpportunity.ats_job_id == ats_job_id)
            )

        # 3. Company name match (normalized)
        norm_company = EntityNormalizer.normalize_company(company_name)
        if norm_company:
            # Query candidate companies with similar prefix/substring
            conditions.append(
                JobOpportunity.canonical_company_name.ilike(f"%{norm_company[:12]}%")
            )

        if not conditions:
            return []

        stmt = select(JobOpportunity).where(or_(*conditions)).limit(25)
        return list(session.execute(stmt).scalars().all())
