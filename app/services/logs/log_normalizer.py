"""Fallback regex normalizer parsing unstructured log text into structured AutomationEvents."""

from datetime import datetime, timezone
import hashlib
import re
from typing import Optional

from app.services.logs.automation_event import (
    AutomationEvent,
    AutomationEventType,
    EventSource,
    LogFileReference,
)


class LogNormalizer:
    """Extracts semantic metadata and event types from known engine log tags.
    
    Used strictly as a FALLBACK when typed Qt signals are absent (e.g. historical logs).
    """

    # Compiled patterns for known engine tags
    _APP_CONFIRMED_RE = re.compile(
        r"\[APPLICATION_CONFIRMED\]\s+Job:\s*'(?P<title>[^']+)'\s*\|\s*Company:\s*'(?P<company>[^']+)'\s*\|\s*URL:\s*'(?P<url>[^']*)'\s*\|\s*Platform:\s*'(?P<platform>[^']+)'(?:\s*\|\s*Time:\s*'(?P<time>[^']+)')?"
    )
    _SEARCH_RE = re.compile(
        r"\[(?P<engine>[A-Za-z]+)Search\]\s+(?:Navigating to:\s*(?P<url>\S+)|Discovered\s+(?P<count>\d+)\s+job cards for '(?P<keyword>[^']+)')"
    )
    _SUBMIT_CONFIRMED_RE = re.compile(
        r"\[(?P<engine>[A-Za-z]+)Submitter\]\s+Submission confirmed for job '(?P<job_id>[^']+)':\s*(?P<reason>.*)"
    )
    _SUBMIT_FAIL_RE = re.compile(
        r"\[(?P<engine>[A-Za-z]+)Submitter\]\s+(?:WARNING|ERROR):\s*(?P<reason>.*)"
    )
    _SAFETY_GATE_RE = re.compile(
        r"\[(?P<engine>[A-Za-z]+)SafetyGate\]\s+(?P<action>PAUSED|Holding application in MANUAL_REQUIRED):\s*(?P<msg>.*)"
    )
    _CAPTCHA_RE = re.compile(
        r"(?i)\b(captcha|cloudflare|recaptcha|arkose|datadome)\b"
    )

    @classmethod
    def parse_line(
        rcls,
        line: str,
        run_id: str = "default",
        line_number: int = 0,
        byte_offset: int = 0,
        file_mtime: float = 0.0,
        log_file: str = "logs/log.txt",
    ) -> AutomationEvent:
        """Parses a raw log line into an AutomationEvent.
        
        If a known tag matches, creates a PARSED_LOG semantic event.
        Otherwise creates a RAW event preserving the text.
        """
        raw_text = line.rstrip("\r\n")
        line_fp = hashlib.sha256(raw_text.encode("utf-8", errors="replace")).hexdigest()[:16]

        raw_ref = LogFileReference(
            log_file=log_file,
            file_mtime=file_mtime,
            line_number=line_number,
            byte_offset=byte_offset,
            line_fingerprint=line_fp,
        )

        # 1. Check Application Confirmed tag
        m = rcls._APP_CONFIRMED_RE.search(raw_text)
        if m:
            platform = m.group("platform").lower()
            title = m.group("title")
            company = m.group("company")
            return AutomationEvent(
                run_id=run_id,
                source=EventSource.PARSED_LOG,
                level="INFO",
                event_type=AutomationEventType.APPLICATION_SUBMITTED,
                platform=platform,
                stage="SUBMISSION",
                company=company,
                job_title=title,
                action="Application Confirmed",
                status="SUCCESS",
                message=f"Application confirmed for '{title}' at '{company}'",
                metadata={"url": m.group("url")},
                raw_reference=raw_ref,
            )

        # 2. Check Submitter Confirmation tag
        m = rcls._SUBMIT_CONFIRMED_RE.search(raw_text)
        if m:
            engine = m.group("engine")
            platform = engine.lower()
            job_id_str = m.group("job_id")
            reason = m.group("reason")
            return AutomationEvent(
                run_id=run_id,
                source=EventSource.PARSED_LOG,
                level="INFO",
                event_type=AutomationEventType.APPLICATION_SUBMITTED,
                platform=platform,
                engine=engine,
                stage="SUBMISSION",
                action="Submit Confirmed",
                status="SUCCESS",
                message=f"Submission confirmed: {reason}",
                metadata={"external_job_id": job_id_str},
                raw_reference=raw_ref,
            )

        # 3. Check Submitter Warning / Failure tag
        m = rcls._SUBMIT_FAIL_RE.search(raw_text)
        if m:
            engine = m.group("engine")
            platform = engine.lower()
            reason = m.group("reason")
            return AutomationEvent(
                run_id=run_id,
                source=EventSource.PARSED_LOG,
                level="ERROR",
                event_type=AutomationEventType.APPLICATION_FAILED,
                platform=platform,
                engine=engine,
                stage="SUBMISSION",
                action="Submit Error",
                status="FAILED",
                message=f"Submission error: {reason}",
                metadata={"reason": reason},
                raw_reference=raw_ref,
            )

        # 4. Check Safety Gate / Manual Required tag
        m = rcls._SAFETY_GATE_RE.search(raw_text)
        if m:
            engine = m.group("engine")
            platform = engine.lower()
            action = m.group("action")
            msg = m.group("msg")
            return AutomationEvent(
                run_id=run_id,
                source=EventSource.PARSED_LOG,
                level="WARNING",
                event_type=AutomationEventType.MANUAL_INTERVENTION,
                platform=platform,
                engine=engine,
                stage="REVIEW",
                action=action,
                status="INTERVENTION",
                message=f"Safety Gate hold: {msg or action}",
                raw_reference=raw_ref,
            )

        # 5. Check Search rotation tag
        m = rcls._SEARCH_RE.search(raw_text)
        if m:
            engine = m.group("engine")
            platform = engine.lower()
            count = m.group("count")
            keyword = m.group("keyword")
            url = m.group("url")
            if count:
                return AutomationEvent(
                    run_id=run_id,
                    source=EventSource.PARSED_LOG,
                    level="INFO",
                    event_type=AutomationEventType.JOB_DISCOVERED,
                    platform=platform,
                    engine=engine,
                    stage="DISCOVER",
                    action=f"Discovered {count} cards",
                    message=f"Discovered {count} job cards for '{keyword}'",
                    metadata={"count": int(count), "keyword": keyword},
                    raw_reference=raw_ref,
                )
            else:
                return AutomationEvent(
                    run_id=run_id,
                    source=EventSource.PARSED_LOG,
                    level="INFO",
                    event_type=AutomationEventType.SEARCH_STARTED,
                    platform=platform,
                    engine=engine,
                    stage="SEARCH",
                    action="Search navigation",
                    message=f"Navigating to search URL: {url}",
                    metadata={"url": url},
                    raw_reference=raw_ref,
                )

        # 6. Check generic CAPTCHA tag
        if rcls._CAPTCHA_RE.search(raw_text):
            return AutomationEvent(
                run_id=run_id,
                source=EventSource.PARSED_LOG,
                level="WARNING",
                event_type=AutomationEventType.CAPTCHA_DETECTED,
                stage="VERIFICATION",
                action="Security challenge detected",
                status="INTERVENTION",
                message=raw_text,
                raw_reference=raw_ref,
            )

        # 7. Fallback: Pure RAW event
        level = "INFO"
        upper = raw_text.upper()
        if "ERROR" in upper or "CRITICAL" in upper or "EXCEPTION" in upper or "FAILED" in upper:
            level = "ERROR"
        elif "WARN" in upper:
            level = "WARNING"

        return AutomationEvent(
            run_id=run_id,
            source=EventSource.RAW,
            level=level,
            event_type=AutomationEventType.RAW_LOG,
            message=raw_text,
            raw_reference=raw_ref,
        )
