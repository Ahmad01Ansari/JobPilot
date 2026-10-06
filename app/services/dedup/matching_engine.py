"""Multi-signal matching engine computing evidence-backed opportunity confidence."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.db.models.job_opportunity import ConfidenceLevel, JobOpportunity
from app.services.dedup.entity_normalizer import EntityNormalizer
from app.services.dedup.url_normalizer import URLNormalizer


@dataclass
class MatchResult:
    """Outcome of multi-signal opportunity matching with preserved evidence."""

    confidence: ConfidenceLevel
    matched_opportunity: Optional[JobOpportunity] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


class MultiSignalMatchingEngine:
    """Evaluates multi-signal similarity between incoming listings and candidate opportunities."""

    @classmethod
    def evaluate_match(
        cls,
        incoming_title: str,
        incoming_company: str,
        incoming_application_url: Optional[str] = None,
        incoming_location: Optional[str] = None,
        incoming_work_style: Optional[str] = None,
        incoming_description: Optional[str] = None,
        candidate_opportunities: Optional[List[JobOpportunity]] = None,
    ) -> MatchResult:
        """Compares an incoming job listing against a set of candidate opportunities.

        Returns:
            MatchResult containing calibrated confidence tier, matched opportunity, and evidence.
        """
        if not candidate_opportunities:
            return MatchResult(
                confidence=ConfidenceLevel.UNIQUE,
                matched_opportunity=None,
                evidence={"candidates_evaluated": 0},
                reason="No candidate opportunities found; treating as unique.",
            )

        # Normalize incoming attributes
        norm_in_company = EntityNormalizer.normalize_company(incoming_company)
        norm_in_title = EntityNormalizer.normalize_title(incoming_title)
        norm_in_app_url = URLNormalizer.normalize_application_url(incoming_application_url)
        in_ats_provider, in_ats_id = URLNormalizer.extract_ats_metadata(norm_in_app_url)
        in_url_hash = URLNormalizer.compute_canonical_url_hash(norm_in_app_url)

        best_possible_match: Optional[Tuple[JobOpportunity, float, Dict[str, Any], str]] = None

        for opp in candidate_opportunities:
            evidence: Dict[str, Any] = {
                "opportunity_id": opp.id,
                "opp_company": opp.canonical_company_name,
                "opp_title": opp.canonical_title,
            }

            # -------------------------------------------------------------
            # SIGNAL 1: ATS Provider & ATS Job ID Match (Definitive EXACT)
            # -------------------------------------------------------------
            if in_ats_provider and in_ats_id and opp.ats_provider and opp.ats_job_id:
                if in_ats_provider == opp.ats_provider and in_ats_id == opp.ats_job_id:
                    evidence.update({
                        "ats_provider": in_ats_provider,
                        "ats_job_id": in_ats_id,
                        "match_type": "ATS_IDENTIFIER",
                    })
                    return MatchResult(
                        confidence=ConfidenceLevel.EXACT,
                        matched_opportunity=opp,
                        evidence=evidence,
                        reason=f"Exact match on {in_ats_provider} ATS requisition ID '{in_ats_id}'.",
                    )
                elif in_ats_provider == opp.ats_provider and in_ats_id != opp.ats_job_id:
                    # Same company and ATS, but DIFFERENT requisition ID -> definitely distinct roles!
                    continue

            # -------------------------------------------------------------
            # SIGNAL 2: Canonical Application URL Match (Definitive EXACT)
            # -------------------------------------------------------------
            if in_url_hash and opp.canonical_url_hash and in_url_hash == opp.canonical_url_hash:
                evidence.update({
                    "canonical_url_matched": norm_in_app_url,
                    "match_type": "CANONICAL_URL",
                })
                return MatchResult(
                    confidence=ConfidenceLevel.EXACT,
                    matched_opportunity=opp,
                    evidence=evidence,
                    reason=f"Exact match on normalized application URL: {norm_in_app_url}",
                )

            # -------------------------------------------------------------
            # SIGNAL 3: Company Entity Normalization
            # -------------------------------------------------------------
            norm_opp_company = EntityNormalizer.normalize_company(opp.canonical_company_name)
            company_match = bool(norm_in_company and norm_opp_company and norm_in_company == norm_opp_company)
            evidence["company_match"] = company_match

            if not company_match:
                # Different companies cannot be the same opportunity
                continue

            # -------------------------------------------------------------
            # SIGNAL 4: Title Token Similarity
            # -------------------------------------------------------------
            title_sim = EntityNormalizer.compute_title_similarity(incoming_title, opp.canonical_title)
            evidence["title_similarity"] = title_sim

            # -------------------------------------------------------------
            # SIGNAL 5: Location / Work Style Compatibility
            # -------------------------------------------------------------
            loc_compatible = EntityNormalizer.are_locations_compatible(
                incoming_location,
                opp.primary_location,
                work_style_a=incoming_work_style,
                work_style_b=opp.work_style,
            )
            evidence["location_compatible"] = loc_compatible

            if not loc_compatible:
                # Incompatible physical locations without remote option disqualify duplicate identity
                continue

            # -------------------------------------------------------------
            # SIGNAL 6: Description Overlap (if both present)
            # -------------------------------------------------------------
            # (Preserved for high confidence confirmation)

            # Evaluate HIGH Confidence
            if title_sim >= 0.85 and loc_compatible:
                evidence["match_type"] = "HIGH_CONFIDENCE_HEURISTIC"
                return MatchResult(
                    confidence=ConfidenceLevel.HIGH,
                    matched_opportunity=opp,
                    evidence=evidence,
                    reason=(
                        f"High confidence match: Company '{opp.canonical_company_name}', "
                        f"title similarity {title_sim:.2f}, compatible location."
                    ),
                )

            # Evaluate POSSIBLE Confidence (Needs review / manual decision)
            if title_sim >= 0.60:
                score = title_sim + (0.1 if loc_compatible else 0.0)
                if not best_possible_match or score > best_possible_match[1]:
                    reason_msg = (
                        f"Possible duplicate: Company '{opp.canonical_company_name}', "
                        f"title similarity {title_sim:.2f} (review recommended)."
                    )
                    best_possible_match = (opp, score, evidence, reason_msg)

        if best_possible_match:
            opp, _, ev, msg = best_possible_match
            ev["match_type"] = "POSSIBLE_REVIEW_REQUIRED"
            return MatchResult(
                confidence=ConfidenceLevel.POSSIBLE,
                matched_opportunity=opp,
                evidence=ev,
                reason=msg,
            )

        return MatchResult(
            confidence=ConfidenceLevel.UNIQUE,
            matched_opportunity=None,
            evidence={"evaluated_candidates": len(candidate_opportunities)},
            reason="No existing opportunity matched with sufficient confidence; treated as unique.",
        )
