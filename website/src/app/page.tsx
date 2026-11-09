import React from "react";
import { DataRain } from "@/components/ui/data-rain";
import { RobotHero } from "@/components/ui/robot-hero";
import { AutomationDemos } from "@/components/AutomationDemos";
import { ProblemSolution } from "@/components/ProblemSolution";
import { DesktopShowcase } from "@/components/DesktopShowcase";
import { WorkflowPipeline } from "@/components/WorkflowPipeline";
import { PlatformGrid } from "@/components/PlatformGrid";
import { ArchitectureSection } from "@/components/ArchitectureSection";
import { DownloadsSection } from "@/components/DownloadsSection";
import { Footer } from "@/components/Footer";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100 selection:bg-orange-safety selection:text-white relative">
      <main className="flex-1 relative">
        {/* Full-Page Interactive Data Rain Background (Active on entire page except footer) */}
        <DataRain
          palette={{
            calm: "#00f2fe",
            mid: "#38bdf8",
            hot: "#ff7a00",
          }}
          flowSpeed={0.9}
          obstacleRadius={68}
          autopilot={true}
          fullscreen={true}
        />

        {/* Page Content Layers (Positioned cleanly above the data rain canvas) */}
        <div className="relative z-10">
          <RobotHero />
          <AutomationDemos />
          <ProblemSolution />
          <DesktopShowcase />
          <WorkflowPipeline />
          <PlatformGrid />
          <ArchitectureSection />
          <DownloadsSection />
        </div>
      </main>
      <Footer />
    </div>
  );
}
