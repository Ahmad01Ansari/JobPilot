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

// Official Apple Vector Icon
function AppleOfficialIcon({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg
      role="img"
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 4.54c.67-.82 1.13-1.96 1.01-3.1-.98.04-2.16.65-2.86 1.47-.62.72-1.16 1.88-1.02 2.99 1.1.08 2.2-.55 2.87-1.36" />
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
            Download JobPilot for Windows, macOS &amp; Linux
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            Verified release packages for Windows, macOS, and Linux are distributed through our official GitHub Releases repository. Pick your platform package below.
          </p>
        </div>

        {/* Release Cards Grid */}
        <div className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-6 max-w-7xl mx-auto">
          
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
                Direct release assets &amp; SHA-256 checksums available in release tag.
              </p>
            </div>
          </div>

          {/* Card 3: macOS Releases */}
          <div className="rounded-2xl border border-slate-700 bg-slate-900/80 p-7 flex flex-col justify-between shadow-xl relative overflow-hidden group hover:border-violet-500/60 transition-all duration-300">
            <div className="absolute top-0 right-0 px-4 py-1.5 bg-violet-950/80 border-b border-l border-violet-800 text-[11px] font-mono text-violet-400 font-semibold rounded-bl-xl">
              RELEASED
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="h-12 w-12 rounded-xl bg-violet-500/15 border border-violet-500/30 flex items-center justify-center text-violet-300 group-hover:scale-105 transition-transform shadow-inner">
                  <AppleOfficialIcon className="h-6 w-6 text-violet-300 drop-shadow-md" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white flex items-center gap-2">
                    macOS (Apple Silicon &amp; Intel)
                  </h3>
                  <p className="text-xs font-mono text-slate-400">DMG Disk Image &amp; Portable Zip</p>
                </div>
              </div>

              <div className="space-y-2 text-xs font-mono bg-obsidian p-3.5 rounded-xl border border-slate-800">
                <div className="flex justify-between text-slate-400">
                  <span>PACKAGES:</span>
                  <span className="text-slate-200">.dmg Drag-to-Apps &amp; .zip</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>OS SUPPORT:</span>
                  <span className="text-slate-200">macOS 11.0+ (Ventura, Sonoma, Sequoia)</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>ARCHITECTURE:</span>
                  <span className="text-slate-200">Apple Silicon (arm64) &amp; Intel (x86_64)</span>
                </div>
              </div>

              <ul className="space-y-1.5 text-xs text-slate-300">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-violet-400 shrink-0" />
                  <span>Native Cocoa backend, Retina scaling &amp; dark mode</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-violet-400 shrink-0" />
                  <span>Encrypted local SQLite vault &amp; macOS Chrome automation</span>
                </li>
              </ul>
            </div>

            <div className="mt-7 pt-5 border-t border-slate-800 space-y-2">
              <a
                href={RELEASES_URL}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-center gap-2 rounded-xl bg-violet-600 hover:bg-violet-500 py-3 text-sm font-semibold text-white shadow-md transition-colors"
              >
                <Download className="h-4 w-4" />
                <span>Download macOS Package on GitHub</span>
              </a>
              <p className="text-center text-[11px] font-mono text-slate-500">
                Direct release assets &amp; SHA-256 checksums available in release tag.
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
