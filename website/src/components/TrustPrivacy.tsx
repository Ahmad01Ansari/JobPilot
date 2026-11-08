"use client";

import React from "react";
import { Shield, Lock, EyeOff, FileText, AlertOctagon, Cpu } from "lucide-react";

interface TrustItem {
  icon: React.ElementType;
  title: string;
  description: string;
}

const TRUST_ITEMS: TrustItem[] = [
  {
    icon: Lock,
    title: "100% Local SQLite Architecture",
    description:
      "All candidate profiles, resume variants, job records, and outreach logs live in a local SQLite database on your computer. There is no remote central cloud database storing your career data.",
  },
  {
    icon: Shield,
    title: "Encrypted Credential Vault",
    description:
      "Platform passwords and session cookies are securely stored using OS-native keyrings and cryptographic key derivation. Secrets are never transmitted to external servers or logged.",
  },
  {
    icon: AlertOctagon,
    title: "Mandatory Human CAPTCHA Handling",
    description:
      "JobPilot does not use automated CAPTCHA solvers or fingerprint evasion bypasses. Whenever a platform displays a verification challenge, automation safely pauses for you to complete it.",
  },
  {
    icon: EyeOff,
    title: "Zero Remote Telemetry & Tracking",
    description:
      "We believe your job search is strictly personal. The desktop application has zero telemetry beacons, third-party analytics trackers, or user behavioral tracking scripts.",
  },
  {
    icon: FileText,
    title: "Sanitized Diagnostic Logs",
    description:
      "All logs pass through automated sanitization filters before being written to disk, ensuring sensitive tokens, auth headers, and passwords are permanently stripped.",
  },
  {
    icon: Cpu,
    title: "Deterministic Non-Hallucinatory Q&A",
    description:
      "Candidate facts originate solely from verified sources (Profile Fact, Resume Fact, or Approved Q&A Rule). JobPilot never allows an LLM to hallucinate false candidate metrics.",
  },
];

export function TrustPrivacy() {
  return (
    <section id="privacy" className="py-20 border-t border-obsidian-border bg-obsidian">
      <div className="mx-auto w-full max-w-[1560px] px-4 sm:px-8 lg:px-12">
        
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3.5 py-1 text-xs font-mono text-emerald-400">
            SECURITY & PRIVACY CONSTITUTION
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Built for Privacy. Designed for Trust.
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            Most career tools operate as cloud SaaS platforms where your resume, job applications, and personal data are stored on third-party servers. JobPilot operates entirely on your desktop machine.
          </p>
        </div>

        {/* 6-box Trust Matrix */}
        <div className="mt-14 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {TRUST_ITEMS.map((item, index) => {
            const Icon = item.icon;
            return (
              <div
                key={index}
                className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 flex flex-col justify-between hover:border-slate-700 transition-colors"
              >
                <div>
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-800/80 text-emerald-400 mb-5">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-base font-bold text-white mb-2">{item.title}</h3>
                  <p className="text-sm text-slate-300 leading-relaxed">
                    {item.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

      </div>
    </section>
  );
}

