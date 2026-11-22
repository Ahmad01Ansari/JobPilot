"""Universal Tool and Intent Registry for JobPilot AI Copilot.

Provides a centralized catalog of all executable capabilities across the application.
Supports two-tier resolution:
- Tier 1: Sub-millisecond deterministic offline matching with speech-to-text phonetic normalization.
- Tier 2: Structured JSON function-calling schema generation for LLM-based tool calling.
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.services.pilot.pilot_models import PilotActionType

logger = logging.getLogger("JobPilot.PilotToolRegistry")

WORD_NUMS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}


def parse_spoken_number(s: str) -> Optional[float]:
    """Extracts numeric values from digit strings or spoken English number words."""
    if not s:
        return None
    clean = s.lower().strip()
    clean_digits = re.sub(r"[^\d\.]", "", clean)
    if clean_digits:
        try:
            return float(clean_digits)
        except ValueError:
            pass
    words = clean.split()
    total = 0.0
    found = False
    for w in words:
        if w in WORD_NUMS:
            total += WORD_NUMS[w]
            found = True
    return total if found else None


def parse_compensation_amount(raw: Any) -> Optional[int]:
    """Robustly parses numeric, currency, words, and voice dictation into integer annual salary."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        val = float(raw)
        if val <= 0:
            return None
        if val < 100:  # e.g. 6.5 -> 6.5 LPA = 650000
            return int(val * 100000)
        return int(val)

    s = str(raw).lower().strip()
    s = re.sub(r"^(?:to\s+|is\s+|the\s+|uh\s+|um\s+)+", "", s).strip()
    s = re.sub(r"[₹$,]", "", s).strip()
    if not s:
        return None

    # 1. 'X lakh Y thousand' (e.g. '3 lakh fifty thousand' or '3 lakh 50 thousand')
    m_lakh_thou = re.search(r"([\d\.]+|[a-z\s]+?)\s*(?:lakhs?|lac|lpa)\s*(?:and\s+)?([\d\.]+|[a-z\s]+?)\s*(?:thousand|grand|k)", s)
    if m_lakh_thou:
        l_val = parse_spoken_number(m_lakh_thou.group(1)) or 0
        t_val = parse_spoken_number(m_lakh_thou.group(2)) or 0
        res = int(l_val * 100000 + t_val * 1000)
        return res if res > 0 else None

    # 2. 'X lakh' / 'X lpa'
    m_lakh = re.search(r"([\d\.]+|[a-z\s]+?)\s*(?:lakhs?|lac|lpa)", s)
    if m_lakh:
        val = parse_spoken_number(m_lakh.group(1))
        if val is not None and val > 0:
            return int(val * 100000)

    # 3. 'X thousand' / 'X k'
    m_k = re.search(r"([\d\.]+|[a-z\s]+?)\s*(?:thousand|grand|k)", s)
    if m_k:
        val = parse_spoken_number(m_k.group(1))
        if val is not None and val > 0:
            return int(val * 1000)

    # 4. Raw digits or words
    val = parse_spoken_number(s)
    if val is not None and val > 0:
        if val < 100:
            return int(val * 100000)
        return int(val)

    return None


def normalize_speech_input(text: str) -> str:
    """Normalizes common speech-to-text slips, phonetic typos, and voice artifacts.

    Handles company names, platforms, compensation formats, and conversational fillers.
    Preserves URLs intact to prevent case mutation.
    """
    if not text:
        return ""

    # Protect URLs so URLs are not mutated by phonetic replacements
    urls = re.findall(r"https?://\S+", text)
    placeholders = {}
    clean = text.strip()
    for i, u in enumerate(urls):
        key = f"__JOBPILOT_URL_PLACEHOLDER_{i}__"
        placeholders[key] = u
        clean = clean.replace(u, key)

    # 1. Phonetic platform and entity replacements
    phonetic_map = [
        (r"\ba\s*vent\s*i\s*q(?:\s*a\s*i)?\b", "AventIQ AI"),
        (r"\bevent\s*iq(?:\s*ai)?\b", "AventIQ AI"),
        (r"\bnow\s*cry\b", "Naukri"),
        (r"\bnokri\b", "Naukri"),
        (r"\bnaukari\b", "Naukri"),
        (r"\blinked\s*in\b", "LinkedIn"),
        (r"\blincon\b", "LinkedIn"),
        (r"\bin\s*deed\b", "Indeed"),
        (r"\bglass\s*door\b", "Glassdoor"),
        (r"\bfound\s*it\b", "Foundit"),
        (r"\bsap\s*success\s*factors\b", "SuccessFactors"),
        (r"\bsuccess\s*factors\b", "SuccessFactors"),
        (r"\bwork\s*day\b", "Workday"),
    ]
    for pattern, repl in phonetic_map:
        clean = re.sub(pattern, repl, clean, flags=re.IGNORECASE)

    # 2. Conversational prefix stripping for cleaner intent matching
    clean = re.sub(
        r"^(?:please\s+|can\s+you\s+(?:please\s+)?|could\s+you\s+(?:please\s+)?|hey\s+(?:bot|pilot|jobpilot)\s+|i\s+want\s+you\s+to\s+|i\s+need\s+you\s+to\s+)",
        "",
        clean,
        flags=re.IGNORECASE,
    ).strip()

    # Restore preserved URLs
    for key, u in placeholders.items():
        clean = clean.replace(key, u)

    return clean

    return clean


@dataclass
class PilotTool:
    """Specification of an autonomous capability exposed to the AI Copilot."""

    name: str
    action_type: PilotActionType
    domain: str
    description: str
    parameters_schema: Dict[str, Any] = field(default_factory=dict)
    fast_patterns: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    _compiled_patterns: List[re.Pattern] = field(init=False, repr=False, default_factory=list)

    def __post_init__(self):
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.fast_patterns
        ]

    def matches(self, text: str) -> Optional[re.Match]:
        """Tests if the input text matches any registered fast pattern."""
        for pattern in self._compiled_patterns:
            m = pattern.search(text)
            if m:
                return m
        return None


class PilotToolRegistry:
    """Central registry of all executable tools across JobPilot domains."""

    _instance: Optional["PilotToolRegistry"] = None

    def __init__(self):
        self._tools: Dict[str, PilotTool] = {}
        self._register_default_tools()

    @classmethod
    def get_instance(cls) -> "PilotToolRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, tool: PilotTool) -> None:
        """Registers a tool in the catalog."""
        self._tools[tool.name] = tool
        logger.debug("Registered PilotTool: %s (%s)", tool.name, tool.domain)

    def get_tool(self, name: str) -> Optional[PilotTool]:
        return self._tools.get(name)

    def list_tools(self, domain: Optional[str] = None) -> List[PilotTool]:
        if domain:
            return [t for t in self._tools.values() if t.domain == domain]
        return list(self._tools.values())

    def match_fast_path(self, text: str) -> Optional[Tuple[PilotTool, Dict[str, Any], str]]:
        """Tier 1: Evaluates registered fast patterns with zero cloud token consumption."""
        normalized = normalize_speech_input(text)
        lower = normalized.lower().strip()

        for tool in self._tools.values():
            match = tool.matches(lower)
            if match:
                params = match.groupdict() if match.groupdict() else {}
                summary = f"Fast-path matched {tool.name}"
                return tool, params, summary
        return None

    def get_llm_tools_schema(self) -> List[Dict[str, Any]]:
        """Generates the OpenAPI/OpenAI-compatible function definitions for LLM tool calling."""
        tools_schema = []
        for tool in self._tools.values():
            tools_schema.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema or {
                        "type": "object",
                        "properties": {},
                    },
                },
            })
        return tools_schema

    def _register_default_tools(self) -> None:
        """Populates the canonical suite of tools covering all 12 JobPilot domains."""

        # -------------------------------------------------------------
        # DOMAIN 1: PROFILE & PROFESSIONAL IDENTITY
        # -------------------------------------------------------------
        self.register(PilotTool(
            name="profile.autofill_from_resume",
            action_type=PilotActionType.UPDATE_PROFILE,
            domain="profile",
            description="Extracts candidate identity, bio, summary, cover letter, skills, work experience history, and education from resume and saves to profile.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["autofill_from_resume"]},
                },
            },
            fast_patterns=[
                r"(?:complete|setup|fill|autofill|populate)\s+(?:my\s+)?profile",
                r"sync\s+(?:my\s+)?resume\s+to\s+profile",
                r"write\s+(?:a\s+)?(?:bio|cover\s+letter)\s+(?:and\s+complete|from\s+resume)",
            ],
        ))

        self.register(PilotTool(
            name="profile.update_work_experience",
            action_type=PilotActionType.UPDATE_PROFILE,
            domain="profile",
            description="Parses or updates candidate work experience, company, title, roles, responsibilities, enterprise projects, and tenure/joining date.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["update_work_experience"]},
                    "joining_date": {"type": "string"},
                    "company": {"type": "string"},
                    "title": {"type": "string"},
                },
            },
            fast_patterns=[
                r"(?:update|add|fill|summarize)\s+(?:my\s+)?(?:work\s+)?experience",
                r"(?:role\s+and\s+responsibilit|projects?).*(?:work\s+experience|profile)",
                r"(?:set|update|change)\s+(?:my\s+)?(?:joining|start|employment)\s+date",
            ],
        ))

        self.register(PilotTool(
            name="profile.update_education",
            action_type=PilotActionType.UPDATE_PROFILE,
            domain="profile",
            description="Parses or updates candidate academic history, university, college, degree, field of study, and graduation year.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["update_education"]},
                    "institution": {"type": "string"},
                    "degree": {"type": "string"},
                },
            },
            fast_patterns=[
                r"(?:update|add|fill)\s+(?:my\s+)?(?:education|academic\s+background|degrees?|university|college)",
                r"education\s+background",
            ],
        ))

        self.register(PilotTool(
            name="profile.update_field",
            action_type=PilotActionType.UPDATE_PROFILE,
            domain="profile",
            description="Updates a single profile field such as current CTC, expected CTC, notice period, location, phone, or web links.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": [
                        "current_ctc", "expected_ctc", "notice_period_days",
                        "linkedin_url", "github_url", "portfolio_url",
                        "location", "phone", "email", "headline", "summary",
                    ]},
                    "value": {"type": "string"},
                },
                "required": ["field", "value"],
            },
            fast_patterns=[
                r"(?:set|update|change)\s+(?:my\s+)?(?:current\s+ctc|current\s+salary)\s+(?:to\s+)?(?P<value>[\w\s\.,₹$]+)",
                r"(?:set|update|change)\s+(?:my\s+)?(?:expected\s+ctc|expected\s+salary)\s+(?:to\s+)?(?P<value>[\w\s\.,₹$]+)",
                r"(?:set|update|change)\s+(?:my\s+)?notice\s+period\s+(?:to\s+)?(?P<value>[\w\s]+)",
                r"(?:set|update|change)\s+(?:my\s+)?(?:linkedin|github|portfolio)(?:\s+url|\s+link)?\s+(?:to\s+)?(?P<value>https?://\S+)",
            ],
        ))

        # -------------------------------------------------------------
        # DOMAIN 2: RESUMES & TAILORING
        # -------------------------------------------------------------
        self.register(PilotTool(
            name="resume.list",
            action_type=PilotActionType.LIST_RESUMES,
            domain="resumes",
            description="Lists all uploaded resumes, active versions, and lineage history in the resume repository.",
            fast_patterns=[
                r"^list\s+resumes?",
                r"^show\s+(?:my\s+)?resumes?",
                r"what\s+resumes?\s+do\s+i\s+have",
            ],
        ))

        self.register(PilotTool(
            name="resume.get_skills",
            action_type=PilotActionType.GET_RESUME_SKILLS,
            domain="resumes",
            description="Extracts and enumerates technical skills, frameworks, and competencies identified in the active resume.",
            fast_patterns=[
                r"(?:what\s+are\s+the\s+)?(?:key\s+)?skills?\s+(?:from|on|in)\s+(?:my\s+)?(?:resume|cv)",
                r"extract\s+skills?\s+from\s+(?:my\s+)?(?:resume|cv)",
            ],
        ))

        self.register(PilotTool(
            name="resume.tailor",
            action_type=PilotActionType.TAILOR_RESUME,
            domain="resumes",
            description="Generates a tailored resume variant or customized bullet points targeted at a specific job title or job description.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                },
                "required": ["target"],
            },
            fast_patterns=[
                r"(?:tailor|design|adapt|optimize)\s+(?:my\s+)?(?:resume|cv)\s+for\s+(?P<target>.+)",
            ],
        ))

        # -------------------------------------------------------------
        # DOMAIN 3: JOB DISCOVERY & SEARCH
        # -------------------------------------------------------------
        self.register(PilotTool(
            name="jobs.search",
            action_type=PilotActionType.SEARCH_JOBS,
            domain="jobs",
            description="Searches indexed job opportunities by keyword, role, location, platform, or remote status.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "platform": {"type": "string"},
                    "remote": {"type": "boolean"},
                },
                "required": ["query"],
            },
            fast_patterns=[
                r"^(?:search|find)\s+(?:for\s+)?(?P<query>.+?)\s+jobs?",
            ],
        ))

        self.register(PilotTool(
            name="jobs.get_top",
            action_type=PilotActionType.GET_TOP_JOBS,
            domain="jobs",
            description="Retrieves the highest-ranked qualified job opportunities meeting minimum match score thresholds.",
            fast_patterns=[
                r"(?:show|list|get)\s+(?:top|eligible|best)\s+(?:jobs?|opportunities)",
            ],
        ))

        self.register(PilotTool(
            name="jobs.apply",
            action_type=PilotActionType.APPLY_JOBS,
            domain="jobs",
            description="Initiates application submission for a specific job ID, job URL, or batch of jobs on a platform.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "integer"},
                    "url": {"type": "string"},
                    "count": {"type": "integer"},
                    "platform": {"type": "string"},
                },
            },
            fast_patterns=[
                r"^apply\s+to\s+#?(?P<job_id>\d+)",
                r"^apply\s+to\s+(?P<url>https?://\S+)",
                r"^apply\s+to\s+(?P<count>\d+)\s+jobs(?:\s+on\s+(?P<platform>\w+))?",
                r"^start\s+applying",
            ],
        ))

        # -------------------------------------------------------------
        # DOMAIN 4: APPLICATIONS TRACKING & PIPELINE
        # -------------------------------------------------------------
        self.register(PilotTool(
            name="applications.query_status",
            action_type=PilotActionType.QUERY_APPLICATION_STATUS,
            domain="applications",
            description="Checks whether an application was submitted to a company or role, returning current status, review stage, and timeline.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "role": {"type": "string"},
                },
                "required": ["company"],
            },
            fast_patterns=[
                r"(?:did\s+i|have\s+i|did\s+we)\s+apply(?:\s+for\s+(?P<role>[^?]+?))?\s+(?:to|at)\s+(?P<company>[^?]+)",
                r"status\s+of\s+(?:my\s+application\s+at\s+)?(?P<company>[^?]+)",
            ],
        ))

        self.register(PilotTool(
            name="applications.get_report",
            action_type=PilotActionType.GET_APPLICATIONS_REPORT,
            domain="applications",
            description="Generates an executive KPI summary of applications submitted today, this week, or total pipeline volume.",
            fast_patterns=[
                r"today\s+apply\s+report",
                r"what\s+did\s+we\s+apply\s+today",
                r"(?:how\s+many|show)\s+applications?\s+(?:sent|submitted|total)",
            ],
        ))

        self.register(PilotTool(
            name="applications.update_status",
            action_type=PilotActionType.UPDATE_APPLICATION_STATUS,
            domain="applications",
            description="Updates the lifecycle stage of an application (e.g. SUBMITTED, UNDER_REVIEW, INTERVIEW, OFFER, REJECTED).",
            parameters_schema={
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "status": {"type": "string"},
                    "update_all": {"type": "boolean"},
                },
                "required": ["company", "status"],
            },
            fast_patterns=[
                r"(?:mark|update)\s+(?P<company>.+?)\s+(?:as|to)\s+(?P<status>rejected|under\s+review|interview|offer|submitted|shortlisted)",
            ],
        ))

        self.register(PilotTool(
            name="applications.delete",
            action_type=PilotActionType.DELETE_APPLICATION,
            domain="applications",
            description="Deletes or archives an application record from the tracking pipeline.",
            requires_confirmation=True,
            parameters_schema={
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "job_id": {"type": "integer"},
                },
            },
            fast_patterns=[
                r"delete\s+application(?:\s+(?:for|to|at)\s+(?P<company>.+))?",
            ],
        ))

        # -------------------------------------------------------------
        # DOMAIN 5: AUTOMATION CONTROLS & RUNNERS
        # -------------------------------------------------------------
        self.register(PilotTool(
            name="automation.start",
            action_type=PilotActionType.START_AUTOMATION,
            domain="automation",
            description="Launches unattended browser automation for a target platform (LinkedIn, Naukri, Indeed, Foundit, Glassdoor, Universal ATS).",
            parameters_schema={
                "type": "object",
                "properties": {
                    "platform": {"type": "string"},
                    "count": {"type": "integer"},
                },
            },
            fast_patterns=[
                r"^run\s+(?P<platform>all|linkedin|naukri|indeed|foundit|glassdoor|universal)(?:\s+bot|\s+automation)?",
                r"^start\s+(?P<platform>all|linkedin|naukri|indeed|foundit|glassdoor|universal)(?:\s+bot|\s+automation)?",
                r"^launch\s+(?P<platform>all|linkedin|naukri|indeed|foundit|glassdoor|universal)",
            ],
        ))

        self.register(PilotTool(
            name="automation.stop",
            action_type=PilotActionType.STOP_AUTOMATION,
            domain="automation",
            description="Immediately requests cooperative graceful termination of any active background automation worker.",
            fast_patterns=[
                r"^stop(?:\s+bot|\s+automation)?$",
                r"^halt(?:\s+automation)?$",
            ],
        ))

        self.register(PilotTool(
            name="automation.pause",
            action_type=PilotActionType.PAUSE_AUTOMATION,
            domain="automation",
            description="Pauses the active automation loop without closing the browser session.",
            fast_patterns=[
                r"^pause(?:\s+bot|\s+automation)?$",
            ],
        ))

        self.register(PilotTool(
            name="automation.resume",
            action_type=PilotActionType.RESUME_AUTOMATION,
            domain="automation",
            description="Resumes a paused automation run.",
            fast_patterns=[
                r"^resume(?:\s+bot|\s+automation)?$",
                r"^continue(?:\s+automation)?$",
            ],
        ))

        self.register(PilotTool(
            name="automation.answer_intervention",
            action_type=PilotActionType.ANSWER_INTERVENTION,
            domain="automation",
            description="Provides an OTP, 2FA security code, or human-in-the-loop review confirmation to an awaiting runner.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                },
                "required": ["answer"],
            },
            fast_patterns=[
                r"(?:otp|code|2fa|verification)\s+(?:is\s+)?(?P<answer>\d{4,8})",
            ],
        ))

        # -------------------------------------------------------------
        # DOMAIN 6: RULES, DEAL-BREAKERS & EXCLUSIONS
        # -------------------------------------------------------------
        self.register(PilotTool(
            name="rules.get",
            action_type=PilotActionType.GET_RULES,
            domain="rules",
            description="Displays active negative keyword exclusions, skip titles, deal-breakers, and minimum match score limits.",
            fast_patterns=[
                r"(?:what\s+are|show|list)\s+(?:the\s+)?(?:skip\s+keywords?|rules?|deal\s*breakers?)",
            ],
        ))

        self.register(PilotTool(
            name="rules.update",
            action_type=PilotActionType.UPDATE_RULES,
            domain="rules",
            description="Adds or removes skip keywords, deal-breakers, or modifies minimum match score and daily limits.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["add_deal_breaker", "remove_deal_breaker", "set_min_score", "set_daily_limit"]},
                    "deal_breaker": {"type": "string"},
                    "min_score": {"type": "integer"},
                    "daily_limit": {"type": "integer"},
                },
                "required": ["type"],
            },
            fast_patterns=[
                r"add\s+(?P<deal_breaker>.+?)\s+(?:as|to|in)\s+skip\s+keywords?",
                r"skip\s+jobs\s+with\s+(?P<deal_breaker>.+)",
                r"remove\s+(?P<deal_breaker>.+?)\s+from\s+skip\s+keywords?",
                r"unskip\s+(?P<deal_breaker>.+)",
                r"set\s+min(?:imum)?\s+score\s+(?:to\s+)?(?P<min_score>\d+)",
            ],
        ))

        # -------------------------------------------------------------
        # DOMAIN 7: SCREENING QNA KNOWLEDGE BASE
        # -------------------------------------------------------------
        self.register(PilotTool(
            name="qna.list",
            action_type=PilotActionType.LIST_QNA,
            domain="qna",
            description="Lists configured screening questionnaire answering rules and fallback values.",
            fast_patterns=[
                r"^list\s+qna",
                r"show\s+(?:my\s+)?screening\s+(?:questions?|rules?)",
            ],
        ))

        self.register(PilotTool(
            name="qna.add",
            action_type=PilotActionType.ADD_QNA,
            domain="qna",
            description="Adds a new automated screening question and answer rule to the persistent catalog.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "answer"],
            },
            fast_patterns=[
                r"add\s+qna(?:\s+question)?\s*[:\-]\s*(?P<question>.+?)\s+answer\s*[:\-]\s*(?P<answer>.+)",
            ],
        ))

        self.register(PilotTool(
            name="qna.test",
            action_type=PilotActionType.TEST_QNA,
            domain="qna",
            description="Simulates screening QnA matching against a hypothetical question to preview how JobPilot will answer.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                },
                "required": ["question"],
            },
            fast_patterns=[
                r"test\s+qna\s+(?:for\s+)?(?P<question>.+)",
            ],
        ))

        # -------------------------------------------------------------
        # DOMAIN 8: INTERVIEWS & CALENDAR
        # -------------------------------------------------------------
        self.register(PilotTool(
            name="interviews.get_report",
            action_type=PilotActionType.GET_INTERVIEWS_REPORT,
            domain="interviews",
            description="Summarizes upcoming and completed recruiter interviews, technical rounds, and calendar schedules.",
            fast_patterns=[
                r"(?:show|list|get)\s+(?:my\s+)?(?:upcoming\s+)?interviews?",
                r"do\s+i\s+have\s+any\s+interviews?",
            ],
        ))

        self.register(PilotTool(
            name="offers.get",
            action_type=PilotActionType.GET_OFFERS,
            domain="offers",
            description="Summarizes job offers received, compensation packages, and candidate CTC facts.",
            fast_patterns=[
                r"what\s+(?:are\s+the\s+)?offers?\s+(?:do\s+)?i\s+have",
                r"show\s+(?:my\s+)?offers?",
            ],
        ))

        # -------------------------------------------------------------
        # DOMAIN 9: PLATFORMS & CREDENTIALS
        # -------------------------------------------------------------
        self.register(PilotTool(
            name="platforms.check",
            action_type=PilotActionType.CHECK_PLATFORMS,
            domain="platforms",
            description="Audits authentication and session readiness for LinkedIn, Naukri, Indeed, Foundit, and Universal ATS.",
            fast_patterns=[
                r"check\s+platforms?",
                r"are\s+(?:my\s+)?platforms?\s+connected",
                r"verify\s+(?:my\s+)?credentials?",
            ],
        ))

        # -------------------------------------------------------------
        # DOMAIN 10: SYSTEM HEALTH, TELEMETRY & DIAGNOSTICS
        # -------------------------------------------------------------
        self.register(PilotTool(
            name="system.get_status",
            action_type=PilotActionType.GET_STATUS,
            domain="system",
            description="Returns system operational status, active thread metrics, database health, and worker states.",
            fast_patterns=[
                r"^system\s+status$",
                r"^status$",
                r"how\s+is\s+the\s+bot\s+doing",
            ],
        ))

        # -------------------------------------------------------------
        # DOMAIN 11: RECRUITER OUTREACH & EMAIL APPLICATIONS
        # -------------------------------------------------------------
        self.register(PilotTool(
            name="outreach.send_email_application",
            action_type=PilotActionType.SEND_EMAIL_APPLICATION,
            domain="outreach",
            description="Sends an email job application or cold outreach email to a recruiter email address with resume attachment and creates an application record.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "recipient_email": {"type": "string"},
                    "role": {"type": "string"},
                    "company": {"type": "string"},
                    "body_text": {"type": "string"},
                    "subject": {"type": "string"},
                },
                "required": ["recipient_email"],
            },
            fast_patterns=[
                r"(?:send|dispatch|draft|write)\s+(?:an?\s+)?(?:email|mail|application\s+email|email\s+application).*?(?:to\s+)?(?P<recipient_email>[\w\.\-_]+@[\w\.\-_]+\.[a-zA-Z]{2,})",
                r"(?:email|mail)\s+(?:application|inquiry).*?(?P<recipient_email>[\w\.\-_]+@[\w\.\-_]+\.[a-zA-Z]{2,})",
            ],
        ))


_GLOBAL_REGISTRY: Optional[PilotToolRegistry] = None


def get_tool_registry() -> PilotToolRegistry:
    """Returns the process-wide tool registry instance."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = PilotToolRegistry.get_instance()
    return _GLOBAL_REGISTRY
