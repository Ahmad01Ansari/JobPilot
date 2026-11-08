
# JobPilot Website — Complete Monorepo Implementation Roadmap

**Document type:** Product & Engineering Implementation Brief
**Project:** JobPilot — Autonomous Career Navigation & Multi-Platform Application Cockpit
**Repository strategy:** Monorepo
**Website location:** `/website`
**Status:** Proposed implementation plan
**Source specifications:** PRD v1.0, TRD v1.0, Application Flow v1.0, UI/UX Design Brief v1.1, Backend Schema v1.0

---

# 1. Executive Direction

## 1.1 Objective

Build a premium, modern, interactive website that communicates the full capabilities of JobPilot, demonstrates its end-to-end workflows, provides user and developer documentation, and distributes verified desktop releases for Windows and Linux.

This must not be a generic SaaS landing page. It should feel like the public product experience of a sophisticated autonomous desktop platform.

The website should help a visitor understand:

1. What JobPilot does.
2. Why it is different from ordinary job-search tools.
3. How its autonomous job discovery and application workflows operate.
4. How it protects candidate information and maintains human control.
5. What the desktop application looks like and how its modules work.
6. How to install and configure the application.
7. How its technical architecture works.
8. How to download, upgrade, and troubleshoot it.

## 1.2 Product positioning

**Primary positioning:**

> Your career. On autopilot.

**Supporting message:**

> Discover opportunities, qualify the right roles, automate repetitive applications, and manage your entire career pipeline from one intelligent desktop cockpit.

**Product narrative:**

Discover → Qualify → Prepare → Apply → Verify → Track → Improve

The website should communicate that JobPilot is more than an application-filling bot. It combines job discovery, candidate profiling, resume management, deterministic Q&A, multi-platform automation, human checkpoints, recruiter outreach, interviews, and analytics.

## 1.3 Product principles

The website must preserve the principles established in the desktop product specifications:

- **Transparent agency:** Visitors should understand what automation does and when human intervention is required.
- **Verified information:** Never advertise an integration or feature as operational without checking the actual implementation and release status.
- **Local-first privacy:** Explain that candidate information and credentials remain on the user's machine, according to the desktop architecture.
- **Human-controlled automation:** Explain the Safe Mode, review checkpoints, CAPTCHA handling, and user confirmation behavior.
- **Technical credibility:** Give developers access to real architecture, module responsibilities, data flows, and troubleshooting information.
- **Performance:** Rich visual experiences must not make the website slow or unusable.
- **Maintainability:** Documentation and product claims must remain synchronized with desktop releases.

---

# 2. Monorepo Architecture

## 2.1 Repository structure

Create the website as an independent application inside the existing repository.

Recommended target structure:

```text
JobPilot/
│
├── app/                         # Existing desktop application
├── platforms/                   # Existing platform automation
├── modules/                     # Existing operational engines
├── config/                      # Existing desktop configuration
├── setup/                       # Existing setup and packaging
├── tests/                       # Existing desktop tests
├── docs/                        # Existing project documentation
│
├── website/                     # NEW: Public website application
│   ├── public/
│   │   ├── images/
│   │   ├── videos/
│   │   ├── brand/
│   │   ├── screenshots/
│   │   └── downloads/
│   │
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx
│   │   │   ├── platform/
│   │   │   ├── demo/
│   │   │   ├── how-it-works/
│   │   │   ├── downloads/
│   │   │   ├── documentation/
│   │   │   ├── developers/
│   │   │   ├── architecture/
│   │   │   ├── changelog/
│   │   │   ├── about/
│   │   │   ├── privacy/
│   │   │   └── terms/
│   │   │
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   ├── navigation/
│   │   │   ├── hero/
│   │   │   ├── animations/
│   │   │   ├── product-showcase/
│   │   │   ├── simulator/
│   │   │   ├── integrations/
│   │   │   ├── downloads/
│   │   │   ├── documentation/
│   │   │   └── common/
│   │   │
│   │   ├── features/
│   │   │   ├── simulator/
│   │   │   ├── download-center/
│   │   │   ├── documentation-search/
│   │   │   └── release-information/
│   │   │
│   │   ├── data/
│   │   │   ├── product/
│   │   │   ├── integrations/
│   │   │   ├── releases/
│   │   │   └── simulator/
│   │   │
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── styles/
│   │   └── types/
│   │
│   ├── content/
│   │   ├── user-guide/
│   │   ├── developer-guide/
│   │   ├── architecture/
│   │   ├── troubleshooting/
│   │   └── release-notes/
│   │
│   ├── scripts/
│   │   ├── sync-product-metadata.ts
│   │   ├── validate-downloads.ts
│   │   └── validate-doc-links.ts
│   │
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   │
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── eslint.config.mjs
│   └── README.md
│
├── shared/                      # Optional shared assets/contracts only
│   ├── branding/
│   └── product-metadata/
│
├── .github/
│   └── workflows/
│       ├── desktop-ci.yml
│       ├── website-ci.yml
│       └── release.yml
│
├── README.md
└── .gitignore
```

This is a target structure, not an instruction to move or rename existing desktop files. The agent must inspect the current repository and preserve its established layout.

## 2.2 Monorepo isolation rules

The desktop application and website must remain separate execution environments.

| Area                   | Desktop                                     | Website                                     |
| ---------------------- | ------------------------------------------- | ------------------------------------------- |
| Runtime                | Python / PySide6                            | Node.js / Next.js                           |
| Primary responsibility | Actual job-search and automation operations | Public product experience and documentation |
| Data                   | Local SQLite database                       | Static or explicitly public content         |
| Credentials            | Local encrypted vault                       | No desktop credentials                      |
| Browser automation     | Selenium and existing automation engines    | No job-portal automation                    |
| User interface         | Qt desktop interface                        | Responsive web interface                    |
| Distribution           | Windows/Linux installers                    | Web deployment                              |
| Testing                | Existing Python test suite                  | Website-specific test suite                 |

Rules:

1. Do not modify existing desktop business logic merely to make the website easier to build.
2. Do not import Python desktop modules directly into the Next.js application.
3. Do not make the website depend on a running desktop process.
4. Do not connect the public website to a user's local SQLite database.
5. Do not expose the local Flask management service to the public internet.
6. Do not store API keys, portal passwords, resumes, or private candidate data in website configuration.
7. Do not share Node.js dependencies with the Python application.
8. Keep desktop and website builds independently executable and testable.

The website may consume explicitly approved product metadata, screenshots, diagrams, release information, and public documentation.

## 2.3 Recommended technology stack

| Layer              | Recommended technology        | Responsibility                         |
| ------------------ | ----------------------------- | -------------------------------------- |
| Framework          | Next.js with App Router       | Website structure and routing          |
| Language           | TypeScript                    | Type safety                            |
| Styling            | Tailwind CSS                  | Responsive design system               |
| UI primitives      | shadcn/ui where appropriate   | Accessible interface primitives        |
| Icons              | Lucide React                  | Consistent icons                       |
| Motion             | Framer Motion / Motion        | UI transitions and interactions        |
| Advanced animation | GSAP                          | Scroll-linked and timeline animations  |
| 3D graphics        | Three.js + React Three Fiber  | Hero and selected product visuals      |
| Documentation      | MDX + Fumadocs                | Searchable technical documentation     |
| Content validation | Zod                           | Metadata and content schema validation |
| Testing            | Vitest + Playwright           | Unit and browser testing               |
| Code quality       | ESLint + Prettier             | Consistent code                        |
| Deployment         | Vercel or self-hosted Next.js | Public website hosting                 |

The agent must verify compatible current package versions before installation and commit the lockfile.

### Rendering strategy

Prefer static generation or server rendering for pages that do not need live user-specific data.

Use client-side components only where necessary:

- Interactive product simulator.
- Navigation interactions.
- Motion and 3D components.
- Documentation search interface.
- Download selection interactions.

Do not turn every page into a client-rendered application.

---

# 3. Website Information Architecture

The website should have the following main routes.

| Route                              | Purpose                             | Priority |
| ---------------------------------- | ----------------------------------- | -------- |
| `/`                              | Main product landing page           | P0       |
| `/platform`                      | Complete product capabilities       | P0       |
| `/demo`                          | Interactive JobPilot simulator      | P0       |
| `/how-it-works`                  | End-to-end workflow explanation     | P1       |
| `/downloads`                     | Windows/Linux release center        | P0       |
| `/documentation`                 | User documentation portal           | P0       |
| `/documentation/getting-started` | Installation and onboarding         | P0       |
| `/documentation/user-guide`      | Feature-specific guides             | P1       |
| `/developers`                    | Developer entry point               | P1       |
| `/architecture`                  | Technical architecture and diagrams | P1       |
| `/changelog`                     | Version history and release notes   | P1       |
| `/about`                         | Product background and vision       | P2       |
| `/privacy`                       | Privacy explanation                 | P0       |
| `/terms`                         | Terms and usage conditions          | P0       |

The global navigation should remain compact and clear:

- Product
- Interactive Demo
- How It Works
- Documentation
- Developers
- Downloads

Primary CTA: **Download JobPilot**

Secondary CTA: **Explore Interactive Demo**

On mobile, use an accessible collapsible navigation menu.

---

# 4. Visual Identity and Design System

## 4.1 Visual direction

Create a premium technical product identity inspired by the clarity and polish of modern developer products such as Linear, Vercel, Raycast, and Stripe.

Use these as quality references, not as designs to copy.

The website should feel:

- Technical.
- Intelligent.
- Precise.
- Modern.
- Calm.
- Trustworthy.
- Slightly futuristic.

Avoid excessive neon, random glowing elements, unnecessary glass effects, and generic AI-generated landing-page layouts.

## 4.2 Brand palette

Use the existing desktop UI/UX specification as the starting point.

| Token           | Value       | Purpose                       |
| --------------- | ----------- | ----------------------------- |
| Deep Obsidian   | `#0F172A` | Primary dark background       |
| Secondary Slate | `#1E293B` | Cards and panels              |
| Tertiary Slate  | `#334155` | Inputs and secondary surfaces |
| Safety Orange   | `#FF5F15` | Primary brand action          |
| Deep Amber      | `#E04F0B` | Orange hover state            |
| Sky Cyan        | `#0EA5E9` | Secondary accent              |
| Emerald         | `#10B981` | Success                       |
| Amber           | `#F59E0B` | Warning and checkpoints       |
| Rose Red        | `#EF4444` | Failure and error             |
| Snow            | `#F8FAFC` | Primary text                  |
| Muted Slate     | `#94A3B8` | Secondary text                |

The desktop design brief is dark-first. The website may introduce a complementary light theme if it can be implemented without diluting the brand.

## 4.3 Typography

Recommended:

- Inter or Geist Sans for body and headings.
- Geist Mono or JetBrains Mono for technical information, terminal output, and code.

Use a clear type hierarchy:

- Display hero heading.
- Section heading.
- Card heading.
- Body text.
- Supporting metadata.
- Technical monospace labels.

## 4.4 Reusable design tokens

Create centralized website tokens for:

- Colors.
- Typography.
- Spacing.
- Border radius.
- Shadows.
- Card surfaces.
- Navigation dimensions.
- Motion duration.
- Motion easing.
- Responsive breakpoints.

Avoid hardcoding visual values throughout individual components.

## 4.5 Responsive requirements

Design for:

- Desktop: 1440px and above.
- Laptop: 1024–1439px.
- Tablet: 768–1023px.
- Mobile: below 768px.

The simulator should remain usable on mobile through simplified layouts, rather than simply shrinking a full desktop interface until it becomes unreadable.

---

# 5. Homepage Implementation

The homepage should tell a coherent product story rather than display disconnected feature cards.

## Section 1 — Cinematic hero

**Objective:** Immediately communicate what JobPilot is.

Content:

- Brand mark and navigation.
- Main headline: "Your career. On autopilot."
- Supporting description.
- Download CTA.
- Interactive demo CTA.
- Platform compatibility indicator.
- Animated product visualization.

### Hero visual concept

Create a central JobPilot interface or abstract automation core surrounded by a small number of floating workflow elements:

- Job discovered.
- Match score.
- Resume selected.
- Application submitted.
- Human checkpoint.

Use subtle motion, depth, and lighting.

A Three.js or React Three Fiber visual may be used here, but it must be optional and progressively loaded.

Do not place essential text inside a canvas.

## Section 2 — The problem and the solution

Explain the repetitive friction of job searching:

- Multiple job portals.
- Repeated profile entry.
- Repeated screening questions.
- Duplicate applications.
- Untracked recruiter conversations.
- Missed follow-ups.

Then show how JobPilot unifies the workflow.

## Section 3 — End-to-end workflow

Create a connected horizontal or vertical workflow:

1. Build candidate profile.
2. Upload resume variants.
3. Discover opportunities.
4. Evaluate job compatibility.
5. Resolve screening questions.
6. Execute applications.
7. Handle human checkpoints.
8. Record application evidence.
9. Track interviews and follow-ups.

Animate the workflow progressively as the visitor scrolls.

## Section 4 — Product showcase

This is one of the most important website sections.

Display a realistic desktop application frame containing selected JobPilot interface screens.

Show the main modules:

- Dashboard.
- Job Search.
- Jobs Queue.
- Automation.
- Applications.
- Resume Vault.
- Q&A Knowledge Base.
- Recruiter Outreach.
- Interviews.
- Follow-ups.
- Analytics.
- Platforms.
- Logs.
- Settings.

Use actual screenshots from the existing desktop application wherever possible.

Do not invent screenshots and present them as actual desktop software.

## Section 5 — Intelligence and automation

Explain the five-tier answer resolution system:

1. Profile facts.
2. Resume facts.
3. Pre-approved Q&A rules.
4. Deterministic calculations.
5. LLM fallback.

Visualize the priority cascade.

Show that every answer has provenance and that uncertain or unfamiliar mandatory fields can trigger a human checkpoint.

The website must not claim that an LLM is free to invent candidate facts.

## Section 6 — Platform ecosystem

Display integrations in organized groups.

**Job portals:**

- LinkedIn.
- Naukri.
- Indeed.
- Glassdoor.
- Foundit.

**Enterprise ATS:**

- Greenhouse.
- Lever.
- Workday.
- Ashby.

**Additional ATS coverage:**

- SmartRecruiters, only if confirmed in the actual implementation and release status.

For each integration, show:

- Platform name and logo.
- Integration category.
- Supported workflow.
- Verified support status.
- Relevant limitations.

Do not use a generic "fully supported" badge for every integration without verification.

## Section 7 — Privacy and safety

Explain:

- Local-first data storage.
- Encrypted credential vault.
- Local SQLite persistence.
- Sanitized logs.
- Human checkpoints.
- CAPTCHA requires human completion.
- No automated CAPTCHA solving.
- No stealth fingerprint evasion.
- Safe Mode and user-controlled automation.

This should be a prominent trust section, not a small footer paragraph.

## Section 8 — Interactive demo CTA

Invite visitors to explore a simulated JobPilot environment.

## Section 9 — Download CTA

Show Windows and Linux download options only when verified release assets are available.

## Section 10 — Footer

Include:

- Product.
- Documentation.
- Developer resources.
- Downloads.
- Changelog.
- Privacy.
- Terms.
- GitHub or other official community links, if confirmed.
- Version information.

---

# 6. Interactive Product Simulator

## 6.1 Purpose

Create a browser-based interactive simulation of the desktop application.

The simulator is a demonstration environment, not a web port of JobPilot.

It should help visitors experience how the desktop application is organized and how its workflows connect.

## 6.2 Simulator layout

Create a desktop-like frame with:

- JobPilot brand area.
- Sidebar navigation.
- Main content panel.
- Top status bar.
- Notification area.
- Responsive controls.

The simulated interface should resemble the actual PySide6 desktop application, while adapting it for a browser.

## 6.3 Simulator modules

Build these modules in priority order.

### Module A — Dashboard

Display:

- Jobs discovered.
- Applications submitted.
- Active interviews.
- Conversion rate.
- Recent activity.
- Platform performance.
- Readiness status.

### Module B — Job Search

Allow the visitor to:

- Select a target role.
- Select a location.
- Select job platforms.
- Start a simulated discovery process.
- View generated sample job listings.

### Module C — Jobs Queue

Display realistic sample jobs with:

- Company.
- Job title.
- Location.
- Platform.
- Match score.
- Qualification status.
- Queue status.

Allow filtering and opening a job detail panel.

### Module D — Automation Console

Simulate the automation lifecycle:

- Initializing.
- Browser ready.
- Navigating to job.
- Detecting application form.
- Resolving answers.
- Filling form.
- Reviewing submission.
- Waiting for confirmation.
- Recording outcome.

Provide a clear pause/checkpoint interaction.

Do not actually open job portals or submit applications from the website.

### Module E — Resume Vault

Display fictional resume variants and their sample metadata.

Demonstrate how different resume variants may be associated with different job categories.

### Module F — Q&A Knowledge Base

Show example questions and answers with their provenance:

- `PROFILE_FACT`
- `RESUME_FACT`
- `QNA_RULE`
- `CALCULATED`
- `LLM_FALLBACK`

Include an example where an uncertain question requires human intervention.

### Module G — Applications

Display a simulated application history and lifecycle.

### Module H — Outreach

Show a fictional recruiter conversation and a follow-up reminder.

### Module I — Analytics

Display sample charts for:

- Discovery-to-application conversion.
- Platform comparison.
- Application velocity.
- Interview progression.

## 6.4 Demo data rules

All simulator information must be generated from clearly labelled fictional data.

Display a persistent label:

**Interactive Demo — Sample Data**

Rules:

1. Never load a real candidate profile.
2. Never access the desktop SQLite database.
3. Never read local resume files.
4. Never request real portal credentials.
5. Never call actual automation engines.
6. Never send emails.
7. Never submit job applications.
8. Do not present sample metrics as actual JobPilot user statistics.

## 6.5 Simulator architecture

Keep simulation data separate from the production desktop application.

Recommended structure:

```text
src/features/simulator/
├── components/
│   ├── simulator-shell.tsx
│   ├── simulator-sidebar.tsx
│   ├── simulator-header.tsx
│   ├── dashboard-panel.tsx
│   ├── job-search-panel.tsx
│   ├── jobs-panel.tsx
│   ├── automation-panel.tsx
│   ├── resumes-panel.tsx
│   ├── qna-panel.tsx
│   ├── applications-panel.tsx
│   ├── outreach-panel.tsx
│   └── analytics-panel.tsx
│
├── data/
│   ├── demo-jobs.ts
│   ├── demo-applications.ts
│   ├── demo-profile.ts
│   ├── demo-resumes.ts
│   └── demo-activity.ts
│
├── state/
│   └── simulator-store.ts
│
├── services/
│   └── simulation-engine.ts
│
└── types/
    └── simulator.types.ts
```

Use a lightweight state-management approach. Zustand is an option if the simulator's shared state becomes complex; otherwise React state and context are sufficient.

The simulation engine should use deterministic scripted transitions, not random events that make demonstrations unreliable.

---

# 7. Product and Workflow Pages

## 7.1 Product page

Route: `/platform`

Organize the product into feature groups.

**Job discovery and qualification**

- Multi-platform search.
- Job ingestion.
- URL normalization.
- SHA-256 fingerprinting.
- Duplicate detection.
- Match scoring.
- Qualification and exclusion rules.

**Candidate intelligence**

- Candidate profile.
- Multiple resume variants.
- Resume parsing.
- ATS readability analysis.
- Five-tier Q&A.
- Answer provenance.

**Autonomous execution**

- Platform automation router.
- Universal ATS state machine.
- Form-field analysis.
- Field validation.
- Checkpoint handling.
- Submission verification.

**Career management**

- Applications history.
- Interview tracking.
- Recruiter outreach.
- Email synchronization.
- Follow-up scheduling.
- Analytics.

Each feature page should explain:

- What the feature does.
- The user problem it solves.
- How the workflow operates.
- Which desktop module supports it.
- Any limitations or requirements.

## 7.2 How It Works page

Route: `/how-it-works`

Create a detailed end-to-end journey:

1. Install JobPilot.
2. Configure candidate profile.
3. Upload resume.
4. Configure Q&A rules.
5. Connect supported platforms.
6. Discover opportunities.
7. Review match scores.
8. Configure automation.
9. Handle human checkpoints.
10. Review recorded applications.
11. Manage interviews and outreach.
12. Evaluate performance analytics.

Provide links from each step to the relevant user guide.

---

# 8. Download Center and Release Distribution

Route: `/downloads`

## 8.1 Platform layout

Display separate release cards for:

- Windows.
- Linux.

Each card should include:

- Current version.
- Release channel.
- Package type.
- Supported operating systems.
- Architecture.
- File size.
- Release date.
- SHA-256 checksum.
- Installation instructions.
- Known issues.
- Changelog.

## 8.2 Release artifacts

The TRD specifies:

**Windows:**

- Standalone executable.
- Inno Setup installer.

**Linux:**

- AppImage.
- Debian package.

The website must only expose actual published release assets.

Do not create fake download links or use placeholder files as real releases.

## 8.3 Release metadata

Create a central release manifest, for example:

```json
{
  "version": "0.1.0-beta.1",
  "channel": "beta",
  "publishedAt": "2026-11-01",
  "platforms": {
    "windows": {
      "status": "unavailable",
      "artifacts": []
    },
    "linux": {
      "status": "unavailable",
      "artifacts": []
    }
  }
}
```

This is a schema example, not a claim about the current published release.

Use a validated schema and update it only through the release process.

Possible future artifact storage:

- GitHub Releases.
- A controlled object-storage bucket.
- An approved self-hosted release endpoint.

Use a stable download metadata source so the website does not need code changes for every release.

## 8.4 Download security

- Verify artifact URLs.
- Display checksums.
- Never link to untrusted third-party mirrors.
- Keep release metadata versioned.
- Validate files before publication.
- Document installation prerequisites.
- Document the limitations of beta releases.

Where signing is supported by the release pipeline, publish and document the relevant signatures.

---

# 9. Documentation Portal

Route: `/documentation`

Documentation is a major part of the product, not an optional appendix.

Use MDX-based documentation with a structured navigation tree and full-text search.

## 9.1 User documentation

Recommended structure:

```text
content/user-guide/
├── introduction.mdx
├── system-requirements.mdx
├── installation/
│   ├── windows.mdx
│   └── linux.mdx
├── getting-started/
│   ├── first-launch.mdx
│   ├── profile-setup.mdx
│   ├── resume-setup.mdx
│   ├── qna-configuration.mdx
│   └── platform-configuration.mdx
├── features/
│   ├── dashboard.mdx
│   ├── job-discovery.mdx
│   ├── job-qualification.mdx
│   ├── automation.mdx
│   ├── applications.mdx
│   ├── resumes.mdx
│   ├── qna-engine.mdx
│   ├── outreach.mdx
│   ├── interviews.mdx
│   ├── follow-ups.mdx
│   └── analytics.mdx
├── safety/
│   ├── safe-mode.mdx
│   ├── human-checkpoints.mdx
│   └── privacy-and-security.mdx
└── troubleshooting/
    ├── browser-issues.mdx
    ├── platform-login.mdx
    ├── database-issues.mdx
    └── installation-issues.mdx
```

## 9.2 Developer documentation

```text
content/developer-guide/
├── index.mdx
├── prerequisites.mdx
├── repository-structure.mdx
├── local-development.mdx
├── configuration.mdx
├── architecture-overview.mdx
├── service-layer.mdx
├── database-layer.mdx
├── platform-adapters.mdx
├── universal-ats-engine.mdx
├── qna-engine.mdx
├── secrets-and-security.mdx
├── testing.mdx
├── packaging.mdx
└── contribution-guide.mdx
```

## 9.3 Architecture documentation

```text
content/architecture/
├── system-overview.mdx
├── application-layers.mdx
├── desktop-event-flow.mdx
├── database-erd.mdx
├── job-discovery-flow.mdx
├── application-execution-flow.mdx
├── universal-ats-state-machine.mdx
├── qna-resolution-flow.mdx
├── human-checkpoint-flow.mdx
├── email-outreach-flow.mdx
└── security-model.mdx
```

Reuse the Mermaid diagrams in the existing specifications where appropriate, after verifying that they accurately represent the implementation.

## 9.4 Documentation UX

Provide:

- Searchable sidebar.
- Breadcrumb navigation.
- Previous/next article links.
- Copy-code buttons.
- Syntax highlighting.
- Responsive Mermaid diagrams.
- Table of contents for long pages.
- Version and update metadata.
- Clear warning and note components.
- Links between user and developer documentation.

Documentation should be easy to navigate for both nontechnical users and developers.

---

# 10. Technical Architecture and Integration Boundaries

## 10.1 Public website architecture

```text
Visitor
   |
   v
Next.js Website
   |
   +---- Public product pages
   |
   +---- Interactive simulator
   |         |
   |         +---- Fictional demo data
   |         +---- Local frontend simulation state
   |
   +---- Documentation system
   |         |
   |         +---- MDX content
   |         +---- Documentation search
   |
   +---- Download center
   |         |
   |         +---- Validated release manifest
   |         +---- Published release assets
   |
   +---- Public product metadata
```

## 10.2 Desktop architecture remains independent

```text
JobPilot Desktop
   |
   +---- PySide6 UI
   |
   +---- Domain services
   |
   +---- Automation engines
   |
   +---- Q&A intelligence
   |
   +---- SQLite local database
   |
   +---- Encrypted secrets vault
   |
   +---- Local Flask management service
```

There should be no public network connection between these two systems in the initial website release.

## 10.3 Future integration boundary

If future versions require desktop-to-website integration, implement a separately designed, authenticated, opt-in API.

Potential future capabilities:

- Public version-check endpoint.
- Release notifications.
- Opt-in update notifications.
- Public changelog feed.
- User-initiated diagnostic upload, with sanitization and explicit consent.

Do not implement cloud sync, remote control, user accounts, multi-tenant SaaS, or remote candidate-data storage as part of this initial project.

Those features are outside the PRD's current local-first product scope.

---

# 11. Animation and Interaction Strategy

## 11.1 Animation philosophy

Use animation to explain product behavior, not simply to decorate the page.

The desired feeling is precise, smooth, and technical.

## 11.2 Priority animation concepts

### Hero: Autonomous workflow core

A central visual representing JobPilot's automation engine, with connected elements representing:

- Candidate profile.
- Job opportunity.
- Resume.
- Q&A resolution.
- Application.
- Analytics.

### Workflow visualization

Animate the progression:

Discover → Qualify → Apply → Verify → Track.

Use connecting lines, state transitions, and contextual labels.

### Product interface reveal

Use layered screenshots or responsive interface panels to introduce product modules.

### Q&A intelligence animation

Show a question moving through the five-tier resolution cascade, with the final answer displaying provenance.

### Automation state machine

Show the application process moving through states and pausing at a human checkpoint when needed.

### Download interaction

Provide a simple platform-selection interaction with clearly visible release status.

## 11.3 Animation performance rules

- Use CSS transforms and opacity where possible.
- Lazy-load 3D assets.
- Avoid unnecessary continuous rendering.
- Pause offscreen animation where practical.
- Provide a static fallback for WebGL failure.
- Respect `prefers-reduced-motion`.
- Avoid blocking page content while animation loads.
- Optimize mobile separately.
- Do not make essential product information available only through animation.

---

# 12. SEO, Accessibility, and Performance

## 12.1 SEO

Implement:

- Page-specific titles and descriptions.
- Open Graph metadata.
- Twitter/X card metadata.
- Canonical URLs.
- Sitemap.
- Robots configuration.
- Descriptive image alt text.
- Semantic HTML.
- Structured metadata where appropriate.

Target product-related search intent around autonomous job application management, job-search automation, job application tracking, and desktop career automation.

Do not use misleading SEO claims or keyword stuffing.

## 12.2 Accessibility

Target WCAG 2.2 AA as the design and testing objective.

Requirements:

- Keyboard-accessible navigation.
- Visible focus states.
- Correct heading hierarchy.
- Sufficient contrast.
- Accessible form labels.
- Screen-reader-friendly controls.
- Reduced-motion support.
- Accessible dialog and menu behavior.
- Meaningful image alternatives.

## 12.3 Performance

Set these initial engineering targets:

- Lighthouse Performance: 90+ on representative pages where practical.
- Accessibility: 95+.
- SEO: 95+.
- Best Practices: 95+.
- Avoid large synchronous JavaScript bundles.
- Lazy-load below-the-fold media.
- Use responsive images.
- Avoid layout shifts caused by late-loading media.
- Keep the documentation experience fast and usable on low-end devices.

These are targets, not guarantees.

---

# 13. Monorepo Maintenance and Long-Term Change Management

This is one of the most important parts of the project.

The desktop application will continue to evolve. The website must not become outdated every time a new tab, service, integration, or automation capability is introduced.

## 13.1 Establish one source of truth

Do not duplicate product facts throughout homepage components, feature pages, simulator data, documentation, and download pages.

Create a structured public product metadata layer.

Example:

```text
website/src/data/product/
├── product-info.ts
├── features.ts
├── modules.ts
├── integrations.ts
├── safety-capabilities.ts
└── product-status.ts
```

Each feature should have metadata such as:

- Stable feature ID.
- Display name.
- Description.
- Category.
- Desktop module or service reference.
- Public route.
- Documentation link.
- Verification status.
- Minimum supported desktop release, where known.

The website should render feature cards, navigation, and related links from this metadata wherever possible.

## 13.2 Feature verification status

Define a controlled status vocabulary:

- `implemented`: Verified in the current desktop implementation.
- `beta`: Available but still subject to beta limitations.
- `planned`: Intended but not yet implemented.
- `experimental`: Present but not considered stable.
- `unavailable`: Not currently distributed or supported.

Only verified features should appear as currently available product capabilities.

The agent must inspect the actual source before assigning statuses. A feature mentioned in a PRD is not automatically proof that the current release implements it.

## 13.3 Change-impact workflow

Whenever the desktop application changes, follow this process:

```text
Desktop Feature Change
        |
        v
Identify affected module/service
        |
        v
Check product metadata
        |
        v
Check simulator behavior
        |
        v
Check user documentation
        |
        v
Check architecture documentation
        |
        v
Check screenshots and feature claims
        |
        v
Check changelog/release metadata
        |
        v
Run website validation
        |
        v
Publish synchronized update
```

Examples:

| Desktop change               | Website changes to review                             |
| ---------------------------- | ----------------------------------------------------- |
| New desktop tab              | Product page, simulator, screenshots, user guide      |
| New platform integration     | Integration list, capability page, setup guide        |
| Updated Q&A logic            | Q&A feature page, architecture diagram, simulator     |
| Changed application workflow | How It Works page, application flow documentation     |
| New database model           | Schema documentation and ERD                          |
| Updated security behavior    | Privacy page, security guide, technical documentation |
| New Windows release          | Download manifest, changelog, installation guide      |
| New Linux package            | Linux download card, installation guide, checksum     |
| UI redesign                  | Product screenshots and simulator presentation        |

## 13.4 Product metadata validation

Create a script that checks:

- Required metadata fields exist.
- Feature IDs are unique.
- Documentation links resolve.
- Routes exist.
- Unsupported integrations are not marked implemented.
- Release artifacts have valid metadata.
- No placeholder download is published as an actual release.

## 13.5 Documentation ownership

Every documentation page should include:

- Page title.
- Description.
- Last reviewed date.
- Applicable desktop version or version range.
- Content owner or responsible module, if useful.

Documentation should be reviewed whenever the associated desktop functionality changes.

## 13.6 Release synchronization

Use one release process to coordinate:

- Desktop version.
- Website release manifest.
- Download links.
- Checksums.
- Changelog.
- Installation documentation.
- Feature status.

Do not make the website version number and desktop version number interchangeable. They are independent applications and should have independent versioning.

## 13.7 Git strategy

Keep the existing repository history and desktop workflow intact.

Recommended branch conventions:

- `feature/website-foundation`
- `feature/website-homepage`
- `feature/website-simulator`
- `feature/website-docs`
- `feature/website-downloads`
- `fix/website-*`

Use clear commits such as:

- `feat(website): add landing page`
- `feat(website): add interactive simulator`
- `docs(website): add installation guides`
- `fix(website): improve mobile navigation`
- `chore(release): update desktop download metadata`

Do not rewrite existing desktop history or change desktop release procedures unnecessarily.

---

# 14. CI/CD and Quality Gates

## 14.1 Separate CI workflows

The monorepo should have independent CI workflows for the desktop application and website.

Website changes should not unnecessarily trigger expensive desktop packaging jobs.

Desktop changes should not automatically trigger a full website deployment unless the website's product metadata, documentation, or release assets are affected.

## 14.2 Website CI checks

On every website pull request:

1. Install locked dependencies.
2. Run formatting and lint checks.
3. Run TypeScript checks.
4. Run unit tests.
5. Validate content metadata.
6. Validate documentation links.
7. Validate release manifest.
8. Build the website.
9. Run selected end-to-end tests.

## 14.3 Desktop-to-website change detection

Add path-aware CI rules for relevant desktop changes.

Examples:

- `app/ui/views/**`
- `app/services/**`
- `platforms/**`
- `modules/**`
- `app/db/models/**`
- `setup/**`
- `docs/**`

When these paths change, trigger a website synchronization review or metadata validation job.

This should not automatically change public product claims. A human or an approved release process must verify the feature status.

## 14.4 End-to-end tests

Critical user journeys:

- Homepage loads.
- Navigation works.
- Product pages render.
- Simulator module navigation works.
- Simulator checkpoint interaction works.
- Documentation search works.
- Download cards show correct release state.
- Download links point to verified artifacts.
- Mobile navigation works.
- Privacy and safety pages render.

---

# 15. Security and Privacy Requirements

Security is part of the product identity.

Requirements:

1. No desktop credentials in website source code.
2. No candidate PII in public simulator fixtures.
3. No local database access.
4. No exposure of the Flask local management server.
5. No public API for automation execution.
6. No secrets in browser bundles.
7. Validate external links.
8. Apply appropriate security headers.
9. Protect any future server-side environment variables.
10. Avoid collecting personal information unless a clearly defined feature requires it.
11. If analytics are introduced, use privacy-conscious configuration and disclose relevant tracking.
12. Keep diagnostic information sanitized before any optional upload.
13. Clearly explain the difference between local desktop data and public website data.

The website must never suggest that it can remotely view, control, or operate the user's desktop JobPilot installation.

---

# 16. Implementation Phases

The AI agent should execute these phases in sequence. Each phase must have a working build and acceptance criteria before moving to the next.

## Phase 0 — Repository discovery and implementation preparation

**Goal:** Understand the existing repository and establish safe boundaries.

Tasks:

- Inspect the repository root.
- Identify the current Python environment and desktop dependency management.
- Identify existing branding and logos.
- Identify existing screenshots and recordings.
- Inspect the current packaging scripts.
- Identify the actual supported platform integrations.
- Inspect current release artifacts.
- Map desktop views and services to website feature groups.
- Identify existing documentation and avoid duplicating it unnecessarily.
- Check current Git conventions.
- Identify deployment options and domain configuration if already decided.

Deliverables:

- Repository integration report.
- Confirmed website directory structure.
- Desktop-to-website feature map.
- Asset inventory.
- List of unverified public claims.
- Website setup proposal.

**Acceptance criteria:**

- Existing desktop application still runs.
- No existing files are moved or broken.
- Website architecture is independent.
- Public product claims are traceable to actual code or approved specifications.

## Phase 1 — Website foundation

**Goal:** Establish a production-quality website application.

Tasks:

- Initialize Next.js and TypeScript in `/website`.
- Configure Tailwind CSS.
- Install and configure UI primitives.
- Establish typography and design tokens.
- Configure routing and layouts.
- Build global header and footer.
- Add responsive navigation.
- Configure metadata defaults.
- Configure linting, formatting, and type checks.
- Configure website-specific testing.
- Add website README with setup commands.

**Acceptance criteria:**

- Website runs independently.
- Desktop Python dependencies remain unaffected.
- All base routes load.
- Responsive navigation works.
- CI can build the website without running the desktop application.

## Phase 2 — Design system and visual foundation

**Goal:** Implement JobPilot's web identity.

Tasks:

- Establish the dark-first palette.
- Implement reusable buttons, badges, cards, containers, and typography.
- Create background and surface treatments.
- Build section layout primitives.
- Implement motion conventions.
- Create responsive layouts.
- Implement reduced-motion behavior.
- Add loading and error states.

**Acceptance criteria:**

- Components use centralized tokens.
- Layout works across mobile, tablet, and desktop.
- Keyboard focus and contrast are tested.
- Animation does not block content.

## Phase 3 — Homepage and marketing pages

**Goal:** Deliver the primary public product experience.

Tasks:

- Build cinematic hero.
- Build problem/solution section.
- Build workflow visualization.
- Build product showcase.
- Build intelligence and automation sections.
- Build platform ecosystem.
- Build privacy and safety section.
- Build CTA and footer.
- Build `/platform`.
- Build `/how-it-works`.
- Build `/about`.

**Acceptance criteria:**

- Main product narrative is understandable without reading documentation.
- Actual screenshots are used wherever the website claims to show the real desktop UI.
- Feature claims are verified.
- All CTAs lead to valid routes or verified actions.
- Mobile layouts are complete.

## Phase 4 — Interactive product simulator

**Goal:** Deliver a convincing interactive demonstration.

Tasks:

- Build simulator shell.
- Build navigation and panel routing.
- Implement sample data.
- Implement dashboard.
- Implement search.
- Implement jobs queue.
- Implement automation simulation.
- Implement checkpoints.
- Implement resume and Q&A panels.
- Implement applications and outreach.
- Implement analytics.
- Add demo-data warning.
- Add responsive simulator behavior.
- Add simulator tests.

**Acceptance criteria:**

- Every advertised simulator module is interactive.
- State transitions are deterministic.
- Checkpoint interactions work.
- No real desktop or portal data is accessed.
- No external applications are submitted.
- Demo data is clearly labelled.

## Phase 5 — Download center and release management

**Goal:** Publish verified desktop distribution information.

Tasks:

- Define release manifest schema.
- Implement release manifest validation.
- Build Windows download card.
- Build Linux download card.
- Add package metadata.
- Add checksum presentation.
- Add changelog integration.
- Add installation documentation links.
- Validate artifact availability.
- Add unavailable and upcoming release states.

**Acceptance criteria:**

- Every active download points to a verified artifact.
- Checksums match published files.
- Missing releases show an honest unavailable state.
- Release updates do not require editing multiple website components.

## Phase 6 — Documentation portal

**Goal:** Deliver user and developer documentation.

Tasks:

- Configure MDX documentation.
- Implement sidebar navigation.
- Implement documentation search.
- Create getting-started guide.
- Create Windows and Linux installation guides.
- Create feature guides.
- Create safety and privacy guides.
- Create developer setup guide.
- Create architecture documentation.
- Add Mermaid diagrams.
- Add version metadata.
- Add code examples.
- Add troubleshooting pages.

**Acceptance criteria:**

- Documentation is searchable.
- Navigation works on mobile and desktop.
- Code blocks are readable and copyable.
- Internal links are validated.
- Technical descriptions match the verified desktop implementation.

## Phase 7 — Architecture, SEO, accessibility, and performance

**Goal:** Prepare the website for public release.

Tasks:

- Complete architecture diagrams.
- Add metadata and Open Graph images.
- Add sitemap and robots configuration.
- Validate canonical URLs.
- Test accessibility.
- Optimize image delivery.
- Optimize 3D assets.
- Test reduced-motion behavior.
- Measure Lighthouse performance.
- Test mobile rendering.
- Add security headers.

**Acceptance criteria:**

- No critical accessibility issues remain.
- No major layout or performance regression.
- SEO metadata is present.
- 3D failure does not break the page.
- Core product information remains accessible without JavaScript-heavy visual components.

## Phase 8 — Release, deployment, and operational handover

**Goal:** Publish the website and make future maintenance repeatable.

Tasks:

- Configure production environment.
- Configure domain and HTTPS.
- Configure hosting.
- Configure website CI/CD.
- Configure release metadata update workflow.
- Configure monitoring and error reporting if required.
- Verify download links.
- Verify documentation.
- Run full regression tests.
- Prepare deployment and rollback instructions.
- Document ownership and change workflow.

**Acceptance criteria:**

- Production build succeeds.
- All public routes work.
- Downloads are verified.
- No secrets are exposed.
- Desktop CI and release workflows remain functional.
- A future desktop release can update the website through the documented synchronization process.

---

# 17. Prioritization

## P0 — Required for initial public website

- Monorepo isolation.
- Website foundation.
- Responsive homepage.
- Product page.
- Interactive demo.
- Download center with truthful release states.
- Getting-started documentation.
- Privacy and safety information.
- SEO basics.
- CI build and validation.

## P1 — Important for product maturity

- Full user guide.
- Developer portal.
- Architecture pages.
- Changelog.
- Advanced simulator modules.
- More detailed workflow animations.
- Searchable documentation.
- Release synchronization automation.
- Full end-to-end testing.

## P2 — Future enhancements

- Public API documentation if an API is introduced.
- Interactive architecture explorer.
- Release notification subscription.
- Opt-in update checker.
- Community and contribution portal.
- Product tutorial videos.
- Localization.
- Optional privacy-conscious website analytics.

Do not introduce cloud accounts, SaaS subscriptions, remote automation, or cloud synchronization unless the product scope is explicitly revised.

---

# 18. Final Acceptance Checklist

The website is ready for public beta when all of the following are true.

### Product and design

- [ ] JobPilot brand identity is consistent.
- [ ] Homepage clearly explains the product.
- [ ] Product features are based on verified capabilities.
- [ ] Actual screenshots are distinguishable from simulated screens.
- [ ] Desktop and mobile layouts work.
- [ ] Animations have accessible fallbacks.

### Simulator

- [ ] Simulator navigation works.
- [ ] Dashboard is interactive.
- [ ] Job discovery simulation works.
- [ ] Jobs queue works.
- [ ] Automation state simulation works.
- [ ] Human checkpoint interaction works.
- [ ] Q&A provenance is demonstrated.
- [ ] Demo data is labelled.
- [ ] No real applications or messages are sent.

### Downloads

- [ ] Windows release state is accurate.
- [ ] Linux release state is accurate.
- [ ] Active download URLs are verified.
- [ ] Checksums are validated.
- [ ] Installation instructions are available.
- [ ] Changelog is synchronized.

### Documentation

- [ ] User installation guide exists.
- [ ] First-launch guide exists.
- [ ] Profile and resume guides exist.
- [ ] Platform setup guide exists.
- [ ] Automation and Safe Mode guides exist.
- [ ] Privacy and safety guide exists.
- [ ] Developer setup guide exists.
- [ ] Architecture documentation exists.
- [ ] Internal documentation links work.

### Engineering

- [ ] Website builds independently.
- [ ] Desktop application remains functional.
- [ ] Desktop dependencies are unchanged unless explicitly required.
- [ ] Website tests pass.
- [ ] Desktop tests remain unaffected.
- [ ] CI path filters work.
- [ ] No secrets or private candidate data are exposed.
- [ ] Production deployment and rollback procedures are documented.

---

# 19. Instructions to the AI Implementation Agent

You are working inside the existing JobPilot monorepo. You already have knowledge of the existing desktop codebase. Your task is to implement a new public website application in a separate `/website` directory.

Treat this document as the product and engineering direction. Treat the existing desktop source code as the authority for what is actually implemented.

## Mandatory execution rules

1. Before coding, inspect the current repository structure and existing project configuration.
2. Do not assume that every PRD feature is already implemented or stable.
3. Do not modify the desktop application's architecture to accommodate the website.
4. Keep Python and Node.js environments independent.
5. Do not introduce a website-to-desktop runtime dependency.
6. Build the website as a separate application within the monorepo.
7. Reuse approved brand assets and actual desktop screenshots.
8. Use fictional, deterministic data for the interactive simulator.
9. Do not expose candidate information, credentials, SQLite data, or local management endpoints.
10. Verify actual Windows and Linux release artifacts before enabling downloads.
11. Do not create placeholder links that look like real downloads.
12. Keep public feature metadata centralized.
13. Build documentation using version-aware MDX content.
14. Add tests and validation as part of implementation, not as a final afterthought.
15. Preserve existing desktop tests, packaging, and release workflows.
16. Prefer reusable components over duplicated page implementations.
17. Optimize 3D and animation for real-world devices.
18. Support keyboard interaction, reduced motion, and responsive layouts.
19. Implement each phase with a working build and acceptance criteria.
20. Do not silently skip a requirement. Record blockers and explain their impact.

## Required first deliverable from the agent

Before implementing the website, produce an implementation plan based on the actual repository.

It must include:

1. Current repository structure and the proposed `/website` integration.
2. Existing desktop feature-to-website mapping.
3. Verified versus unverified product capabilities.
4. Available brand assets, screenshots, and videos.
5. Actual Windows and Linux packaging/release status.
6. Recommended Next.js application structure.
7. Dependency and environment setup.
8. Detailed page/component breakdown.
9. Simulator architecture and data model.
10. Documentation migration and content plan.
11. CI/CD changes and path filters.
12. Security and privacy boundaries.
13. Test strategy.
14. Phase-wise implementation tasks and dependencies.
15. Risks, blockers, and decisions requiring human approval.

After that report is approved, implement the phases in order.

Do not start by generating every page in one large implementation. Establish the foundation, build the design system, complete the homepage, then develop the simulator, documentation, and release center.

**Final engineering objective:** A polished, high-performance public JobPilot website that evolves alongside the existing desktop application without coupling the two applications or compromising the local-first privacy and safety architecture.
