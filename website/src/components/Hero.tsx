"use client";

import React from "react";
import Link from "next/link";
import { Download, Terminal, ShieldCheck, ChevronRight, Cpu, Zap } from "lucide-react";

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-12 pb-20 lg:pt-20 lg:pb-28">
      {/* Background Cockpit Grid */}
      <div className="absolute inset-0 cockpit-grid opacity-60 pointer-events-none" />
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-orange-safety/10 blur-[120px] rounded-full pointer-events-none" />
      <div className="absolute top-1/3 right-10 w-[400px] h-[300px] bg-cyan-pilot/10 blur-[120px] rounded-full pointer-events-none" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          
          {/* Left Column: Core Value Proposition */}
          <div className="lg:col-span-7 space-y-6 text-center lg:text-left">
            {/* Pill */}
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-obsidian-surface/80 px-3.5 py-1.5 text-xs font-mono text-slate-300 backdrop-blur-md">
              <span className="flex h-2 w-2 rounded-full bg-cyan-pilot" />
              <span>DESKTOP AUTONOMOUS COCKPIT</span>
              <span className="text-slate-600">•</span>
              <span className="text-orange-400 font-semibold">LOCAL-FIRST</span>
            </div>

            {/* Headline */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white leading-[1.1]">
              Your career. <br />
              <span className="bg-gradient-to-r from-orange-safety via-orange-400 to-amber-300 bg-clip-text text-transparent">
                On autopilot.
              </span>
            </h1>

            {/* Supporting paragraph */}
            <p className="mx-auto lg:mx-0 max-w-2xl text-base sm:text-lg text-slate-300 leading-relaxed">
              Discover opportunities across LinkedIn, Indeed, Glassdoor & Enterprise ATS systems. 
              JobPilot prepares resumes, resolves screening questions with deterministic 5-tier accuracy, 
              and executes verified applications with mandatory human checkpoints.
            </p>

            {/* Dual CTAs */}
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4">
              <Link
                href="#automation-demos"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 rounded-xl bg-orange-safety px-6 py-3.5 text-base font-semibold text-white shadow-lg shadow-orange-safety/20 hover:bg-orange-hover hover:shadow-orange-safety/35 transition-all active:scale-95"
              >
                <Zap className="h-5 w-5" />
                <span>Watch Automation Demos</span>
              </Link>

              <Link
                href="#downloads"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl border border-slate-700 bg-obsidian-surface px-6 py-3.5 text-base font-medium text-slate-200 hover:bg-slate-800 hover:text-white transition-all"
              >
                <Download className="h-4 w-4 text-cyan-pilot" />
                <span>Get Desktop Releases</span>
              </Link>
            </div>

            {/* Trust Badges */}
            <div className="pt-4 flex flex-wrap items-center justify-center lg:justify-start gap-6 text-xs font-mono text-slate-400">
              <div className="flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                <span>100% Local SQLite Vault</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Cpu className="h-4 w-4 text-cyan-pilot" />
                <span>Zero Cloud Telemetry</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Terminal className="h-4 w-4 text-orange-400" />
                <span>Human Review Checkpoints</span>
              </div>
            </div>
          </div>

          {/* Right Column: Pure CSS/SVG Cockpit Radar & Telemetry Display */}
          <div className="lg:col-span-5 flex justify-center">
            <div className="relative w-full max-w-[420px] aspect-square rounded-2xl border border-obsidian-border bg-obsidian-surface/60 p-6 shadow-2xl backdrop-blur-xl flex flex-col justify-between">
              
              {/* Cockpit Header */}
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-ping" />
                  <span className="font-mono text-xs font-bold text-slate-200 uppercase tracking-wider">
                    AUTONOMOUS CORE // ACTIVE
                  </span>
                </div>
                <span className="font-mono text-[11px] text-slate-500">ENGINE v0.4.5</span>
              </div>

              {/* Center Radar Graphic (CSS/SVG Animated) */}
              <div className="relative my-4 flex items-center justify-center">
                {/* Radar Concentric Circles */}
                <div className="relative w-56 h-56 rounded-full border border-slate-800 flex items-center justify-center">
                  <div className="w-40 h-40 rounded-full border border-slate-800/80 flex items-center justify-center">
                    <div className="w-24 h-24 rounded-full border border-orange-safety/30 flex items-center justify-center">
                      <div className="w-3 h-3 rounded-full bg-orange-safety shadow-[0_0_15px_#FF5F15]" />
                    </div>
                  </div>

                  {/* Crosshairs */}
                  <div className="absolute inset-x-0 top-1/2 h-px bg-slate-800/60" />
                  <div className="absolute inset-y-0 left-1/2 w-px bg-slate-800/60" />

                  {/* Rotating Radar Sweep Line */}
                  <div className="absolute inset-0 radar-sweep origin-center pointer-events-none">
                    <div className="w-1/2 h-1/2 bg-gradient-to-br from-orange-safety/25 to-transparent rounded-tl-full" />
                  </div>
                </div>

                {/* Floating Telemetry Badges */}
                <div className="absolute -top-2 -left-2 rounded-lg border border-slate-700/80 bg-obsidian/90 px-3 py-1.5 shadow-lg">
                  <div className="text-[10px] font-mono text-slate-400">TARGET MATCH</div>
                  <div className="text-xs font-mono font-bold text-emerald-400">94.2% FIT</div>
                </div>

                <div className="absolute -bottom-2 -right-2 rounded-lg border border-slate-700/80 bg-obsidian/90 px-3 py-1.5 shadow-lg">
                  <div className="text-[10px] font-mono text-slate-400">PROVENANCE</div>
                  <div className="text-xs font-mono font-bold text-cyan-pilot">PROFILE_FACT</div>
                </div>
              </div>

              {/* Live Telemetry Status Stream */}
              <div className="space-y-1.5 font-mono text-[11px] bg-obsidian/80 rounded-lg p-3 border border-slate-800">
                <div className="flex justify-between text-slate-400">
                  <span>DISCOVERY:</span>
                  <span className="text-slate-200">142 roles ingested</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>UNIVERSAL ATS:</span>
                  <span className="text-emerald-400">Form mapped (Greenhouse)</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>CHECKPOINT:</span>
                  <span className="text-amber-400">Safe Review Confirmed</span>
                </div>
              </div>

            </div>
          </div>

        </div>
      </div>
    </section>
  );
}
