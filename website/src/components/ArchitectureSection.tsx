"use client";

import React, { useState } from "react";
import { Layers, Database, Cpu, Shield, ChevronDown, CheckCircle2, Lock, Terminal } from "lucide-react";

interface FAQItem {
  q: string;
  a: string;
}

const FAQS: FAQItem[] = [
  {
    q: "How does JobPilot protect my private resume and portal passwords?",
    a: "JobPilot is 100% local-first. All candidate records, resume variants, and job logs are stored in an encrypted SQLite database on your computer. Credentials and portal session cookies are stored in your operating system's native secure keyring (Windows Credential Manager / Linux Secret Service). No credentials are ever sent to cloud servers.",
  },
  {
    q: "Does JobPilot bypass CAPTCHAs or platform security protections?",
    a: "No. JobPilot strictly abides by a zero automated CAPTCHA bypass policy. Whenever an anti-bot challenge (such as Cloudflare Turnstile or hCaptcha) appears, the automation engine safely enters a Human Checkpoint pause, allowing you to solve it manually in the browser before resuming.",
  },
  {
    q: "How does the 5-Tier Q&A engine prevent AI hallucinations?",
    a: "JobPilot enforces a strict priority cascade: Profile Facts → Resume Facts → Pre-Approved Q&A Rules → Mathematical Calculations → Constrained LLM. If an answer cannot be proven by your master candidate facts, automation halts for your review rather than inventing false certifications or years of experience.",
  },
  {
    q: "What are the minimum system requirements for Windows and Linux?",
    a: "JobPilot requires a 64-bit operating system (Ubuntu 20.04+, Debian 11+, Fedora 36+, or Windows 10/11) and Google Chrome or Chromium installed for browser automation. The standalone executable and AppImage bundles include all required Python and Qt runtime libraries.",
  },
  {
    q: "How does JobPilot avoid freezing the desktop user interface during scraping?",
    a: "All browser automations, network requests, and database queries execute in background worker threads (QThread / TaskRunner pool). The main Qt GUI thread only listens to signals and updates UI cards, ensuring 60fps responsiveness throughout multi-hour automation sessions.",
  },
];

export function ArchitectureSection() {
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0);

  return (
    <section id="architecture" className="py-20 border-t border-slate-800 bg-slate-950/70 backdrop-blur-[1px]">
      <div className="mx-auto w-full max-w-[1560px] px-4 sm:px-8 lg:px-12 space-y-16">
        
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-pilot/30 bg-cyan-pilot/10 px-3.5 py-1 text-xs font-mono text-cyan-400">
            ENGINEERING SPECIFICATION & FAQ
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            System Architecture & Deep Dive
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            Understand how JobPilot achieves reliable desktop performance through strict layer boundaries, thread safety, and defensive security.
          </p>
        </div>

        {/* 4 Architectural Layers */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-3">
            <div className="text-[10px] font-mono text-cyan-400 uppercase font-bold">Layer 1</div>
            <h3 className="text-base font-bold text-white">Presentation (UI)</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              PySide6 desktop views. Communicates purely via Service calls and Qt signals. Never accesses SQLite sessions or browser drivers directly.
            </p>
            <div className="text-[11px] font-mono text-slate-500 pt-2 border-t border-slate-800">
              app/ui/views/
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-3">
            <div className="text-[10px] font-mono text-orange-400 uppercase font-bold">Layer 2</div>
            <h3 className="text-base font-bold text-white">Domain Services</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Coordinates Q&A derivation, profile fact aggregation, and thread management with cooperative cancellation flags.
            </p>
            <div className="text-[11px] font-mono text-slate-500 pt-2 border-t border-slate-800">
              app/services/
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-3">
            <div className="text-[10px] font-mono text-emerald-400 uppercase font-bold">Layer 3</div>
            <h3 className="text-base font-bold text-white">Automation Engines</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Universal ATS state machine and platform adapters. Isolated in worker QThreads to keep the GUI fluid and responsive.
            </p>
            <div className="text-[11px] font-mono text-slate-500 pt-2 border-t border-slate-800">
              platforms/ & universal_agent/
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-3">
            <div className="text-[10px] font-mono text-purple-400 uppercase font-bold">Layer 4</div>
            <h3 className="text-base font-bold text-white">Local Vault</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Local SQLite with WAL mode and 30s busy timeouts. Passwords stored in OS keyrings. Sanitized diagnostics on disk.
            </p>
            <div className="text-[11px] font-mono text-slate-500 pt-2 border-t border-slate-800">
              app/db/ & SecretsService
            </div>
          </div>
        </div>

        {/* FAQ Accordion Section */}
        <div className="max-w-5xl mx-auto space-y-4 pt-6">
          <div className="text-xs font-mono uppercase tracking-wider text-slate-400 text-center pb-2">
            Frequently Asked Questions
          </div>

          {FAQS.map((faq, i) => {
            const isOpen = openFaqIndex === i;
            return (
              <div
                key={i}
                className="rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden transition-colors"
              >
                <button
                  onClick={() => setOpenFaqIndex(isOpen ? null : i)}
                  className="w-full p-5 text-left flex items-center justify-between gap-4 font-bold text-sm sm:text-base text-white hover:text-orange-400 transition-colors"
                >
                  <span>{faq.q}</span>
                  <ChevronDown
                    className={`h-4 w-4 text-slate-400 transition-transform shrink-0 ${
                      isOpen ? "rotate-180 text-orange-safety" : ""
                    }`}
                  />
                </button>
                {isOpen && (
                  <div className="px-5 pb-5 text-xs sm:text-sm text-slate-300 leading-relaxed border-t border-slate-800/80 pt-3">
                    {faq.a}
                  </div>
                )}
              </div>
            );
          })}
        </div>

      </div>
    </section>
  );
}

