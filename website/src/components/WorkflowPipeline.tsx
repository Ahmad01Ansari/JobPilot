"use client";

import React, { useRef, useEffect, useState } from "react";
import { UserCheck, Search, HelpCircle, Workflow, AlertCircle, Award } from "lucide-react";

// ============================================================================
// SECTION 1 CANVAS: Data Matrix & Neural Node Stream (Steps 01 & 04)
// Local Ingestion & Universal State Machine Flow
// ============================================================================
function DataMatrixCanvas({ isHovered, mousePos }: { isHovered: boolean; mousePos: { x: number; y: number } }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 320);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 260);

    const handleResize = () => {
      if (!canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };
    window.addEventListener("resize", handleResize);

    // Particle nodes
    const nodeCount = 22;
    const nodes = Array.from({ length: nodeCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.45,
      vy: (Math.random() - 0.5) * 0.45,
      r: Math.random() * 2 + 1.5,
    }));

    // Data streams
    const streamColumns = Math.floor(width / 36);
    const streams = Array.from({ length: streamColumns }, (_, i) => ({
      x: i * 36 + 18,
      y: Math.random() * height,
      speed: Math.random() * 1.2 + 0.6,
      chars: ["0", "1", "0x", "λ", "[]", "->"],
    }));

    let frame = 0;
    const render = () => {
      frame++;
      ctx.clearRect(0, 0, width, height);

      const targetOpacity = isHovered ? 0.85 : 0.2;
      const speedMultiplier = isHovered ? 2.5 : 1.0;

      // 1. Vertical data rain
      ctx.font = "9px monospace";
      streams.forEach((s, idx) => {
        s.y += s.speed * speedMultiplier;
        if (s.y > height + 20) {
          s.y = -20;
        }
        const char = s.chars[(frame + idx) % s.chars.length];
        ctx.fillStyle = isHovered ? "rgba(0, 242, 254, 0.45)" : "rgba(56, 189, 248, 0.15)";
        ctx.fillText(char, s.x, s.y);

        if (isHovered && Math.random() > 0.85) {
          ctx.fillStyle = "rgba(255, 255, 255, 0.7)";
          ctx.fillText(char, s.x, s.y);
        }
      });

      // 2. Node network
      nodes.forEach((n, i) => {
        n.x += n.vx * speedMultiplier;
        n.y += n.vy * speedMultiplier;

        if (n.x < 0) n.x = width;
        if (n.x > width) n.x = 0;
        if (n.y < 0) n.y = height;
        if (n.y > height) n.y = 0;

        // Draw connections
        for (let j = i + 1; j < nodes.length; j++) {
          const n2 = nodes[j];
          const dist = Math.hypot(n.x - n2.x, n.y - n2.y);
          if (dist < 85) {
            const alpha = (1 - dist / 85) * (isHovered ? 0.45 : 0.12);
            ctx.strokeStyle = `rgba(0, 242, 254, ${alpha})`;
            ctx.lineWidth = isHovered ? 1.2 : 0.8;
            ctx.beginPath();
            ctx.moveTo(n.x, n.y);
            ctx.lineTo(n2.x, n2.y);
            ctx.stroke();
          }
        }

        // Draw node
        ctx.fillStyle = isHovered ? "#00f2fe" : "#38bdf8";
        ctx.beginPath();
        ctx.arc(n.x, n.y, isHovered ? n.r * 1.3 : n.r, 0, Math.PI * 2);
        ctx.fill();
      });

      // 3. Interactive Mouse Attractor
      if (isHovered && mousePos.x >= 0 && mousePos.y >= 0) {
        // Draw laser threads to nearest nodes
        nodes.forEach((n) => {
          const dist = Math.hypot(mousePos.x - n.x, mousePos.y - n.y);
          if (dist < 110) {
            const alpha = (1 - dist / 110) * 0.75;
            ctx.strokeStyle = `rgba(0, 255, 198, ${alpha})`;
            ctx.lineWidth = 1.4;
            ctx.beginPath();
            ctx.moveTo(mousePos.x, mousePos.y);
            ctx.lineTo(n.x, n.y);
            ctx.stroke();
          }
        });

        // Glowing cursor pulse
        const radGrad = ctx.createRadialGradient(mousePos.x, mousePos.y, 2, mousePos.x, mousePos.y, 45);
        radGrad.addColorStop(0, "rgba(0, 242, 254, 0.45)");
        radGrad.addColorStop(0.5, "rgba(56, 189, 248, 0.18)");
        radGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
        ctx.fillStyle = radGrad;
        ctx.beginPath();
        ctx.arc(mousePos.x, mousePos.y, 45, 0, Math.PI * 2);
        ctx.fill();
      }

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animId);
    };
  }, [isHovered, mousePos]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 h-full w-full pointer-events-none rounded-2xl"
    />
  );
}

// ============================================================================
// SECTION 2 CANVAS: Multi-Portal Sonar Radar Sweep (Steps 02 & 05)
// Discovery Scanner & Human Checkpoint Safety Sweep
// ============================================================================
function RadarScanCanvas({ isHovered, mousePos }: { isHovered: boolean; mousePos: { x: number; y: number } }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 320);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 260);

    const handleResize = () => {
      if (!canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };
    window.addEventListener("resize", handleResize);

    // Target blips on the radar
    const blips = [
      { rRatio: 0.35, angle: 0.7, label: "LinkedIn" },
      { rRatio: 0.65, angle: 2.2, label: "Indeed" },
      { rRatio: 0.5, angle: 4.1, label: "Foundit" },
      { rRatio: 0.8, angle: 5.4, label: "Greenhouse" },
    ];

    let angle = 0;
    let ripples: { x: number; y: number; r: number; alpha: number }[] = [];

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      const cx = width / 2;
      const cy = height / 2;
      const maxRadius = Math.min(width, height) * 0.44;
      const sweepSpeed = isHovered ? 0.045 : 0.016;

      angle = (angle + sweepSpeed) % (Math.PI * 2);

      // 1. Concentric Range Rings
      const ringCount = 3;
      ctx.lineWidth = isHovered ? 1.2 : 0.8;
      for (let i = 1; i <= ringCount; i++) {
        const r = (maxRadius / ringCount) * i;
        ctx.strokeStyle = isHovered ? "rgba(255, 122, 0, 0.35)" : "rgba(245, 158, 11, 0.12)";
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.stroke();
      }

      // 2. Crosshair Axes
      ctx.strokeStyle = isHovered ? "rgba(255, 122, 0, 0.22)" : "rgba(245, 158, 11, 0.08)";
      ctx.beginPath();
      ctx.moveTo(cx - maxRadius, cy);
      ctx.lineTo(cx + maxRadius, cy);
      ctx.moveTo(cx, cy - maxRadius);
      ctx.lineTo(cx, cy + maxRadius);
      ctx.stroke();

      // 3. Sweeping Radar Beam Cone
      const coneAngle = Math.PI / 4; // 45 degrees
      const beamGrad = ctx.createRadialGradient(cx, cy, 2, cx, cy, maxRadius);
      beamGrad.addColorStop(0, isHovered ? "rgba(255, 122, 0, 0.55)" : "rgba(245, 158, 11, 0.22)");
      beamGrad.addColorStop(1, "rgba(255, 122, 0, 0)");

      ctx.fillStyle = beamGrad;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, maxRadius, angle - coneAngle, angle);
      ctx.closePath();
      ctx.fill();

      // Sharp Leading Beam Line
      ctx.strokeStyle = isHovered ? "#ff7a00" : "rgba(245, 158, 11, 0.4)";
      ctx.lineWidth = isHovered ? 2.0 : 1.2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(angle) * maxRadius, cy + Math.sin(angle) * maxRadius);
      ctx.stroke();

      // 4. Target Blips
      blips.forEach((b) => {
        const bx = cx + Math.cos(b.angle) * (maxRadius * b.rRatio);
        const by = cy + Math.sin(b.angle) * (maxRadius * b.rRatio);

        // Calculate angular distance to current beam
        let diff = (angle - b.angle + Math.PI * 2) % (Math.PI * 2);
        const isLit = diff < coneAngle || isHovered;
        const blipAlpha = isLit ? Math.max(0.2, 1 - diff / coneAngle) : 0.15;

        // Blip outer halo
        ctx.fillStyle = `rgba(255, 122, 0, ${blipAlpha * (isHovered ? 0.9 : 0.4)})`;
        ctx.beginPath();
        ctx.arc(bx, by, isHovered ? 4.5 : 3, 0, Math.PI * 2);
        ctx.fill();

        // Blip core
        ctx.fillStyle = isLit ? "#ffffff" : "rgba(255, 122, 0, 0.4)";
        ctx.beginPath();
        ctx.arc(bx, by, isHovered ? 2.2 : 1.5, 0, Math.PI * 2);
        ctx.fill();
      });

      // 5. Interactive Mouse Sonar Ripples
      if (isHovered && mousePos.x >= 0 && mousePos.y >= 0) {
        if (Math.random() > 0.88) {
          ripples.push({ x: mousePos.x, y: mousePos.y, r: 4, alpha: 0.8 });
        }
      }

      ripples.forEach((rp, idx) => {
        rp.r += 2.2;
        rp.alpha -= 0.025;
        ctx.strokeStyle = `rgba(255, 122, 0, ${Math.max(0, rp.alpha)})`;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.arc(rp.x, rp.y, rp.r, 0, Math.PI * 2);
        ctx.stroke();
      });
      ripples = ripples.filter((rp) => rp.alpha > 0);

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animId);
    };
  }, [isHovered, mousePos]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 h-full w-full pointer-events-none rounded-2xl"
    />
  );
}

// ============================================================================
// SECTION 3 CANVAS: Cryptographic Hex Shield & Hash Lattice (Steps 03 & 06)
// 5-Tier Deterministic Q&A & Cryptographic Audit Ledger
// ============================================================================
function CryptoShieldCanvas({ isHovered, mousePos }: { isHovered: boolean; mousePos: { x: number; y: number } }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 320);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 260);

    const handleResize = () => {
      if (!canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };
    window.addEventListener("resize", handleResize);

    // Floating Hash Badges
    const hashTokens = [
      { text: "SHA-256", x: width * 0.25, y: height * 0.35, vx: 0.15, vy: -0.2 },
      { text: "TIER_1", x: width * 0.72, y: height * 0.28, vx: -0.2, vy: 0.15 },
      { text: "AUDIT_OK", x: width * 0.3, y: height * 0.75, vx: 0.18, vy: 0.1 },
      { text: "LOCAL_VAULT", x: width * 0.68, y: height * 0.8, vx: -0.15, vy: -0.18 },
    ];

    let t = 0;
    const render = () => {
      t += 0.02;
      ctx.clearRect(0, 0, width, height);

      const hexSize = 28;
      const speedMultiplier = isHovered ? 2.0 : 1.0;

      // 1. Honeycomb Hexagonal Matrix
      const xSpacing = hexSize * 1.732;
      const ySpacing = hexSize * 1.5;

      ctx.lineWidth = isHovered ? 1.0 : 0.6;
      for (let y = -hexSize; y < height + hexSize; y += ySpacing) {
        const row = Math.floor(y / ySpacing);
        const xOffset = row % 2 === 0 ? 0 : xSpacing / 2;

        for (let x = -hexSize; x < width + hexSize; x += xSpacing) {
          const hx = x + xOffset;
          const hy = y;

          // Gentle sine breathing
          const wave = Math.sin(t + hx * 0.015 + hy * 0.015);
          const baseAlpha = (wave * 0.5 + 0.5) * (isHovered ? 0.38 : 0.09);

          ctx.strokeStyle = isHovered ? `rgba(192, 132, 252, ${baseAlpha})` : `rgba(52, 211, 153, ${baseAlpha})`;

          // Draw hexagon
          ctx.beginPath();
          for (let s = 0; s < 6; s++) {
            const angle = (Math.PI / 3) * s + Math.PI / 6;
            const px = hx + hexSize * 0.58 * Math.cos(angle);
            const py = hy + hexSize * 0.58 * Math.sin(angle);
            if (s === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          }
          ctx.closePath();
          ctx.stroke();
        }
      }

      // 2. Floating Crypto Hash Tokens (Interactive on hover to preserve background legibility)
      if (isHovered) {
        ctx.font = "bold 9px monospace";
        hashTokens.forEach((tk) => {
          tk.x += tk.vx * speedMultiplier;
          tk.y += tk.vy * speedMultiplier;

          if (tk.x < 20) tk.vx = Math.abs(tk.vx);
          if (tk.x > width - 60) tk.vx = -Math.abs(tk.vx);
          if (tk.y < 20) tk.vy = Math.abs(tk.vy);
          if (tk.y > height - 20) tk.vy = -Math.abs(tk.vy);

          // Chip badge
          ctx.fillStyle = "rgba(168, 85, 247, 0.25)";
          ctx.strokeStyle = "rgba(192, 132, 252, 0.6)";
          ctx.lineWidth = 1;
          ctx.strokeRect(tk.x - 4, tk.y - 10, 68, 14);
          ctx.fillRect(tk.x - 4, tk.y - 10, 68, 14);

          ctx.fillStyle = "#e9d5ff";
          ctx.fillText(tk.text, tk.x, tk.y);
        });
      }

      // 3. Interactive Mouse Cipher Sparks
      if (isHovered && mousePos.x >= 0 && mousePos.y >= 0) {
        // Laser rays from mouse cursor
        for (let k = 0; k < 4; k++) {
          const sparkAngle = t * 2.5 + (Math.PI / 2) * k;
          const sx = mousePos.x + Math.cos(sparkAngle) * 36;
          const sy = mousePos.y + Math.sin(sparkAngle) * 36;

          ctx.strokeStyle = "rgba(16, 185, 129, 0.65)";
          ctx.lineWidth = 1.3;
          ctx.beginPath();
          ctx.moveTo(mousePos.x, mousePos.y);
          ctx.lineTo(sx, sy);
          ctx.stroke();

          ctx.fillStyle = "#34d399";
          ctx.beginPath();
          ctx.arc(sx, sy, 2, 0, Math.PI * 2);
          ctx.fill();
        }

        // Mouse center glow
        const radGrad = ctx.createRadialGradient(mousePos.x, mousePos.y, 2, mousePos.x, mousePos.y, 45);
        radGrad.addColorStop(0, "rgba(192, 132, 252, 0.45)");
        radGrad.addColorStop(0.6, "rgba(52, 211, 153, 0.2)");
        radGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
        ctx.fillStyle = radGrad;
        ctx.beginPath();
        ctx.arc(mousePos.x, mousePos.y, 45, 0, Math.PI * 2);
        ctx.fill();
      }

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animId);
    };
  }, [isHovered, mousePos]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 h-full w-full pointer-events-none rounded-2xl"
    />
  );
}

// ============================================================================
// WORKFLOW CARD WITH DYNAMIC HOVER ANIMATION & LINEAR GRADIENT
// ============================================================================
interface Step {
  number: string;
  title: string;
  subtitle: string;
  description: string;
  icon: React.ElementType;
  badge: string;
  badgeColor: string;
  sectionIndex: number; // 0: Column 1, 1: Column 2, 2: Column 3
}

const STEPS: Step[] = [
  {
    number: "01",
    title: "Candidate Ingestion",
    subtitle: "Local Master Facts",
    description:
      "Ingest your profile, education, certifications, and multiple resume variants. All facts remain strictly on your machine in encrypted SQLite storage.",
    icon: UserCheck,
    badge: "100% LOCAL",
    badgeColor: "border-cyan-500/30 text-cyan-400 bg-cyan-950/30",
    sectionIndex: 0,
  },
  {
    number: "02",
    title: "Multi-Portal Discovery",
    subtitle: "SHA-256 Deduplication",
    description:
      "JobPilot searches LinkedIn, Indeed, Glassdoor, and direct career boards simultaneously, computing unique content hashes to eliminate duplicate listings.",
    icon: Search,
    badge: "MULTI-ENGINE",
    badgeColor: "border-slate-500/30 text-slate-300 bg-slate-900/30",
    sectionIndex: 1,
  },
  {
    number: "03",
    title: "5-Tier Q&A Match",
    subtitle: "Deterministic Precision",
    description:
      "Every screening question cascades through Profile -> Resume -> Pre-Approved Rules -> Formula -> LLM Fallback. Zero invented facts or hallucinated metrics.",
    icon: HelpCircle,
    badge: "PROVENANCE TRACKED",
    badgeColor: "border-orange-safety/30 text-orange-400 bg-orange-950/30",
    sectionIndex: 2,
  },
  {
    number: "04",
    title: "Universal ATS Execution",
    subtitle: "Full State Machine",
    description:
      "The Universal Agent analyzes dynamic web forms, resolves iframe boundaries, maps candidate data to inputs, and uploads targeted resume variants.",
    icon: Workflow,
    badge: "AUTOMATED",
    badgeColor: "border-emerald-500/30 text-emerald-400 bg-emerald-950/30",
    sectionIndex: 0,
  },
  {
    number: "05",
    title: "Human Checkpoint",
    subtitle: "Zero Risk Automation",
    description:
      "Before final submission or whenever sensitive questions (salary, visa, or CAPTCHA) appear, automation halts for your review and explicit approval.",
    icon: AlertCircle,
    badge: "SAFE MODE MANDATORY",
    badgeColor: "border-amber-500/30 text-amber-400 bg-amber-950/30",
    sectionIndex: 1,
  },
  {
    number: "06",
    title: "Audit & Follow-up",
    subtitle: "Verified Evidence",
    description:
      "A timestamped application record is committed to your local ledger, scheduling automated recruiter follow-up reminders and interview milestones.",
    icon: Award,
    badge: "AUDITED LEDGER",
    badgeColor: "border-purple-500/30 text-purple-400 bg-purple-950/30",
    sectionIndex: 2,
  },
];

function WorkflowCard({ step }: { step: Step }) {
  const [isHovered, setIsHovered] = useState(false);
  const [mousePos, setMousePos] = useState({ x: -1, y: -1 });
  const cardRef = useRef<HTMLDivElement | null>(null);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  const handleMouseEnter = () => setIsHovered(true);
  const handleMouseLeave = () => {
    setIsHovered(false);
    setMousePos({ x: -1, y: -1 });
  };

  const Icon = step.icon;

  // Custom gradient borders per section
  const gradientBorderClasses = [
    // Section 1: Electric Cyan & Cobalt
    isHovered
      ? "border-cyan-400/80 shadow-[0_0_30px_rgba(6,182,212,0.28)]"
      : "border-slate-800 hover:border-cyan-500/50",
    // Section 2: Safety Orange & Amber Gold
    isHovered
      ? "border-orange-safety/80 shadow-[0_0_30px_rgba(255,122,0,0.28)]"
      : "border-slate-800 hover:border-orange-safety/50",
    // Section 3: Electric Violet & Emerald Green
    isHovered
      ? "border-purple-400/80 shadow-[0_0_30px_rgba(168,85,247,0.28)]"
      : "border-slate-800 hover:border-purple-500/50",
  ];

  const iconColorClasses = [
    "bg-cyan-950/60 text-cyan-400 border border-cyan-500/30",
    "bg-orange-950/60 text-orange-safety border border-orange-safety/30",
    "bg-purple-950/60 text-purple-400 border border-purple-500/30",
  ];

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`relative rounded-2xl border bg-slate-900/80 p-6 sm:p-7 transition-all duration-300 flex flex-col justify-between overflow-hidden backdrop-blur-md ${gradientBorderClasses[step.sectionIndex]}`}
    >
      {/* 3 Distinct Section Background Canvas Animations */}
      {step.sectionIndex === 0 && <DataMatrixCanvas isHovered={isHovered} mousePos={mousePos} />}
      {step.sectionIndex === 1 && <RadarScanCanvas isHovered={isHovered} mousePos={mousePos} />}
      {step.sectionIndex === 2 && <CryptoShieldCanvas isHovered={isHovered} mousePos={mousePos} />}

      {/* Ambient Gradient Corner Sheen */}
      <div
        className={`absolute inset-0 pointer-events-none transition-opacity duration-300 ${
          isHovered ? "opacity-100" : "opacity-0"
        } ${
          step.sectionIndex === 0
            ? "bg-[radial-gradient(ellipse_at_top_right,rgba(6,182,212,0.12),transparent_70%)]"
            : step.sectionIndex === 1
            ? "bg-[radial-gradient(ellipse_at_top_right,rgba(255,122,0,0.14),transparent_70%)]"
            : "bg-[radial-gradient(ellipse_at_top_right,rgba(168,85,247,0.14),transparent_70%)]"
        }`}
      />

      {/* Content Layer (Above Canvas) */}
      <div className="relative z-10 flex flex-col justify-between h-full">
        <div>
          <div className="flex items-center justify-between pb-4">
            <span
              className={`font-mono text-2xl font-black transition-colors duration-300 ${
                isHovered
                  ? step.sectionIndex === 0
                    ? "text-cyan-400"
                    : step.sectionIndex === 1
                    ? "text-orange-safety"
                    : "text-purple-400"
                  : "text-slate-700"
              }`}
            >
              {step.number}
            </span>
            <span
              className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full border transition-all duration-300 ${step.badgeColor} ${
                isHovered ? "scale-105 shadow-sm" : ""
              }`}
            >
              {step.badge}
            </span>
          </div>

          <div className="flex items-center gap-3 mt-1">
            <div
              className={`flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-300 ${
                iconColorClasses[step.sectionIndex]
              } ${isHovered ? "scale-110 shadow-md" : ""}`}
            >
              <Icon className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white tracking-tight">{step.title}</h3>
              <p className="text-xs font-mono text-slate-400">{step.subtitle}</p>
            </div>
          </div>

          <p className="mt-4 text-sm text-slate-300 leading-relaxed font-normal">
            {step.description}
          </p>
        </div>

        {/* Dynamic Interactive Status Bar */}
        <div className="mt-6 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
          <span className="flex items-center gap-1.5">
            <span
              className={`h-1.5 w-1.5 rounded-full transition-all duration-300 ${
                isHovered
                  ? step.sectionIndex === 0
                    ? "bg-cyan-400 shadow-[0_0_6px_#06b6d4]"
                    : step.sectionIndex === 1
                    ? "bg-orange-safety shadow-[0_0_6px_#ff7a00]"
                    : "bg-purple-400 shadow-[0_0_6px_#c084fc]"
                  : "bg-slate-600"
              }`}
            />
            <span>
              {isHovered
                ? step.sectionIndex === 0
                  ? "Live Neural Stream // Interactive"
                  : step.sectionIndex === 1
                  ? "Sonar Active // Tracking Beam"
                  : "Hex Proof // Ledger Locked"
                : "Deterministic Pipeline"}
            </span>
          </span>

          <span className="text-[10px] text-slate-400 transition-colors">
            {isHovered ? "High Contrast Active" : "Hover to Inspect"}
          </span>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// MAIN PIPELINE SECTION EXPORT
// ============================================================================
export function WorkflowPipeline() {
  return (
    <section id="workflow" className="py-20 border-t border-slate-800/80 bg-slate-950/70 backdrop-blur-[1px] relative overflow-hidden">
      {/* Background Architectural Accent Grid */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.025] bg-[radial-gradient(#ffffff_1px,transparent_1px)] [background-size:24px_24px]" />

      <div className="relative z-10 mx-auto w-full max-w-[1560px] px-4 sm:px-8 lg:px-12">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-950/20 px-3.5 py-1 text-xs font-mono text-cyan-400 backdrop-blur-md">
            <span>DETERMINISTIC PIPELINE</span>
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
            <span>3 INTERACTIVE PHASES</span>
          </div>

          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight leading-tight">
            How JobPilot Operates
          </h2>

          <p className="text-base sm:text-lg text-slate-300 max-w-2xl mx-auto leading-relaxed">
            A reliable pipeline engineered to eliminate repetitive application friction while maintaining total human control across every portal.
          </p>
        </div>

        {/* 3 Column Grid with 3 Distinct Section Animations */}
        <div className="mt-14 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {STEPS.map((step) => (
            <WorkflowCard key={step.number} step={step} />
          ))}
        </div>
      </div>
    </section>
  );
}
