"""Deterministic relevance ranking algorithm and tokenization utilities for Universal Search."""

import re
from typing import List, Optional, Set, Tuple


def normalize_query(query: str) -> Tuple[str, List[str]]:
    """Normalizes query text, folds case, strips punctuation, and extracts distinct tokens."""
    raw = str(query or "").strip()
    if not raw:
        return "", []

    # Lowercase folding
    lowered = raw.casefold()

    # Extract tokens by alphanumeric and hyphen patterns
    tokens = [t for t in re.findall(r"[\w\-]+", lowered) if t]

    return lowered, tokens


def calculate_relevance_score(
    raw_query: str,
    tokens: List[str],
    entity_id: int,
    primary_text: str,
    secondary_text: Optional[str] = None,
    tertiary_text: Optional[str] = None,
    long_text: Optional[str] = None,
    prefix_tags: Optional[List[str]] = None,
) -> Tuple[float, List[str]]:
    """Calculates deterministic relevance score (0.0 - 100.0) and matched field list.

    Hierarchy:
    1. Exact ID or Prefix Match (e.g. 123 or JOB-123) ──► 100.0
    2. Exact Primary Field Match ──► 95.0
    3. Prefix Primary Field Match ──► 85.0
    4. All Tokens Present in Primary Field ──► 75.0
    5. Exact Secondary Match ──► 65.0
    6. Multi-Token Partial Matches ──► 40.0 - 60.0
    7. Long-Text / Description Match ──► 30.0
    """
    matched_fields: List[str] = []
    q_clean = raw_query.strip().casefold()
    p_clean = (primary_text or "").strip().casefold()
    s_clean = (secondary_text or "").strip().casefold()
    t_clean = (tertiary_text or "").strip().casefold()
    l_clean = (long_text or "").strip().casefold()

    # 1. Exact ID or Explicit Prefix Match (Score: 100.0)
    if q_clean == str(entity_id):
        matched_fields.append("id")
        return 100.0, matched_fields

    if prefix_tags:
        for tag in prefix_tags:
            tag_clean = tag.strip().casefold()
            if q_clean in (f"{tag_clean}-{entity_id}", f"{tag_clean}{entity_id}"):
                matched_fields.append("id_prefix")
                return 100.0, matched_fields

    # 2. Exact Primary Field Match (Score: 95.0)
    if q_clean and q_clean == p_clean:
        matched_fields.append("primary_exact")
        return 95.0, matched_fields

    # 3. Prefix Primary Field Match (Score: 85.0)
    if q_clean and p_clean.startswith(q_clean):
        matched_fields.append("primary_prefix")
        return 85.0, matched_fields

    # 4. All Tokens in Primary Field (Score: 75.0)
    if tokens and all(t in p_clean for t in tokens):
        matched_fields.append("primary_tokens")
        return 75.0, matched_fields

    # 5. Exact Secondary Field Match (Score: 65.0)
    if q_clean and q_clean == s_clean:
        matched_fields.append("secondary_exact")
        return 65.0, matched_fields

    # 6. Multi-Token Overlap across Primary, Secondary, Tertiary (Score: 40.0 - 60.0)
    if tokens:
        combined = f"{p_clean} {s_clean} {t_clean}"
        matched_count = sum(1 for t in tokens if t in combined)
        if matched_count > 0:
            ratio = matched_count / len(tokens)
            score = 40.0 + (ratio * 20.0)  # 40.0 to 60.0
            if any(t in p_clean for t in tokens):
                matched_fields.append("primary")
            if any(t in s_clean for t in tokens):
                matched_fields.append("secondary")
            if any(t in t_clean for t in tokens):
                matched_fields.append("tertiary")
            return score, matched_fields

    # 7. Long-Text / Description Match (Score: 30.0)
    if tokens and any(t in l_clean for t in tokens):
        matched_fields.append("description")
        return 30.0, matched_fields

    return 0.0, matched_fields
