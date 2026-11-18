"""
JobPilot Platform & UI Knowledge Base.
Single source of truth for UI flows, feature documentation, and operational navigation.
Provides grounded retrieval-augmented generation (RAG) to eliminate AI hallucinations.
"""

import re
from typing import Any, Dict, List, Optional


JOBPILOT_KNOWLEDGE_DOCS: List[Dict[str, Any]] = [
    {
        "id": "daily_apply_limit",
        "title": "Changing Daily Apply Limit & Platform Batch Thresholds",
        "keywords": [
            "daily apply limit", "daily limit", "apply limit", "change limit",
            "application limit", "daily goal", "max applies", "switch number",
            "batch limit", "how to change my daily apply limit", "limit"
        ],
        "summary": "How to change daily application limits and batch goals in JobPilot.",
        "ui_path": [
            "1. Click **Platforms** in the sidebar (or press `Ctrl+4` for Job Search).",
            "2. Locate the platform card (**LinkedIn**, **Naukri**, **Indeed**, **Foundit**, or **Glassdoor**) and click **Configure**.",
            "3. In the Platform Configuration dialog, adjust **Daily Application Goal** (e.g. 30 jobs/day) or **Max Applications per Batch (Switch Number)**.",
            "4. Click **Save Configuration** to update SQLite and platform automation engines.",
            "5. *Direct Chat Shortcut*: You can also simply say: `'set daily limit to 30'` or `'set max applies to 25'`."
        ],
        "chat_commands": ["set daily limit to <number>", "set max applies to <number>"],
        "content": (
            "In JobPilot, the Daily Application Limit can be configured in two places:\n"
            "1. **Platforms View (`Platforms`)**: Click **Configure** on any platform card (LinkedIn, Naukri, Indeed, Foundit, Glassdoor) "
            "to adjust your **Daily Application Goal** (e.g. 30 applications/day) and **Batch Switch Number**.\n"
            "2. **Job Search Strategy (`Ctrl+4`)**: Adjust the global batch limits and cycle automation parameters.\n"
            "3. **Chat Command**: Say `'set daily limit to 30'` directly in this chat to update the limit instantly."
        ),
    },
    {
        "id": "email_outreach",
        "title": "Email Outreach Workspace & Recruiter Campaigns",
        "keywords": [
            "email outreach", "outreach", "cold email", "email feature",
            "what is the email outreach feature", "recruiter email", "email campaign",
            "outreach workspace", "recruiter contact", "send email"
        ],
        "summary": "JobPilot Email Outreach feature for contacting recruiters and hiring managers.",
        "ui_path": [
            "1. Click **Outreach** in the sidebar (or press `Ctrl+6`).",
            "2. Connect your email account (SMTP/IMAP) under Outreach Settings or configure credentials.",
            "3. Add recruiter contacts (email, name, company, target role).",
            "4. Select or customize an email template: First Touch Pitch, Value-Add Follow-Up, or Post-Interview Note.",
            "5. Schedule and launch outreach sequences with automated open tracking and reply detection."
        ],
        "chat_commands": ["status of outreach", "list outreach campaigns"],
        "content": (
            "The **Outreach Workspace** (`Ctrl+6` or sidebar **Outreach**) is JobPilot's automated recruiter direct-messaging suite:\n"
            "• **Recruiter Directory**: Store and organize recruiter and hiring manager contacts per company.\n"
            "• **Campaign Templates**: Pre-built, high-converting cold email and follow-up templates tailored to tech & RPA roles.\n"
            "• **Automated Sequences**: Multi-step follow-ups scheduled at 3-day and 7-day intervals with reply detection.\n"
            "• **Email Account Connection**: Connect your personal email via secure SMTP/IMAP credentials with zero vendor lock-in."
        ),
    },
    {
        "id": "universal_ats_agent",
        "title": "Universal ATS Agent (Greenhouse, Lever, Workday, Ashby)",
        "keywords": [
            "universal agent", "universal ats", "workday", "greenhouse", "lever",
            "ashby", "external job", "portal application", "career site", "company portal"
        ],
        "summary": "Autonomous application agent for corporate career sites and ATS portals.",
        "ui_path": [
            "1. Go to **Jobs** (`Ctrl+3`) and filter by 'Company Portal' or click **Universal Apply** on any listing.",
            "2. Alternatively, paste any corporate job URL (e.g. `https://boards.greenhouse.io/...` or Workday link) directly into the Copilot chat.",
            "3. JobPilot parses the portal structure, maps your verified profile facts and resume, and submits the application automatically."
        ],
        "chat_commands": ["paste any job URL into chat to trigger universal application"],
        "content": (
            "The **Universal ATS Agent** automates applications on company career sites beyond job boards:\n"
            "• Supports: Greenhouse, Lever, Workday, Ashby, BambooHR, and SmartRecruiters.\n"
            "• Auto-detects ATS archetype, renders forms, answers screening questionnaires from your QnA knowledge base, and uploads your active resume.\n"
            "• How to run: Simply paste any external job URL into this chat or click 'Universal Apply' in the Jobs Explorer."
        ),
    },
    {
        "id": "job_search_strategy",
        "title": "Job Search Strategy, Skip Rules & Negative Keywords",
        "keywords": [
            "search strategy", "skip keywords", "negative keywords", "filters",
            "instant skip rules", "bad words", "exclude", "search terms", "job search"
        ],
        "summary": "Configure search terms, location, experience, and instant 0.01s pre-filter skip keywords.",
        "ui_path": [
            "1. Click **Job Search** in the sidebar (or press `Ctrl+4`).",
            "2. Under **Search Strategy**: Set search terms (e.g. 'RPA Developer', 'Python Automation') and target location.",
            "3. Under **Instant Skip Rules**: Add title words to skip in 0.01s (e.g. 'android', 'ios', 'mechanical', 'civil').",
            "4. Under **Description Filters**: Add terms to blacklist after opening job descriptions.",
            "5. Click **Save Configuration** (or toggle 'Apply to All Platforms')."
        ],
        "chat_commands": ["add <word> in skip keyword list", "remove <word> from skip list", "what are skip keywords?"],
        "content": (
            "The **Job Search Strategy** view (`Ctrl+4`) controls discovery and pre-filtering:\n"
            "• **Instant Skip Rules**: Keywords checked against job titles in 0.01s before opening listings to save bandwidth.\n"
            "• **Description Filters**: Terms blacklisted inside job descriptions (e.g. US Citizen Only, Security Clearance).\n"
            "• **Chat Management**: You can add/remove keywords directly by saying `'add unity as skip keyword in list'` or `'what are skip keywords?'`."
        ),
    },
    {
        "id": "platforms_configuration",
        "title": "Platform Credentials & Automated Bot Management",
        "keywords": [
            "platforms", "credentials", "platform settings", "login", "linkedin login",
            "naukri login", "indeed login", "stealth", "headless"
        ],
        "summary": "Configure platform credentials, stealth profiles, and automation engines.",
        "ui_path": [
            "1. Click **Platforms** in the sidebar.",
            "2. Select any platform (LinkedIn, Naukri, Indeed, Foundit, Glassdoor).",
            "3. Click **Configure** to enter your username, password, and apply modes (Easy Apply Only vs All).",
            "4. Toggle platform ON/OFF to enable or disable it from automated runs."
        ],
        "chat_commands": ["check platforms", "run linkedin", "run indeed", "run naukri"],
        "content": (
            "The **Platforms** view is where you manage your job board integrations:\n"
            "• Credentials are encrypted and stored locally via JobPilot's SecretsService.\n"
            "• Supports dedicated Chrome user data directories to preserve active login cookies and session tokens.\n"
            "• Say `'check platforms'` in chat to see real-time credential status across all platforms."
        ),
    },
    {
        "id": "profile_and_qna",
        "title": "Candidate Profile Facts & Screening QnA Knowledge Base",
        "keywords": [
            "profile", "qna", "qna rules", "screening questions", "answers",
            "ctc", "salary", "notice period", "experience", "candidate facts"
        ],
        "summary": "Candidate facts, verified experience, and automated question-and-answer rules.",
        "ui_path": [
            "1. Click **Profile** in the sidebar (or press `Ctrl+0`).",
            "2. **Tab 1 (Personal & Professional Facts)**: Update Current CTC, Expected CTC, Notice Period, Current Employer, and Target Role.",
            "3. **Tab 2 (Screening QnA Rules)**: Review and add answers for common recruiter screener questions (e.g. 'Are you authorized to work?', 'Notice period?')."
        ],
        "chat_commands": ["list qna", "add qna", "about my current ctc", "what is the offer i have"],
        "content": (
            "The **Profile & QnA** view (`Ctrl+0`) powers the AI answering engine:\n"
            "• **Profile Facts**: Verified candidate ground truth (Current Employer: AventIQ AI, Current CTC: ₹3.5 LPA, Expected CTC: ₹5.5 LPA, Notice: 30 days).\n"
            "• **Screening QnA**: Exact rules matching employer questionnaires with zero hallucination."
        ),
    },
    {
        "id": "resumes_management",
        "title": "Resume Library, Skill Parsing & Tailoring",
        "keywords": [
            "resumes", "resume library", "upload resume", "tailor resume",
            "skills from resume", "active resume", "default resume"
        ],
        "summary": "Manage resume versions, extract technical skills, and tailor content for roles.",
        "ui_path": [
            "1. Click **Resumes** in the sidebar.",
            "2. Click **Upload Resume** (PDF/DOCX) to add new versions.",
            "3. Toggle **Set as Default** to choose which resume automated bots submit to employers.",
            "4. Click **Parse Skills** to sync technical competencies directly into your screening profile."
        ],
        "chat_commands": ["list resumes", "extract resume", "what are the key skills from my resume", "design a resume for tech lead"],
        "content": (
            "The **Resumes** view manages candidate application documents:\n"
            "• Supports multi-version resume management with automated skill parsing.\n"
            "• Chat integration: Say `'what are the key skills from my resume'` to view verified competencies, or `'design a resume for Tech Lead'` for tailored bullet points."
        ),
    },
    {
        "id": "applications_pipeline",
        "title": "Applications Pipeline & Status Tracking",
        "keywords": [
            "applications", "pipeline", "track applications", "status", "submitted",
            "under review", "rejected", "interviews", "offers"
        ],
        "summary": "Track application states, review recruiter stages, and view submission audit trails.",
        "ui_path": [
            "1. Click **Applications** in the sidebar (or press `Ctrl+5`).",
            "2. Filter by status: **Submitted**, **Under Review**, **Interviewing**, **Offers**, or **Rejected**.",
            "3. Click **Update** on any row to change status manually, or click **Audit** to inspect the screener questions answered during submission."
        ],
        "chat_commands": ["today apply report", "status of <company>", "did i apply to <company>", "mark all <company> as rejected"],
        "content": (
            "The **Applications Pipeline** (`Ctrl+5`) tracks the entire recruitment lifecycle:\n"
            "• Records all automated and manual submissions with full audit trails.\n"
            "• Chat integration: Say `'did i apply to fugentex'` or `'mark all gamma labs as rejected'` to update states in real time."
        ),
    },
    {
        "id": "automation_cockpit",
        "title": "Automation Cockpit & Live Chrome Execution",
        "keywords": [
            "automation", "bot", "run bot", "cockpit", "live execution",
            "console", "start automation", "stop automation", "pause automation"
        ],
        "summary": "Monitor live browser workers, screening questionnaires, and submission logs in real time.",
        "ui_path": [
            "1. Click **Automation** in the sidebar (or press `Ctrl+2`).",
            "2. Select platform target and click **Start Automation** (or use Copilot chat).",
            "3. Watch real-time metrics (Discovered, Evaluated, Qualified, Applied, Skipped).",
            "4. Pause, Resume, or Stop execution at any time."
        ],
        "chat_commands": ["run linkedin", "run indeed", "pause bot", "resume bot", "stop automation"],
        "content": (
            "The **Automation Cockpit** (`Ctrl+2`) displays live unattended bot execution:\n"
            "• Shows real-time Chrome streaming logs and candidate screening actions.\n"
            "• Prompts human-in-the-loop intervention dialogs if 2FA or CAPTCHAs require user confirmation."
        ),
    },
]


class PlatformKnowledgeBase:
    """Retrieval-Augmented Generation (RAG) engine for JobPilot UI flows and platform capabilities."""

    def __init__(self):
        self.docs = JOBPILOT_KNOWLEDGE_DOCS

    def retrieve(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """Finds most relevant platform documentation chunks using token overlap and keyword matching."""
        if not query or not query.strip():
            return []

        lower_query = query.lower().strip()
        query_tokens = set(re.findall(r"\w+", lower_query))

        scored_docs = []
        for doc in self.docs:
            score = 0
            # Check exact keyword matches
            for kw in doc["keywords"]:
                if kw in lower_query:
                    score += 15
                elif any(token in kw for token in query_tokens):
                    score += 3

            # Check title match
            for token in query_tokens:
                if token in doc["title"].lower():
                    score += 5

            if score > 0:
                scored_docs.append((score, doc))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored_docs[:top_k]]

    def get_grounded_answer(self, query: str) -> Optional[str]:
        """Provides direct, verified answers for exact UI navigation or feature explanation queries."""
        lower_query = query.lower().strip()

        # Check for "how to change daily apply limit" or "daily limit"
        if any(p in lower_query for p in ["daily apply limit", "daily limit", "change daily limit", "change apply limit", "change my daily"]):
            doc = next((d for d in self.docs if d["id"] == "daily_apply_limit"), None)
            if doc:
                return (
                    "### Changing Your Daily Apply Limit in JobPilot\n\n"
                    "You can change your daily application limit in JobPilot through two UI locations or via direct chat:\n\n"
                    "**Method 1: Via Platforms View**\n"
                    "1. Click **Platforms** in the left sidebar.\n"
                    "2. Locate the platform card (**LinkedIn**, **Naukri**, **Indeed**, etc.) and click **Configure**.\n"
                    "3. In the dialog, update the **Daily Application Goal** (e.g. `30` or `50` applications/day) or **Max Applications per Batch**.\n"
                    "4. Click **Save Configuration**.\n\n"
                    "**Method 2: Via Job Search Strategy (`Ctrl+4`)**\n"
                    "• Open **Job Search** and update the batch application thresholds and cycle controls.\n\n"
                    "**Method 3: Direct Copilot Command**\n"
                    "• Simply say: `'set daily limit to 30'` or `'set max applies to 25'` right here in this chat."
                )

        # Check for "what is email outreach"
        if any(p in lower_query for p in ["email outreach", "outreach feature", "what is email outreach", "outreach workspace"]):
            doc = next((d for d in self.docs if d["id"] == "email_outreach"), None)
            if doc:
                return (
                    "### What is the Email Outreach Feature in JobPilot?\n\n"
                    "The **Email Outreach Workspace** (`Ctrl+6` or sidebar **Outreach**) is JobPilot's automated recruiter direct-messaging suite designed to help you land interviews faster through cold email:\n\n"
                    "• **Recruiter Contact Directory**: Organize and manage recruiter and hiring manager emails by target company.\n"
                    "• **Proven Cold Email Templates**: Ready-to-send templates tailored for Tech, Python, and RPA roles (First Touch, Value-Add Follow-Up, and Post-Interview Note).\n"
                    "• **Automated Follow-Up Sequences**: Schedule multi-touch follow-ups at 3-day and 7-day intervals with reply detection.\n"
                    "• **Secure Account Connection**: Connect your personal email using secure SMTP/IMAP credentials with complete privacy and zero third-party data tracking."
                )

        # High-confidence grounded matching across all platform knowledge modules
        scored = []
        query_tokens = set(re.findall(r"\w+", lower_query))
        for doc in self.docs:
            for kw in doc["keywords"]:
                if kw in lower_query:
                    scored.append((len(kw), doc))
                    break
        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            top_doc = scored[0][1]
            is_inquiry = any(q in lower_query for q in [
                "what is", "what are", "how to", "how do", "where is", "where do", "where can",
                "explain", "show me", "tell me about", "guide", "workflow", "feature"
            ]) or any(kw == lower_query for kw in top_doc["keywords"])
            if is_inquiry:
                lines = [f"### {top_doc['title']}\n"]
                lines.append(top_doc["content"] + "\n")
                if top_doc.get("ui_path"):
                    lines.append("**Desktop Navigation Flow:**")
                    lines.extend(top_doc["ui_path"])
                    lines.append("")
                if top_doc.get("chat_commands"):
                    cmds = ", ".join([f"`'{c}'`" for c in top_doc["chat_commands"]])
                    lines.append(f"**Chat Shortcuts:** {cmds}")
                return "\n".join(lines)

        return None
