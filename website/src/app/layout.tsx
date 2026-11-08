import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://jobpilot-automation.vercel.app"),
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
  openGraph: {
    title: "JobPilot — Autonomous Career Navigation & Multi-Platform Application Cockpit",
    description:
      "Discover opportunities, qualify the right roles, automate repetitive applications, and manage your entire career pipeline from one intelligent, local-first desktop cockpit.",
    url: "https://jobpilot-automation.vercel.app",
    siteName: "JobPilot",
    images: [
      {
        url: "/brand/jobpilot_badge.png",
        width: 1200,
        height: 630,
        alt: "JobPilot Autonomous Career Cockpit",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "JobPilot — Autonomous Career Navigation & Multi-Platform Application Cockpit",
    description:
      "Discover opportunities, qualify the right roles, automate repetitive applications, and manage your entire career pipeline from one intelligent, local-first desktop cockpit.",
    images: ["/brand/jobpilot_badge.png"],
  },
  icons: {
    icon: "/brand/jobpilot-symbol-dark.svg",
    shortcut: "/brand/jobpilot-symbol-dark.svg",
    apple: "/brand/jobpilot-symbol-dark.svg",
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
        <link rel="icon" href="/brand/jobpilot-symbol-dark.svg" type="image/svg+xml" />
      </head>
      <body className="min-h-screen bg-obsidian text-slate-100 antialiased selection:bg-orange-safety selection:text-white">
        {children}
      </body>
    </html>
  );
}

