"""Event correlation, deduplication, and failure clustering engine."""

from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from app.services.logs.automation_event import AutomationEvent, EventSource


class EventCorrelator:
    """Provides windowed deduplication, monotonic sequencing, and failure clustering.
    
    Guarantees that duplicate occurrences across signals and raw logs result in
    exactly one semantic AutomationEvent.
    """

    # Regex patterns for normalizing error messages for clustering
    _JOB_ID_RE = re.compile(r"(?i)\bjob[_\s-]?\d+\b")
    _URL_RE = re.compile(r"https?://\S+")
    _TIMESTAMP_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?\b")
    _HEX_RE = re.compile(r"\b[0-9a-fA-F]{8,}\b")
    _DIGITS_RE = re.compile(r"\b\d+\b")

    def __init__(self, deduplication_window_seconds: float = 5.0, max_cache_size: int = 2000):
        self.window_seconds = deduplication_window_seconds
        self.max_cache_size = max_cache_size

        # LRU cache: fingerprint -> (monotonic_time, AutomationEvent)
        self._recent_events: OrderedDict[str, Tuple[float, AutomationEvent]] = OrderedDict()

        # Entity index: (run_id, event_type_str, entity_key) -> (monotonic_time, AutomationEvent)
        self._entity_index: Dict[Tuple[str, str, str], Tuple[float, AutomationEvent]] = {}

        # Monotonic sequence counter per run_id
        self._sequences: Dict[str, int] = {}

    def _get_entity_keys(self, event: AutomationEvent) -> List[str]:
        """Generates candidate entity keys for alias-aware correlation."""
        keys = []
        if event.job_id:
            keys.append(f"job:{event.job_id}")
        if event.application_id:
            keys.append(f"app:{event.application_id}")
        if event.metadata and event.metadata.get("external_job_id"):
            keys.append(f"ext:{event.metadata['external_job_id']}")
        if event.job_title and event.company:
            t = str(event.job_title).strip().lower()
            c = str(event.company).strip().lower()
            if t and c:
                keys.append(f"tc:{t}@{c}")
        return keys

    def _prune(self, now: float) -> None:
        """Evicts expired fingerprints and entity index entries."""
        cutoff = now - self.window_seconds
        keys_to_remove = []
        for fp, (seen_time, _) in self._recent_events.items():
            if seen_time < cutoff:
                keys_to_remove.append(fp)
            else:
                break
        for k in keys_to_remove:
            self._recent_events.pop(k, None)

        # Prune entity index
        expired_entities = [k for k, (seen_time, _) in self._entity_index.items() if seen_time < cutoff]
        for ek in expired_entities:
            self._entity_index.pop(ek, None)

        # Enforce size bounds
        while len(self._recent_events) > self.max_cache_size:
            self._recent_events.popitem(last=False)

    def correlate(self, event: AutomationEvent) -> Optional[AutomationEvent]:
        """Processes an incoming event through deduplication and assigns a monotonic sequence.
        
        Returns:
            The AutomationEvent if accepted, or None if it is a duplicate within the time window.
        """
        now = time.monotonic()
        self._prune(now)

        fingerprint = event.get_fingerprint()
        e_type_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
        candidate_keys = self._get_entity_keys(event)

        existing_match: Optional[AutomationEvent] = None

        # 1. Check exact fingerprint
        if fingerprint in self._recent_events:
            _, existing_match = self._recent_events[fingerprint]

        # 2. Check entity keys if no exact fingerprint match
        if not existing_match and candidate_keys:
            for ckey in candidate_keys:
                idx_key = (event.run_id, e_type_str, ckey)
                if idx_key in self._entity_index:
                    seen_time, candidate = self._entity_index[idx_key]
                    if (now - seen_time) <= self.window_seconds:
                        existing_match = candidate
                        break

        # Duplicate handling
        if existing_match is not None:
            # Merge raw reference if existing didn't have one and incoming does
            if existing_match.raw_reference is None and event.raw_reference is not None:
                existing_match.raw_reference = event.raw_reference

            # Merge IDs if existing was missing them
            if not existing_match.job_id and event.job_id:
                existing_match.job_id = event.job_id
            if not existing_match.application_id and event.application_id:
                existing_match.application_id = event.application_id

            # Precedence promotion (SIGNAL > STRUCTURED_LOG > PARSED_LOG > RAW)
            precedence = {
                EventSource.SIGNAL: 4,
                EventSource.STRUCTURED_LOG: 3,
                EventSource.PARSED_LOG: 2,
                EventSource.RAW: 1,
            }
            if precedence.get(event.source, 0) > precedence.get(existing_match.source, 0):
                existing_match.source = event.source
                if event.message:
                    existing_match.message = event.message
                if event.metadata:
                    existing_match.metadata.update(event.metadata)

            # Drop as duplicate
            return None

        # Assign strictly monotonic sequence number per run_id
        current_seq = self._sequences.get(event.run_id, 0) + 1
        self._sequences[event.run_id] = current_seq
        event.sequence = current_seq

        # Record in caches
        self._recent_events[fingerprint] = (now, event)
        for ckey in candidate_keys:
            idx_key = (event.run_id, e_type_str, ckey)
            self._entity_index[idx_key] = (now, event)

        return event

    def normalize_error_message(self, message: str) -> str:
        """Strips dynamic identifiers, timestamps, URLs, and numbers for clustering."""
        if not message:
            return ""
        norm = self._JOB_ID_RE.sub("<JOB_ID>", message)
        norm = self._URL_RE.sub("<URL>", norm)
        norm = self._TIMESTAMP_RE.sub("<TIMESTAMP>", norm)
        norm = self._HEX_RE.sub("<HEX>", norm)
        norm = self._DIGITS_RE.sub("<NUM>", norm)
        # Collapse whitespace
        norm = re.sub(r"\s+", " ", norm).strip()
        return norm

    def get_cluster_key(self, event: AutomationEvent) -> str:
        """Generates a deterministic cluster hash for grouping repeated failures."""
        norm_msg = self.normalize_error_message(event.message)
        components = [
            str(event.platform or "unknown"),
            str(event.stage or "unknown"),
            str(event.event_type.value if hasattr(event.event_type, "value") else event.event_type),
            norm_msg,
        ]
        raw_key = ":".join(components)
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def reset_run(self, run_id: str) -> None:
        """Resets the sequence counter for a specific run."""
        self._sequences.pop(run_id, None)

    def clear(self) -> None:
        """Clears all caches and sequence counters."""
        self._recent_events.clear()
        self._entity_index.clear()
        self._sequences.clear()
