Redesign the existing JobPilot "Automation Control Center" page into a modern, premium automation playground / execution command center.

IMPORTANT:
- This is a UI/UX transformation only.
- Do NOT change the existing backend architecture, services, database models, automation engines, Selenium logic, signals, or business logic.
- Do NOT remove existing functionality.
- Reuse the existing data, signals, state, and actions.
- Do NOT create fake backend functionality just to make the UI look complete.
- Keep the current PySide6 architecture and existing component/service boundaries.
- Only improve the presentation, information hierarchy, interactions, layout, and visual design.
- The result must look like a real production SaaS/ATS automation product, not an admin panel or developer console.

REFERENCE:
The current page is the existing Automation Control Center. Treat it as the functional source of truth and redesign it rather than creating a completely unrelated screen.

==================================================
CORE DESIGN DIRECTION
==================================================

The page should feel like:

"Mission Control + Automation Playground + Live Job Application Workspace"

Imagine a modern ATS combined with a browser automation control center.

The user should immediately understand:

1. Is automation running?
2. Which platform is running?
3. What keyword is currently being processed?
4. What job is currently being processed?
5. How much work has been completed?
6. What is the automation doing RIGHT NOW?
7. How many jobs were discovered/evaluated/qualified/applied/skipped?
8. Are there errors or manual interventions?
9. What happened during the current run?
10. Can I safely stop the automation?

The page should feel alive even when automation is running.

==================================================
VISUAL STYLE
==================================================

Move away from the current "many dark rectangular boxes" design.

Use a modern SaaS/ATS visual language:

- clean
- spacious
- premium
- minimal
- professional
- information-dense without feeling crowded
- subtle borders
- subtle shadows
- restrained corner radius
- strong typography hierarchy
- semantic colors
- modern iconography
- clear active states
- excellent spacing
- strong visual grouping

Do NOT:
- use excessive borders around every element
- create nested boxes inside boxes everywhere
- use huge empty containers
- use excessive gradients
- use neon/glowing effects
- make it look like a gaming dashboard
- use random emojis
- use decorative elements that don't communicate information
- make every metric a giant card

The UI should resemble a modern ATS/SaaS product.

==================================================
THEME SYSTEM
==================================================

Support BOTH:

1. Dark theme
2. Light theme

Do not implement light mode as simply "dark mode with white backgrounds."

Create a proper semantic design-token system:

Dark:
- application background
- surface
- elevated surface
- border
- primary text
- secondary text
- muted text
- primary accent
- success
- warning
- danger
- info

Light:
- white / very light application background
- white cards
- subtle gray borders
- dark text
- muted slate text
- same semantic accent colors

All components must consume theme tokens.

Do not hardcode colors throughout the view.

==================================================
NEW PAGE STRUCTURE
==================================================

Redesign the page into approximately these sections:

--------------------------------------------------
1. PAGE HEADER / RUN COMMAND BAR
--------------------------------------------------

Top:

Automation

"Run and monitor your job application automation in real time."

On the right:

[ LinkedIn Ready ]
[ Naukri Ready ]

Primary action:

[ ▶ Start Automation ]

Secondary:

[ ■ Stop ]

The primary action should be visually dominant.

When running:

Start becomes disabled.

Stop becomes prominent.

Display:

● RUNNING
or
● IDLE
or
● STOPPING
or
● ERROR

Use status badges rather than large rectangular status boxes.

--------------------------------------------------
2. ACTIVE RUN HERO / LIVE PLAYGROUND
--------------------------------------------------

This should become the main visual focus of the page.

Create a large "Live Automation" area.

Example concept:

┌───────────────────────────────────────────────────────────┐
│ ● RUNNING                         LinkedIn · Easy Apply   │
│                                                           │
│ Searching for                                            │
│ RPA Developer                                             │
│                                                           │
│ Currently processing                                      │
│ RPA Developer — ABC Technologies                         │
│                                                           │
│ ███████████████████░░░░░░░                               │
│                                                           │
│ Evaluating job 18 of 42                                  │
│                                                           │
│ [View Job]                         [Stop Automation]       │
└───────────────────────────────────────────────────────────┘

Make this feel like the automation is actually "alive."

Include:

- current platform
- current keyword
- current job
- current operation
- elapsed time
- current step
- progress
- current application state

Possible current states:

DISCOVERING
EVALUATING
QUALIFYING
OPENING JOB
APPLYING
ANSWERING QUESTIONS
SUBMITTING
COMPLETED
WAITING
MANUAL ACTION REQUIRED
ERROR

Do not fake these states. Bind them to existing automation state/signals where available.

--------------------------------------------------
3. LIVE AUTOMATION PIPELINE
--------------------------------------------------

Create a horizontal or compact pipeline visualization:

DISCOVERED
   ↓
EVALUATED
   ↓
QUALIFIED
   ↓
APPLYING
   ↓
SUBMITTED

Show counts beneath each stage.

Example:

      124              86              31              22              18
   Discovered       Evaluated       Qualified        Applying        Submitted

Use subtle progress visualization.

This should visually communicate the automation pipeline much better than six disconnected metric cards.

--------------------------------------------------
4. RUN METRICS
--------------------------------------------------

Create a compact KPI row.

Metrics:

Jobs discovered
Jobs evaluated
Qualified
Submitted
Skipped
Errors

Each metric should have:

- small icon
- label
- large value
- optional delta/context
- semantic status color

Example:

Jobs discovered
124

Evaluated
86

Qualified
31

Submitted
18

Skipped
55

Errors
1

Do not create huge tall cards.

Keep them compact and readable.

--------------------------------------------------
5. CURRENT JOB WORKSPACE
--------------------------------------------------

Add a "Current Job" panel.

When processing a job, display:

Company
Job title
Platform
Location
Experience
Salary if available
Application type
Current stage

Example:

ABC Technologies
RPA Developer

LinkedIn
Bangalore · 2–4 years

Easy Apply

Status:
Answering application questions

Actions:

[ Open Job ]
[ View Application ]

If no active job:

"No job is currently being processed."

Show a useful empty state instead of an empty black rectangle.

--------------------------------------------------
6. LIVE ACTIVITY STREAM
--------------------------------------------------

Replace the giant empty terminal-like area with a structured activity timeline.

Title:

Live Activity

Each event should be a clean activity row:

19:42:18
✓ Job discovered
RPA Developer — ABC Technologies

19:42:21
✓ Job qualified
Experience requirement matched

19:42:28
→ Opening Easy Apply
ABC Technologies

19:42:41
✓ Application submitted
RPA Developer — ABC Technologies

Use semantic event types:

SUCCESS
INFO
WARNING
ERROR
ACTION
MANUAL_REQUIRED

Use subtle icons and timestamps.

The activity stream should auto-scroll while automation runs.

Add:

[ Pause Auto-scroll ]

[ Clear ]

Do not make it look like a raw terminal unless the user specifically opens detailed logs.

--------------------------------------------------
7. RUN SUMMARY / SESSION HISTORY
--------------------------------------------------

Add a compact "Current Run" or "Last Run" section.

Example:

Last run
LinkedIn · 18 Sep 2026 · 32 min

Jobs discovered       124
Qualified              31
Applications           18
Skipped                55
Errors                  1

[ View Run Details ]

If the backend already exposes run history, use it.

If not, design the UI so it can consume it later without fake data.

--------------------------------------------------
8. MANUAL INTERVENTION AREA
--------------------------------------------------

This is important for real automation.

When login/captcha/manual action is required, show a prominent but clean alert:

⚠ Manual action required

LinkedIn session requires attention.

[ Open Browser ]
[ I've Resolved It ]

Possible states:

- LOGIN_REQUIRED
- CAPTCHA_DETECTED
- MANUAL_ACTION_REQUIRED
- QUESTION_REQUIRES_INPUT
- SESSION_EXPIRED

Do NOT hide these events inside logs.

They should become first-class UI states.

--------------------------------------------------
9. ERROR STATE
--------------------------------------------------

Errors should be visible but not visually overwhelming.

Example:

⚠ 2 automation errors

Latest:
Unable to open application page.

[ View Details ]

Use a red/danger treatment only for actual errors.

Warnings should use amber.

Normal activity should remain neutral.

==================================================
INTERACTION DESIGN
==================================================

The Automation page should behave like a real control center.

When IDLE:

Show:
- platform selection
- start action
- connection status
- previous run summary
- empty state

When RUNNING:

Show:
- active status
- live progress
- current keyword
- current job
- real-time activity
- metrics updating
- stop action

When STOPPING:

Show:
- STOPPING state
- disable start
- progress until worker exits

When COMPLETED:

Show:
- success state
- run summary
- completed metrics
- "Run Again"

When ERROR:

Show:
- error summary
- affected platform
- recovery action
- logs/details

==================================================
PLATFORM SELECTION
==================================================

Make platform selection modern.

Instead of a basic dropdown:

Use compact platform selector cards/tabs:

[ LinkedIn ]
Ready
Last run: 18 min ago

[ Naukri ]
Ready
Last run: 1 hr ago

[ All Platforms ]

If "All Platforms" exists, execute sequentially according to the existing backend behavior.

Do not introduce concurrent browser automation.

==================================================
MICRO INTERACTIONS
==================================================

Add subtle professional interactions:

- button hover
- button pressed state
- status transitions
- progress animation
- metric number updates
- activity item entrance
- toast notification after start/stop/completion
- smooth theme transition if supported
- subtle card hover

Avoid flashy animations.

Automation should feel active, not distracting.

==================================================
RESPONSIVE DESKTOP LAYOUT
==================================================

The current page wastes horizontal and vertical space.

Use the available desktop width efficiently.

Recommended structure:

Top:
Page header + actions

Then:
Large Live Automation Hero

Then:
Pipeline

Then:
Metrics

Then:
Two-column workspace

LEFT:
Current Job + Current Run

RIGHT:
Live Activity

Then:
Run History / Summary

Use responsive layouts so the page works well at:

1920x1080
1600x900
1366x768

Avoid fixed dimensions that cause clipping.

==================================================
EMPTY STATES
==================================================

Never show huge blank dark rectangles.

For example, instead of:

[ huge empty Live Activity box ]

show:

No automation is running

Start an automation run to see live activity here.

[ ▶ Start Automation ]

Similarly:

No active job

The current job being evaluated will appear here.

==================================================
TYPOGRAPHY
==================================================

Create clear hierarchy:

Page title:
large / strong

Subtitle:
small / muted

Section title:
medium / semibold

Metric:
large / bold

Metric label:
small / muted

Activity:
normal readable body text

Timestamp:
small / muted

Avoid making every heading look like a bordered label.

==================================================
ICONOGRAPHY
==================================================

Use ONE consistent icon system.

Do not use arbitrary emojis.

Suggested icon semantics:

Play → start
Stop → stop
Search → discovering
Check → qualified/submitted
Clock → waiting
Warning → warning/manual intervention
Error → failure
Browser → platform
Briefcase → job
Activity → live execution
Terminal/log → detailed logs

==================================================
ACCESSIBILITY
==================================================

Ensure:

- strong text contrast
- visible keyboard focus
- buttons have accessible labels
- status isn't communicated by color alone
- icon-only buttons have tooltips
- tables/activity streams remain keyboard accessible

==================================================
DATA / BACKEND SAFETY
==================================================

CRITICAL:

Do not invent fake automation data.

The UI must consume the existing:

- AutomationManager
- AutomationWorker
- Qt signals
- AutomationBridge
- JobService
- ApplicationService
- LogService
- existing LinkedIn/Naukri automation

Map existing signals into the new visual components.

For example:

started
→ run status

progress
→ metrics + current keyword

job_found
→ activity stream + discovered count

app_submitted
→ submitted count + activity

error
→ error state/activity

finished
→ run summary

If a desired UI value does not currently exist in the backend, create a clean UI placeholder/state rather than fabricating data.

Do NOT modify Selenium behavior.

Do NOT rewrite LinkedIn automation.

Do NOT rewrite Naukri automation.

Do NOT modify database architecture merely for visual purposes.

==================================================
CODE QUALITY
==================================================

Refactor the current AutomationView into reusable components.

Prefer components such as:

AutomationHeader
PlatformSelector
AutomationHero
AutomationPipeline
AutomationMetricRow
CurrentJobCard
LiveActivityStream
RunSummaryCard
ManualInterventionBanner
AutomationStatusBadge

Do not put the entire UI into one giant file.

Use the existing design system/theme manager if already available.

If a design-system layer does not yet exist, create it first.

==================================================
IMPORTANT VISUAL TARGET
==================================================

The final result should NOT look like:

"Python desktop application with boxes."

It should look like:

"A polished modern ATS product with a real automation execution playground."

The first impression should be:

"Something is actually running here."

The user should be able to glance at the page and immediately understand the automation state and progress.

Prioritize:

1. Visual hierarchy
2. Live execution visibility
3. Clear actions
4. Information density
5. Modern ATS aesthetics
6. Light/dark theme consistency
7. Professional spacing
8. Real-time feedback
9. Empty/loading/error states
10. Reusable components

Preserve all existing functionality while completely transforming the visual experience.
