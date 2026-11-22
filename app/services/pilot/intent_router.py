"""Natural Language Intent Router for JobPilot AI Pilot.

Translates candidate instructions, speech transcripts, and action tag triggers
into strongly-typed PilotAction payloads. Supports dual-engine execution:
LLM-based structured inference via AIGateway with a battle-tested offline
heuristic engine that executes instantly with 0 cloud dependencies.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.pilot.pilot_models import PilotActionType
from app.services.pilot.tool_registry import (
    get_tool_registry,
    normalize_speech_input,
    parse_compensation_amount,
)

logger = logging.getLogger("JobPilot.IntentRouter")

URL_REGEX = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

PLATFORMS = ["all", "linkedin", "indeed", "naukri", "foundit", "glassdoor", "universal"]

STATUS_KEYWORD_MAP = {
    "under review": "UNDER_REVIEW",
    "in review": "UNDER_REVIEW",
    "recruiter contacted": "RECRUITER_CONTACTED",
    "rejected": "REJECTED",
    "reject": "REJECTED",
    "declined": "REJECTED",
    "interviewing": "INTERVIEW",
    "interview": "INTERVIEW",
    "scheduled": "INTERVIEW",
    "offered": "OFFER",
    "offer": "OFFER",
    "accepted": "OFFER",
    "submitted": "SUBMITTED",
    "applied": "SUBMITTED",
    "shortlisted": "SHORTLISTED",
    "shortlist": "SHORTLISTED",
    "contacted": "RECRUITER_CONTACTED",
    "assessment": "ASSESSMENT",
    "withdrawn": "WITHDRAWN",
    "withdraw": "WITHDRAWN",
    "junk": "JUNK",
    "trash": "JUNK",
}

def resolve_status_keyword(raw_word: str) -> Optional[str]:
    """Resolves canonical status with exact and typo-tolerant fuzzy matching."""
    clean = raw_word.strip().lower()
    if clean in STATUS_KEYWORD_MAP:
        return STATUS_KEYWORD_MAP[clean]
    import difflib
    close = difflib.get_close_matches(clean, list(STATUS_KEYWORD_MAP.keys()), n=1, cutoff=0.65)
    if close:
        return STATUS_KEYWORD_MAP[close[0]]
    return None


class IntentRouter:
    """Parses candidate intent and maps queries to executable actions."""

    def __init__(self, ai_gateway=None, tool_registry=None):
        self.ai_gateway = ai_gateway
        self.tool_registry = tool_registry or get_tool_registry()

    def parse_intent(self, text: str) -> Tuple[PilotActionType, Dict[str, Any], str]:
        """Main entry point: Universal Hybrid Semantic Router."""
        clean_text = text.strip()
        if not clean_text:
            return PilotActionType.CHAT, {}, "Empty prompt."

        # 0. Voice / Speech-to-Text Phonetic Normalization
        normalized_text = normalize_speech_input(clean_text)

        # 1. Fast-Path: Direct pasted job URL
        urls = URL_REGEX.findall(clean_text)
        if urls and len(clean_text.split()) <= 3:
            return PilotActionType.APPLY_JOBS, {"url": urls[0]}, f"Pasted job URL: {urls[0]}"

        # 2. Fast-Path: Unambiguous one-word control signals (0ms execution)
        lower = normalized_text.lower()
        if lower in ("stop", "stop bot", "stop automation", "halt"):
            return PilotActionType.STOP_AUTOMATION, {}, "Stopping active automation."
        if lower in ("pause", "pause automation", "pause bot"):
            return PilotActionType.PAUSE_AUTOMATION, {}, "Requesting automation pause."
        if lower in ("resume", "resume automation", "continue"):
            return PilotActionType.RESUME_AUTOMATION, {}, "Resuming automation."

        # 3. Primary Universal Path: Semantic LLM Tool Calling (if AI Gateway is available and configured)
        if self.ai_gateway:
            try:
                action, params, summary = self._infer_via_llm(normalized_text)
                if action != PilotActionType.UNKNOWN:
                    logger.info("LLM semantic router classified '%s' -> %s (%s)", normalized_text[:40], action.value, summary)
                    return action, params, summary
            except Exception as e:
                logger.debug("LLM semantic routing failed or bypassed: %s", e)

        # 4. Fallback Path: High-precision deterministic rules (offline / fail-safe)
        matched = self._infer_via_rules(normalized_text)
        if matched[0] != PilotActionType.UNKNOWN and matched[0] != PilotActionType.CHAT:
            return matched

        # 5. Fast-Path Tool Registry (covers registered domain tool extensions)
        if self.tool_registry:
            tool_match = self.tool_registry.match_fast_path(normalized_text)
            if tool_match:
                tool, params, summary = tool_match
                logger.info("Tool registry fast-path matched '%s' -> %s (%s)", normalized_text[:40], tool.action_type.value, summary)
                return tool.action_type, params, summary

        return matched

    def _infer_via_llm(self, text: str) -> Tuple[PilotActionType, Dict[str, Any], str]:
        """Queries AIGateway with structured JSON schema prompt."""
        from app.services.ai.models import AIRequest

        cfg = self.ai_gateway.get_config() if hasattr(self.ai_gateway, "get_config") else {}
        model_name = cfg.get("model", "openai/gpt-oss-120b")

        system_prompt = (
            "You are the JobPilot Universal AI Intent Router. Your job is to classify candidate instructions "
            "into exact system actions and extract structured parameters.\n\n"
            "AVAILABLE ACTIONS:\n"
            "1. 'query_application_status': Inquiries asking if the candidate applied to a job, company, or checking review/interview status. "
            "Examples: 'did i apply to fugentex?', 'have i applied to infosys?', 'status of my application at google', 'is my resume still under review at gamma labs?'. "
            "Parameters: {'company': string, 'role': string (optional), 'job_id': integer (optional)}.\n"
            "2. 'update_rules': Adding or removing skip keywords, negative title exclusions, deal-breakers, or setting match score / daily limits. "
            "Examples: 'add unity as skip keyword in list', 'drop php from negative keywords', 'skip jobs with rust', 'never apply to mechanical', 'set min score to 80%'. "
            "Parameters: {'type': 'add_deal_breaker'|'remove_deal_breaker'|'set_min_score'|'set_daily_limit', 'deal_breaker': string, 'min_score': integer, 'daily_limit': integer}.\n"
            "3. 'get_rules': Asking to view or list active skip keywords, exclusion rules, or deal-breakers. "
            "Examples: 'what are my skip keywords?', 'list exclusion rules', 'show rules'. Parameters: {}.\n"
            "4. 'update_application_status': Instructing to update or change an application's stage or status. "
            "Examples: 'mark all gamma labs as rejected', 'update infosys to under review'. "
            "Parameters: {'company': string, 'status': 'REJECTED'|'UNDER_REVIEW'|'INTERVIEW'|'SUBMITTED'|'OFFER', 'update_all': boolean}.\n"
            "5. 'get_offers': Inquiries about job offers, compensation, CTC, salary packages, or offer letters. "
            "Examples: 'what offers do i have?', 'tell me about the ncare md offer', 'what is my current ctc?'. "
            "Parameters: {'query': string}.\n"
            "6. 'get_resume_skills': Inquiries asking what technical skills or competencies are on the candidate's resume. "
            "Examples: 'what are the key skills from my resume?', 'extract skills from my cv'. Parameters: {}.\n"
            "7. 'tailor_resume': Requesting to design or tailor resume content for a specific role or JD. "
            "Examples: 'design a resume for tech lead', 'tailor my resume for python engineer'. "
            "Parameters: {'target': string}.\n"
            "8. 'search_jobs': Finding or searching for job opportunities in the local database. "
            "Examples: 'find remote python developer jobs', 'search rpa engineer jobs'. "
            "Parameters: {'query': string, 'platform': string (optional), 'remote': boolean (optional)}.\n"
            "9. 'apply_jobs': Explicit imperative commands to submit applications to specific jobs or URLs. "
            "Examples: 'apply to #704', 'apply to job 608', 'apply to 5 jobs on linkedin', 'start applying now'. "
            "Parameters: {'count': integer, 'job_id': integer (optional), 'platform': string (optional), 'url': string (optional)}.\n"
            "10. 'get_applications_report': Asking for reports or summaries of jobs applied today or in total. "
            "Examples: 'today apply report', 'what did we apply today', 'how many jobs applied?'. "
            "Parameters: {'timeframe': 'today'|'all'}.\n"
            "11. 'start_automation': Explicit imperative commands to launch or start the bot on a platform. "
            "Examples: 'run linkedin bot', 'start naukri automation', 'launch indeed'. "
            "Parameters: {'platform': string, 'count': integer (optional)}.\n"
            "12. 'stop_automation': 'stop bot', 'halt automation'. Parameters: {}.\n"
            "13. 'pause_automation': 'pause bot'. Parameters: {}.\n"
            "14. 'resume_automation': 'resume bot'. Parameters: {}.\n"
            "15. 'update_profile': Updating or completing candidate profile, setting bio/summary, cover letter, links (LinkedIn, GitHub, portfolio), CTC, skills, work experience history (roles, responsibilities, projects, joining/start dates), or educational background from resume. "
            "Examples: 'update my work experience according to my resume', 'summarize my current job experience and projects into work experience', 'get role and responsibility from resume and add to work experience', 'add my educational background', 'set my joining date to Nov 2024', 'complete setup my profile based on my resume', 'change my ctc to 15 lpa'. "
            "Parameters: {'action': 'update_work_experience'|'update_education'|'autofill_from_resume'|'update_field', 'field': string (optional), 'value': any (optional)}.\n"
            "16. 'send_email_application': Direct instructions to send an email job application or cold outreach inquiry to a recipient email address. "
            "Examples: 'send an email application to hr@example.com for rpa developer', 'send email to ahmad.ansari.dev@gamil.com asking about openings'. "
            "Parameters: {'recipient_email': string, 'role': string (optional), 'company': string (optional), 'subject': string (optional)}.\n"
            "17. 'chat': General career advice, interview preparation, questions out of system scope, or conversational greetings. "
            "Parameters: {'text': string}.\n"
            "18. 'add_qna': Adding a question and answer pair to the candidate QnA knowledge base. "
            "Examples: 'add qna what is your notice period = immediate', 'save answer for relocations: yes'. "
            "Parameters: {'question': string, 'answer': string, 'raw': string}.\n"
            "19. 'test_qna': Testing how the QnA matching engine resolves an interview or screening question. "
            "Examples: 'test question do you know python?'. Parameters: {'question': string}.\n"
            "20. 'list_qna': Listing all saved custom QnA rules, answers, and screening knowledge. "
            "Examples: 'list qna', 'show questions', 'show qna'. Parameters: {}.\n\n"
            "CRITICAL: Consequential actions ('apply_jobs', 'start_automation') MUST ONLY be chosen for direct imperative commands, "
            "NEVER for questions like 'did i apply' or 'how to apply'. Return strictly valid JSON: {\"action\": string, \"parameters\": object, \"summary\": string}."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User instruction: {text}"},
        ]

        request = AIRequest(
            messages=messages,
            model=model_name,
            temperature=0.0,
        )

        resp = self.ai_gateway.chat(request)
        raw_content = resp.content.strip() if hasattr(resp, "content") else str(resp).strip()
        # Clean markdown json code blocks if present
        if raw_content.startswith("```"):
            raw_content = re.sub(r"^```(?:json)?\s*", "", raw_content, flags=re.IGNORECASE)
            raw_content = re.sub(r"\s*```$", "", raw_content)
        m_json = re.search(r"(\{.*\})", raw_content, re.DOTALL)
        if m_json:
            data = json.loads(m_json.group(1))
        else:
            data = json.loads(raw_content)

        action_str = data.get("action", "").lower()
        params = data.get("parameters", {})
        summary = data.get("summary", "")

        action_map = {
            "start_automation": PilotActionType.START_AUTOMATION,
            "stop_automation": PilotActionType.STOP_AUTOMATION,
            "pause_automation": PilotActionType.PAUSE_AUTOMATION,
            "resume_automation": PilotActionType.RESUME_AUTOMATION,
            "get_applications_report": PilotActionType.GET_APPLICATIONS_REPORT,
            "get_top_jobs": PilotActionType.GET_TOP_JOBS,
            "search_jobs": PilotActionType.SEARCH_JOBS,
            "apply_jobs": PilotActionType.APPLY_JOBS,
            "check_platforms": PilotActionType.CHECK_PLATFORMS,
            "extract_resume": PilotActionType.EXTRACT_RESUME,
            "get_resume_skills": PilotActionType.GET_RESUME_SKILLS,
            "list_resumes": PilotActionType.LIST_RESUMES,
            "tailor_resume": PilotActionType.TAILOR_RESUME,
            "get_offers": PilotActionType.GET_OFFERS,
            "update_application_status": PilotActionType.UPDATE_APPLICATION_STATUS,
            "query_application_status": PilotActionType.QUERY_APPLICATION_STATUS,
            "delete_application": PilotActionType.DELETE_APPLICATION,
            "update_profile": PilotActionType.UPDATE_PROFILE,
            "get_interviews_report": PilotActionType.GET_INTERVIEWS_REPORT,
            "add_qna": PilotActionType.ADD_QNA,
            "test_qna": PilotActionType.TEST_QNA,
            "list_qna": PilotActionType.LIST_QNA,
            "get_rules": PilotActionType.GET_RULES,
            "update_rules": PilotActionType.UPDATE_RULES,
            "get_status": PilotActionType.GET_STATUS,
            "send_email_application": PilotActionType.SEND_EMAIL_APPLICATION,
            "get_followups": PilotActionType.GET_FOLLOWUPS,
            "execute_followup": PilotActionType.EXECUTE_FOLLOWUP,
            "snooze_followup": PilotActionType.SNOOZE_FOLLOWUP,
            "cancel_followup": PilotActionType.CANCEL_FOLLOWUP,
            "answer_intervention": PilotActionType.ANSWER_INTERVENTION,
            "chat": PilotActionType.CHAT,
        }

        action = action_map.get(action_str, PilotActionType.UNKNOWN)
        if action == PilotActionType.UPDATE_RULES and "deal_breaker" in params and "type" not in params:
            params["type"] = "add_deal_breaker"
        return action, params, summary

    def _infer_via_rules(self, text: str) -> Tuple[PilotActionType, Dict[str, Any], str]:
        """High-precision deterministic pattern matcher for 100% offline reliability."""
        lower = text.lower()
        urls = URL_REGEX.findall(text)

        # 1. 2FA Code / OTP / Verification Answers
        code_match = re.search(r"\b(\d{4,8})\b", text)
        if ("code" in lower or "otp" in lower or "2fa" in lower or "verification" in lower) and code_match:
            code = code_match.group(1)
            return PilotActionType.ANSWER_INTERVENTION, {"answer": code}, f"Parsed verification code: {code}"

        # 1a. Direct Email Application / Recruiter Cold Outreach Intent
        email_match = re.search(r"\b([a-zA-Z0-9\.\-_+]+@[a-zA-Z0-9\.\-_]+\.[a-zA-Z]{2,})\b", text)
        if email_match and any(w in lower for w in ["email", "mail", "send", "outreach", "apply", "application", "inquiry", "opening", "openings"]):
            rec_email = email_match.group(1).strip()
            # Try specific job title extraction first (e.g. "RPL developer", "RPA developer", "Software Engineer")
            specific_roles = re.findall(
                r"\b(?:for|as|role\s+of)\s+(?:the\s+|a\s+)?([a-zA-Z0-9\.\-_/]+(?:\s+[a-zA-Z0-9\.\-_/]+){0,3}\s+(?:developer|engineer|architect|associate|analyst|manager|lead|specialist|consultant))\b",
                text,
                re.IGNORECASE,
            )
            if specific_roles:
                detected_role = specific_roles[-1].strip()
            else:
                role_match = re.search(
                    r"(?:for\s+(?:the\s+)?|as\s+(?:a\s+)?|role\s+of\s+)([a-zA-Z0-9\s\.\-_/]+?)"
                    r"(?:\s+across|\s+and|\s+profile|\s+to|\s+at|\s+company|\s+with|\s+just|\s+write|$)",
                    text,
                    re.IGNORECASE,
                )
                detected_role = role_match.group(1).strip() if role_match else "RPA & AI Automation Engineer"

            if any(k in detected_role.lower() for k in ("email", "mail", "application", "opening", "openings", "the", "a", "an", "below email id")):
                detected_role = "RPA & AI Automation Engineer"

            # Normalize speech-to-text typo RPL -> RPA
            if re.search(r"\brpl\b", detected_role, re.IGNORECASE):
                detected_role = re.sub(r"\brpl\b", "RPA", detected_role, flags=re.IGNORECASE)

            detected_comp = None
            if "do not mention" not in lower and "dont mention" not in lower:
                comp_match = re.search(r"(?:company\s+(?:is|called|named)?\s*([a-zA-Z0-9\s\.\-_/]+?)(?:\s+do\s+not|\s+just|\s+write|$))", text, re.IGNORECASE)
                if comp_match:
                    detected_comp = comp_match.group(1).strip()

            return (
                PilotActionType.SEND_EMAIL_APPLICATION,
                {
                    "recipient_email": rec_email,
                    "role": detected_role,
                    "company": detected_comp,
                    "raw_prompt": text,
                },
                f"Send email application to {rec_email} for role '{detected_role}'",
            )

        # 1aa. Outreach Cadence Follow-Up Inquiries & Human-in-the-Loop Actions
        if any(k in lower for k in ("followup", "follow-up", "follow up", "cadence")):
            if any(w in lower for w in ("send", "dispatch", "shoot", "approve", "confirm", "deliver")):
                fu_id_match = re.search(r"\b(?:id|#)\s*(\d+)\b", text, re.IGNORECASE)
                comp_match = re.search(r"(?:for|to|at)\s+([a-zA-Z0-9\s\.\-_]+?)(?:\s+now|\s+please|\s+today|$)", text, re.IGNORECASE)
                return (
                    PilotActionType.EXECUTE_FOLLOWUP,
                    {
                        "followup_id": int(fu_id_match.group(1)) if fu_id_match else None,
                        "company": comp_match.group(1).strip() if comp_match else None,
                    },
                    "Send approved outreach follow-up email",
                )
            if any(w in lower for w in ("snooze", "delay", "postpone", "later", "hold")):
                days_match = re.search(r"(\d+)\s*(?:day|days)", text, re.IGNORECASE)
                days = int(days_match.group(1)) if days_match else 3
                return (
                    PilotActionType.SNOOZE_FOLLOWUP,
                    {"days": days},
                    f"Snooze outreach cadence by {days} days",
                )
            if any(w in lower for w in ("cancel", "stop", "abort", "remove", "dismiss")):
                return (
                    PilotActionType.CANCEL_FOLLOWUP,
                    {},
                    "Cancel outreach follow-up cadence",
                )
            return (
                PilotActionType.GET_FOLLOWUPS,
                {},
                "Check pending and due outreach follow-up cadences",
            )

        # 1b. Complete / Autofill Profile Setup Intent
        is_profile_setup = (
            any(phrase in lower for phrase in [
                "complete setup my profile",
                "setup my profile",
                "complete my profile",
                "setup profile",
                "complete profile",
                "fill my profile",
                "fill profile",
                "autofill profile",
                "auto fill profile",
                "autofill my profile",
                "populate my profile",
                "populate profile",
                "sync resume to profile",
                "sync my resume to profile",
                "write a bio",
                "write bio",
                "write a cover letter",
                "write cover letter",
            ])
            or (
                ("profile" in lower or "bio" in lower or "cover letter" in lower)
                and ("resume" in lower or "missing" in lower or "complete" in lower or "update" in lower or "setup" in lower)
                and any(w in lower for w in ["resume", "bio", "cover letter", "github", "linkedin", "missing details", "details", "data"])
            )
        )
        if is_profile_setup and not any(k in lower for k in ["status", "application", "record"]):
            return PilotActionType.UPDATE_PROFILE, {"action": "autofill_from_resume"}, "Complete candidate profile setup from resume and AI generation"

        # 1c. Specific Web Link Updates (LinkedIn, GitHub, Portfolio)
        m_link = re.search(
            r"(?:change|update|set)\s+(?:the\s+)?(?:my\s+)?(linkedin|github|portfolio)\s*(?:url|link)?\s*(?:to|as)?\s*(https?://[^\s]+|[a-zA-Z0-9_\-\.]+)",
            text,
            flags=re.IGNORECASE,
        )
        if m_link and not any(k in lower for k in ["status", "application", "record"]):
            platform_link = m_link.group(1).lower()
            link_val = m_link.group(2).strip()
            field_name = f"{platform_link}_url"
            return PilotActionType.UPDATE_PROFILE, {"field": field_name, "value": link_val}, f"Update candidate {platform_link} URL: {link_val}"

        # 1d. Work Experience, Projects, Roles & Responsibilities Intent
        m_exp_req = (
            any(k in lower for k in [
                "work experience", "experience history", "job experience", "job history",
                "role and responsibilit", "roles and responsibilit", "roles & responsibilit",
                "current job and responsibilit", "my work experience", "experience part",
                "joining date", "start date", "end date",
            ])
            or (
                ("experience" in lower or "responsibility" in lower or "responsibilities" in lower or "project" in lower or "projects" in lower or "joining date" in lower or "start date" in lower)
                and any(w in lower for w in ["resume", "profile", "aventiq", "write into", "add", "update", "summarize", "populate", "role", "job", "joining date", "start date", "set", "change"])
                and not any(k in lower for k in ["status", "application", "record", "delete", "remove"])
            )
        )
        if m_exp_req:
            # Check if this is specifically a joining date or start date update
            m_join = re.search(r"(?:joining\s+date|start\s+date)\s+(?:to|as|is)?\s*([a-zA-Z0-9\s,]+)", text, re.IGNORECASE)
            val = m_join.group(1).strip() if m_join else None
            return (
                PilotActionType.UPDATE_PROFILE,
                {"action": "update_work_experience", "target": "experience", "field": "start_date" if val else "work_experiences", "value": val, "raw_prompt": text},
                "Update candidate work experience, roles, responsibilities, and projects",
            )

        # 1e. Education / Academic Background Intent
        m_edu_req = (
            any(k in lower for k in [
                "educational background", "education background", "education history", "academic background",
                "academic credentials", "my education", "my degree", "my university", "my college",
            ])
            or (
                ("education" in lower or "degree" in lower or "university" in lower or "college" in lower or "academic" in lower)
                and any(w in lower for w in ["resume", "profile", "add", "update", "populate", "background", "history"])
                and not any(k in lower for k in ["status", "application", "record", "delete", "remove"])
            )
        )
        if m_edu_req:
            return (
                PilotActionType.UPDATE_PROFILE,
                {"action": "update_education", "target": "education", "raw_prompt": text},
                "Update candidate education & academic background",
            )

        # 1f. Profile Update Intent (Current/Expected CTC, salary, notice period, role, location, experience)

        # 1f-1. Compound CTC Update (Both Expected & Current CTC in single prompt, voice-tolerant e.g. "ctg", "uh", "lakh")
        clean_comp_text = re.sub(r"\bctg\b", "ctc", lower)
        if ("ctc" in clean_comp_text or "salary" in clean_comp_text) and any(k in clean_comp_text for k in ["expected", "target", "current"]):
            m_exp = re.search(r"(?:expected|target)\s+(?:ctc|salary|comp|package)?\s*(?:to\s+|is\s+|as\s+)?(?:the\s+|uh\s+)?([a-zA-Z0-9\s\.,₹$]+?)(?:\s+and|\s+with|\s+current|$)", clean_comp_text)
            m_curr = re.search(r"(?:current)\s+(?:ctc|salary|comp|package)?\s*(?:to\s+|is\s+|as\s+)?(?:the\s+|uh\s+)?([a-zA-Z0-9\s\.,₹$]+?)(?:\s+and|\s+with|\s+expected|$)", clean_comp_text)
            if m_exp or m_curr:
                exp_raw = m_exp.group(1).strip() if m_exp else None
                curr_raw = m_curr.group(1).strip() if m_curr else None
                exp_amt = parse_compensation_amount(exp_raw) if exp_raw else None
                curr_amt = parse_compensation_amount(curr_raw) if curr_raw else None
                if exp_amt is not None or curr_amt is not None:
                    return (
                        PilotActionType.UPDATE_PROFILE,
                        {
                            "action": "update_compensation",
                            "field": "compensation",
                            "expected_ctc": exp_amt,
                            "current_ctc": curr_amt,
                            "expected_ctc_raw": exp_raw,
                            "current_ctc_raw": curr_raw,
                            "raw_prompt": text,
                        },
                        f"Update candidate compensation (Current: {curr_amt}, Expected: {exp_amt})",
                    )

        # 1f-2. Bare CTC / Salary update request without any specified amount (ask user for value instead of 0)
        m_bare_ctc = re.search(r"^(?:please\s+)?(?:change|update|set|modify)\s+(?:the\s+)?(?:my\s+)?(?:current\s+|expected\s+)?(?:ctc|salary|compensation|package|ctg)\s*$", clean_comp_text)
        if m_bare_ctc:
            return (
                PilotActionType.UPDATE_PROFILE,
                {
                    "action": "prompt_missing_ctc",
                    "field": "ctc",
                    "raw_prompt": text,
                },
                "Prompt candidate for CTC amount",
            )

        m_prof = re.search(
            r"(change|update|set)\s+(?:the\s+)?(?:my\s+)?"
            r"(current\s+(?:ctc|salary|states?|status|comp|package)|expected\s+(?:ctc|salary|states?|status|comp|package)|target\s+(?:ctc|salary|states?|status|comp|package)|ctc|salary|notice(?:\s+period)?)\s+"
            r"(?:(?:from\s+)?[\d\.]+\s*(?:lpa|lakhs?|lac|days?)?\s+)?(?:to\s+|as\s+)?([a-zA-Z0-9\s\.,₹$]+)",
            clean_comp_text
        )
        if m_prof:
            raw_field = m_prof.group(2).strip()
            raw_amt = m_prof.group(3).strip()
            if "notice" in raw_field:
                num_match = re.search(r"(\d+)", raw_amt)
                num_val = int(num_match.group(1)) if num_match else 30
                return PilotActionType.UPDATE_PROFILE, {"field": "notice_period_days", "value": num_val}, f"Update candidate notice period: {num_val} days"

            parsed_comp = parse_compensation_amount(raw_amt)
            if parsed_comp is not None:
                if "expect" in raw_field or "target" in raw_field:
                    return PilotActionType.UPDATE_PROFILE, {"field": "expected_ctc", "value": parsed_comp}, f"Update candidate expected CTC: {parsed_comp}"
                else:
                    return PilotActionType.UPDATE_PROFILE, {"field": "current_ctc", "value": parsed_comp}, f"Update candidate current CTC: {parsed_comp}"

        m_role = re.search(r"(?:change|update|set)\s+(?:the\s+)?(?:my\s+)?(?:current\s+)?(title|role|designation)\s+(?:to|as)\s+(.+)", lower)
        if m_role and not any(k in lower for k in ["status", "application", "record"]):
            new_title = m_role.group(2).strip().title()
            return PilotActionType.UPDATE_PROFILE, {"field": "current_title", "value": new_title}, f"Update candidate title: {new_title}"

        m_loc = re.search(r"(?:change|update|set)\s+(?:the\s+)?(?:my\s+)?(?:current\s+)?(location|city)\s+(?:to|as)\s+([a-zA-Z\s]+)", lower)
        if m_loc and not any(k in lower for k in ["status", "application", "record"]):
            new_loc = m_loc.group(2).strip().title()
            return PilotActionType.UPDATE_PROFILE, {"field": "location", "value": new_loc}, f"Update candidate location: {new_loc}"

        m_exp = re.search(r"(?:change|update|set)\s+(?:the\s+)?(?:my\s+)?(?:total\s+)?experience\s+(?:(?:from\s+)?[\d\.]+\s*(?:years?|yrs?)?\s+)?(?:to|as)\s+([\d\.]+)\s*(?:years?|yrs?)?", lower)
        if m_exp:
            exp_val = float(m_exp.group(1))
            return PilotActionType.UPDATE_PROFILE, {"field": "years_of_experience", "value": exp_val}, f"Update candidate experience: {exp_val} years"

        # 1c. Delete Application / Record Intent
        known_platforms = ["linkedin", "naukri", "indeed", "glassdoor", "foundit", "email"]
        detected_plat = None
        for p_name in known_platforms:
            if p_name in lower:
                detected_plat = p_name
                break

        m_del = re.search(
            r"(?:delete|remove)\s+(?:all\s+)?(?:applications?\s+(?:for|of)\s+|records?\s+(?:for|of)\s+)?"
            r"([a-zA-Z0-9\s\.\-&/]+?)"
            r"(?:\s+application|\s+record|\s+from\s+pipeline|\s+from\s+(?:the\s+)?(?:this|[a-zA-Z]+)(?:\s+platform)?|$)",
            lower
        )
        if m_del and any(w in lower for w in ["delete", "remove"]) and not any(p in lower for p in ["deal breaker", "dealbreaker", "rule", "rules", "qna", "skip", "keyword", "keywords", "exclusion", "negative"]):
            comp = m_del.group(1).strip()
            if comp and comp not in ["all", "the", "my"]:
                return PilotActionType.DELETE_APPLICATION, {"company": comp, "platform": detected_plat}, f"Delete application and records for {comp}."

        # 1d. Interviews Report (active vs past interviews)
        if any(w in lower for w in ["interview", "interveiw", "interviewing"]) and any(w in lower for w in ["how many", "which", "what", "show", "list", "status", "report", "round", "rounds"]):
            return PilotActionType.GET_INTERVIEWS_REPORT, {}, "Generating verified interview status report."

        # 1e. Mark / Update Status (supports "all", typo tolerance e.g. "rjected", "insfosys")
        m_mark = re.search(r"mark(?:ed)?\s+(all\s+)?(?:the\s+)?(?:applications?\s+(?:for|of)\s+)?([a-zA-Z0-9\s\.\-&/]+?)\s+(?:as|to)\s+([a-zA-Z\s]+)", lower)
        if m_mark:
            is_all = bool(m_mark.group(1))
            comp = m_mark.group(2).strip()
            st_raw = m_mark.group(3).strip()
            resolved = resolve_status_keyword(st_raw)
            if resolved:
                return PilotActionType.UPDATE_APPLICATION_STATUS, {"company": comp, "status": resolved, "update_all": is_all}, f"Update application status for {comp} to {resolved}."

        m_for = re.search(r"for\s+(all\s+)?([a-zA-Z0-9\s\.\-&/]+?)\s+(?:is\s+)?mark(?:ed)?\s+as\s+([a-zA-Z\s]+)", lower)
        if m_for:
            is_all = bool(m_for.group(1))
            comp = m_for.group(2).strip()
            st_raw = m_for.group(3).strip()
            resolved = resolve_status_keyword(st_raw)
            if resolved:
                return PilotActionType.UPDATE_APPLICATION_STATUS, {"company": comp, "status": resolved, "update_all": is_all}, f"Update application status for {comp} to {resolved}."

        m_upd = re.search(r"(?:update|set|change)\s+(?:the\s+)?(?:status\s+(?:of|for)\s+)?(all\s+)?([a-zA-Z0-9\s\.\-&/]+?)\s+(?:status\s+)?to\s+([a-zA-Z\s]+)", lower)
        if m_upd:
            is_all = bool(m_upd.group(1))
            comp = m_upd.group(2).strip()
            st_raw = m_upd.group(3).strip()
            resolved = resolve_status_keyword(st_raw)
            if resolved:
                return PilotActionType.UPDATE_APPLICATION_STATUS, {"company": comp, "status": resolved, "update_all": is_all}, f"Update application status for {comp} to {resolved}."

        m_comp_mark = re.search(r"([a-zA-Z0-9\s\.\-&/]+?)\s+(?:application\s+)?mark(?:ed)?\s+as\s+([a-zA-Z\s]+)", lower)
        if m_comp_mark:
            c = m_comp_mark.group(1).strip()
            st_raw = m_comp_mark.group(2).strip()
            resolved = resolve_status_keyword(st_raw)
            if resolved and c not in ["please", "can you", "i want to"]:
                return PilotActionType.UPDATE_APPLICATION_STATUS, {"company": c, "status": resolved, "update_all": False}, f"Update application status for {c} to {resolved}."

        # 1f. Specific Company / Role Application Status Inquiries
        m_inq = re.search(
            r"^(?:did\s+i|did\s+we|have\s+i|have\s+we|was\s+i|am\s+i|check\s+if\s+i|check\s+if\s+we)\s+(?:already\s+)?(?:apply|applied)\s+(?:to|for|at|with)?\s*(.+)$",
            lower
        )
        if not m_inq:
            m_inq = re.search(
                r"^(?:is\s+there\s+an\s+application\s+for|check\s+application\s+for)\s+(.+)$",
                lower
            )
        if m_inq:
            payload = m_inq.group(1).strip().rstrip("?.! ")
            m_id = re.search(r"^(?:#|job\s+|id\s+)?(\d{2,6})$", payload)
            if m_id:
                return PilotActionType.QUERY_APPLICATION_STATUS, {"job_id": int(m_id.group(1))}, f"Querying application status for Job #{m_id.group(1)}."
            if " at " in payload:
                role_part, comp_part = payload.rsplit(" at ", 1)
                return PilotActionType.QUERY_APPLICATION_STATUS, {"company": comp_part.strip(), "role": role_part.strip()}, f"Querying application status for {comp_part.strip()}."
            elif " for " in payload:
                role_part, comp_part = payload.rsplit(" for ", 1)
                return PilotActionType.QUERY_APPLICATION_STATUS, {"company": comp_part.strip(), "role": role_part.strip()}, f"Querying application status for {comp_part.strip()}."
            else:
                return PilotActionType.QUERY_APPLICATION_STATUS, {"company": payload}, f"Querying application status for {payload}."

        m_stat_comp = re.search(r"(?:status\s+of|check|how\s+is)\s+(?:my\s+)?(?:application\s+(?:for|at)\s+)?([a-zA-Z0-9\s\.\-&/]+?)(?:\s+application|\s+status|\s*\?|$)", lower)
        if m_stat_comp and not any(p in lower for p in ["apply report", "applications report", "pipeline report", "summary", "platforms", "platform", "interview", "interveiw"]):
            target_comp = m_stat_comp.group(1).strip()
            if target_comp and target_comp not in ["my", "the", "all", "our", "recent"]:
                return PilotActionType.QUERY_APPLICATION_STATUS, {"company": target_comp}, f"Querying application status for {target_comp}."

        # 2. Applications & Today's Apply Reports (MUST RUN BEFORE APPLY_JOBS)
        report_patterns = [
            "apply report", "applications report", "application report",
            "today apply report", "today's report", "today report",
            "what did we apply", "what did you apply", "applied today",
            "recent applications", "application status", "pipeline report",
            "how many jobs applied", "applications summary", "show applications",
            "list applications"
        ]
        if any(p in lower for p in report_patterns):
            timeframe = "today" if ("today" in lower or "what did we apply" in lower) else "all"
            return PilotActionType.GET_APPLICATIONS_REPORT, {"timeframe": timeframe}, "Generating applications report from database."

        # 3. Start Automation Commands
        # Matches: "run linkedin", "run the linkedin automation", "start indeed bot", "launch naukri", "run automation"
        start_verbs = ["run", "start", "launch", "execute", "trigger", "begin", "fire up"]
        has_start_verb = any(re.search(rf"\b{re.escape(v)}\b", lower) for v in start_verbs)

        if has_start_verb and ("automation" in lower or "bot" in lower or any(p in lower for p in PLATFORMS) or "easy apply" in lower):
            # Detect platform (prioritize 'all' if user mentions all automation / all platforms)
            if re.search(r"\b(all|all\s+platforms?|everything)\b", lower):
                platform = "all"
            else:
                platform = "linkedin"  # Default
                for p in PLATFORMS:
                    if p != "all" and p in lower:
                        platform = p
                        break

            params: Dict[str, Any] = {"platform": platform}
            if urls:
                params["url"] = urls[0]
                params["platform"] = "universal"

            if "headless" in lower:
                params["headless"] = True
            elif "visible" in lower or "show browser" in lower:
                params["headless"] = False

            display_platform = "All Platforms" if platform == "all" else platform.capitalize()
            return PilotActionType.START_AUTOMATION, params, f"Starting {display_platform} automation engine."

        # 4. Stop / Pause / Resume Automation Control
        is_cv_action = any(w in lower for w in ["extract", "parse", "tailor", "list", "upload", "default", "my resume", "active resume", "resumes"])
        if re.search(r"\b(pause|freeze|hold)\b", lower):
            return PilotActionType.PAUSE_AUTOMATION, {}, "Requesting automation pause."
        if not is_cv_action and (
            re.search(r"\b(unpause|continue)\b", lower)
            or re.search(r"\bresume\s+(automation|bot|worker|pilot|run|task)\b", lower)
            or lower.strip() == "resume"
        ):
            return PilotActionType.RESUME_AUTOMATION, {}, "Resuming automation."
        if re.search(r"\b(stop|cancel|abort|halt|terminate)\b", lower):
            return PilotActionType.STOP_AUTOMATION, {}, "Stopping active automation."

        # 5. Platform Status & Credential Verification
        if any(p in lower for p in ["check platforms", "platform status", "are platforms ready", "check credentials", "is linkedin configured", "platform readiness", "platforms"]):
            return PilotActionType.CHECK_PLATFORMS, {}, "Checking readiness and credentials of automation platforms."

        # 6. Top Opportunities & Eligible Jobs List
        if (
            any(p in lower for p in ["show eligible jobs", "top jobs", "top opportunities", "matching jobs", "eligible jobs", "show matches", "qualified jobs"])
            or re.search(r"\btop\s+(\d+)?\s*jobs?\b", lower)
            or ("top" in lower and "job" in lower and ("find" in lower or "recommend" in lower or "today" in lower or "show" in lower))
        ):
            count_match = re.search(r"\btop\s+(\d+)\b", lower)
            limit = int(count_match.group(1)) if count_match else 10
            return PilotActionType.GET_TOP_JOBS, {"limit": limit}, f"Fetching top {limit} qualified job opportunities from database."

        # 7. Candidate Offers & Company Intelligence
        if any(w in lower for w in ["offer", "offers", "job offer", "received offer", "about the offer", "company offer", "what offer", "which company offer"]):
            return PilotActionType.GET_OFFERS, {"query": text}, "Retrieving candidate job offers and company background."

        # 8. General Operational Status & Telemetry Queries
        if any(q in lower for q in ["status", "daily report", "progress", "summary today", "metrics", "kpi"]):
            return PilotActionType.GET_STATUS, {}, "Retrieving live operational status."

        # 9. Resume & Profile Operations
        if any(p in lower for p in ["key skills", "skills from my resume", "skills from resume", "my skills", "what are my skills", "what skills", "list skills", "show skills"]):
            return PilotActionType.GET_RESUME_SKILLS, {}, "Extracting key technical skills from candidate resume."
        if any(p in lower for p in ["extract resume", "parse resume", "read my resume", "read resume", "extract facts"]):
            return PilotActionType.EXTRACT_RESUME, {}, "Extracting facts from current resume."
        if any(p in lower for p in ["list resumes", "show resumes", "my resumes", "resume versions"]):
            return PilotActionType.LIST_RESUMES, {}, "Listing candidate resumes in library."
        if any(k in lower for k in ["tailor", "design", "customize", "adapt", "build"]) and "resume" in lower:
            target = re.sub(r".*(tailor|design|customize|adapt|build)\s+(my\s+)?(a\s+)?resume\s*(for|to)?\s*", "", lower).strip()
            target = re.sub(r"\b(for\s+me|please|me|a\s+role|role|roles|jobs?|for)\b", "", target, flags=re.IGNORECASE).strip()
            target = re.sub(r"\s+", " ", target).strip()
            if not target or target.lower() in ("this", "the jd", "this job", "target role"):
                target = "Senior Automation Engineer"
            elif target.lower() == "full stack":
                target = "Full Stack Engineer"
            return PilotActionType.TAILOR_RESUME, {"target": target}, f"Designing tailored resume for: {target}"

        # 10. QnA Knowledge Base Management
        if "add qna" in lower or "save answer" in lower:
            stripped = re.sub(r"^(?:add\s+qna|save\s+answer)\s*[:\-]?\s*", "", text, flags=re.IGNORECASE).strip()
            q_part = ""
            a_part = ""
            if "=" in stripped:
                parts = stripped.split("=", 1)
                q_part, a_part = parts[0].strip(), parts[1].strip()
            elif "->" in stripped:
                parts = stripped.split("->", 1)
                q_part, a_part = parts[0].strip(), parts[1].strip()
            params_dict: Dict[str, Any] = {"raw": text}
            if q_part and a_part:
                params_dict["question"] = q_part
                params_dict["answer"] = a_part
            return PilotActionType.ADD_QNA, params_dict, "Adding custom answer to QnA knowledge base."
        if "test question" in lower:
            q_text = re.sub(r".*test\s+question\s*", "", text, flags=re.IGNORECASE).strip()
            return PilotActionType.TEST_QNA, {"question": q_text}, f"Testing match for question: '{q_text}'"
        if "list qna" in lower or "show qna" in lower or "show questions" in lower:
            return PilotActionType.LIST_QNA, {}, "Listing saved QnA rules and answers."

        # 10. Explicit Add / Remove of Skip Keywords and Deal-Breakers
        # A. Add variations (suffix: 'add unity as skip keyword in list', 'add unity to skip keywords'; prefix: 'add skip keyword unity')
        m_add_skip = re.search(
            r"(?:add|insert|include|put)\s+([a-zA-Z0-9\+\#\.\-_/]+(?:\s+[a-zA-Z0-9\+\#\.\-_/]+)?)\s+(?:as\s+(?:a\s+|an\s+)?|in\s+(?:the\s+)?|to\s+(?:the\s+)?|into\s+(?:the\s+)?|under\s+(?:the\s+)?)(?:(?:the\s+)?skip\s+keywords?(?:\s+in\s+list|\s+list)?|(?:the\s+)?skip\s+list|skips?|negative\s+keywords?(?:\s+list)?|negative\s+title\s+words?(?:\s+list)?|exclusion\s+list|exclusions?|deal\s+breakers?)",
            lower
        )
        if not m_add_skip:
            m_add_skip = re.search(
                r"(?:add|insert|include|put)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:skip\s+keywords?|skip\s+list|skips?|negative\s+keywords?|negative\s+title\s+words?|exclusion\s+list|exclusions?|deal\s+breakers?)(?:\s*:|\s+for|\s+called|\s+is|\s+named|\s+as|\s+)?\s+([a-zA-Z0-9\+\#\.\-_/]+(?:\s+[a-zA-Z0-9\+\#\.\-_/]+)?)",
                lower
            )
        if m_add_skip:
            target = m_add_skip.group(1).strip()
            target = re.sub(r"[\.\!\?\'\"]", "", target).strip()
            if target and target not in ("keyword", "keywords", "rule", "rules", "list", "skip", "skips"):
                return PilotActionType.UPDATE_RULES, {"type": "add_deal_breaker", "deal_breaker": target}, f"Add skip keyword: '{target}'"

        # B. Remove variations (suffix: 'remove unity from skip list', 'remove unity as skip keyword'; prefix: 'remove skip keyword unity')
        m_rem_skip = re.search(
            r"(?:remove|delete|unskip|allow|drop)\s+([a-zA-Z0-9\+\#\.\-_/]+(?:\s+[a-zA-Z0-9\+\#\.\-_/]+)?)\s+(?:from\s+(?:the\s+)?|in\s+(?:the\s+)?|out\s+of\s+(?:the\s+)?|as\s+(?:a\s+|an\s+)?)(?:(?:the\s+)?skip\s+keywords?(?:\s+in\s+list|\s+list)?|(?:the\s+)?skip\s+list|skips?|negative\s+keywords?(?:\s+list)?|negative\s+title\s+words?(?:\s+list)?|exclusion\s+list|exclusions?|deal\s+breakers?)",
            lower
        )
        if not m_rem_skip:
            m_rem_skip = re.search(
                r"(?:remove|delete|unskip|allow|drop)\s+(?:the\s+)?(?:skip\s+keywords?|skip\s+list|skips?|negative\s+keywords?|negative\s+title\s+words?|exclusion\s+list|exclusions?|deal\s+breakers?)(?:\s*:|\s+for|\s+called|\s+is|\s+named|\s+)?\s+([a-zA-Z0-9\+\#\.\-_/]+(?:\s+[a-zA-Z0-9\+\#\.\-_/]+)?)",
                lower
            )
        if not m_rem_skip:
            m_rem_skip = re.search(r"^(?:please\s+)?(?:unskip|allow)\s+([a-zA-Z0-9\+\#\.\-_/]+(?:\s+[a-zA-Z0-9\+\#\.\-_/]+)?)$", lower)
        if m_rem_skip:
            target = m_rem_skip.group(1).strip()
            target = re.sub(r"[\.\!\?\'\"]", "", target).strip()
            if target and target not in ("keyword", "keywords", "rule", "rules", "list", "skip", "skips"):
                return PilotActionType.UPDATE_RULES, {"type": "remove_deal_breaker", "deal_breaker": target}, f"Remove skip keyword: '{target}'"

        # 10b. Rules & Skip Keywords Inspection Queries
        is_action = any(lower.startswith(act) for act in ["add ", "insert ", "include ", "put ", "remove ", "delete ", "drop ", "unskip ", "allow "])
        is_query = any(q in lower for q in ["what", "show", "give me", "which", "how many", "view", "tell me", "display", "?"]) or lower.startswith("list") or "list of" in lower
        rule_query_phrases = [
            "skip keyword", "skip keywords", "deal breaker", "deal breakers",
            "exclusion rule", "exclusion rules", "excluded keyword", "excluded keywords",
            "negative keyword", "negative keywords", "show rules", "list rules",
            "what are the rules", "what are rules", "view rules", "my rules",
            "get rules", "rules list"
        ]
        if not is_action and (
            (is_query and any(w in lower for w in ["skip", "exclude", "rule", "deal breaker", "negative"]))
            or any(p in lower for p in rule_query_phrases)
        ):
            return PilotActionType.GET_RULES, {}, "Retrieving active skip keywords, deal-breakers, and exclusion rules."

        # 10c. Imperative Rule Modifications (Deal-breakers, Min Score, Daily Limit)
        m_skip = re.search(r"^(?:please\s+)?(?:skip|exclude|don't apply to|do not apply to|never apply to|avoid)\s+(?:jobs?\s+(?:that\s+need|requiring|with)?\s*)?([a-zA-Z0-9\+\#\.\s\-_/]+)$", lower)
        if m_skip and not is_query:
            target = m_skip.group(1).strip()
            target = re.sub(r"[\.\!\?]", "", target).strip()
            if target and target not in ("keyword", "keywords", "skip keyword", "skip keywords", "rule", "rules", "deal breaker", "deal breakers"):
                return PilotActionType.UPDATE_RULES, {"type": "add_deal_breaker", "deal_breaker": target}, f"Add deal-breaker: '{target}'"

        score_match = re.search(r"(min(imum)?\s+score|match\s+score)\s*(to|is|=|:)?\s*(\d{1,3})%?", lower)
        if score_match:
            score = int(score_match.group(4))
            return PilotActionType.UPDATE_RULES, {"type": "set_min_score", "min_score": score}, f"Set minimum score threshold to {score}%"

        limit_match = re.search(r"(daily\s+limit|max\s+applies)\s*(to|is|=|:)?\s*(\d{1,3})", lower)
        if limit_match:
            limit_val = int(limit_match.group(3))
            return PilotActionType.UPDATE_RULES, {"type": "set_daily_limit", "daily_limit": limit_val}, f"Set daily application limit to {limit_val}"

        # 11. Apply to Jobs (Direct Imperative Action Only)
        is_apply_inquiry = bool(re.search(r"^(?:did\s+i|did\s+we|have\s+i|have\s+we|was\s+i|am\s+i|check\s+if\s+i|check\s+if\s+we|how\s+many|where\s+did|what\s+did|why\s+did|can\s+i|how\s+to|how\s+do\s+i|should\s+i)\b", lower))
        is_apply_negation = any(p in lower for p in ["dont apply", "don't apply", "do not apply", "never apply", "stop apply", "apply report", "application report", "applications report", "apply mode", "easy apply only"])

        job_id_match = re.search(r"\bapply\s+(?:to\s+)?(?:#|job\s+|id\s+)?(\d{2,6})\b", lower)
        count_match = re.search(r"\bapply\s+(?:to\s+)?(\d{1,2})\s+jobs?\b", lower)
        is_direct_apply = bool(re.search(r"^(?:please\s+)?(?:start\s+applying|begin\s+applying|apply\s+now|apply\s+to|apply\s+for|apply\s+on)\b", lower)) or bool(urls and "apply" in lower)

        if not is_apply_inquiry and not is_apply_negation and (job_id_match or count_match or is_direct_apply):
            job_id = int(job_id_match.group(1)) if job_id_match else None
            count = int(count_match.group(1)) if count_match else (1 if job_id else 5)
            params: Dict[str, Any] = {"count": count}
            if job_id:
                params["job_id"] = job_id
            if urls:
                params["url"] = urls[0]
            for p in PLATFORMS:
                if p in lower:
                    params["platform"] = p
                    break
            summary_txt = f"Queuing application to job #{job_id}." if job_id else f"Queuing application to {count} matching jobs."
            return PilotActionType.APPLY_JOBS, params, summary_txt

        # 12. Job Search
        if any(w in lower for w in ["find", "search", "look for", "discover", "get jobs"]):
            params = {}
            for p in PLATFORMS:
                if p in lower:
                    params["platform"] = p
                    break
            if "remote" in lower:
                params["remote"] = True
            keywords_candidate = re.sub(r"^(please\s+)?(find\s+(out\s+)?|search\s+for\s+|search\s+|look\s+for\s+|discover\s+)", "", text, flags=re.IGNORECASE).strip()
            params["query"] = keywords_candidate
            return PilotActionType.SEARCH_JOBS, params, f"Initiating search: {keywords_candidate}"

        # Default: General Chat / Career Guidance
        return PilotActionType.CHAT, {"text": text}, "Consulting AI Pilot career assistant."
