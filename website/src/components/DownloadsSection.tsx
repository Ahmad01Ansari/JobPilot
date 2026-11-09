"use client";

import React from "react";
import Image from "next/image";
import { Download, CheckCircle2, ExternalLink } from "lucide-react";

// Official Microsoft Windows 4-Pane Vector Icon
function WindowsOfficialIcon({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg
      role="img"
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.551H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.949-1.801" />
    </svg>
  );
}

export function DownloadsSection() {
  const RELEASES_URL = "https://github.com/Ahmad01Ansari/JobPilot/releases";

  return (
    <section id="downloads" className="py-20 border-t border-slate-800 bg-slate-950/70 backdrop-blur-[1px]">
      <div className="mx-auto w-full max-w-[1560px] px-4 sm:px-8 lg:px-12">
        
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-orange-safety/30 bg-orange-safety/10 px-3.5 py-1 text-xs font-mono text-orange-400">
            OFFICIAL DESKTOP DISTRIBUTION
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Download JobPilot for Windows &amp; Linux
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            Verified release packages for both Windows and Linux are distributed through our official GitHub Releases repository. Pick your platform package below.
          </p>
        </div>

        {/* Release Cards Grid */}
        <div className="mt-14 grid grid-cols-1 md:grid-cols-2 gap-8 max-w-6xl mx-auto">
          
          {/* Card 1: Linux Releases (Featuring Official Tux Penguin) */}
          <div className="rounded-2xl border border-slate-700 bg-slate-900/80 p-7 flex flex-col justify-between shadow-xl relative overflow-hidden group hover:border-orange-500/60 transition-all duration-300">
            <div className="absolute top-0 right-0 px-4 py-1.5 bg-emerald-950/80 border-b border-l border-emerald-800 text-[11px] font-mono text-emerald-400 font-semibold rounded-bl-xl">
              RELEASED
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="h-12 w-12 rounded-xl bg-orange-safety/15 border border-orange-safety/30 flex items-center justify-center p-1.5 group-hover:scale-105 transition-transform shadow-inner">
                  <Image
                    src="/brand/linux-tux.svg"
                    alt="Linux Tux Penguin"
                    width={36}
                    height={36}
                    className="w-auto h-8 drop-shadow-md select-none"
                    priority
                  />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white flex items-center gap-2">
                    Linux (x86_64)
                  </h3>
                  <p className="text-xs font-mono text-slate-400">AppImage, .deb, tar.gz</p>
                </div>
              </div>

              <div className="space-y-2 text-xs font-mono bg-obsidian p-3.5 rounded-xl border border-slate-800">
                <div className="flex justify-between text-slate-400">
                  <span>PACKAGES:</span>
                  <span className="text-slate-200">AppImage (137 MB) &amp; .deb (116 MB)</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>OS SUPPORT:</span>
                  <span className="text-slate-200">Ubuntu 20.04+, Debian 11+, Fedora 36+</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>ARCHITECTURE:</span>
                  <span className="text-slate-200">x86_64 / amd64</span>
                </div>
              </div>

              <ul className="space-y-1.5 text-xs text-slate-300">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                  <span>Includes offline SQLite WAL engine and local vault</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                  <span>Automated Selenium Chrome/Chromium profile pairing</span>
                </li>
              </ul>
            </div>

            <div className="mt-7 pt-5 border-t border-slate-800 space-y-2">
              <a
                href={RELEASES_URL}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-center gap-2 rounded-xl bg-orange-safety py-3 text-sm font-semibold text-white shadow-md hover:bg-orange-hover transition-colors"
              >
                <Download className="h-4 w-4" />
                <span>Download Linux Package on GitHub</span>
              </a>
              <p className="text-center text-[11px] font-mono text-slate-500">
                Direct release assets &amp; SHA-256 checksums available in release tag.
              </p>
            </div>
          </div>

          {/* Card 2: Windows Releases */}
          <div className="rounded-2xl border border-slate-700 bg-slate-900/80 p-7 flex flex-col justify-between shadow-xl relative overflow-hidden group hover:border-cyan-500/60 transition-all duration-300">
            <div className="absolute top-0 right-0 px-4 py-1.5 bg-cyan-950/80 border-b border-l border-cyan-800 text-[11px] font-mono text-cyan-400 font-semibold rounded-bl-xl">
              RELEASED
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="h-12 w-12 rounded-xl bg-cyan-pilot/15 border border-cyan-pilot/30 flex items-center justify-center text-cyan-400 group-hover:scale-105 transition-transform shadow-inner">
                  <WindowsOfficialIcon className="h-6 w-6 text-cyan-400 drop-shadow-md" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white flex items-center gap-2">
                    Windows (x64)
                  </h3>
                  <p className="text-xs font-mono text-slate-400">Inno Setup Installer &amp; Portable Exe</p>
                </div>
              </div>

              <div className="space-y-2 text-xs font-mono bg-obsidian p-3.5 rounded-xl border border-slate-800">
                <div className="flex justify-between text-slate-400">
                  <span>PACKAGES:</span>
                  <span className="text-slate-200">Setup Wizard (.exe) &amp; Portable Zip</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>OS SUPPORT:</span>
                  <span className="text-slate-200">Windows 10 / Windows 11 (64-bit)</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>SCALING:</span>
                  <span className="text-slate-200">125% / 150% High-DPI Certified</span>
                </div>
              </div>

              <ul className="space-y-1.5 text-xs text-slate-300">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-cyan-400 shrink-0" />
                  <span>Native Windows taskbar and system tray integration</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-cyan-400 shrink-0" />
                  <span>Windows Credential Manager secrets protection</span>
                </li>
              </ul>
            </div>

            <div className="mt-7 pt-5 border-t border-slate-800 space-y-2">
              <a
                href={RELEASES_URL}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-center gap-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 py-3 text-sm font-semibold text-white shadow-md transition-colors"
              >
                <Download className="h-4 w-4" />
                <span>Download Windows Package on GitHub</span>
              </a>
              <p className="text-center text-[11px] font-mono text-slate-500">
                Grab both Windows and Linux release artifacts from the same release tag.
              </p>
            </div>
          </div>

        </div>

        {/* Global Release Hub Footer Callout */}
        <div className="mt-12 text-center">
          <a
            href={RELEASES_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 text-sm font-mono text-slate-400 hover:text-white transition-colors"
          >
            <span>View All Released Tags & Artifacts on GitHub</span>
            <ExternalLink className="h-3.5 w-3.5 text-orange-safety" />
          </a>
        </div>

      </div>
    </section>
  );
}
