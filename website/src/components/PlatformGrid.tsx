"use client";

import React, { useState } from "react";
import { CheckCircle2, Clock, Globe, Shield, Cpu, ExternalLink, ArrowRight, Layers, Sparkles } from "lucide-react";

interface PlatformItem {
  id: string;
  name: string;
  brandColor: string;
  badge: "Verified Operational" | "Beta Integration";
  badgeType: "verified" | "beta";
  summary: string;
  metrics: string;
  capabilities: string[];
}

const JOB_PORTALS: PlatformItem[] = [
  {
    id: "linkedin",
    name: "LinkedIn",
    brandColor: "#0a66c2",
    badge: "Verified Operational",
    badgeType: "verified",
    summary: "Automated search, Easy Apply workflow, job status parsing, and rate-limited submission.",
    metrics: "Easy Apply • Cookie Session",
    capabilities: ["Pre-flight safety gate", "Rate-limit pacing", "Status tracker"],
  },
  {
    id: "naukri",
    name: "Naukri",
    brandColor: "#0078db",
    badge: "Verified Operational",
    badgeType: "verified",
    summary: "Multi-parameter job search, direct apply flow, questionnaire mapping, and quota monitoring.",
    metrics: "Direct Apply • Daily Quota",
    capabilities: ["Questionnaire resolver", "Quota monitor", "Diagnostic logging"],
  },
  {
    id: "indeed",
    name: "Indeed",
    brandColor: "#2164f4",
    badge: "Verified Operational",
    badgeType: "verified",
    summary: "Intelligent job discovery, form analyzer, multi-step application handling, and checkpoint pauses.",
    metrics: "Multi-Step • Form Analyzer",
    capabilities: ["Input classifier", "Pagination recovery", "Resume injector"],
  },
  {
    id: "glassdoor",
    name: "Glassdoor",
    brandColor: "#0caa41",
    badge: "Verified Operational",
    badgeType: "verified",
    summary: "Discovery and application detection engine with integrated modal recovery and review parsing.",
    metrics: "Modal Recovery • Safe Submit",
    capabilities: ["Popup manager", "Page classifier", "Safe submission"],
  },
  {
    id: "foundit",
    name: "Foundit (Monster)",
    brandColor: "#8b5cf6",
    badge: "Beta Integration",
    badgeType: "beta",
    summary: "Job discovery and apply adapter currently undergoing community testing and calibration.",
    metrics: "Beta Telemetry • Testing",
    capabilities: ["Session checker", "Search parser", "Continuous calibration"],
  },
];

const ENTERPRISE_ATS: PlatformItem[] = [
  {
    id: "greenhouse",
    name: "Greenhouse",
    brandColor: "#00b171",
    badge: "Verified Operational",
    badgeType: "verified",
    summary: "Universal Agent parses standard Greenhouse candidate forms, custom screening questions, and uploads.",
    metrics: "Universal State Machine",
    capabilities: ["Field-to-fact mapping", "Multi-questionnaire support", "Cover letter injection"],
  },
  {
    id: "lever",
    name: "Lever",
    brandColor: "#f26522",
    badge: "Verified Operational",
    badgeType: "verified",
    summary: "Seamless single-page and multi-page application processing with automatic resume parsing detection.",
    metrics: "Single-Page Fast Apply",
    capabilities: ["Custom questions", "Instant parsing check", "Deterministic input match"],
  },
  {
    id: "workday",
    name: "Workday",
    brandColor: "#f58220",
    badge: "Verified Operational",
    badgeType: "verified",
    summary: "Multi-stage enterprise application tracking with iframe navigation and account-session retention.",
    metrics: "Iframe Boundary Resolver",
    capabilities: ["Multi-stage step navigation", "Cross-origin frame traversal", "Field validation recovery"],
  },
  {
    id: "ashby",
    name: "Ashby",
    brandColor: "#6366f1",
    badge: "Verified Operational",
    badgeType: "verified",
    summary: "Modern ATS form analyzer handling nested inputs, reactive schemas, and interactive validation.",
    metrics: "Reactive Form Engine",
    capabilities: ["Dynamic input detection", "Interactive validation", "Instant submission audit"],
  },
];

function PlatformCard({ item }: { item: PlatformItem }) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="relative rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6 transition-all duration-300 flex flex-col justify-between overflow-hidden backdrop-blur-md hover:border-slate-700 hover:bg-slate-900 shadow-lg group h-full min-h-[265px]"
      style={{
        boxShadow: isHovered ? `0 0 25px ${item.brandColor}18` : undefined,
        borderColor: isHovered ? `${item.brandColor}60` : undefined,
      }}
    >
      {/* Brand Ambient Glow Sheen */}
      <div
        className="absolute inset-0 pointer-events-none transition-opacity duration-300"
        style={{
          opacity: isHovered ? 0.08 : 0,
          background: `radial-gradient(ellipse at top right, ${item.brandColor}, transparent 70%)`,
        }}
      />

      {/* Top Header: Brand Name + Status Badge */}
      <div className="flex-1 flex flex-col">
        <div className="flex items-center justify-between gap-2 pb-3 border-b border-slate-800/80">
          <div className="flex items-center gap-2.5 min-w-0">
            <span
              className="h-3 w-3 rounded-full shrink-0 transition-transform group-hover:scale-125"
              style={{
                backgroundColor: item.brandColor,
                boxShadow: `0 0 10px ${item.brandColor}`,
              }}
            />
            <h3 className="font-bold text-white text-base sm:text-lg tracking-tight group-hover:text-slate-100 transition-colors truncate">
              {item.name}
            </h3>
          </div>

          <span
            className={`inline-flex items-center gap-1.5 text-[10px] font-mono px-2 py-0.5 rounded-full border shrink-0 whitespace-nowrap ${
              item.badgeType === "verified"
                ? "border-emerald-500/30 text-emerald-400 bg-emerald-950/40"
                : "border-amber-500/30 text-amber-400 bg-amber-950/40"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                item.badgeType === "verified" ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
              }`}
            />
            <span>{item.badge}</span>
          </span>
        </div>

        {/* Core Summary */}
        <p className="mt-3.5 text-xs sm:text-sm text-slate-300 leading-relaxed font-normal flex-1">
          {item.summary}
        </p>

        {/* Feature Capabilities Pills */}
        <div className="mt-4 flex flex-wrap gap-1.5">
          {item.capabilities.map((cap, i) => (
            <span
              key={i}
              className="text-[10px] font-mono px-2 py-0.5 rounded-md border border-slate-800 bg-slate-950/70 text-slate-400 group-hover:text-slate-300 group-hover:border-slate-700 transition-colors"
            >
              {cap}
            </span>
          ))}
        </div>
      </div>

      {/* Bottom Telemetry Metric */}
      <div className="mt-5 pt-3 border-t border-slate-800/60 flex items-center justify-between gap-2 text-[11px] font-mono text-slate-400 min-w-0">
        <span className="flex items-center gap-1.5 text-slate-400 min-w-0 truncate">
          <Cpu className="h-3.5 w-3.5 text-slate-500 shrink-0" />
          <span className="truncate">{item.metrics}</span>
        </span>
        <span
          className="shrink-0 text-[10px] font-mono font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border whitespace-nowrap"
          style={{
            borderColor: `${item.brandColor}50`,
            color: item.brandColor,
            backgroundColor: `${item.brandColor}15`,
          }}
        >
          Ready
        </span>
      </div>
    </div>
  );
}

export function PlatformGrid() {
  const [activeTab, setActiveTab] = useState<"all" | "portals" | "ats">("all");

  return (
    <section id="platforms" className="py-20 border-t border-slate-800/80 bg-slate-950/70 relative overflow-hidden">
      {/* Background Accent Grid */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.025] bg-[radial-gradient(#ffffff_1px,transparent_1px)] [background-size:24px_24px]" />

      <div className="relative z-10 mx-auto w-full max-w-[1560px] px-4 sm:px-8 lg:px-12">
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-orange-safety/30 bg-orange-safety/10 px-3.5 py-1 text-xs font-mono text-orange-400 backdrop-blur-md">
            <span>MULTI-ENGINE INTEGRATION MATRIX</span>
            <span className="h-1.5 w-1.5 rounded-full bg-orange-safety" />
            <span>9 VERIFIED ADAPTERS</span>
          </div>

          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight leading-tight">
            Supported Platforms &amp; Enterprise ATS Engines
          </h2>

          <p className="text-base sm:text-lg text-slate-300 max-w-2xl mx-auto leading-relaxed">
            Every adapter corresponds to verified automation logic in the JobPilot desktop engine. Zero mock APIs, zero third-party cloud scrapers.
          </p>

          {/* Dual-Deck Category Filter Switcher */}
          <div className="pt-2 flex justify-center w-full">
            <div className="inline-flex flex-wrap sm:flex-nowrap items-center justify-center p-1 rounded-xl bg-slate-900 border border-slate-800 font-mono text-xs shadow-inner max-w-full gap-1">
              <button
                type="button"
                onClick={() => setActiveTab("all")}
                className={`px-3 sm:px-4 py-1.5 rounded-lg transition-all ${
                  activeTab === "all"
                    ? "bg-slate-800 text-white font-semibold shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                All Supported ({JOB_PORTALS.length + ENTERPRISE_ATS.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("portals")}
                className={`px-3 sm:px-4 py-1.5 rounded-lg transition-all ${
                  activeTab === "portals"
                    ? "bg-slate-800 text-white font-semibold shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Job Portals ({JOB_PORTALS.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("ats")}
                className={`px-3 sm:px-4 py-1.5 rounded-lg transition-all ${
                  activeTab === "ats"
                    ? "bg-slate-800 text-white font-semibold shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Enterprise ATS ({ENTERPRISE_ATS.length})
              </button>
            </div>
          </div>
        </div>

        {/* DUAL DECK 1: Public Job Portals (5 Platforms) */}
        {(activeTab === "all" || activeTab === "portals") && (
          <div className="mt-14 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
              <div className="flex items-center gap-2">
                <Globe className="h-4 w-4 text-cyan-400" />
                <h3 className="font-mono text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Major Job Portals &amp; Career Networks
                </h3>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                5 Engines • Real-Time Discovery &amp; Apply
              </span>
            </div>

            {/* 5-Column Balanced Grid (Zero Orphaned Cards) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-5">
              {JOB_PORTALS.map((portal) => (
                <PlatformCard key={portal.id} item={portal} />
              ))}
            </div>
          </div>
        )}

        {/* DUAL DECK 2: Enterprise ATS Systems (4 Platforms) */}
        {(activeTab === "all" || activeTab === "ats") && (
          <div className="mt-14 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
              <div className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-orange-safety" />
                <h3 className="font-mono text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Enterprise Applicant Tracking Systems (ATS)
                </h3>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                Universal Agent State Machine • Iframe Traversals
              </span>
            </div>

            {/* 4-Column Balanced Grid (Zero Orphaned Cards) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {ENTERPRISE_ATS.map((ats) => (
                <PlatformCard key={ats.id} item={ats} />
              ))}
            </div>
          </div>
        )}

        {/* Bottom Local Verification Callout */}
        <div className="mt-12 rounded-2xl border border-slate-800/90 bg-slate-900/40 p-5 flex flex-col sm:flex-row items-center justify-between gap-4 font-mono text-xs text-slate-400">
          <div className="flex items-center gap-3">
            <Shield className="h-5 w-5 text-emerald-400 shrink-0" />
            <p className="text-slate-300">
              <strong className="text-white">Deterministic Execution:</strong> All 9 platform automations run through local browser sessions using your master candidate profile. Credentials never leave your machine.
            </p>
          </div>
          <a
            href="#automation-demos"
            className="shrink-0 text-orange-400 hover:text-orange-300 flex items-center gap-1.5 font-semibold transition-colors"
          >
            <span>Watch Live Demos</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </a>
        </div>

      </div>
    </section>
  );
}
