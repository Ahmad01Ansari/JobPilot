# JobPilot — Sidebar & Navigation UX Transformation

Redesign the JobPilot desktop application's LEFT SIDEBAR into a premium, modern ATS/job-automation navigation system.

This is a UI/UX transformation.

DO NOT change backend services, database models, automation engines, Selenium logic, or business logic.

The existing navigation functionality must remain available.

The goal is to transform the current sidebar from a traditional desktop-app navigation into something that feels like a modern SaaS ATS / recruitment automation product.

============================================================
1. CURRENT PROBLEMS TO FIX
============================================================

The current sidebar has several UX problems:

1. Navigation hierarchy is not logical.
2. Automation, which is the core execution playground, is buried under "Intelligence".
3. Jobs, Applications, Interviews and Follow-ups do not visually communicate a natural recruitment lifecycle.
4. Candidate-related pages are separated from the rest of the workflow without enough hierarchy.
5. Icons are inconsistent and look like emojis/text symbols rather than a professional application icon system.
6. Expanded and collapsed sidebar icon positions are not perfectly aligned.
7. Icon-to-label spacing is inconsistent.
8. Active navigation states look too heavy.
9. The "SMART ATS" subtitle below JobPilot does not communicate the product's actual purpose clearly.
10. Sidebar feels like a Python desktop application rather than a polished modern ATS.
11. Collapsing the sidebar can cause awkward alignment/content positioning.
12. Section labels are visually weak and navigation hierarchy is not immediately obvious.

Fix all of these.

============================================================
2. PRODUCT BRANDING
============================================================

Current:

JobPilot
SMART ATS

Replace the secondary branding.

Use:

JobPilot
JOB AUTOMATION

The visual hierarchy should be:

JobPilot
JOB AUTOMATION

"JobPilot" is the primary brand.

"JOB AUTOMATION" is a small uppercase product descriptor.

Do NOT use:
- SMART ATS
- AI ATS
- AI POWERED ATS
- generic marketing slogans

Keep the branding compact and professional.

The logo should remain simple:

[ JP ] JobPilot

The JP logo should use the existing brand accent.

Do not make the logo excessively large.

============================================================
3. INFORMATION ARCHITECTURE
============================================================

Reorganize the navigation into the following hierarchy:

------------------------------------------------------------
WORKSPACE
------------------------------------------------------------

Dashboard
Automation

Automation is intentionally near the top.

Reason:

Automation is the central execution playground of JobPilot.

The user should be able to reach it immediately.

------------------------------------------------------------
JOBS
------------------------------------------------------------

All Jobs
Easy Apply
Company Portal
Job Search

This represents the job discovery layer.

Important:

"All Jobs" is the master job view.

"Easy Apply" and "Company Portal" are filtered job views.

Do not create duplicate navigation concepts that imply separate databases.

------------------------------------------------------------
PIPELINE
------------------------------------------------------------

Applications
Interviews
Follow-ups

This represents the recruitment lifecycle after job discovery/application.

The natural mental model is:

Jobs
    ↓
Applications
    ↓
Interviews
    ↓
Follow-ups

------------------------------------------------------------
INSIGHTS
------------------------------------------------------------

Analytics

Analytics is a reporting/decision-support area, not an execution area.

------------------------------------------------------------
CANDIDATE
------------------------------------------------------------

Profile
Resumes

Candidate information should be visually grouped together.

------------------------------------------------------------
SYSTEM
------------------------------------------------------------

Platforms
Logs
Settings

These are configuration/diagnostic pages.

============================================================
4. FINAL SIDEBAR ORDER
============================================================

The final navigation should be:

WORKSPACE

  Dashboard
  Automation

JOBS

  All Jobs
  Easy Apply
  Company Portal
  Job Search

PIPELINE

  Applications
  Interviews
  Follow-ups

INSIGHTS

  Analytics

CANDIDATE

  Profile
  Resumes

SYSTEM

  Platforms
  Logs
  Settings

Do not add additional navigation items unless they already exist in the application.

Do not remove existing functionality.

If the current application internally uses different route names, preserve the route names and only change their visual presentation/order.

============================================================
5. WHY THIS ORDER MATTERS
============================================================

The sidebar should communicate the user's workflow:

DISCOVER
    ↓
JOBS
    ↓
APPLY
    ↓
APPLICATION
    ↓
INTERVIEW
    ↓
FOLLOW-UP
    ↓
ANALYZE

And separately:

CANDIDATE
SYSTEM

Automation is placed near the top because it is the core action/execution environment.

This should be immediately understandable without reading documentation.

============================================================
6. MODERN ICON SYSTEM
============================================================

The current sidebar uses emoji-like symbols such as:

📊
👤
📄
🌐
🔍
💼
📋
📅
⏰
📈
⚡
💻
⚙

DO NOT use emoji characters as navigation icons.

They look inconsistent across Linux/system fonts and do not provide a professional SaaS appearance.

Use ONE consistent vector icon system.

Prefer:
- existing project icon system if already available
- SVG icons
- Qt-compatible vector icons
- an existing icon library already present in the project

Do NOT introduce a new dependency unless necessary.

Use consistent stroke weight and visual style.

Suggested semantic icon mapping:

Dashboard
→ grid/dashboard icon

Automation
→ play-circle / bot / workflow icon

All Jobs
→ briefcase

Easy Apply
→ lightning / send / zap icon

Company Portal
→ building / external-link icon

Job Search
→ search

Applications
→ file-check / send

Interviews
→ calendar

Follow-ups
→ clock / message-circle

Analytics
→ chart

Profile
→ user

Resumes
→ file-text

Platforms
→ globe / network

Logs
→ terminal / activity

Settings
→ settings/gear

Use the project's existing icon conventions where possible.

============================================================
7. ICON ALIGNMENT
============================================================

This is a critical requirement.

Expanded sidebar:

┌──────────────┐
│  icon  Label │
│  icon  Label │
│  icon  Label │
└──────────────┘

Every icon must have exactly the same horizontal position.

Do NOT let icon position depend on label length.

Use a fixed icon column.

For example:

SIDEBAR CONTENT
│
├── ICON COLUMN: fixed width
│
└── LABEL COLUMN: flexible

All icons must align vertically.

Example:

[icon] Dashboard
[icon] Automation
[icon] All Jobs
[icon] Easy Apply
[icon] Applications
[icon] Interviews

The left edge of every icon must be identical.

The label starting position must also be identical.

============================================================
8. COLLAPSED SIDEBAR
============================================================

When collapsed:

Only icons should remain.

Example:

┌──────┐
│  JP  │
│      │
│  ▦   │
│  ▶   │
│      │
│  💼  │
│  ⚡  │
│  🏢  │
│      │
│  ◫   │
│  ◷   │
└──────┘

But use SVG/vector icons rather than emojis.

Every icon must be centered in exactly the same horizontal centerline.

Do NOT simply hide labels while keeping the expanded layout geometry.

Collapsed mode must have its own correct geometry:

expanded:
icon + label

collapsed:
centered icon

The icon must not shift unpredictably.

============================================================
9. SIDEBAR WIDTH
============================================================

Use two intentional sidebar widths.

Expanded:

approximately 220–250 px

Collapsed:

approximately 64–72 px

Do not make the sidebar unnecessarily wide.

The main content area must automatically resize/reflow when the sidebar changes state.

Avoid:

- content clipping
- horizontal overlap
- widgets moving underneath the sidebar
- incorrect margins
- partially hidden page titles

The current screenshot shows the main content becoming awkwardly clipped when the sidebar state changes.

Fix the parent layout geometry.

Use proper Qt layout management instead of manually positioning the main content.

============================================================
10. COLLAPSE / EXPAND BEHAVIOR
============================================================

Add a professional collapse button.

The collapse button should be located near the top navigation/header area.

Use:

expanded:
← / panel-left icon

collapsed:
→ / panel-right icon

Do NOT use a hamburger icon if it causes ambiguity between:

- application menu
- sidebar collapse
- mobile navigation

For desktop, a panel-collapse icon is clearer.

If the existing hamburger interaction is already required, preserve its behavior but redesign its visual treatment.

============================================================
11. ACTIVE NAVIGATION STATE
============================================================

The active page should be immediately recognizable.

Current active state:

large dark-red block

Replace it with a modern ATS active-state treatment.

Recommended:

- subtle accent background
- thin accent indicator on the left
- accent-colored icon
- stronger label weight
- subtle border or glow only if needed

Example:

│
│  ┌────────────────────────────┐
│  │ ▸  ⚡ Automation            │
│  └────────────────────────────┘
│

Use the JobPilot accent color.

Do NOT make the active state look like a giant red button.

The navigation item is not a button/action.

It is a selected location.

============================================================
12. HOVER STATE
============================================================

Navigation items should have subtle hover feedback.

Hover:

- slightly elevated background
- icon becomes more visible
- label becomes slightly brighter

Do NOT use aggressive animations.

Transition should be approximately 120–180 ms if animation is supported.

============================================================
13. SECTION LABELS
============================================================

Current section labels:

OVERVIEW
CANDIDATE
OPERATIONS
PIPELINE
INTELLIGENCE
SYSTEM

These labels should become cleaner.

Use:

WORKSPACE
JOBS
PIPELINE
INSIGHTS
CANDIDATE
SYSTEM

Section labels should be:

- small
- uppercase
- letter-spaced
- muted
- visually subtle

Do not put every section inside a bordered rectangle.

The current boxed section headers make the sidebar feel old-fashioned.

Instead:

WORKSPACE

  Dashboard
  Automation


JOBS

  All Jobs
  Easy Apply
  Company Portal
  Job Search

Use whitespace to establish grouping.

============================================================
14. NAVIGATION ITEM HEIGHT
============================================================

Use consistent navigation item height.

Recommended:

approximately 36–42 px

Each item should have:

- icon
- label
- consistent vertical padding
- consistent spacing

Do not let different labels create different row heights.

============================================================
15. GROUP SPACING
============================================================

Use meaningful spacing between groups.

Example:

WORKSPACE
Dashboard
Automation

small gap

JOBS
All Jobs
Easy Apply
Company Portal
Job Search

medium gap

PIPELINE
Applications
Interviews
Follow-ups

medium gap

INSIGHTS
Analytics

medium gap

CANDIDATE
Profile
Resumes

medium gap

SYSTEM
Platforms
Logs
Settings

This makes the hierarchy readable without requiring borders.

============================================================
16. OPTIONAL BADGES
============================================================

Where useful, allow small contextual badges.

Examples:

Applications    12
Follow-ups       3
Interviews       2

But do NOT add fake numbers.

Only show badges when backed by actual database/service data.

If no data exists:

do not show "0" everywhere.

The sidebar should remain clean.

============================================================
17. SIDEBAR FOOTER
============================================================

At the bottom, optionally provide a compact system/status area.

For example:

● Engine Ready
● Database Connected

But do not duplicate the entire application's bottom status bar.

If system status already exists elsewhere, don't repeat it.

Keep the sidebar footer minimal.

============================================================
18. USER PROFILE AREA
============================================================

The candidate profile should NOT dominate the sidebar.

If the current profile/avatar exists, keep it compact.

Preferred:

[avatar] Ahmad Raza
        Candidate

or:

[avatar]

when collapsed.

Do not make a huge profile card.

The primary navigation must remain visually dominant.

============================================================
19. RESPONSIVE DESKTOP BEHAVIOR
============================================================

The sidebar must work correctly at:

1920 × 1080
1600 × 900
1366 × 768

At smaller widths:

- sidebar may collapse automatically if existing architecture supports it
- otherwise allow manual collapse
- main content must remain usable

Never allow:

sidebar > available window width

or:

main content hidden behind sidebar

============================================================
20. LIGHT AND DARK THEME
============================================================

The sidebar must support both:

DARK THEME
LIGHT THEME

Do not simply invert colors.

Use semantic theme tokens.

Dark theme:

background
surface
hover
active
border
primary text
secondary text
muted text
accent

Light theme:

background
surface
hover
active
border
primary text
secondary text
muted text
accent

All navigation components must consume the global theme.

Do not hardcode colors inside individual sidebar widgets.

============================================================
21. BRAND ACCENT
============================================================

Use one primary JobPilot accent throughout:

- logo
- active navigation
- focus state
- selected icons
- primary actions

Use semantic colors only for status.

Do not make the entire sidebar colorful.

The sidebar should be mostly neutral with a controlled accent.

============================================================
22. TYPOGRAPHY
============================================================

Brand:

JobPilot
→ strong, clean, modern

JOB AUTOMATION
→ tiny uppercase descriptor

Section labels:
→ 10–11 px
→ uppercase
→ letter spacing
→ muted

Navigation:
→ 13–14 px
→ medium weight

Active navigation:
→ slightly stronger weight

Avoid excessive bold text.

============================================================
23. MICRO-INTERACTIONS
============================================================

Add subtle polished interactions:

- hover transition
- active state transition
- collapse/expand transition
- icon color transition
- tooltip when collapsed

Do NOT use:

- bouncing
- glowing neon
- excessive shadows
- large animations
- flashy gradients

The product should feel professional, not like a gaming dashboard.

============================================================
24. TOOLTIP BEHAVIOR
============================================================

When collapsed, hovering an icon should show a tooltip:

Dashboard
Automation
All Jobs
Easy Apply
Company Portal
Applications
Interviews
Follow-ups
Analytics
Profile
Resumes
Platforms
Logs
Settings

Tooltip must be positioned outside the collapsed sidebar without clipping.

============================================================
25. IMPORTANT AUTOMATION PRIORITY
============================================================

Automation is one of the most important pages in JobPilot.

Its navigation placement must reflect that.

The user journey should feel like:

Dashboard
    ↓
Automation
    ↓
Jobs
    ↓
Applications
    ↓
Interviews
    ↓
Follow-ups
    ↓
Analytics

Automation should never feel buried under an unrelated "Intelligence" category.

============================================================
26. DO NOT CHANGE ROUTING
============================================================

This is a visual/navigation transformation.

Do not break:

- NAV_ITEMS
- route identifiers
- view registration
- signal connections
- navigation handlers
- permissions
- service dependencies

If the existing application has 13 navigation destinations, preserve all 13 destinations.

Only reorganize their presentation.

If the architecture requires keeping the existing NAV_ITEMS ordering internally, create a presentation/order mapping rather than breaking route definitions.

============================================================
27. DO NOT CREATE DUPLICATE NAVIGATION ITEMS
============================================================

For the new Jobs hierarchy:

All Jobs
Easy Apply
Company Portal
Job Search

these may be views/filters over the existing Jobs system.

Do not create duplicate backend pages or duplicate database entities just for navigation.

Reuse the existing JobsView/service architecture.

============================================================
28. COMPONENT ARCHITECTURE
============================================================

Do not keep all sidebar logic in one giant view.

Create/reuse components such as:

Sidebar
    ├── SidebarBrand
    ├── SidebarCollapseButton
    ├── SidebarSection
    ├── SidebarNavItem
    ├── SidebarTooltip
    └── SidebarFooter

Use a data-driven navigation definition.

Example concept:

NavigationGroup(
    title="WORKSPACE",
    items=[
        Dashboard,
        Automation
    ]
)

NavigationGroup(
    title="JOBS",
    items=[
        All Jobs,
        Easy Apply,
        Company Portal,
        Job Search
    ]
)

Do not hardcode the same widget creation logic repeatedly.

============================================================
29. ICON DATA MODEL
============================================================

Navigation configuration should define:

- route
- label
- icon
- section
- tooltip
- optional badge provider

For example:

{
    "route": "automation",
    "label": "Automation",
    "icon": "automation",
    "section": "WORKSPACE"
}

The exact implementation should follow the existing project architecture.

============================================================
30. VISUAL QA
============================================================

After implementation, render screenshots of:

1. Expanded + Dark
2. Collapsed + Dark
3. Expanded + Light
4. Collapsed + Light

Also verify:

5. Automation active
6. Jobs active
7. Applications active
8. Settings active

Check specifically:

- every icon has identical alignment
- every label begins at the same x-coordinate
- active item is visually clear
- section spacing is consistent
- collapse state is centered
- sidebar does not clip main content
- main content reflows correctly
- branding is clean
- no emoji icons remain
- no random icon styles remain

============================================================
31. ACCEPTANCE CRITERIA
============================================================

The redesigned sidebar should feel like:

"Modern SaaS ATS + Job Automation Platform"

NOT:

"Python desktop application with a list of buttons."

The user should understand the product structure within seconds.

Final hierarchy:

JOBPILOT
JOB AUTOMATION

WORKSPACE
  Dashboard
  Automation

JOBS
  All Jobs
  Easy Apply
  Company Portal
  Job Search

PIPELINE
  Applications
  Interviews
  Follow-ups

INSIGHTS
  Analytics

CANDIDATE
  Profile
  Resumes

SYSTEM
  Platforms
  Logs
  Settings

The sidebar should be:

- modern
- minimal
- aligned
- consistent
- responsive
- theme-aware
- accessible
- visually balanced
- ATS-oriented
- automation-oriented
- production-quality

Most importantly:

DO NOT simply make the existing sidebar prettier.

Rebuild its INFORMATION HIERARCHY and VISUAL SYSTEM while preserving all existing functionality.
