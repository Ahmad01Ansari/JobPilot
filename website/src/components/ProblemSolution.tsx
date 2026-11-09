"use client";

import React from "react";
import { XCircle, CheckCircle, ArrowRight, ShieldAlert, Cpu } from "lucide-react";

export function ProblemSolution() {
  const PAIN_POINTS = [
    "Fragmented job searches across 4+ different platforms with duplicate postings",
    "Manually re-typing the same work experience and screening answers 50+ times a week",
    "Unforgiving ATS portals (Workday, Greenhouse, Lever) with tedious multi-page forms",
    "Cloud SaaS job bots scraping your private credentials and uploading resumes to public servers",
    "Hallucinating AI bots submitting fake qualifications or fabricated metrics under your name",
    "Untracked recruiter threads resulting in missed follow-ups and lost interview opportunities",
  ];

  const JOBPILOT_SOLUTIONS = [
    "Unified multi-engine discovery with SHA-256 deduplication across all portals",
    "Automated form mapping powered by a local, deterministic Universal ATS engine",
    "5-Tier Q&A provenance engine: every answer maps to a verified profile or resume fact",
    "100% Local-First desktop architecture: zero telemetry, zero cloud database leaks",
    "Mandatory Human Checkpoints: review sensitive fields (salary, visa) before submission",
    "Integrated recruiter inbox with automated timeline tracking and follow-up reminders",
  ];

  return (
    <section className="py-20 border-t border-obsidian-border bg-obsidian-surface/40">
      <div className="mx-auto w-full max-w-[1560px] px-4 sm:px-8 lg:px-12">
        
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-rose-500/30 bg-rose-500/10 px-3.5 py-1 text-xs font-mono text-rose-400">
            THE CURRENT JOB HUNT IS BROKEN
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Manual Application Fatigue vs. Autonomous Cockpit
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            Applying to 200+ jobs manually is an exhausting administrative ordeal. Generic cloud bots risk your reputation with hallucinated answers. JobPilot brings pilot-grade rigor to your desktop.
          </p>
        </div>

        {/* Comparison Grid */}
        <div className="mt-14 grid grid-cols-1 lg:grid-cols-2 gap-8">
          
          {/* Left: The Manual Friction */}
          <div className="rounded-2xl border border-rose-900/30 bg-rose-950/10 p-8 sm:p-10 space-y-6">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-rose-400">
                <ShieldAlert className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">Manual Application Chaos</h3>
                <p className="text-xs font-mono text-rose-400/80">THE STATUS QUO</p>
              </div>
            </div>

            <ul className="space-y-4 text-sm text-slate-300">
              {PAIN_POINTS.map((point, index) => (
                <li key={index} className="flex items-start gap-3">
                  <XCircle className="h-5 w-5 text-rose-500 shrink-0 mt-0.5" />
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Right: The JobPilot Cockpit */}
          <div className="rounded-2xl border border-emerald-900/40 bg-emerald-950/15 p-8 sm:p-10 space-y-6 relative overflow-hidden">
            <div className="absolute top-0 right-0 px-4 py-1.5 bg-emerald-900/80 text-[11px] font-mono text-emerald-300 font-semibold rounded-bl-xl border-l border-b border-emerald-700">
              DESKTOP COCKPIT
            </div>

            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                <Cpu className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">JobPilot Autonomous System</h3>
                <p className="text-xs font-mono text-emerald-400/80">ENGINEERED RECOVERY</p>
              </div>
            </div>

            <ul className="space-y-4 text-sm text-slate-200">
              {JOBPILOT_SOLUTIONS.map((solution, index) => (
                <li key={index} className="flex items-start gap-3">
                  <CheckCircle className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{solution}</span>
                </li>
              ))}
            </ul>
          </div>

        </div>

      </div>
    </section>
  );
}

