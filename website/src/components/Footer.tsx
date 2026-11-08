"use client";

import React from "react";
import Image from "next/image";
import Link from "next/link";
import { Terminal, Shield, Github, Download, Zap } from "lucide-react";

export function Footer() {
  const GITHUB_REPO = "https://github.com/Ahmad01Ansari/JobPilot";
  const GITHUB_RELEASES = "https://github.com/Ahmad01Ansari/JobPilot/releases";

  return (
    <footer className="relative z-20 border-t border-slate-800 bg-slate-950 py-14">
      <div className="mx-auto w-full max-w-[1560px] px-4 sm:px-8 lg:px-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 pb-12 border-b border-slate-800">
          
          {/* Brand Info */}
          <div className="md:col-span-2 space-y-4">
            <div className="flex items-center gap-2.5">
              <Image
                src="/brand/jobpilot-symbol-color.svg"
                alt="JobPilot Mascot Icon"
                width={32}
                height={32}
              />
              <span className="font-sans text-xl font-bold tracking-tight text-white">
                Job<span className="text-orange-safety">Pilot</span>
              </span>
            </div>
            <p className="max-w-md text-sm text-slate-400 leading-relaxed">
              Autonomous career discovery and application cockpit. Built with Python and PySide6 for local-first privacy, deterministic Q&A resolution, and human-verified automation.
            </p>
            <div className="flex items-center gap-3 text-xs font-mono text-slate-500 pt-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span>CORE v0.4.5-beta</span>
              <span>•</span>
              <span>CHANNEL: private-beta</span>
            </div>
          </div>

          {/* Product Links */}
          <div className="space-y-3">
            <div className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold">
              On-Page Sections
            </div>
            <ul className="space-y-2 text-sm text-slate-400">
              <li>
                <Link href="#automation-demos" className="hover:text-white transition-colors text-orange-400 font-medium flex items-center gap-1.5">
                  <Zap className="h-3.5 w-3.5" />
                  <span>Automation Demos</span>
                </Link>
              </li>
              <li>
                <Link href="#showcase" className="hover:text-white transition-colors">
                  Desktop UI Showcase
                </Link>
              </li>
              <li>
                <Link href="#workflow" className="hover:text-white transition-colors">
                  Autonomous Flow
                </Link>
              </li>
              <li>
                <Link href="#platforms" className="hover:text-white transition-colors">
                  Supported Platforms
                </Link>
              </li>
              <li>
                <Link href="#downloads" className="hover:text-white transition-colors">
                  Desktop Releases
                </Link>
              </li>
            </ul>
          </div>

          {/* Engineering & Trust Links */}
          <div className="space-y-3">
            <div className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold">
              Trust & Source
            </div>
            <ul className="space-y-2 text-sm text-slate-400">
              <li>
                <Link href="#architecture" className="hover:text-white transition-colors">
                  Local-First Security
                </Link>
              </li>
              <li>
                <Link href="#architecture" className="hover:text-white transition-colors">
                  System Architecture & FAQ
                </Link>
              </li>
              <li>
                <a
                  href={GITHUB_REPO}
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-white transition-colors flex items-center gap-1.5"
                >
                  <Github className="h-3.5 w-3.5" />
                  <span>GitHub Repository</span>
                </a>
              </li>
              <li>
                <a
                  href={GITHUB_RELEASES}
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-white transition-colors flex items-center gap-1.5 text-orange-400"
                >
                  <Download className="h-3.5 w-3.5" />
                  <span>Download Windows & Linux</span>
                </a>
              </li>
            </ul>
          </div>

        </div>

        {/* Bottom Attribution */}
        <div className="pt-8 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-4">
          <p>© {new Date().getFullYear()} JobPilot Project. All rights reserved.</p>
          <div className="flex items-center gap-4">
            <Link href="#architecture" className="hover:underline">Privacy &amp; Security</Link>
            <span className="font-mono text-slate-600">•</span>
            <span className="font-mono">
              Designed for Desktop Reliability
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
