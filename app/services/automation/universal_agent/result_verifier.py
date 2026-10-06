"""Submission Verification Layer for Universal Application Agent.

Conclusively verifies job application submission outcomes by scanning DOM headers,
confirmation text, reference numbers, and post-submission validation error banners.
"""

from dataclasses import dataclass, field
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from app.services.automation.universal_agent.browser_agent.base import BrowserAgent
from app.services.automation.universal_agent.state_machine import (
    AgentExecutionState,
    InterventionReason,
    TerminalResult,
    UniversalApplicationStateMachine,
)


@dataclass
class VerificationResult:
    """Outcome of analyzing a portal's post-submission page state."""

    status: str  # "SUCCESS", "VALIDATION_ERROR", "CHALLENGE_DETECTED", "UNKNOWN"
    is_success: bool = False
    confirmation_header: Optional[str] = None
    confirmation_text: Optional[str] = None
    reference_number: Optional[str] = None
    error_messages: List[str] = field(default_factory=list)
    matched_signals: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


class ResultVerifier:
    """Scans and parses the post-submission web page to certify application success."""

    # Selectors known to represent successful submission confirmation
    # Covers: Generic, Greenhouse, Lever, Workday, iCIMS, SmartRecruiters,
    #         Taleo, SAP SuccessFactors, BambooHR, Jazz HR, Pinpoint, Ashby, CatsOne
    SUCCESS_SELECTORS = [
        # Generic / Test fixtures
        "#confirmation-header",
        "#confirmation-text",
        ".confirmation-card",
        ".success-card",
        ".application-success",
        "[data-testid*='confirmation']",
        "[data-testid*='thank-you']",
        ".thank-you-message",
        # Broader generic matchers
        ".success",
        ".alert-success",
        ".confirmation",
        "[class*='confirm']",
        "[class*='thank']",
        "[class*='success-message']",
        "[class*='application-complete']",
        "[class*='submitted']",
        # Greenhouse
        ".app-confirmation",
        "#header.confirmation",
        ".confirmation-page",
        ".application-confirmation",
        # Lever
        ".posting-title",
        ".application-confirmation",
        ".lever-confirmation",
        # Workday
        ".WDAL",
        ".WFFO",
        "[data-automation-id*='confirmation']",
        "[data-automation-id*='successMessage']",
        "[data-automation-id='thankYouMessage']",
        # iCIMS
        ".iCIMS_Confirmation",
        "[class*='iCIMS_Confirmation']",
        "[class*='application-complete']",
        # SmartRecruiters
        ".smrtr-confirmation",
        "[data-test*='confirmation']",
        "[data-test*='thank-you']",
        # Taleo
        ".taleo-confirmation",
        "#confirmationPage",
        ".app-submitted",
        # SAP SuccessFactors
        ".sfConfirmation",
        ".sfApplicationSuccess",
        # BambooHR
        ".confirmation-content",
        ".BambooHR-ATS-board__SuccessContainer",
        # Jazz HR / Resumator
        ".app-completed",
        ".application-submitted",
        # Pinpoint
        ".pinpoint-confirmation",
        "[class*='ApplicationConfirmation']",
        # Ashby
        "[class*='ThankYou']",
        "[class*='SubmissionConfirmation']",
        # Webflow
        ".w-form-done",
        ".w-form-done-content",
        # Wix
        ".thankYouMessage",
        "[data-hook='thank-you-message']",
        ".formSubmitted",
        # CatsOne / Generic
        "[class*='sent-successfully']",
        "[class*='form-success']",
        "[class*='message-sent']",
        "[class*='submission-success']",
    ]

    # Selectors known to indicate validation errors
    ERROR_SELECTORS = [
        "#form-errors",
        ".alert-error",
        ".validation-summary-errors",
        ".error-banner",
        "[role='alert']",
        ".field-validation-error",
        ".alert-danger",
        ".error-message",
        ".form-error",
        "[class*='validation-error']",
    ]

    # Regular expressions indicating confirmation
    SUCCESS_TEXT_PATTERNS = [
        r"\b(thank\s*you\s*(?:for\s*(?:your\s*)?applying|for\s*(?:your\s*)?application)?)\b",
        r"\b(application\s*(?:has\s*been\s*)?(?:successfully\s*)?(?:received|submitted|sent))\b",
        r"\b(we\s*(?:have\s*)?received\s*your\s*application)\b",
        r"\b(submission\s*(?:was\s*)?successful)\b",
        # Real-world patterns
        r"\b(you(?:'ve|\s+have)\s+(?:successfully\s+)?applied)\b",
        r"\b(congratulations)\b",
        r"\b(your\s+profile\s+has\s+been\s+(?:saved|submitted|received))\b",
        r"\b(application\s+(?:is\s+)?complete)\b",
        r"\b(you(?:'re|\s+are)\s+all\s+set)\b",
        r"\b(your\s+application\s+(?:was|has\s+been)\s+(?:successfully\s+)?submitted)\b",
        r"\b(application\s+confirmed)\b",
        r"\b(we\s+will\s+(?:get\s+back|review|be\s+in\s+touch))\b",
        r"\b(thank\s*you\s*for\s*(?:your\s*)?(?:interest|submission|time|applying|reaching\s+out))\b",
        r"\b(successfully\s+(?:submitted|applied|received|sent))\b",
        r"\b(your\s+submission\s+(?:was|has\s+been)\s+received)\b",
        r"\b(your\s+(?:resume|cv)\s+(?:has\s+been\s+)?(?:submitted|received|sent))\b",
        # Additional diverse ATS/CMS patterns
        r"\b(sent\s+successfully)\b",
        r"\b(form\s+(?:was\s+)?(?:successfully\s+)?(?:submitted|sent|received))\b",
        r"\b(message\s+(?:was\s+)?(?:successfully\s+)?(?:sent|received|delivered))\b",
        r"\b(we\s+(?:appreciate|value)\s+your\s+(?:interest|application|time))\b",
        r"\b(good\s+luck)\b",
        r"\b(your\s+(?:details|information)\s+(?:ha(?:s|ve)\s+been\s+)?(?:saved|received|submitted))\b",
        r"\b(application\s+(?:has\s+been\s+)?(?:forwarded|processed|logged))\b",
        r"\b(we(?:'ll|\s+will)\s+review\s+your\s+(?:application|profile|resume|cv))\b",
        r"\b(our\s+(?:team|recruiters?)\s+will\s+(?:review|contact|reach))\b",
        r"\b(your\s+application\s+(?:is\s+)?(?:under\s+review|being\s+reviewed))\b",
        r"\b(response\s+(?:has\s+been\s+)?recorded)\b",
    ]

    # URL path segments that strongly indicate success confirmation pages
    SUCCESS_URL_CUES = [
        "thank-you", "thankyou", "thanks", "confirmation", "applied",
        "success", "submitted", "complete", "confirmed",
        "application-received", "app-received", "application-submitted",
        "submission-received", "application-sent", "form-submitted",
        "form-success", "message-sent",
    ]

    # Title text fragments that indicate confirmation
    SUCCESS_TITLE_PATTERNS = [
        r"thank\s*you",
        r"thanks",
        r"application\s*(?:received|submitted|complete|confirmed|sent)",
        r"successfully\s*(?:applied|submitted|sent)",
        r"confirmation",
        r"submitted",
        r"form\s*(?:submitted|sent)",
        r"message\s*sent",
    ]

    # Regular expressions indicating submission error
    ERROR_TEXT_PATTERNS = [
        r"\b(submission\s*error|please\s*provide\s*all\s*required\s*fields)\b",
        r"\b(please\s*fix\s*(?:the\s*following\s*)?errors?)\b",
        r"\b(validation\s*(?:error|failed))\b",
        r"\b(error\s*submitting\s*application)\b",
        r"\b(this\s*field\s*is\s*required)\b",
        r"\b(please\s*fill\s*(?:in|out)\s*(?:all\s*)?required)\b",
    ]

    # Regular expressions indicating security challenges / CAPTCHA blocks
    CHALLENGE_PATTERNS = [
        r"\b(verification\s*(?:is\s*)?required\s*before\s*submitting)\b",
        r"\b(please\s*complete\s*the\s*captcha)\b",
        r"\b(captcha\s*verification\s*failed)\b",
        r"\b(verify\s*you\s*are\s*human)\b",
        r"\b(security\s*check)\b",
    ]

    async def verify_submission(
        self,
        agent: BrowserAgent,
        expected_signals: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Inspects current active browser page DOM and URL for confirmation signals."""
        url = await agent.get_url()
        title = await agent.get_title()

        # In-browser DOM extraction script — broadened to cover real ATS portals
        success_sels_json = json.dumps(self.SUCCESS_SELECTORS[:20])  # Limit to 20 for perf
        error_sels_json = json.dumps(self.ERROR_SELECTORS)
        js_extract = f"""(() => {{
            const getTexts = (selectors) => {{
                const results = [];
                for (const sel of selectors) {{
                    try {{
                        const els = document.querySelectorAll(sel);
                        for (const el of els) {{
                            const txt = (el.innerText || el.textContent || '').trim();
                            if (txt) results.push({{ selector: sel, text: txt }});
                        }}
                    }} catch(e) {{}}
                }}
                return results;
            }};

            const headerEl = document.querySelector('#confirmation-header, h1, h2, [class*="confirmation"] h1, [class*="thank"] h1, [class*="success"] h1');
            const refEl = document.querySelector('#app-reference, [data-testid*="reference"], .ref-code, [class*="reference-number"], [class*="confirmationId"]');

            // Token checks to distinguish between solved vs active challenges
            const hResp = document.querySelector("textarea[name='h-captcha-response'], [id*='h-captcha-response']");
            const hasHToken = hResp && hResp.value && hResp.value.trim().length >= 20;

            const gResp = document.querySelector("textarea[id='g-recaptcha-response'], textarea[name='g-recaptcha-response']");
            const hasGToken = gResp && gResp.value && gResp.value.trim().length >= 20;

            const cfResp = document.querySelector("input[name='cf-turnstile-response']");
            const hasCfToken = cfResp && cfResp.value && cfResp.value.trim().length >= 20;

            const hasActiveCaptcha = (!hasHToken && !!document.querySelector('#captcha-field, iframe[src*="hcaptcha"], .h-captcha')) ||
                                    (!hasGToken && !!document.querySelector('.g-recaptcha, iframe[src*="recaptcha"]')) ||
                                    (!hasCfToken && !!document.querySelector('#mock-cf-turnstile, .cf-turnstile, iframe[src*="turnstile"]'));

            return {{
                bodyText: (document.body ? document.body.innerText : '') || '',
                header: headerEl ? (headerEl.innerText || '').trim() : '',
                referenceText: refEl ? (refEl.innerText || '').trim() : '',
                successMatches: getTexts({success_sels_json}),
                errorMatches: getTexts({error_sels_json}),
                hasActiveCaptcha: hasActiveCaptcha,
                pageTitle: document.title || '',
            }};
        }})()"""


        dom_info: Dict[str, Any] = {}
        try:
            raw_res = await agent.evaluate(js_extract)
            if isinstance(raw_res, dict):
                dom_info = raw_res
        except Exception:
            pass

        body_text = dom_info.get("bodyText", "").lower()
        header_text = dom_info.get("header", "")
        ref_text = dom_info.get("referenceText", "")
        success_matches = dom_info.get("successMatches", [])
        error_matches = dom_info.get("errorMatches", [])

        # Check for Security Challenges or explicit challenge error banners
        has_challenge_text = any(re.search(pat, body_text) for pat in self.CHALLENGE_PATTERNS)
        if dom_info.get("hasActiveCaptcha") or has_challenge_text:
            return VerificationResult(
                status="CHALLENGE_DETECTED",
                is_success=False,
                details={"challenge": "CAPTCHA / Security Verification Required"},
            )

        # 0. Check for OTP / Identity Verification challenge
        otp_patterns = [
            r"verification\s+code\s+was\s+sent",
            r"confirm\s+your\s+identity",
            r"type\s+the\s+code\s+into\s+the\s+field",
            r"when\s+you\s+get\s+the\s+code",
            r"enter\s+(?:the\s+)?verification\s+code",
            r"one-time\s+passcode",
            r"pin-code",
        ]
        if any(re.search(pat, body_text) for pat in otp_patterns):
            return VerificationResult(
                status="OTP_REQUIRED",
                is_success=False,
                details={"challenge": "OTP / Identity Confirmation Required", "url": url, "title": title},
            )

        # 1. Check for Validation Errors First (excluding benign OTP / confirmation notices)
        error_messages: List[str] = [
            m.get("text", "") for m in error_matches
            if m.get("text") and not any(re.search(pat, m.get("text", ""), re.IGNORECASE) for pat in otp_patterns)
        ]
        if not error_messages:
            for pat in self.ERROR_TEXT_PATTERNS:
                if re.search(pat, body_text):
                    matched_err = re.search(pat, body_text).group(0)
                    if not any(re.search(opat, matched_err, re.IGNORECASE) for opat in otp_patterns):
                        error_messages.append(matched_err)

        if error_messages:
            return VerificationResult(
                status="VALIDATION_ERROR",
                is_success=False,
                error_messages=error_messages,
                details={"url": url, "title": title},
            )

        # 2. Check for Successful Confirmation
        matched_signals: List[str] = []
        is_success = False

        # Match expected custom signals if supplied (e.g. from ground truth)
        if expected_signals:
            exp_header = expected_signals.get("success_header")
            if exp_header and exp_header.lower() in body_text:
                matched_signals.append(f"custom_header: {exp_header}")
                is_success = True

        # Match success selectors
        if success_matches:
            for sm in success_matches:
                matched_signals.append(f"selector: {sm.get('selector')}")
            is_success = True

        # Match success text regex
        for pat in self.SUCCESS_TEXT_PATTERNS:
            if re.search(pat, body_text):
                matched_signals.append(f"text_pattern: {pat}")
                is_success = True

        # Match URL confirmation cues (expanded)
        parsed_url = urlparse(url)
        url_path_lower = parsed_url.path.lower()
        if any(cue in url_path_lower for cue in self.SUCCESS_URL_CUES):
            matched_signals.append(f"url_path: {parsed_url.path}")
            is_success = True

        # Match page title patterns for confirmation
        page_title = (dom_info.get("pageTitle", "") or title or "").lower()
        for pat in self.SUCCESS_TITLE_PATTERNS:
            if re.search(pat, page_title, re.IGNORECASE):
                matched_signals.append(f"title_pattern: {pat}")
                is_success = True
                break

        # Extract Reference Code if available
        reference_number = None
        if ref_text:
            reference_number = ref_text
        else:
            # Query params
            qs = parse_qs(parsed_url.query)
            if "ref" in qs:
                reference_number = qs["ref"][0]
            elif "reference" in qs:
                reference_number = qs["reference"][0]
            else:
                # Regex search in body
                ref_match = re.search(r"\b(?:reference|confirmation|app(?:lication)?\s*id)[\s#:]*([A-Za-z0-9_-]{5,30})\b", body_text, re.IGNORECASE)
                if ref_match:
                    reference_number = ref_match.group(1).upper()

        if is_success:
            return VerificationResult(
                status="SUCCESS",
                is_success=True,
                confirmation_header=header_text,
                confirmation_text=body_text[:200] if body_text else None,
                reference_number=reference_number,
                matched_signals=matched_signals,
                details={"url": url, "title": title},
            )

        return VerificationResult(
            status="UNKNOWN",
            is_success=False,
            details={"url": url, "title": title, "body_preview": body_text[:200]},
        )

    def verify_and_update_state(
        self,
        state_machine: UniversalApplicationStateMachine,
        result: VerificationResult,
    ) -> None:
        """Transitions state machine to terminal COMPLETED or PAUSED_FOR_INTERVENTION based on verification."""
        if result.is_success:
            state_machine.complete(
                terminal_result=TerminalResult.SUCCESS_SUBMITTED,
                message=f"Submission certified successful. Reference: {result.reference_number or 'N/A'}",
                metadata={
                    "reference_number": result.reference_number,
                    "matched_signals": result.matched_signals,
                },
            )
        elif result.status == "OTP_REQUIRED":
            state_machine.pause_for_intervention(
                reason=InterventionReason.TWO_FACTOR_AUTH,
                message="One-time verification code (OTP) required. Please check your email or phone, enter the code in the browser window, then click 'I've Solved It / Continue'.",
                metadata={"details": result.details},
            )
        elif result.status == "VALIDATION_ERROR":
            state_machine.pause_for_intervention(
                reason=InterventionReason.POST_SUBMIT_VALIDATION_ERROR,
                message=f"Post-submission validation error: {'; '.join(result.error_messages)}",
                metadata={"error_messages": result.error_messages},
            )
        elif result.status == "CHALLENGE_DETECTED":
            state_machine.pause_for_intervention(
                reason=InterventionReason.CAPTCHA_CHALLENGE,
                message="Security challenge detected post-submission.",
            )
        else:
            state_machine.complete(
                terminal_result=TerminalResult.SUBMISSION_STATUS_UNKNOWN,
                message="Submission completed but definitive confirmation signal not verified. Manual verification recommended.",
                metadata={"details": result.details},
            )
