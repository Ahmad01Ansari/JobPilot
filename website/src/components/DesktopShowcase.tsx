"use client";

import React, { useState } from "react";
import Image from "next/image";
import { LayoutDashboard, Zap, ListFilter, HelpCircle, Mail, BarChart3, CheckCircle2 } from "lucide-react";

interface TabItem {
  id: string;
  label: string;
  icon: React.ElementType;
  title: string;
  description: string;
  image: string;
  highlights: string[];
}

const TABS: TabItem[] = [
  {
    id: "dashboard",
    label: "Main Cockpit",
    icon: LayoutDashboard,
    title: "Mission Control & Live Telemetry",
    description:
      "Monitor application velocity, interview conversions, platform health, and pending human checkpoints from a unified high-resolution cockpit.",
    image: "/screens/screenshot_main_window.png",
    highlights: [
      "Real-time discovery & application stats",
      "Per-platform quota indicators",
      "Immediate alert for pending human checkpoints",
    ],
  },
  {
    id: "automation",
    label: "Universal Automation",
    icon: Zap,
    title: "Universal ATS & Platform Automation Engine",
    description:
      "Inspect the live automation timeline as JobPilot navigates job portals, identifies form fields, resolves questions, and halts for review.",
    image: "/screens/screenshot_automation.png",
    highlights: [
      "Live state machine timeline widget",
      "Target company & portal status",
      "Safe Mode with one-click pause & human intervention",
    ],
  },
  {
    id: "jobs",
    label: "Jobs Queue",
    icon: ListFilter,
    title: "Intelligent Match Scoring & Deduplication",
    description:
      "Every ingested opportunity is hashed via SHA-256 to eliminate duplicates across portals and scored against your master career facts.",
    image: "/screens/screenshot_jobs.png",
    highlights: [
      "SHA-256 fingerprint deduplication",
      "Role match percentage & keyword breakdown",
      "Batch apply or individually qualify opportunities",
    ],
  },
  {
    id: "qna",
    label: "5-Tier Q&A",
    icon: HelpCircle,
    title: "Deterministic Knowledge Base with Full Provenance",
    description:
      "Screening questions are resolved through a strict 5-tier cascade: Profile Fact → Resume Fact → Pre-Approved Rule → Formula → LLM fallback.",
    image: "/screens/screenshot_qna.png",
    highlights: [
      "Traceable provenance on every generated answer",
      "Strict zero-hallucination policy for candidate facts",
      "Unknown mandatory fields automatically flag human checkpoints",
    ],
  },
  {
    id: "outreach",
    label: "Recruiter Outreach",
    icon: Mail,
    title: "Direct Recruiter Synchronization & Follow-ups",
    description:
      "Manage recruiter conversations, track follow-up dates, and maintain momentum through scheduled reminder sequences.",
    image: "/screens/screenshot_outreach.png",
    highlights: [
      "Contextual recruiter email & LinkedIn templates",
      "Automated follow-up scheduling",
      "Audit trail of all outbound communications",
    ],
  },
  {
    id: "analytics",
    label: "Analytics",
    icon: BarChart3,
    title: "Pipeline Conversion & Platform Performance",
    description:
      "Evaluate which portals deliver actual interviews and optimize your resume variant allocations based on empirical conversion data.",
    image: "/screens/screenshot_analytics.png",
    highlights: [
      "Application-to-interview conversion funnel",
      "Platform efficiency comparisons (LinkedIn vs Indeed vs ATS)",
      "Daily application velocity tracking",
    ],
  },
];

export function DesktopShowcase() {
  const [activeTab, setActiveTab] = useState<TabItem>(TABS[0]);

  return (
    <section id="showcase" className="relative py-20 border-t border-obsidian-border bg-obsidian-deep/50">
      <div className="mx-auto w-full max-w-[1560px] px-4 sm:px-8 lg:px-12">
        
        {/* Section Heading */}
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-orange-safety/30 bg-orange-safety/10 px-3.5 py-1 text-xs font-mono text-orange-400">
            AUTHENTIC DESKTOP EXPERIENCE
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Engineered for Precision. <br />
            Built for Desktop Reliability.
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            No mockups or concept art. Explore actual widescreen screenshots from the JobPilot PySide6 desktop interface running on macOS, Windows, and Linux.
          </p>
        </div>

        {/* Tab Navigation Controls */}
        <div className="mt-10 flex flex-wrap items-center justify-center gap-2">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab.id === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab)}
                className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs sm:text-sm font-medium transition-all ${
                  isActive
                    ? "bg-slate-800 text-white border border-orange-safety/50 shadow-md shadow-orange-safety/10"
                    : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200 border border-transparent"
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? "text-orange-safety" : "text-slate-500"}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Realistic Desktop Application Frame */}
        <div className="mt-8 rounded-2xl border border-slate-700 bg-obsidian shadow-2xl overflow-hidden">
          {/* OS Titlebar */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-900/80">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-rose-500/80 inline-block" />
              <span className="h-3 w-3 rounded-full bg-amber-500/80 inline-block" />
              <span className="h-3 w-3 rounded-full bg-emerald-500/80 inline-block" />
              <span className="ml-3 font-mono text-xs text-slate-400 hidden sm:inline">
                JobPilot — {activeTab.title}
              </span>
            </div>
            <div className="flex items-center gap-3 font-mono text-[11px] text-slate-500">
              <span className="hidden md:inline">1600 × 1000 NATIVE CAPTURE</span>
              <span className="text-emerald-400 bg-emerald-950/60 border border-emerald-800/40 px-2 py-0.5 rounded">
                VERIFIED UI
              </span>
            </div>
          </div>

          {/* Screenshot Display */}
          <div className="relative aspect-[16/10] w-full bg-obsidian-deep overflow-hidden">
            <Image
              src={activeTab.image}
              alt={`JobPilot ${activeTab.title} Interface Screen`}
              fill
              sizes="(max-width: 1280px) 100vw, 1280px"
              priority
              className="object-contain"
            />
          </div>

          {/* Tab Information Footer */}
          <div className="p-6 sm:p-8 bg-slate-900/90 border-t border-slate-800 grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
            <div className="md:col-span-2 space-y-2">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <span>{activeTab.title}</span>
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed">
                {activeTab.description}
              </p>
            </div>
            <div className="space-y-2 border-t md:border-t-0 md:border-l border-slate-800 pt-4 md:pt-0 md:pl-6">
              <div className="text-xs font-mono uppercase tracking-wider text-slate-400">
                Key Architecture
              </div>
              <ul className="space-y-1.5 text-xs text-slate-300">
                {activeTab.highlights.map((h, i) => (
                  <li key={i} className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-orange-safety shrink-0" />
                    <span>{h}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

      </div>
    </section>
  );
}

