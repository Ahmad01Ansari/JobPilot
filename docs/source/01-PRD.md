# Product Requirements Document (PRD)
## JobPilot — Autonomous Career Navigation & Multi-Platform Application Cockpit

**Document Version:** 1.0.0  
**Status:** Approved / Active Production Specification  
**Author:** Product Management & Software Architecture Team  
**Date:** November 2026  
**Target Release:** v0.1.0-beta.2  

---

## 1. Executive Summary

JobPilot is an intelligent, client-side autonomous job application cockpit designed to eliminate the repetitive friction and cognitive fatigue of modern job searching. Operating as a native cross-platform desktop application powered by PySide6 (Qt) and Python 3.11, JobPilot automates the entire lifecycle of finding, qualifying, and applying to high-match opportunities across major job portals (**LinkedIn Easy Apply**, **Naukri.com**, **Indeed**, **Glassdoor**, and **Foundit**) as well as modern enterprise Applicant Tracking Systems (**Greenhouse**, **Lever**, **Workday**, and **Ashby**).

Unlike speculative or predatory web scraping tools, JobPilot operates with strict architectural and ethical guardrails: it features a 5-tier deterministic Question & Answer reasoning engine that tracks the exact provenance of every candidate response, strictly adheres to anti-evasion standards (never attempting automated CAPTCHA bypass or stealth fingerprint spoofing), and fail-closes into safe human-in-the-loop checkpoints whenever sensitive verification or unfamiliar fields are encountered.

---

## 2. Product Vision & Strategic Objectives

### 2.1 Product Vision
To empower ambitious professionals with an intelligent, reliable, and completely private career copilot that works autonomously in the background—accurately discovering tailored job openings, formulating truthful responses from verified candidate facts, and submitting hundreds of tailored applications with zero hallucination.

### 2.2 Core Strategic Objectives
1. **Application Velocity:** Enable candidates to scale their verified job application throughput from 5–10 manual applications per day to 50–100+ highly targeted, error-free submissions daily.
2. **Zero Hallucination Guarantee:** Enforce that every submitted profile field, compensation figure, notice period, and screening answer originates from verified candidate records (`PROFILE_FACT`, `RESUME_FACT`, or explicit `QNA_RULE`), never fabricating qualifications.
3. **Multi-Ecosystem Coverage:** Provide a single unified control cockpit managing submissions across traditional portals (LinkedIn, Naukri, Indeed) and direct employer ATS platforms (Greenhouse, Lever, Workday).
4. **Data Sovereignty & Privacy:** Maintain all candidate resumes, credentials, job history, and secrets locally on the candidate's machine in an encrypted SQLite vault (`SecretsService`), eliminating third-party cloud data leaks.
5. **Fail-Closed Human Safety:** Implement cooperative checkpoints that pause execution and invite human review whenever OTPs, CAPTCHAs, or subjective essay prompts arise.

---

## 3. Problem Statement & Market Opportunity

### 3.1 The Candidate Dilemma
* **High Friction & Redundancy:** The average job search requires filling out 150–300 applications to secure competitive offers. Candidates waste 15–30 minutes per application re-typing identical work histories, education details, and boilerplate screening responses.
* **Portal Fragmentation:** Candidates must independently manage separate logins, search queries, and application histories across LinkedIn, Naukri, Indeed, and bespoke corporate career pages.
* **Opaque Tracking:** Manual spreadsheet tracking leads to lost follow-up opportunities, duplicate applications, and missed recruiter communications.
* **The "AI Slop" Trap:** Uncontrolled browser extensions and naive LLM wrappers frequently hallucinate degrees, guess salaries, or attempt stealth evasion techniques that risk permanent candidate blacklisting.

### 3.2 The JobPilot Solution
JobPilot solves this by offering a native, enterprise-grade desktop cockpit that unifies search, resume versioning, deterministic Q&A resolution, and browser automation into a cohesive, auditable desktop workflow.

---

## 4. Target Users & User Personas

### Persona A: The High-Velocity Tech Professional (Arjun, Senior RPA & Python Engineer)
* **Demographics:** 4–8 years experience, actively seeking competitive senior engineering roles.
* **Pain Points:** Spends 2 hours every evening applying on Naukri and LinkedIn; repeatedly calculates CTC conversions and types notice period constraints.
* **Goals:** Automate repetitive submissions with 100% factual accuracy; monitor submission status in a unified local dashboard.
* **Primary Features Used:** Automation Console, Q&A Knowledge Base, Jobs Repository, System Tray Observability.

### Persona B: The Career Transitioner (Sarah, Mid-Level Product Analyst)
* **Demographics:** 2–4 years experience, transitioning across sectors, applying to diverse roles.
* **Pain Points:** Needs to tailor resumes per domain; struggles to track application stages and recruiter follow-ups.
* **Goals:** Match specific resume versions to job titles; track interview rounds and scheduled follow-ups.
* **Primary Features Used:** Resume Vault (Version Manager), Interviews View, Follow-ups Engine, Analytics.

---

## 5. User Stories

### Epic 1: Candidate Profiling & Resume Vault
* **US-101 (Profile Management):** *As a candidate*, I want to enter my comprehensive personal, professional, compensation, and work authorization facts once, *so that* JobPilot can reuse them across all portal submissions.
* **US-102 (Multi-Resume Targeting):** *As a candidate*, I want to upload multiple versions of my PDF resume and designate domain-specific defaults, *so that* backend engineering jobs receive my technical CV while data roles receive my analytics CV.
* **US-103 (Resume Parsing):** *As a candidate*, I want the system to parse my uploaded PDF and extract skills, education, and past companies automatically, *so that* I don't have to populate profile tables manually.

### Epic 2: Autonomous Multi-Platform Execution
* **US-201 (Multi-Portal Automation):** *As a candidate*, I want to launch automated application runs across LinkedIn, Naukri, Indeed, Glassdoor, and Foundit from a single desktop dashboard, *so that* I don't have to manually navigate multiple websites.
* **US-202 (Universal ATS Integration):** *As a candidate*, I want JobPilot to parse and complete direct company job applications on Greenhouse, Lever, Workday, and Ashby, *so that* I can apply directly to corporate careers pages.
* **US-203 (Cooperative Pause & Resume):** *As a candidate*, I want the automation engine to pause safely and alert me when an OTP, CAPTCHA, or verification challenge appears, *so that* I can complete it manually without crashing the bot.

### Epic 3: Deterministic Q&A & Answer Provenance
* **US-301 (Screening Question Resolution):** *As a candidate*, I want JobPilot to answer common recruiter screening questions (experience years, notice period, salary expectations, authorization) using verified facts, *so that* my answers are always consistent and accurate.
* **US-302 (Answer Provenance Audit):** *As a candidate*, I want to see the exact source (`profile`, `resume`, `rule`, `calculation`, or `llm`) of every answered question, *so that* I have complete visibility into what was submitted on my behalf.
* **US-303 (Pre-Submission Validation):** *As a candidate*, I want the system to validate generated answers against hard physical bounds (e.g., notice period between 0 and 180 days), *so that* malformed or hallucinated responses are never sent.

### Epic 4: Observability, Audit & Analytics
* **US-401 (Submission History & Audit Trail):** *As a candidate*, I want to review every submitted application along with a full audit log and submission screenshot, *so that* I have proof of application.
* **US-402 (Application Velocity & Analytics):** *As a candidate*, I want to see my weekly application counts, platform breakdown, and conversion rates, *so that* I can optimize my search strategy.
* **US-403 (Recruiter Outreach & Follow-ups):** *As a candidate*, I want to generate tailored cold outreach messages and track post-submission follow-ups, *so that* I maintain momentum throughout the interview pipeline.

---

## 6. Functional Requirements (FR)

| ID | Requirement Title | Detailed Specification | Source Mapping |
| :--- | :--- | :--- | :--- |
| **FR-01** | **Candidate Profile Storage** | Maintain structured candidate facts across 4 domains: Personal, Professional, Education, and Compensation/Notice. Synchronize with local storage. | [`app/ui/views/profile_view.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/ui/views/profile_view.py), [`app/db/models/user.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/db/models/user.py) |
| **FR-02** | **Resume Management & Parsing** | Support PDF upload, SHA-256 deduplication, automatic text extraction via PyPDF2/pdfplumber, and active default targeting. | [`app/services/resume_service.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/services/resume_service.py), [`app/services/resume_parser.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/services/resume_parser.py) |
| **FR-03** | **Job Ingestion & Fingerprinting** | Ingest job postings from portal search results. Compute a deterministic SHA-256 fingerprint (`company|title|platform|url`) to prevent duplicates. | [`app/db/models/job.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/db/models/job.py), [`app/services/job_service.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/services/job_service.py) |
| **FR-04** | **Candidate-Job Qualification** | Score candidate compatibility (0–100) using title matching, keyword extraction, and experience bounds. Assign discrete decisions (`STRONG_MATCH`, `REJECTED`). | [`app/services/job_qualification_service.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/services/job_qualification_service.py), [`modules/qualification_engine.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/modules/qualification_engine.py) |
| **FR-05** | **Multi-Platform Automation Router** | Route execution requests to dedicated platform drivers (LinkedIn, Naukri, Indeed, Glassdoor, Foundit, Universal ATS) through a unified interface. | [`platforms/router.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/platforms/router.py), [`platforms/base_platform.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/platforms/base_platform.py) |
| **FR-06** | **Universal ATS State Machine** | Execute complex multi-page corporate applications through a 12-state deterministic FSM (`NAVIGATING` to `VERIFYING`). Support Greenhouse, Lever, Workday, Ashby. | [`app/services/automation/universal_agent/`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/services/automation/universal_agent/) |
| **FR-07** | **Multi-Tier Q&A Engine** | Resolve form questions using a 5-tier fallback: 1. Profile Fact, 2. Resume Fact, 3. Q&A Canonical Rule, 4. Math Calculation, 5. LLM Fallback. | [`modules/qna_engine.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/modules/qna_engine.py), [`app/services/qna_service.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/services/qna_service.py) |
| **FR-08** | **Answer Constraint Validation** | Intercept generated answers before DOM input. Validate notice period (0–180 days), non-negative compensation, and valid email/phone formats. | [`modules/qna_engine.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/modules/qna_engine.py#L40-L90) |
| **FR-09** | **Encrypted Credential Vault** | Encrypt platform passwords and AI API keys using Fernet symmetric encryption with 0o600 file permissions. | [`app/services/secrets_service.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/services/secrets_service.py) |
| **FR-10** | **Submission Audit & Screenshot** | Capture full-page audit screenshots and SHA-256 hashes upon successful application completion; record exact submission timestamp. | [`modules/tracker.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/modules/tracker.py), [`app/db/models/application.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/db/models/application.py) |
| **FR-11** | **Interview & Pipeline Tracker** | Track multi-round interview stages (HR, Technical, Managerial, Final), dates, meeting links, status, and candidate feedback notes. | [`app/ui/views/interviews_view.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/ui/views/interviews_view.py), [`app/db/models/interview.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/db/models/interview.py) |
| **FR-12** | **Recruiter Outreach Center** | Manage recruiter directory, generate customized cold messages using LLM templates, and log communication timestamps. | [`app/ui/views/outreach/`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/ui/views/outreach/), [`app/services/outreach_service.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/services/outreach_service.py) |
| **FR-13** | **Direct Email Outreach & Gmail 2-Way Sync** | Direct SMTP cold outreach, IMAP 2-way reply synchronization, Gmail sync label isolation, template CRUD with variable interpolation, and automated multi-touch follow-up scheduling. | [`app/ui/views/email_platform_dialog.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/ui/views/email_platform_dialog.py), [`app/services/inbound_sync_service.py`](file:///home/ahmad10raza/Documents/Mastering/JobPilot/app/services/inbound_sync_service.py) |

---

## 7. Non-Functional Requirements (NFR)

### 7.1 Performance & Responsiveness
* **NFR-P1 (UI Thread Isolation):** The PySide6 main Qt thread must never execute blocking network requests, browser automation, database transactions, or sleep statements. All heavy workloads must run in worker threads (`QThread` / `TaskRunner`).
* **NFR-P2 (Startup Latency):** Cold application startup to interactive GUI state must complete within 2.5 seconds on standard desktop hardware.
* **NFR-P3 (Memory Bounds):** Memory consumption must remain below 450 MB during idle state and below 900 MB during active dual-browser automation runs. In-memory log streams must use bounded ring buffers (`deque(maxlen=1000)`).

### 7.2 Reliability & Concurrency
* **NFR-R1 (SQLite Concurrency):** All database transactions must operate in WAL mode (`PRAGMA journal_mode = WAL;`) with a 30,000ms busy timeout to prevent `database is locked` deadlocks.
* **NFR-R2 (Graceful Lifecycle):** Child processes (Chrome, ChromeDriver) must be cooperatively tracked and cleanly terminated on application exit via `ProcessManager.safe_terminate_process` without leaving orphaned background processes.

### 7.3 Security & Secret Hygiene
* **NFR-S1 (Zero Plaintext Secrets):** API keys (OpenAI, Groq, DeepSeek, Gemini) and portal passwords must never be stored in plain text or emitted to logs.
* **NFR-S2 (Automated Log Sanitization):** All system stdout, stderr, and exported diagnostic bundles must pass through `LogSanitizer` to redact Bearer tokens, cookies, passwords, and candidate PII.
* **NFR-S3 (Ethical Bot Compliance):** The application must strictly refuse to implement automated CAPTCHA bypass, stealth evasion, or rate-limit circumvention.

---

## 8. Business Rules & Operational Constraints

1. **Daily Application Caps:** The user can configure maximum daily application quotas per platform (e.g., maximum 50 on LinkedIn, 100 on Naukri) to prevent platform account flagging.
2. **Deterministic Deduplication:** A job is considered duplicate and skipped if its computed SHA-256 fingerprint matches an existing entry with status `SUBMITTED`, `APPLYING`, or `SUCCESS`.
3. **Fail-Closed Review Checkpoint:** If an application form requires an answer that cannot be resolved with $\ge 0.70$ confidence, or contains an unrecognized mandatory field, automation must hold and trigger `MANUAL_REQUIRED`.
4. **Compensation Protection:** Expected CTC submitted to portals must strictly reflect the candidate's verified range. The bot is prohibited from bidding below the user's defined minimum salary threshold.

---

## 9. Scope Boundaries

### 9.1 In-Scope (Implemented & Supported)
* Native PySide6 Desktop GUI (13 operational views, dark/light themes, splash screen, tray icon).
* Native automation engines for LinkedIn Easy Apply, Naukri.com, Indeed Apply, Glassdoor, Foundit, and Universal ATS (Greenhouse, Lever, Workday, Ashby).
* 5-tier Q&A reasoning engine with provenance tracking.
* Local SQLite WAL database with 16 SQLAlchemy models.
* PDF resume parsing and multi-resume vault.
* Encrypted credential storage via Fernet symmetric encryption.
* Audit logging with screenshot capture.
* Local Flask web management dashboard on port 5000.

### 9.2 Out-of-Scope (Non-Goals / Excluded)
* Multi-tenant recruiter SaaS hosting (JobPilot is candidate-centric, not an employer ATS).
* Automated CAPTCHA solving or stealth bot evasion mechanisms.
* Direct financial transactions or paid job board sponsorships.
* Real-time automated voice / telephone interview impersonation.

