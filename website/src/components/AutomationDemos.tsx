"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Zap,
  Play,
  Pause,
  RotateCcw,
  CheckCircle2,
  Terminal,
  Film,
  Sparkles,
  ExternalLink,
} from "lucide-react";

interface AutomationStep {
  title: string;
  badge: string;
  description: string;
  logText: string;
  targetHighlight: string;
  provenance?: string;
}

interface AutomationType {
  id: string;
  title: string;
  badge: string;
  platformCategory: string;
  videoUrl: string;
  gifUrl: string;
  posterImage: string;
  codePath: string;
  overview: string;
  capabilities: string[];
  steps: AutomationStep[];
}

const AUTOMATION_ENGINES: AutomationType[] = [
  {
    id: "universal-ats",
    title: "Universal ATS State Machine",
    badge: "FLAGSHIP ENGINE",
    platformCategory: "Greenhouse • Lever • Workday • Ashby",
    videoUrl: "/videos/demo-universal-ats.mp4",
    gifUrl: "/videos/demo-universal-ats.gif",
    posterImage: "/videos/demo-universal-ats.gif",
    codePath: "app/services/automation/universal_agent/",
    overview:
      "Autonomous state machine that resolves dynamic application forms on enterprise ATS portals, traverses nested iframes, injects verified facts, and pauses for human checkpoints on sensitive fields.",
    capabilities: [
      "FrameResolver: Navigates cross-origin iframes in Workday & Lever",
      "FieldMapper: Semantic classification of inputs without hardcoded IDs",
      "5-Tier Q&A: Injects candidate facts with verifiable audit tags",
      "SnapshotRecorder: Commits SHA-256 submission evidence to local SQLite",
    ],
    steps: [
      {
        title: "Page & DOM Analysis",
        badge: "STATE: ANALYZE",
        description: "Scans DOM tree, identifies form containers, and resolves iframe boundaries.",
        logText: "[UniversalAgent] PageAnalyzer: 14 candidate inputs detected. Frame: iframe#app-frame",
        targetHighlight: "Form Container Detected (14 fields)",
      },
      {
        title: "Semantic Field Mapping",
        badge: "STATE: MAP_FIELDS",
        description: "Matches inputs against Master Profile: Legal Name, Phone, Email, LinkedIn, Resume.",
        logText: "[FieldMapper] Mapped 12 standard inputs to Candidate Facts. Variant: resume_backend.pdf",
        targetHighlight: "Inputs Mapped (Legal Name, Phone, Email)",
        provenance: "PROFILE_FACT",
      },
      {
        title: "5-Tier Q&A Resolution",
        badge: "STATE: RESOLVE_QNA",
        description: "Resolves screening questions deterministically: experience tenure, sponsorship, tech stack.",
        logText: "[ValidationResolver] Question: 'Years of Experience' → Resolved '5+ years' (Zero Hallucination)",
        targetHighlight: "Resolved: 5+ Yrs Experience",
        provenance: "RESUME_FACT",
      },
      {
        title: "File Attachment & Security",
        badge: "STATE: VAULT_ATTACH",
        description: "Attaches candidate resume artifact directly from encrypted local storage.",
        logText: "[VaultService] Injected resume artifact: Ahmad_Raza_Resume.pdf (SHA-256 verified)",
        targetHighlight: "Resume PDF Attached",
        provenance: "VAULT_FILE",
      },
      {
        title: "Submission & Evidence Commit",
        badge: "STATE: VERIFIED",
        description: "Form submitted, confirmation receipt verified, and SHA-256 snapshot recorded.",
        logText: "[ResultVerifier] HTTP 200 OK receipt. Evidence hash sha256:9b1a8f... stored in local SQLite",
        targetHighlight: "Application Submitted & Audited",
      },
    ],
  },
  {
    id: "foundit",
    title: "Foundit Flow Detector & Applier",
    badge: "FLOW DETECTOR",
    platformCategory: "Foundit • Monster • Direct & Questionnaire",
    videoUrl: "/videos/demo-foundit.mp4",
    gifUrl: "/videos/demo-foundit.gif",
    posterImage: "/videos/demo-foundit.gif",
    codePath: "platforms/foundit/applier.py",
    overview:
      "Inspects Foundit / Monster job openings upon clicking Apply, dynamically classifying application flows into Direct, Multi-Step Questionnaire, or External ATS redirects.",
    capabilities: [
      "Flow Classifier: Autodetects DIRECT, QUESTIONNAIRE, EXTERNAL ATS, and ALREADY_APPLIED",
      "Dynamic Form Filling: Resolves candidate experience, expected salary, and notice period",
      "Session Reuse: Operates using authenticated browser cookies without credential re-entry",
      "Unified Tracker: Records real-time lifecycle status transitions directly into SQLite",
    ],
    steps: [
      {
        title: "Flow Analysis & Classification",
        badge: "FLOW DETECT",
        description: "Scans application modal to classify flow as Direct Apply, Questionnaire, or External ATS.",
        logText: "[FounditApplier] Inspecting application modal: Flow classified as DIRECT_APPLY",
        targetHighlight: "Flow: Direct Apply Detected",
      },
      {
        title: "Candidate Fact Injection",
        badge: "AUTO-FILL",
        description: "Injects verified legal name, email coordinates, phone, and current job title.",
        logText: "[FounditForm] Injected Profile Coordinates: Name, Email, Phone from Master Profile",
        targetHighlight: "Candidate Coordinates Mapped",
        provenance: "PROFILE_FACT",
      },
      {
        title: "Resume & Portfolio Attachment",
        badge: "VAULT ATTACH",
        description: "Attaches primary resume variant from encrypted local storage vault.",
        logText: "[FounditSubmitter] Attached primary resume variant from local vault",
        targetHighlight: "Resume PDF Attached",
        provenance: "VAULT_FILE",
      },
      {
        title: "Screening & Notice Period",
        badge: "SCREENING",
        description: "Resolves notice period, expected CTC, and location preferences deterministically.",
        logText: "[ValidationResolver] Resolved tenure, current role, and notice period (30 Days)",
        targetHighlight: "Notice Period: 30 Days",
        provenance: "RESUME_FACT",
      },
      {
        title: "Submission & Evidence Commit",
        badge: "SUBMISSION",
        description: "Submits application form, captures receipt, and updates Cockpit tracking ledger.",
        logText: "[FounditApplier] Application submitted successfully. Recorded to Cockpit ledger",
        targetHighlight: "Recorded to Cockpit Ledger",
      },
    ],
  },
  {
    id: "naukri",
    title: "Naukri Direct Apply & Safety Gate",
    badge: "REGIONAL ADAPTER",
    platformCategory: "Naukri Direct Apply • Lever Archetype",
    videoUrl: "/videos/demo-naukri.mp4",
    gifUrl: "/videos/demo-naukri.gif",
    posterImage: "/videos/demo-naukri.gif",
    codePath: "platforms/naukri/applier.py",
    overview:
      "High-precision adapter designed for Indian job boards and direct career portals with intelligent rate limiting, notice period injection, and session cookie reuse.",
    capabilities: [
      "Zero Password Transmission: Operates directly via local browser session cookies",
      "Dynamic Questionnaire Handling: Injects notice period, current CTC, and location preferences",
      "Humanized Velocity: Randomized interaction jitter (1.8s - 3.4s) prevents bot detection",
      "Status Ledger: Emits real-time progress events to desktop Cockpit",
    ],
    steps: [
      {
        title: "Session Authentication Check",
        badge: "AUTH CHECK",
        description: "Verifies existing active session cookie without entering credentials.",
        logText: "[NaukriEngine] Validating local profile session... Authenticated as Candidate",
        targetHighlight: "Session Active (No Credential Input)",
      },
      {
        title: "Resume Attachment & Classification",
        badge: "RESUME UPLOAD",
        description: "Uploads verified candidate resume artifact to ATS input.",
        logText: "[LeverAdapter] Uploaded resume: Ahmad_Raza_Resume.pdf",
        targetHighlight: "Resume PDF Attached",
      },
      {
        title: "Candidate Fact Injection",
        badge: "AUTO-FILL",
        description: "Fills candidate profile coordinates, current title, and portfolio links.",
        logText: "[FormFiller] Injected Full Name, Email, Phone, Company, LinkedIn, GitHub",
        targetHighlight: "Profile Inputs Completed",
        provenance: "PROFILE_FACT",
      },
      {
        title: "Notice Period & Experience Tenure",
        badge: "SCREENING",
        description: "Selects experience tenure and inputs notice period days.",
        logText: "[QnAResolver] Experience: 5-8 years. Notice period: 30 Days",
        targetHighlight: "Notice Period: 30 Days",
        provenance: "RESUME_FACT",
      },
      {
        title: "Direct Application Complete",
        badge: "CONFIRMATION",
        description: "Application successfully submitted and receipt recorded in Cockpit.",
        logText: "[NaukriEngine] Application submitted. Evidence hash stored in SQLite",
        targetHighlight: "Naukri Ledger Updated",
      },
    ],
  },
  {
    id: "indeed-glassdoor",
    title: "Indeed & Glassdoor Submitter",
    badge: "AGGREGATOR ENGINE",
    platformCategory: "Indeed • Glassdoor • Workday Bridge",
    videoUrl: "/videos/demo-indeed.mp4",
    gifUrl: "/videos/demo-indeed.gif",
    posterImage: "/videos/demo-indeed.gif",
    codePath: "platforms/indeed/ & platforms/glassdoor/",
    overview:
      "Detects whether an opportunity uses native easy application or redirects to an enterprise ATS portal (like Workday), seamlessly executing multi-step form traversal.",
    capabilities: [
      "Router: Automatically detects direct apply vs external ATS redirect",
      "Form Analyzer: Classifies multi-page job application questions and file upload fields",
      "CAPTCHA Interceptor: Safely halts automation when Cloudflare / hCaptcha appears",
      "Anti-Detection Delays: Emulates realistic human typing and scrolling velocities",
    ],
    steps: [
      {
        title: "External ATS Redirect Bridge",
        badge: "ROUTING",
        description: "Detects external Workday application portal and transitions seamlessly.",
        logText: "[PlatformRouter] Destination: Workday Portal detected. Activating multi-step agent",
        targetHighlight: "Workday Bridge Activated",
      },
      {
        title: "Step 1: Personal Coordinates",
        badge: "WORKDAY STEP 1",
        description: "Injects candidate legal name, email, and phone number.",
        logText: "[WorkdayAgent] Step 1 Complete: Injected candidate contact facts",
        targetHighlight: "Candidate Information Filled",
        provenance: "PROFILE_FACT",
      },
      {
        title: "Step 2: Experience & Resume Upload",
        badge: "WORKDAY STEP 2",
        description: "Uploads resume and maps experience tenure dropdown.",
        logText: "[WorkdayAgent] Step 2 Complete: Attached Ahmad_Raza_Resume.pdf. Auth: Yes",
        targetHighlight: "Experience & Resume Uploaded",
        provenance: "VAULT_FILE",
      },
      {
        title: "Step 3: Review & Final Submission",
        badge: "WORKDAY STEP 3",
        description: "Performs pre-submission validation review and clicks Submit Application.",
        logText: "[WorkdayAgent] Review verified. Submitting application...",
        targetHighlight: "Review & Submit",
      },
      {
        title: "Receipt Confirmed & Audited",
        badge: "CONFIRMATION",
        description: "Captures Workday submission receipt #APP-WIZARD-1122 and commits to local SQLite.",
        logText: "[ResultVerifier] Receipt #APP-WIZARD-1122 recorded to local Cockpit",
        targetHighlight: "Evidence Stored in Local Vault",
      },
    ],
  },
];

export function AutomationDemos() {
  const [activeEngine, setActiveEngine] = useState<AutomationType>(AUTOMATION_ENGINES[0]);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [mediaFormat, setMediaFormat] = useState<"video" | "gif">("video");
  const videoRef = useRef<HTMLVideoElement>(null);

  // Sync video play/pause with state
  useEffect(() => {
    if (mediaFormat === "video" && videoRef.current) {
      if (isPlaying) {
        videoRef.current.play().catch(() => {});
      } else {
        videoRef.current.pause();
      }
    }
  }, [isPlaying, activeEngine, mediaFormat]);

  // Auto-advance step indicator alongside video loop
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPlaying) {
      interval = setInterval(() => {
        setCurrentStepIndex((prev) => (prev + 1) % activeEngine.steps.length);
      }, 2600);
    }
    return () => clearInterval(interval);
  }, [isPlaying, activeEngine]);

  const handleSelectEngine = (engine: AutomationType) => {
    setActiveEngine(engine);
    setCurrentStepIndex(0);
    setIsPlaying(true);
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
      videoRef.current.play().catch(() => {});
    }
  };

  const handleTogglePlay = () => {
    if (mediaFormat === "video" && videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
        setIsPlaying(false);
      } else {
        videoRef.current.play().catch(() => {});
        setIsPlaying(true);
      }
    } else {
      setIsPlaying(!isPlaying);
    }
  };

  const handleRestart = () => {
    setCurrentStepIndex(0);
    setIsPlaying(true);
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
      videoRef.current.play().catch(() => {});
    }
  };

  const currentStep = activeEngine.steps[currentStepIndex] || activeEngine.steps[0];

  return (
    <section id="automation-demos" className="relative py-24 bg-slate-950/70 backdrop-blur-[1px] text-slate-100 overflow-hidden border-t border-slate-800">
      
      {/* Background Glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[500px] bg-orange-safety/5 blur-[140px] pointer-events-none rounded-full" />

      <div className="relative mx-auto w-full max-w-[1560px] px-4 sm:px-8 lg:px-12">
        
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-orange-safety/40 bg-orange-safety/10 px-3.5 py-1 text-xs font-mono text-orange-400">
            <Sparkles className="h-3.5 w-3.5 text-orange-safety" />
            <span>REAL BROWSER AUTOMATION RECORDINGS</span>
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-white">
            See the Automation Engines in Action
          </h2>
          <p className="text-base sm:text-lg text-slate-400 leading-relaxed">
            Real browser screen recordings showing JobPilot navigating ATS portals, typing candidate facts character-by-character, attaching resumes, and confirming submissions.
          </p>
        </div>

        {/* Engine Tabs */}
        <div className="mt-12 flex flex-wrap items-center justify-center gap-2 sm:gap-3">
          {AUTOMATION_ENGINES.map((engine) => {
            const isSelected = engine.id === activeEngine.id;
            return (
              <button
                key={engine.id}
                onClick={() => handleSelectEngine(engine)}
                className={`flex items-center gap-2 rounded-xl px-4 py-3 text-xs sm:text-sm font-semibold transition-all ${
                  isSelected
                    ? "bg-slate-800 text-white border border-orange-safety shadow-lg shadow-orange-safety/10"
                    : "text-slate-400 hover:bg-slate-900 hover:text-slate-200 border border-slate-800"
                }`}
              >
                <Zap className={`h-4 w-4 ${isSelected ? "text-orange-safety" : "text-slate-500"}`} />
                <span>{engine.title}</span>
              </button>
            );
          })}
        </div>

        {/* Main Video Demo Display Frame */}
        <div className="mt-8 rounded-2xl border border-slate-700 bg-obsidian shadow-2xl overflow-hidden">
          
          {/* Top Control Bar / Player Chrome */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-5 py-3.5 border-b border-slate-800 bg-slate-900/90">
            <div className="flex items-center gap-3">
              <span className="h-3 w-3 rounded-full bg-rose-500/80 inline-block" />
              <span className="h-3 w-3 rounded-full bg-amber-500/80 inline-block" />
              <span className="h-3 w-3 rounded-full bg-emerald-500/80 inline-block" />
              <span className="font-mono text-xs text-white font-bold hidden sm:inline ml-2">
                {activeEngine.title}
              </span>
              <span className="text-[11px] font-mono text-cyan-400 bg-cyan-950/60 border border-cyan-800/40 px-2.5 py-0.5 rounded">
                {activeEngine.platformCategory}
              </span>
            </div>

            {/* Video Playback Controls & Format Toggle */}
            <div className="flex items-center gap-3">
              
              {/* MP4 / GIF Toggle */}
              <div className="flex items-center rounded-lg bg-slate-800 p-0.5 border border-slate-700 text-[11px] font-mono">
                <button
                  onClick={() => setMediaFormat("video")}
                  className={`px-2.5 py-1 rounded-md transition-colors ${
                    mediaFormat === "video" ? "bg-orange-safety text-white font-bold" : "text-slate-400 hover:text-white"
                  }`}
                >
                  HD Video
                </button>
                <button
                  onClick={() => setMediaFormat("gif")}
                  className={`px-2.5 py-1 rounded-md transition-colors ${
                    mediaFormat === "gif" ? "bg-orange-safety text-white font-bold" : "text-slate-400 hover:text-white"
                  }`}
                >
                  GIF
                </button>
              </div>

              <button
                onClick={handleTogglePlay}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-mono text-slate-200 transition-colors"
                title={isPlaying ? "Pause playback" : "Resume playback"}
              >
                {isPlaying ? <Pause className="h-3.5 w-3.5 text-amber-400" /> : <Play className="h-3.5 w-3.5 text-emerald-400" />}
                <span>{isPlaying ? "Pause" : "Play"}</span>
              </button>

              <button
                onClick={handleRestart}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                title="Restart demo video"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </button>

              <div className="text-xs font-mono text-slate-400">
                Phase {currentStepIndex + 1} of {activeEngine.steps.length}
              </div>
            </div>
          </div>

          {/* Stepper Progress Bar */}
          <div className="grid grid-cols-5 h-1.5 bg-slate-900">
            {activeEngine.steps.map((_, idx) => (
              <div
                key={idx}
                onClick={() => {
                  setCurrentStepIndex(idx);
                }}
                className={`cursor-pointer transition-colors ${
                  idx <= currentStepIndex ? "bg-orange-safety" : "bg-slate-800"
                }`}
              />
            ))}
          </div>

          {/* Split Display: Real Recording on Left, Telemetry & Specs on Right */}
          <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[500px]">
            
            {/* Left: Real Browser Automation Video / GIF */}
            <div className="lg:col-span-7 relative bg-slate-950 flex flex-col justify-center items-center overflow-hidden border-b lg:border-b-0 lg:border-r border-slate-800">
              
              {mediaFormat === "video" ? (
                <video
                  ref={videoRef}
                  key={activeEngine.videoUrl}
                  src={activeEngine.videoUrl}
                  poster={activeEngine.posterImage}
                  autoPlay
                  loop
                  muted
                  playsInline
                  className="w-full h-auto object-contain bg-slate-950"
                />
              ) : (
                <img
                  key={activeEngine.gifUrl}
                  src={activeEngine.gifUrl}
                  alt={`${activeEngine.title} Real-time Demonstration`}
                  className="w-full h-auto object-contain bg-slate-950"
                />
              )}

              {/* Minimal Top-Right HUD Badge (Clean, non-obtrusive) */}
              <div className="absolute top-3 right-3 hidden sm:flex items-center gap-2 rounded-lg border border-orange-safety/50 bg-slate-950/85 px-3 py-1.5 text-xs font-mono text-orange-400 shadow-lg backdrop-blur-md">
                <span className="h-2 w-2 rounded-full bg-orange-safety" />
                <span className="font-bold uppercase tracking-wider">{currentStep.badge}</span>
              </div>

              {/* Slim Bottom Status Bar (Unobstructed view of form) */}
              <div className="w-full bg-slate-900/95 border-t border-slate-800 px-4 py-2.5 flex items-center justify-between text-xs font-mono">
                <div className="flex items-center gap-2 overflow-hidden text-ellipsis whitespace-nowrap">
                  <span className="text-orange-400 font-bold">{currentStep.badge}:</span>
                  <span className="text-slate-200">{currentStep.title}</span>
                </div>
                {currentStep.provenance && (
                  <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 shrink-0 ml-2">
                    {currentStep.provenance}
                  </span>
                )}
              </div>

            </div>

            {/* Right: Live Telemetry Terminal & Codebase Specs */}
            <div className="lg:col-span-5 p-6 sm:p-7 flex flex-col justify-between space-y-6 bg-slate-900/60">
              
              {/* Architecture Overview */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono uppercase tracking-wider text-slate-400">
                    Engine Overview
                  </span>
                  <span className="text-[11px] font-mono text-slate-500">
                    {activeEngine.codePath}
                  </span>
                </div>
                <h3 className="text-lg font-bold text-white">{activeEngine.title}</h3>
                <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                  {activeEngine.overview}
                </p>
              </div>

              {/* Current Active Step Deep-Dive */}
              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono text-orange-400 font-bold uppercase">
                    Phase {currentStepIndex + 1}: {currentStep.badge}
                  </span>
                  <span className="text-[11px] font-mono text-emerald-400">
                    {currentStep.targetHighlight}
                  </span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  {currentStep.description}
                </p>
              </div>

              {/* Real-time Streaming Terminal Log Box */}
              <div className="rounded-xl border border-slate-800 bg-obsidian p-4 font-mono text-xs space-y-2">
                <div className="flex items-center justify-between text-slate-500 border-b border-slate-800 pb-2">
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <Terminal className="h-3.5 w-3.5 text-orange-safety" />
                    <span>ENGINE LOG TELEMETRY</span>
                  </span>
                  <span className="text-[10px] text-emerald-400">● LIVE</span>
                </div>
                <div className="text-slate-300 break-words leading-relaxed pt-1">
                  {currentStep.logText}
                </div>
              </div>

              {/* Engine Capabilities Checklist */}
              <div className="space-y-2">
                <div className="text-xs font-mono uppercase tracking-wider text-slate-400">
                  Adapter Architecture
                </div>
                <ul className="space-y-1.5 text-xs text-slate-300">
                  {activeEngine.capabilities.map((cap, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-orange-safety shrink-0 mt-0.5" />
                      <span>{cap}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Step Navigation Pill Selectors */}
              <div className="pt-3 border-t border-slate-800 flex flex-wrap gap-2">
                {activeEngine.steps.map((st, sIdx) => (
                  <button
                    key={sIdx}
                    onClick={() => {
                      setCurrentStepIndex(sIdx);
                    }}
                    className={`text-[11px] font-mono px-2.5 py-1 rounded-lg transition-all ${
                      sIdx === currentStepIndex
                        ? "bg-orange-safety text-white font-bold"
                        : "bg-slate-800 text-slate-400 hover:text-white"
                    }`}
                  >
                    Phase {sIdx + 1}
                  </button>
                ))}
              </div>

            </div>

          </div>

        </div>

        {/* Verification Footer Label */}
        <div className="mt-8 text-center text-xs font-mono text-slate-500 flex items-center justify-center gap-2">
          <Film className="h-3.5 w-3.5 text-orange-400" />
          <span>Recorded live from JobPilot browser automation runs using local candidate facts and sandboxed form execution.</span>
        </div>

      </div>
    </section>
  );
}
