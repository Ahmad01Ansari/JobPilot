"use client";

import React, { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Download, Menu, X, Zap, Github } from "lucide-react";

export function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const GITHUB_REPO = "https://github.com/Ahmad01Ansari/JobPilot";

  return (
    <header className="sticky top-0 z-50 w-full border-b border-obsidian-border bg-obsidian/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand Logo & Version Pill */}
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2.5 transition-opacity hover:opacity-90">
            <Image
              src="/brand/jobpilot-symbol-color.svg"
              alt="JobPilot Mascot Icon"
              width={34}
              height={34}
              priority
              className="drop-shadow-[0_0_12px_rgba(255,95,21,0.3)]"
            />
            <span className="font-sans text-xl font-bold tracking-tight text-white">
              Job<span className="text-orange-safety">Pilot</span>
            </span>
          </Link>
          <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-orange-safety/30 bg-orange-safety/10 px-2.5 py-0.5 text-xs font-mono font-medium text-orange-400">
            <span className="h-1.5 w-1.5 rounded-full bg-orange-safety animate-pulse" />
            v0.4.5-beta
          </span>
        </div>

        {/* Desktop Single-Page Nav Links */}
        <nav className="hidden lg:flex items-center gap-6 text-sm font-medium text-slate-300">
          <Link
            href="#automation-demos"
            className="text-orange-400 hover:text-orange-300 flex items-center gap-1.5 font-semibold transition-colors"
          >
            <Zap className="h-4 w-4 text-orange-safety" />
            <span>Automation Demos</span>
          </Link>
          <Link href="#showcase" className="transition-colors hover:text-white">
            Desktop UI
          </Link>
          <Link href="#workflow" className="transition-colors hover:text-white">
            Workflow
          </Link>
          <Link href="#platforms" className="transition-colors hover:text-white">
            Platforms
          </Link>
          <Link href="#privacy" className="transition-colors hover:text-white">
            Privacy Vault
          </Link>
          <Link href="#architecture" className="transition-colors hover:text-white">
            Architecture
          </Link>
          <Link href="#downloads" className="transition-colors hover:text-white">
            Downloads
          </Link>
        </nav>

        {/* Action CTAs */}
        <div className="hidden sm:flex items-center gap-3">
          <a
            href={GITHUB_REPO}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900/80 px-3.5 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition-all"
          >
            <Github className="h-4 w-4" />
            <span className="hidden md:inline">GitHub</span>
          </a>

          <Link
            href="#downloads"
            className="flex items-center gap-2 rounded-lg bg-orange-safety px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all hover:bg-orange-hover hover:shadow-orange-safety/25 hover:shadow-lg active:scale-95"
          >
            <Download className="h-4 w-4" />
            <span>Download Beta</span>
          </Link>
        </div>

        {/* Mobile menu button */}
        <div className="flex lg:hidden">
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="inline-flex items-center justify-center rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white focus:outline-none focus:ring-2 focus:ring-orange-safety"
            aria-expanded={mobileMenuOpen}
          >
            <span className="sr-only">Toggle navigation menu</span>
            {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-b border-obsidian-border bg-obsidian-surface px-4 py-4 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-slate-700/50">
            <span className="text-xs font-mono text-slate-400">STATUS: PRIVATE BETA</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-orange-safety/10 px-2 py-0.5 text-xs font-mono text-orange-400">
              v0.4.5-beta
            </span>
          </div>
          <Link
            href="#automation-demos"
            onClick={() => setMobileMenuOpen(false)}
            className="flex items-center gap-2 text-sm font-semibold text-orange-400 hover:text-orange-300 py-1"
          >
            <Zap className="h-4 w-4" />
            Automation Demos
          </Link>
          <Link
            href="#showcase"
            onClick={() => setMobileMenuOpen(false)}
            className="block text-sm font-medium text-slate-300 hover:text-white py-1"
          >
            Desktop UI
          </Link>
          <Link
            href="#workflow"
            onClick={() => setMobileMenuOpen(false)}
            className="block text-sm font-medium text-slate-300 hover:text-white py-1"
          >
            Autonomous Workflow
          </Link>
          <Link
            href="#platforms"
            onClick={() => setMobileMenuOpen(false)}
            className="block text-sm font-medium text-slate-300 hover:text-white py-1"
          >
            Supported Platforms
          </Link>
          <Link
            href="#privacy"
            onClick={() => setMobileMenuOpen(false)}
            className="block text-sm font-medium text-slate-300 hover:text-white py-1"
          >
            Local-First Privacy
          </Link>
          <Link
            href="#architecture"
            onClick={() => setMobileMenuOpen(false)}
            className="block text-sm font-medium text-slate-300 hover:text-white py-1"
          >
            System Architecture & FAQ
          </Link>
          <Link
            href="#downloads"
            onClick={() => setMobileMenuOpen(false)}
            className="block text-sm font-medium text-slate-300 hover:text-white py-1"
          >
            Download Releases
          </Link>
          <div className="pt-2 flex flex-col gap-2">
            <Link
              href="#downloads"
              onClick={() => setMobileMenuOpen(false)}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-orange-safety py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-orange-hover"
            >
              <Download className="h-4 w-4" />
              Download JobPilot
            </Link>
            <a
              href={GITHUB_REPO}
              target="_blank"
              rel="noreferrer"
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-800 py-2 text-sm font-medium text-slate-300 hover:text-white"
            >
              <Github className="h-4 w-4" />
              GitHub Repository
            </a>
          </div>
        </div>
      )}
    </header>
  );
}
