# JobPilot — Application Flow Specification

**Document Identifier:** `JOBPILOT-DOC-03-FLOW`  
**Classification:** Proprietary / Engineering Specification  
**Version:** 1.0.0-PROD  
**Target Release:** JobPilot v0.1.0-beta.1  
**Lead Architect:** Principal Solutions Architect & Interaction Designer  
**Date:** November 2026  

---

## 1. Executive Workflow Overview

JobPilot coordinates candidate profiles, resume variants, platform automation engines, and deterministic AI scoring into a unified, high-reliability desktop application flow. The system operates locally on the user's workstation, maintaining local SQLite storage and initiating isolated, stealthy browser sessions under user-configured boundaries.

This document details the complete end-to-end operational workflows, sequence diagrams, state machines, and exception handling paths governing candidate and recruiter interactions.

---

## 2. End-to-End Candidate Lifecycle

The candidate lifecycle spans onboarding, profile configuration, automated job discovery, multi-platform applications, human checkpoint intervention, and post-submission interview tracking.

```mermaid
graph TD
    Start([Application Launch]) --> Init[Initialize SQLite WAL & Secrets Vault]
    Init --> Onboard{Profile Configured?}
    
    Onboard -- No --> SetupProfile[Complete Profile: Skills, Target Roles, Salary Bounds]
    SetupProfile --> UploadResume[Upload PDF/DOCX Resume & Trigger ATS Parsing]
    UploadResume --> ConfigureQnA[Seed Custom Q&A Rules & Preferences]
    
    Onboard -- Yes --> Dashboard[Active Dashboard View]
    ConfigureQnA --> Dashboard
    
    Dashboard --> SelectMode{Select Workflow}
    
    SelectMode --> SearchJobs[Job Discovery & Scrape Mode]
    SelectMode --> RunAutomation[Direct Apply Automation]
    SelectMode --> ManageOutreach[Recruiter Outreach & Networking]
    SelectMode --> TrackInterviews[Interview Schedule & Preparation]
    
    SearchJobs --> Deduplicate[Deduplicate via SHA-256 Fingerprint]
    Deduplicate --> MatchScore[Calculate AI Semantic Fit & Score]
    MatchScore --> JobInventory[(Jobs Queue)]
    
    JobInventory --> RunAutomation
    RunAutomation --> DispatchWorker[Spawn Background TaskRunner]
    DispatchWorker --> LaunchBrowser[Launch Isolated Chromium Instance]
    LaunchBrowser --> ApplyLoop{Apply Loop Active?}
    
    ApplyLoop -- Next Job --> NavJob[Navigate to Job Posting]
    NavJob --> DetectATS[Detect ATS Type: Workday / Greenhouse / Lever / Platform]
    DetectATS --> FormStep[Autofill Form Fields via 5-Tier QnA]
    
    FormStep --> CheckpointNeeded{Ambiguity or Safe Mode Checkpoint?}
    CheckpointNeeded -- Yes --> NotifyUI[Emit Qt Signal: Request Human Decision]
    NotifyUI --> UserChoice{User Action}
    UserChoice -- Approve/Edit --> FormStep
    UserChoice -- Skip --> LogSkip[Log Job as Skipped]
    LogSkip --> ApplyLoop
    
    CheckpointNeeded -- No --> SubmitStep[Submit Application]
    SubmitStep --> RecordApp[Log Application Record & Update Daily Quotas]
    RecordApp --> ApplyLoop
    
    ApplyLoop -- Quota Reached / Stop --> EndLoop[Graceful Teardown & Metrics Refresh]
    EndLoop --> Dashboard
```

---

## 3. Candidate Journey (Step-by-Step Sequence)

### 3.1 Initial Setup and Resume Parsing Sequence
When a candidate adds a new resume, the file is parsed, indexed, and vectorized locally.

```mermaid
sequenceDiagram
    autonumber
    actor Candidate
    participant UI as ResumesView (PySide6)
    participant RS as ResumeService
    participant PDF as PDF/Docx Parser
    participant DB as SQLite DB (WAL)
    
    Candidate->>UI: Select PDF Resume File
    UI->>RS: upload_resume(file_path, candidate_id)
    RS->>PDF: parse_document_sections(file_bytes)
    PDF-->>RS: extracted_text, skills, experience_years, education
    RS->>RS: compute_ats_formatting_score(extracted_text)
    RS->>DB: insert_resume_record(parsed_metadata)
    DB-->>RS: resume_id confirmed
    RS-->>UI: ResumeModel updated
    UI-->>Candidate: Render Resume Card with ATS Score & Extracted Keywords
```

---

## 4. Job Discovery, Ingestion & Deduplication Flow

JobPilot ingests job listings from multiple sources (LinkedIn, Naukri, Indeed, Glassdoor, and custom search queries) and filters them using strict semantic rules and SHA-256 hashing.

```mermaid
flowchart TD
    subgraph Scraping Engines
        S1[LinkedIn Search Engine]
        S2[Naukri Search Engine]
        S3[Indeed Search Engine]
        S4[Glassdoor Search Engine]
    end

    S1 & S2 & S3 & S4 --> RawStream[Raw Job Stream: Title, Company, Location, Description, URL]
    RawStream --> CleanURL[Sanitize URL & Remove Tracking UTM Parameters]
    CleanURL --> HashGen[Generate SHA-256 Fingerprint: Title + Company + CleanURL]
    
    HashGen --> CheckDB{Fingerprint in DB?}
    CheckDB -- Yes: Duplicate --> DropJob[Discard Duplicate Listing]
    CheckDB -- No: Unique --> CheckExclusions{Match Exclusion Rules?}
    
    CheckExclusions -- Blacklisted Company / Bad Keyword --> ExcludeJob[Tag as EXCLUDED]
    CheckExclusions -- Passes Filters --> EvalMatch[Calculate Semantic Match Score]
    
    EvalMatch --> ScoreThreshold{Score >= Min Match %?}
    ScoreThreshold -- Below Threshold --> LowMatch[Tag as LOW_MATCH]
    ScoreThreshold -- Meets Threshold --> SaveQueue[Insert into `jobs` and `job_opportunities` Table]
    
    SaveQueue --> NotifyEvent[Emit `job_discovered` Signal to UI & Dashboard]
```

---

## 5. Multi-Platform Application Execution Sequence

The application execution loop operates in an asynchronous worker thread, ensuring the desktop GUI remains responsive at 60 FPS while interacting with external browser instances.

```mermaid
sequenceDiagram
    autonumber
    actor User as Candidate
    participant UI as AutomationView
    participant POS as PlatformOrchestratorService
    participant TR as TaskRunner (Background Thread)
    participant SEC as SecretsService
    participant SEL as Selenium CDP Driver
    participant ATS as Universal ATS Engine
    participant QNA as QnAService
    participant DB as SQLite Database

    User->>UI: Click "Start Automation" (Platform=LinkedIn, Mode=Safe)
    UI->>POS: start_automation(config)
    POS->>SEC: get_platform_credentials(platform)
    SEC-->>POS: decrypted_credentials
    POS->>TR: spawn_worker(run_target_loop)
    TR->>SEL: initialize_browser(profile_path, stealth=True)
    SEL-->>TR: browser_ready

    loop For Each Qualified Job in Queue
        TR->>SEL: navigate_to_job(job_url)
        TR->>ATS: inspect_form_structure(dom_tree)
        ATS-->>TR: detected_archetype (e.g. Greenhouse / Easy Apply)
        
        loop Form Step Progression
            TR->>ATS: extract_form_fields()
            ATS->>QNA: resolve_fields(field_descriptors)
            QNA-->>ATS: resolved_answers (with Provenance)
            ATS->>SEL: autofill_fields(resolved_answers)
            
            opt Ambiguous Field or Safe Mode Trigger
                ATS->>UI: emit_checkpoint_request(field_data)
                UI-->>User: Display Checkpoint Modal / Drawer
                User->>UI: Provide or Confirm Answer
                UI->>ATS: resolve_checkpoint(confirmed_data)
            end
            
            ATS->>SEL: click_next_step()
        end

        ATS->>SEL: submit_application()
        SEL-->>TR: confirmation_detected
        TR->>DB: record_application(job_id, status="APPLIED", timestamp)
        TR->>UI: emit_application_applied(app_summary)
        UI-->>User: Update Applications Table & Live Timeline
    end

    TR->>SEL: close_session()
    TR-->>POS: worker_completed
    POS-->>UI: emit_automation_finished()
```

---

## 6. 5-Tier Q&A Resolution & Provenance Flow

The Question & Answer engine routes application form questions through a zero-hallucination deterministic resolution hierarchy:

```mermaid
flowchart TD
    InField["Incoming Form Field: Label, Type, Options"] --> Norm["Normalize Question Text & Lowercase"]
    
    Norm --> T1{"Tier 1: Explicit Profile Fact?"}
    T1 -- Yes --> A1["Return Profile Field Value<br/>Provenance: PROFILE_FACT<br/>Confidence: 1.00"]
    
    T1 -- No --> T2{"Tier 2: Resume Fact?"}
    T2 -- Yes --> A2["Extract from Verified Resume Section<br/>Provenance: RESUME_FACT<br/>Confidence: 0.95"]
    
    T2 -- No --> T3{"Tier 3: User Q&A Rules?"}
    T3 -- Yes --> A3["Lookup question_answer_rules Table<br/>Provenance: QNA_RULE<br/>Confidence: 0.90"]
    
    T3 -- No --> T4{"Tier 4: Deterministic Math?"}
    T4 -- Yes --> A4["Calculate via Math or Date Formula<br/>Provenance: CALCULATED<br/>Confidence: 0.85"]
    
    T4 -- No --> T5{"Tier 5: LLM Client Active?"}
    T5 -- Yes --> A5["Invoke LLM Fallback (Gemini/Groq/OpenAI)<br/>Provenance: LLM_FALLBACK<br/>Confidence: 0.75"]
    
    T5 -- No --> Checkpoint["Trigger Desktop Human Checkpoint<br/>Confidence: 0.00"]
    
    A1 & A2 & A3 & A4 & A5 --> SafeCheck{"Safe Mode Active & Confidence < 0.85?"}
    SafeCheck -- Yes --> Checkpoint
    SafeCheck -- No --> Output["Inject Value into DOM Element"]
    Checkpoint --> UserResolution["Candidate Resolves via UI"]
    UserResolution --> LearnRule{"Save as Future Rule?"}
    LearnRule -- Yes --> SaveRule["Persist in question_answer_rules"]
    LearnRule -- No --> Output
    SaveRule --> Output
```

---

## 7. Email Outreach & Recruiter Follow-Up Workflow

JobPilot coordinates direct recruiter cold outreach, 2-way Gmail/IMAP synchronization, and automated multi-touch follow-ups through dedicated background workers.

```mermaid
sequenceDiagram
    autonumber
    actor Candidate
    participant UI as Outreach Workspace (Ctrl+6)
    participant OS as OutreachService
    participant SMTP as SMTP Worker
    participant IMAP as InboundSyncService
    participant FUS as FollowUpScheduler
    participant DB as SQLite DB

    Candidate->>UI: Select Recruiter Contact & Template (e.g. "Cold InMail")
    UI->>OS: compose_email(contact_id, template_id, variables)
    OS-->>UI: rendered_preview_with_tokens
    Candidate->>UI: Click "Send Outreach Email"
    UI->>SMTP: dispatch_email_async(credentials, recipient, payload)
    SMTP-->>UI: dispatch_confirmed(message_id)
    UI->>DB: insert_communication(direction="OUTBOUND", channel="EMAIL")
    UI->>FUS: schedule_follow_up(contact_id, delay_days=3)
    FUS->>DB: insert_follow_up(due_date, status="PENDING")

    par Periodic Inbound Reply Synchronization
        IMAP->>IMAP: poll_mailbox(sync_label="JobPilot/Outreach")
        opt Recruiter Reply Detected
            IMAP->>DB: insert_communication(direction="INBOUND", channel="EMAIL")
            IMAP->>FUS: cancel_scheduled_followups(contact_id, reason="REPLY_RECEIVED")
            IMAP->>UI: emit_inbound_reply_received(thread_id)
            UI-->>Candidate: Desktop Notification: "Recruiter Replied!"
        end
    end
```

---

## 8. Interview Preparation & Lifecycle Management

When an application converts into an interview, the interview lifecycle engine activates:

```mermaid
stateDiagram-v2
    [*] --> SCHEDULED: Application Status -> "INTERVIEW"
    SCHEDULED --> PREPARATION: Generate Cheat Sheet & Common Questions
    PREPARATION --> CONDUCTED: Candidate Completes Interview
    
    CONDUCTED --> AWAITING_FEEDBACK: Send Thank You Note & Log Impressions
    AWAITING_FEEDBACK --> NEXT_ROUND: Passed -> Schedule Round N+1
    AWAITING_FEEDBACK --> OFFER_RECEIVED: Final Round Passed
    AWAITING_FEEDBACK --> REJECTED: Candidate Dropped
    
    NEXT_ROUND --> PREPARATION
    OFFER_RECEIVED --> ACCEPTED: Candidate Signs
    OFFER_RECEIVED --> DECLINED: Candidate Rejects Offer
    
    ACCEPTED --> [*]
    DECLINED --> [*]
    REJECTED --> [*]
```

---

## 9. Error Handling, Exception Flows & Recovery

JobPilot incorporates fail-safe recovery patterns to handle network drops, platform changes, and system crashes gracefully:

| Error Condition | Trigger Point | Automated Recovery Protocol | Fail-Closed Fallback |
|---|---|---|---|
| **Rate Limit Triggered** | Platform HTTP 429 or search lock | Immediate worker backoff; pause platform automation for 60 minutes. | Notify candidate in UI; switch to secondary configured platform. |
| **CAPTCHA / Challenge** | Cloudflare Turnstile or platform puzzle | Halt worker thread immediately; sound desktop alert; focus browser window. | Candidate completes challenge manually; clicks "Resume" in UI. |
| **DOM Element Missing** | Selector change or dynamic JS load | Retry up to 3 times with exponential backoff and alternate XPath heuristics. | Mark step as ambiguous; trigger Human Checkpoint drawer. |
| **Database Lock / Busy** | SQLite simultaneous write collision | Automatically wait using SQLite `busy_timeout = 30000ms`. | Log retry; fail operation safely without data corruption. |
| **Abrupt App Termination** | Power loss or OS process kill | WAL journal automatically recovers uncommitted transactions on startup. | Re-open database cleanly; stale automation flags reset to `IDLE`. |
| **Browser Zombie / Orphan** | Desktop UI closed while worker active | `ApplicationLifecycleManager` terminates browser trees via `ProcessManager`. | Force kill child process tree (`taskkill /F /T` or `os.killpg`). |

---

## 10. Dashboard Navigation & Information Hierarchy

```mermaid
graph LR
    subgraph Navigation Sidebar
        NAV1[Dashboard: KPI Cards & Live Activity]
        NAV2[Jobs: Match Engine & Job Finder]
        NAV3[Applications: History, Kanban & Funnel]
        NAV4[Automation: Multi-Platform Control Center]
        NAV5[Profile: Master Career Facts]
        NAV6[Q&A: Smart Rules & Provenance Review]
        NAV7[Resumes: ATS Analysis & Variants]
        NAV8[Outreach: Recruiter Contacts CRM]
        NAV9[Interviews: Prep & Schedule Tracker]
        NAV10[Analytics: Velocity & Conversion Metrics]
        NAV11[Settings: Platform Credentials & Safety]
    end

    NAV1 --> NAV2 & NAV3 & NAV4
    NAV4 --> NAV3
    NAV2 --> NAV4
    NAV5 & NAV6 & NAV7 --> NAV4
    NAV3 --> NAV9
    NAV8 --> NAV9
```

