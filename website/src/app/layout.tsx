import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "JobPilot — Autonomous Career Navigation & Multi-Platform Application Cockpit",
  description:
    "Discover opportunities, qualify the right roles, automate repetitive applications, and manage your entire career pipeline from one intelligent, local-first desktop cockpit.",
  keywords: [
    "JobPilot",
    "job search automation",
    "desktop career cockpit",
    "universal ATS applier",
    "LinkedIn automation",
    "local-first job agent",
  ],
  icons: {
    icon: "/brand/jobpilot-symbol-color.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark scroll-smooth">
      <head>
        <link rel="icon" href="/brand/jobpilot-symbol-color.svg" type="image/svg+xml" />
      </head>
      <body className="min-h-screen bg-obsidian text-slate-100 antialiased selection:bg-orange-safety selection:text-white">
        {children}
      </body>
    </html>
  );
}

