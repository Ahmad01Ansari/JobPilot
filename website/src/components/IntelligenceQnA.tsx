"use client";

import React, { useState } from "react";
import { Check, Shield, AlertTriangle, ArrowDown, Sparkles, Database, FileText, Calculator, HelpCircle } from "lucide-react";

interface CascadeTier {
  id: string;
  tierNumber: string;
  name: string;
  sourceBadge: string;
  description: string;
  example: string;
  icon: React.ElementType;
  badgeStyle: string;
}

const TIERS: CascadeTier[] = [
  {
    id: "profile",
    tierNumber: "Tier 1",
    name: "Master Profile Facts",
    sourceBadge: "PROFILE_FACT",
    description: "Exact candidate truth: Legal Name, Phone, Email, Authorized Work Locations, LinkedIn URL, GitHub URL.",
    example: "What is your phone number? → +1 (555) 019-2834",
    icon: Database,
    badgeStyle: "bg-cyan-950/60 text-cyan-400 border-cyan-800",
  },
  {
    id: "resume",
    tierNumber: "Tier 2",
    name: "Targeted Resume Facts",
    sourceBadge: "RESUME_FACT",
    description: "Parsed facts from your active resume variant: Years of Experience, Past Employers, Tech Stack, Education degrees.",
    example: "How many years of Python experience do you have? → 6 years",
    icon: FileText,
    badgeStyle: "bg-emerald-950/60 text-emerald-400 border-emerald-800",
  },
  {
    id: "rules",
    tierNumber: "Tier 3",
    name: "Pre-Approved Q&A Rules",
    sourceBadge: "QNA_RULE",
    description: "Pre-configured answers to recurring screening questions (sponsorship, relocations, background checks, remote preferences).",
    example: "Will you now or in the future require visa sponsorship? → No",
    icon: Shield,
    badgeStyle: "bg-purple-950/60 text-purple-400 border-purple-800",
  },
  {
    id: "calc",
    tierNumber: "Tier 4",
    name: "Deterministic Calculations",
    sourceBadge: "CALCULATED",
    description: "Mathematical dates and durations derived from employment history (e.g. Total Years in Distributed Systems).",
    example: "Calculate cumulative engineering tenure → 7.5 years",
    icon: Calculator,
    badgeStyle: "bg-blue-950/60 text-blue-400 border-blue-800",
  },
  {
    id: "llm",
    tierNumber: "Tier 5",
    name: "Constrained LLM Fallback",
    sourceBadge: "LLM_FALLBACK",
    description: "Handles novel essay/open-ended questions strictly constrained by your master facts. If uncertain, pauses for human review.",
    example: "Why do you want to work here? → Formulated from your past experience",
    icon: Sparkles,
    badgeStyle: "bg-amber-950/60 text-amber-400 border-amber-800",
  },
];

export function IntelligenceQnA() {
  const [selectedTier, setSelectedTier] = useState<string>("profile");

  return (
    <section id="qna" className="py-20 border-t border-obsidian-border bg-obsidian-deep/60">
      <div className="mx-auto w-full max-w-[1560px] px-4 sm:px-8 lg:px-12">
        
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-orange-safety/30 bg-orange-safety/10 px-3.5 py-1 text-xs font-mono text-orange-400">
            DETERMINISTIC PROVENANCE ENGINE
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            5-Tier Q&amp;A Resolution Cascade
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            JobPilot never allows an AI model to hallucinate your qualifications. Every single form input is resolved in strict priority order, recording its audit source in your local ledger.
          </p>
        </div>

        {/* 2-Column Priority Cascade & Telemetry Console */}
        <div className="mt-14 grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* Left Column: 5-Tier Priority Cascade */}
          <div className="lg:col-span-7 space-y-3">
            {TIERS.map((tier, index) => {
              const Icon = tier.icon;
              const isSelected = selectedTier === tier.id;

              return (
                <div
                  key={tier.id}
                  onClick={() => setSelectedTier(tier.id)}
                  className={`cursor-pointer rounded-2xl border p-5 transition-all ${
                    isSelected
                      ? "border-orange-safety/70 bg-slate-900/90 shadow-xl shadow-orange-safety/5"
                      : "border-slate-800 bg-slate-900/40 hover:border-slate-700 hover:bg-slate-900/60"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-800 text-orange-safety shrink-0">
                        <Icon className="h-4 w-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono text-slate-400 font-bold uppercase">
                            {tier.tierNumber}
                          </span>
                          <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${tier.badgeStyle}`}>
                            {tier.sourceBadge}
                          </span>
                        </div>
                        <h3 className="text-sm sm:text-base font-bold text-white mt-0.5">
                          {tier.name}
                        </h3>
                      </div>
                    </div>

                    <div className="text-xs font-mono text-slate-500">
                      Priority #{index + 1}
                    </div>
                  </div>

                  <p className="mt-2.5 text-xs sm:text-sm text-slate-300 leading-relaxed pl-0 sm:pl-[48px]">
                    {tier.description}
                  </p>

                  <div className="mt-2.5 sm:ml-[48px] rounded-lg bg-obsidian/90 px-3 py-2 text-xs font-mono text-slate-300 border border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                    <span className="text-slate-400 shrink-0">Sample Resolution:</span>
                    <span className="text-emerald-400 font-medium break-words">{tier.example}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Right Column: Live Provenance Inspector & Safety Guarantee */}
          <div className="lg:col-span-5 space-y-4 lg:sticky lg:top-24">
            
            {/* Active Tier Inspector Card */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 backdrop-blur-md shadow-xl space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <span className="text-xs font-mono uppercase tracking-wider text-slate-400">
                  Active Tier Provenance Inspector
                </span>
                <span className="text-xs font-mono text-orange-400 font-bold">
                  {TIERS.find((t) => t.id === selectedTier)?.sourceBadge}
                </span>
              </div>

              <div>
                <h4 className="text-lg font-bold text-white">
                  {TIERS.find((t) => t.id === selectedTier)?.name}
                </h4>
                <p className="text-xs sm:text-sm text-slate-300 mt-1 leading-relaxed">
                  {TIERS.find((t) => t.id === selectedTier)?.description}
                </p>
              </div>

              <div className="space-y-2 rounded-xl bg-slate-950 p-4 border border-slate-800 font-mono text-xs">
                <div className="flex justify-between text-slate-400">
                  <span>Engine Layer:</span>
                  <span className="text-slate-200">app/services/qna_engine/</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Audit Tag:</span>
                  <span className="text-cyan-400">{TIERS.find((t) => t.id === selectedTier)?.sourceBadge}</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Confidence Threshold:</span>
                  <span className="text-emerald-400">Deterministic (100%)</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>SQLite Ledger:</span>
                  <span className="text-amber-400">application_answers table</span>
                </div>
              </div>

              <div className="rounded-xl bg-slate-950/60 p-3.5 border border-slate-800/80">
                <span className="text-[11px] font-mono text-slate-400 block mb-1">Audit Trail Payload:</span>
                <code className="text-[11px] font-mono text-emerald-400 break-all">
                  &#123; "tier": "{TIERS.find((t) => t.id === selectedTier)?.tierNumber}", "provenance": "{TIERS.find((t) => t.id === selectedTier)?.sourceBadge}", "value": "{TIERS.find((t) => t.id === selectedTier)?.example}" &#125;
                </code>
              </div>
            </div>

            {/* Zero Hallucination Guarantee Callout */}
            <div className="rounded-xl border border-amber-900/40 bg-amber-950/20 p-4 sm:p-5 flex items-start gap-3 text-xs sm:text-sm text-amber-300">
              <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
              <p>
                <strong>Zero Hallucination Guarantee:</strong> If an application requires a mandatory answer that cannot be proven by Tiers 1-4, JobPilot automatically triggers a <strong>Human Checkpoint Dialog</strong> on your desktop. It never invents certifications, dates, or contact info.
              </p>
            </div>

          </div>

        </div>

      </div>
    </section>
  );
}
