# JobPilot — Global UI/UX Design System & Component Specification

This document defines the canonical UI/UX design system, visual specifications, theme tokens, typography rules, layout hierarchy, and element styling standards for the **JobPilot** desktop application.

---

## 1. Design Philosophy & Aesthetic Core

JobPilot is engineered as an **enterprise-grade ATS (Applicant Tracking System) Command Center** inspired by modern high-productivity developer and recruiter platforms (such as *Ashby, Linear, Raycast, Greenhouse,* and *GitHub*).

```
   ┌────────────────────────────────────────────────────────────────────────┐
   │                        JOBPILOT DESIGN PILLARS                         │
   ├───────────────────┬───────────────────┬──────────────────┬─────────────┤
   │ 1. High Density   │ 2. Pitch Canvas   │ 3. Safety Orange │ 4. Keyboard │
   │    & Scannability │    & Glass Depth  │    Brand Energy  │    Velocity │
   │ Clean tables,     │ Obsidian base     │ High-impact      │ Shortcuts   │
   │ compact metrics,  │ surfaces with     │ vibrant accents  │ (Ctrl+1..9, │
   │ zero waste space. │ subtle borders.   │ for primary CTA. │ Ctrl+K).    │
   └───────────────────┴───────────────────┴──────────────────┴─────────────┘
```

### Core Design Principles
1. **Scannable Information Hierarchy:** Recruitment pipelines require processing dozens of jobs, stages, and metrics in seconds. Data density is prioritized over decorative whitespace.
2. **Refined Dark Canvas by Default:** An obsidian neutral backdrop (`#0F1117`) reduces ocular fatigue during lengthy job application and hunting sessions, while the crisp light canvas (`#F6F8FA`) remains available for daytime environments.
3. **Safety Orange Accent Tone (`#FF5F15`):** High-energy primary accents provide sharp visual cues for mission-critical actions (Run Automation, Easy Apply, Next Step) without visual clutter.
4. **Instant Tactile Feedback:** Every button, table row, nav entry, and dialog element features explicit hover, focus, active, and disabled states.

---

## 2. Global Color System & Design Tokens

JobPilot relies on a centralized token registry defined in [`app/ui/theme.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/theme.py). The system supports dynamic runtime theme switching via `ThemeManager`.

### 2.1 Color Palettes Comparison

| Token Name | Refined Dark Canvas (Default) | Crisp Light Canvas | Semantic Purpose |
|---|---|---|---|
| `background` | `#0F1117` | `#F6F8FA` | Root application window & canvas background |
| `surface` | `#161B22` | `#FFFFFF` | Primary card, sidebar, and container surface |
| `surface_alt` | `#1C2128` | `#F0F2F5` | Secondary elevated surface, table headers, inactive tabs |
| `surface_elevated`| `#22272E` | `#EAEEF2` | Popovers, active dialog panels, hover states |
| `surface_hover` | `#262C36` | `#EAEFF5` | Interactive list items, hoverable cards |
| `surface_active`| `#FF5F1522` (13% α) | `#FF5F1518` (9% α) | Active sidebar item background fill |
| `border` | `#262C36` | `#D0D7DE` | Subtle component boundaries, card outlines |
| `border_light` | `#333A46` | `#AFB8C1` | Input focus boundaries, elevated separators |
| `border_subtle`| `#ffffff0d` (5% α) | `#0000000d` (5% α) | Whispering dividers and table grid lines |
| `primary` | `#FF5F15` | `#FF5F15` | Vibrant Safety Orange primary action accent |
| `primary_hover`| `#E04F0B` | `#E04F0B` | Deepened safety orange on hover/active press |
| `primary_subtle`| `#FF5F1518` (9% α) | `#FF5F1518` (9% α) | Orange badge backdrop, highlight tints |
| `accent` | `#FF7A3D` | `#FF7A3D` | Soft warm secondary orange highlight |
| `text` | `#F0F6FC` | `#1F2328` | High-contrast body text & active headings |
| `text_muted` | `#8B949E` | `#656D76` | Secondary labels, timestamps, metadata |
| `text_dark` | `#6E7681` | `#8C959F` | Hints, placeholders, disabled controls |

### 2.2 Status & Semantic Feedback Tokens

| Semantic Role | Dark Base | Dark Subtle Fill (α 9%) | Light Base | Light Subtle Fill | Usage Context |
|---|---|---|---|---|---|
| **Success** | `#2EA043` | `#2EA04318` | `#1A7F37` | `#1A7F3718` | Submitted, Ready, Active, Offer, Qualified |
| **Warning** | `#D29922` | `#D2992218` | `#9A6700` | `#9A670018` | Under Review, Manual Check, Needs Review |
| **Danger** | `#F85149` | `#F8514918` | `#CF222E` | `#CF222E18` | Failed, Rejected, Overdue, Cancelled |
| **Info / Royal**| `#388BFD` | `#388BFD18` | `#0969DA` | `#0969DA18` | Scheduled, System Info, Discovered |
| **Purple** | `#A371F7` | `#A371F718` | `#8250DF` | `#8250DF18` | Interview Scheduled, Technical Assessment |
| **Cyan** | `#39C5CF` | `#39C5CF18` | `#0598AB` | `#0598AB18` | Automation Running, Live Engine Activity |

---

## 3. Typography & Text Hierarchy

JobPilot utilizes the native operating system typographic cascade to guarantee sub-pixel rendering sharpness across Linux, macOS, and Windows.

### 3.1 Font Family Cascade
```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, Helvetica, Arial, sans-serif;
```

### 3.2 Typographic Scale & Application

| Hierarchy Level | Font Size | Font Weight | Letter Spacing | Text Color | Usage Example |
|---|---|---|---|---|---|
| **Display / KPI** | `26px` / `24px` | `800` (Boldest) | `-0.5px` | `#F0F6FC` | Metric Cards numeric figures (`lbl_value`) |
| **Page Title** | `22px` | `700` (Bold) | `-0.2px` | `#F0F6FC` | `PageHeader` title (`PageHeaderTitle`) |
| **Greeting Banner**| `18px` | `800` (Bold) | `-0.3px` | `#F0F6FC` | `WelcomeBanner` candidate greeting |
| **Section Title** | `14px` – `16px` | `700` (Bold) | `normal` | `#F0F6FC` | `TopBarTitle`, `QGroupBox::title`, Card headers |
| **Primary Body** | `13px` | `500` / `600` | `normal` | `#F0F6FC` | Table content, dialog inputs, descriptions |
| **Secondary Meta**| `12px` | `500` / `600` | `normal` | `#8B949E` | Subtitles, helper text, tooltips, footer |
| **Table Headers** | `11px` | `700` (Bold) | `+0.5px` | `#8B949E` | `QHeaderView::section` (UPPERCASE) |
| **Micro Labels** | `10px` | `700` (Bold) | `+0.4px` | Dynamic | Metric Card trend pills, row tags |

---

## 4. Application Shell & Window Geometry

The root application window (`MainWindow`) orchestrates a responsive 5-zone layout structure:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│  WINDOW TITLEBAR: JobPilot — Desktop Job Automation Platform                   [-][□][×]         │
├──────────────┬───────────────────────────────────────────────────────────────────────────────────┤
│              │ TOPBAR (h: 56px)                                                                  │
│              │  [Page Title]    [🔍 Search jobs... Ctrl+K]    LinkedIn: ● Naukri: ● Indeed: ●  👤│
│              ├───────────────────────────────────────────────────────────────────────────────────┤
│              │ NOTIFICATION TOAST BAR (Collapsible, h: 42px)                                     │
│ SIDEBAR      ├───────────────────────────────────────────────────────────────────────────────────┤
│  EXP: 240px  │                                                                                   │
│  COL:  68px  │ VIEWPORT AREA (QStackedWidget)                                                    │
│              │                                                                                   │
│  [Logo/Brand]│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  [Navigation │  │ PageHeader (Title + Subtitle + Action Buttons)                              │  │
│   Groups]    │  ├─────────────────────────────────────────────────────────────────────────────┤  │
│              │  │ View Content (KPI Cards, Recruitment Funnel, Jobs Table, Form Tabs)        │  │
│  [Collapse <]│  │                                                                             │  │
│  [Engine ●]  │  └─────────────────────────────────────────────────────────────────────────────┘  │
├──────────────┴───────────────────────────────────────────────────────────────────────────────────┤
│ STATUSBAR (h: 24px): DB: Connected (SQLite) | Engine: Idle | Automation: Ready                   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Window Constraints
- **Default Geometry:** `1280px` width × `800px` height.
- **Minimum Geometry:** `1024px` width × `680px` height (prevents viewport clipping).

### 4.2 Sidebar Specifications ([`app/ui/sidebar.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/sidebar.py))
- **Expanded Width:** `240px`
- **Collapsed Width:** `68px` (Icon-only mode with tooltips)
- **Item Height:** `33px`
- **Fixed Icon Column:** `26px` (Centers icons at `17px` size for pixel-aligned collapsed/expanded alignment)
- **Transition Animation:** Smooth parallel property animation (`180ms`, `QEasingCurve.InOutQuad`).
- **Active State Accent:** `3px` left solid bar with `#FF5F15` Safety Orange and translucent `#FF5F1522` background.
- **Section Grouping Structure:**
  1. `WORKSPACE`: Dashboard (`Ctrl+1`), Automation
  2. `JOBS`: All Jobs (`Ctrl+6`), Easy Apply, Company Portal, Job Search (`Ctrl+5`)
  3. `PIPELINE`: Applications (`Ctrl+7`), Interviews (`Ctrl+8`), Follow-ups (`Ctrl+9`)
  4. `INSIGHTS`: Analytics
  5. `CANDIDATE`: Profile (`Ctrl+2`), Resumes (`Ctrl+3`)
  6. `SYSTEM`: Platforms (`Ctrl+4`), Logs, Settings

### 4.3 Top Bar ([`app/ui/top_bar.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/top_bar.py))
- **Height:** `56px` fixed
- **Surface:** `#161B22` with `#262C36` bottom border
- **Global Search Trigger:** Pill input button (`Ctrl+K`) with `320px` minimum width, `#1C2128` background, and hover accent outline.
- **Platform Health Trackers:** Decoupled status pills displaying real-time engine health for **LinkedIn**, **Naukri**, and **Indeed**.
- **Candidate Profile Pill:** Direct profile snapshot showing the active candidate's name.

### 4.4 Status Bar ([`app/ui/status_bar.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/status_bar.py))
- **Height:** `24px` fixed
- **Background:** `#161B22` with `#262C36` top border
- **Telemetry Indicators:** Database connectivity, automation engine status, and scheduled tasks.

---

## 5. UI Elements & Component Library

### 5.1 Push Buttons & Interactive Controls

```
  Primary Button:        [  ⚡ Start Automation  ]  (Safety Orange #FF5F15)
  Secondary Button:      [  ⚙ Configure Rules   ]  (Elevated Charcoal #1C2128)
  Tool / Icon Button:    [  🔍  ]  [  ⛶  ]  [  ✕  ]  (Subtle Hover Fill)
```

#### Primary Action Button
- **Background:** `#FF5F15` (Safety Orange)
- **Hover:** `#E04F0B`
- **Text Color:** `#FFFFFF`
- **Border:** None
- **Border Radius:** `8px`
- **Padding:** `8px 16px`
- **Font Weight:** `700` (Bold)

#### Secondary / Surface Button
- **Background:** `#161B22` (or `#1C2128`)
- **Hover:** `#262C36`
- **Pressed:** `#1C2128`
- **Border:** `1px solid #262C36`
- **Hover Border:** `#333A46` (or `#FF5F15`)
- **Text Color:** `#F0F6FC`
- **Border Radius:** `8px`

#### Ghost / Header Action Button
- **Background:** Transparent
- **Hover:** `#262C36`
- **Padding:** `4px 8px`
- **Border Radius:** `6px`

---

### 5.2 Status Badges & Pills ([`app/ui/widgets/status_badge.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/status_badge.py))

All platform, engine, and job lifecycle statuses use standardized pill dimensions (`110px × 24px`) with high-contrast text and matching alpha borders.

```
┌────────────────────────────────────────────────────────────────────────┐
│  STATUS PILL BADGE SPECIFICATION                                       │
│                                                                        │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐               │
│   │  Submitted   │   │ Under Review │   │  Interview   │               │
│   └──────────────┘   └──────────────┘   └──────────────┘               │
│      (Success)          (Warning)           (Purple)                   │
│                                                                        │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐               │
│   │ Shortlisted  │   │   Rejected   │   │ Manual Check │               │
│   └──────────────┘   └──────────────┘   └──────────────┘               │
│      (Primary)          (Danger)           (Warning)                   │
└────────────────────────────────────────────────────────────────────────┘
```

#### Status Color Map

| Status Category | Raw Status Codes | Foreground | Background | Border |
|---|---|---|---|---|
| **Success** | `SUBMITTED`, `OFFER`, `COMPLETED`, `READY`, `QUALIFIED` | `#34D399` | `#064E3B` | `#059669` |
| **Warning** | `UNDER_REVIEW`, `WARNING`, `MANUAL_REQUIRED`, `PENDING` | `#FBBF24` | `#451A03` | `#D97706` |
| **Primary** | `SHORTLISTED`, `RECRUITER_CONTACTED`, `ACTIVE` | `#FB923C` | `#431407` | `#EA580C` |
| **Purple** | `ASSESSMENT`, `INTERVIEW`, `SCHEDULED` | `#C084FC` | `#2E1065` | `#7C3AED` |
| **Danger** | `REJECTED`, `FAILED`, `OVERDUE`, `CANCELLED` | `#F87171` | `#450A0A` | `#DC2626` |
| **Info** | `DISCOVERED`, `APPLYING` | `#38BDF8` | `#082F49` | `#0284C7` |
| **Neutral** | `NOT_APPLIED`, `SKIPPED`, `IDLE` | `#9CA3AF` | `#1F2937` | `#374151` |

---

### 5.3 Modern Metric Cards ([`app/ui/widgets/metric_card.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/metric_card.py))

Used on the Dashboard, Analytics, and Applications overview to show real-time KPIs:
- **Card Container:** `#161B22` surface, `1px solid #262C36`, `12px` border radius.
- **Hover Glow:** Border transitions to `accent_color` at 50% opacity, surface shifts to `#1C2128`.
- **Icon Circular Badge:** `30px × 30px` rounded pill with `15px` radius, filled with 12% alpha accent tint.
- **Trend Tag:** Right-aligned uppercase pill badge displaying conversion velocity or active status.
- **Numeric Display:** `24px` – `26px`, weight `800`, letter-spacing `-0.5px`, crisp `#F0F6FC`.
- **Title Label:** `11px`, uppercase, letter-spacing `0.5px`, slate `#8B949E`.

---

### 5.4 Form Inputs, Dropdowns & Controls

#### Text Fields & Editors (`QLineEdit`, `QTextEdit`, `QPlainTextEdit`)
- **Background:** `#161B22` (Dark) / `#FFFFFF` (Light)
- **Border:** `1px solid #262C36`
- **Border Radius:** `8px` (or `6px` in compact dialog forms)
- **Padding:** `8px 12px`
- **Focus Ring:** Border transitions to `#FF5F15` Safety Orange (zero fuzzy blur, clean 1px stroke).
- **Selection Highlight:** `#FF5F15` background with white text.

#### Dropdowns (`QComboBox`)
- **Drop-down Arrow Frame:** Clean, borderless right column with `26px` width.
- **Popup Menu (`QAbstractItemView`):**
  - Background: `#161B22`
  - Border: `1px solid #262C36`
  - Padding: `4px`
  - Selected Item: Safety Orange `#FF5F15` with crisp white text.

#### Checkboxes (`QCheckBox`)
- **Indicator Size:** `18px × 18px`
- **Border Radius:** `4px`
- **Checked State:** Solid `#FF5F15` fill with embedded SVG checkmark (`assets/icons/check.svg`).
- **Hover State:** Border highlights to `#FF5F15`.

#### Progress Bars (`QProgressBar`)
- **Track Rail:** `#1C2128` (Dark) with `4px` border radius.
- **Fill Chunk:** `#FF5F15` with matching `4px` rounded edge.
- **Label:** Center-aligned, high-contrast text.

---

### 5.5 Data Tables (`QTableWidget` & `QTableView`)

JobPilot presents high-volume recruitment logs and job postings in streamlined data grids:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ COMPANY           │ ROLE                        │ PLATFORM  │ STATUS       │ DATE       │ ACTION │
├───────────────────┼─────────────────────────────┼───────────┼──────────────┼────────────┼────────┤
│ Google            │ Senior Python Engineer      │ LinkedIn  │ Shortlisted  │ 2026-09-24 │ [...]  │
│ Amazon            │ Full Stack Developer        │ Indeed    │ Under Review │ 2026-09-25 │ [...]  │
│ Microsoft         │ Backend Automation Lead     │ Naukri    │ Submitted    │ 2026-09-26 │ [...]  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Header Section (`QHeaderView::section`):**
  - Background: `#1C2128`
  - Text Color: `#8B949E`
  - Typography: `11px`, Weight `700`, Uppercase, `letter-spacing: 0.5px`.
  - Border: No vertical borders, clean `1px solid #262C36` bottom divider.
  - Padding: `10px 14px`
- **Grid Lines:** `gridline-color: transparent` (modern flat appearance, row separation handled via hover highlights).
- **Row Hover State:** Background transitions to `#262C36`.
- **Row Selected State:** `#262C36` with white text.
- **Scrollbars:** Custom `6px` ultra-thin pill scrollbars with `#333A46` thumb and `#FF5F15` hover state.

---

### 5.6 Pill Tab Widgets (`QTabWidget` & `QTabBar`)

- **Tab Container Pane:** Border `1px solid #262C36`, surface `#161B22`, radius `10px`.
- **Inactive Tab:** Surface `#1C2128`, text `#8B949E`, padding `8px 18px`, radius `8px`.
- **Selected Tab:** Solid `#FF5F15` fill, bold white text, subtle orange border.
- **Hover Tab:** Surface `#262C36`, text `#F0F6FC`.

---

## 6. Dialogs, Modals & Command Palettes

JobPilot implements focused modal dialogs for high-intent workflows.

### 6.1 Global Command Palette (`GlobalSearchDialog` — `Ctrl+K`)
- **Trigger:** `Ctrl+K` or clicking the Top Bar search input.
- **Layout:** Centered modal overlay (`640px` width) with instant live filtering across Jobs, Companies, Applications, and Interviews.
- **Quick Filters:** Category chips (`All`, `Jobs`, `Applications`, `Interviews`, `Companies`).
- **Keyboard Navigation:** Arrow Up / Down for row selection, `Enter` to navigate, `Esc` to dismiss.

### 6.2 Application Transition Modal (`StatusTransitionDialog`)
- **Purpose:** Move applications through stages, schedule interviews, or attach recruiter notes.
- **Structure:** Multi-tab card (`Status Update`, `Interview Scheduling`, `Follow-up Task`, `Audit History`).
- **Visuals:** Form layout with aligned inputs, contextual date-time pickers, and dynamic stage previews.

### 6.3 Onboarding Setup Wizard (`OnboardingWizardDialog`)
- **Auto-Launch:** Automatically presents on fresh installation if `general.onboarding_completed` is false.
- **Steps:**
  1. Candidate Personal Details & Compensation
  2. Primary Resume Selection & PDF Parser
  3. Platform Credentials (LinkedIn / Naukri / Indeed)
  4. Search Keywords & Location Criteria
  5. AI Screening Q&A Rules Configuration

### 6.4 Notification Toast Banner (`NotificationBar`)
- **Placement:** Anchored directly below `TopBar`, spanning full viewport width.
- **Appearance:** Modern dark banner with a 4px solid left accent stripe corresponding to event severity:
  - Success: `#2EA043`
  - Warning: `#D29922`
  - Danger: `#F85149`
  - Info: `#388BFD`
- **Dismissal:** Auto-dismiss timeout (`4000ms`) or instant manual close via `✕` button.

---

## 7. Vector Icon System (`SidebarIconPainter`)

To avoid external raster bitmap dependencies or blurry font icons at high DPI, all sidebar and primary navigation icons are procedurally drawn with vector math via PySide6 `QPainter` in [`app/ui/sidebar_icons.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/sidebar_icons.py).

### 7.1 Coordinate System & Rendering Rules
- **Base Canvas:** Normalized `18 × 18` coordinate grid.
- **Pen Stroke:** `1.8px` width, `RoundCap` cap style, `RoundJoin` join style.
- **Anti-aliasing:** Always enabled (`QPainter.RenderHint.Antialiasing`).
- **Dynamic Theming:** Icons receive `QColor` from the current theme state (muted slate in idle, Safety Orange in active/hover).

### 7.2 Vector Icon Registry

| Icon ID | Key Visual Geometry | Associated Route |
|---|---|---|
| `dashboard` | 4-quadrant rounded rectangles | `dashboard` |
| `automation` | Outer circle with centered forward play triangle | `automation` |
| `briefcase` | Rounded suitcase body with arched top handle | `jobs` |
| `lightning` | Angular 6-point lightning bolt path | `easy_apply` |
| `building` | Multi-story corporate building with window grid and door | `company_portal` |
| `search` | Angled magnifying glass lens with diagonal stem | `search` |
| `file_check` | Folded-corner document with centered checkmark | `applications` |
| `calendar` | Calendar grid body with dual top binder rings | `interviews` |
| `clock` | Circular clock face with 90° center hands | `followups` |
| `chart` | Cartesian axes with upward stepping bar chart | `analytics` |
| `user` | Circular head avatar with curved shoulder base | `profile` |
| `file_text` | Document outline with 3 horizontal ruled content lines | `resumes` |
| `globe` | Latitude/longitude concentric circular wireframe | `platforms` |
| `terminal` | Command prompt chevron `>` with underscore `_` | `logs` |
| `gear` | Cogwheel ring with 8 symmetrical radial teeth | `settings` |

---

## 8. UX Motion, Shortcuts & Velocity Standards

### 8.1 Motion & Transition Timings

| Transition | Duration | Easing Curve | Purpose |
|---|---|---|---|
| **Sidebar Collapse / Expand** | `180ms` | `QEasingCurve.InOutQuad` | Smooth navigation drawer expansion |
| **Notification Toast Show / Hide**| `150ms` | `QEasingCurve.OutCubic` | Non-intrusive alert appearance |
| **Card Hover Elevation** | Instant (QSS) | Linear | Immediate tactile mouse feedback |
| **Theme Mode Crossfade** | Dynamic | Instant QSS swap | Seamless light/dark transition |

### 8.2 Global Keyboard Shortcuts Matrix

| Shortcut | Target Action / View | Context |
|---|---|---|
| `Ctrl + K` | Open Global Command Palette Search Modal | Universal |
| `Ctrl + 1` | Navigate to **Dashboard** | Universal |
| `Ctrl + 2` | Navigate to **Profile** | Universal |
| `Ctrl + 3` | Navigate to **Resumes** | Universal |
| `Ctrl + 4` | Navigate to **Platforms** | Universal |
| `Ctrl + 5` | Navigate to **Job Search** | Universal |
| `Ctrl + 6` | Navigate to **Jobs** | Universal |
| `Ctrl + 7` | Navigate to **Applications** | Universal |
| `Ctrl + 8` | Navigate to **Interviews** | Universal |
| `Ctrl + 9` | Navigate to **Follow-ups** | Universal |
| `Esc` | Close active Modal / Dialog / Search Palette | Dialog active |
| `Enter` | Submit / Confirm active Form or Selection | Dialog active |

---

## 9. Implementation Guide for New Views

When adding a new view or widget to JobPilot, follow these mandatory design rules:

### Step 1: Use Theme Tokens (Never Hardcode Random Hex Codes)
Always import `COLORS` and `ThemeManager` from `app.ui.theme`:
```python
from app.ui.theme import COLORS, ThemeManager

# Example QSS styling using tokens
my_widget.setStyleSheet(f"""
    QWidget {{
        background-color: {COLORS['surface']};
        color: {COLORS['text']};
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
    }}
""")
```

### Step 2: Use `PageHeader` for Title & Actions
Every top-level view should start with the standardized `PageHeader`:
```python
from app.ui.widgets.page_header import PageHeader

header = PageHeader(
    title="Section Title",
    subtitle="Explaining what the user manages or reviews on this screen."
)
btn_action = QPushButton("Add New Item")
header.add_action_widget(btn_action)
layout.addWidget(header)
```

### Step 3: Wrap Main Content in a Smooth Scroll Area
Desktop viewport sizes vary. Always place grid or list contents inside a borderless `QScrollArea`:
```python
scroll = QScrollArea()
scroll.setWidgetResizable(True)
scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
```

### Step 4: Use `StatusBadge` for States
Never render raw text for status strings. Use `StatusBadge`:
```python
from app.ui.widgets.status_badge import StatusBadge

badge = StatusBadge(status_string, status_type="success")
```

### Step 5: Connect Real-Time Signal Updates
Ensure the view exposes a `refresh()` method and connects to `AppState`:
```python
def set_app_state(self, state: AppState):
    self.app_state = state
    self.app_state.data_updated.connect(self._on_data_updated)
```

---

## 10. Summary Cheat Sheet

```
+───────────────────────────+──────────────────────────────────────────────────+
| TOKEN / COMPONENT         | CANONICAL SPECIFICATION                          |
+───────────────────────────+──────────────────────────────────────────────────+
| Canvas Dark Background    | #0F1117 (Obsidian pitch neutral)                 |
| Canvas Light Background   | #F6F8FA (Crisp light neutral)                    |
| Card Surface              | #161B22 (Border: 1px solid #262C36, R: 12px)     |
| Primary Action Accent     | #FF5F15 (Safety Orange, Hover: #E04F0B)          |
| Primary Typography        | -apple-system, BlinkMacSystemFont, Segoe UI      |
| Base Font Size            | 13px (Body), 22px (Page Title), 24px (KPI Value) |
| Standard Status Badge     | 110px × 24px (Fixed pill geometry, bold 11px)    |
| Sidebar Dimensions        | 240px Expanded / 68px Collapsed                  |
| Primary Command Palette   | Ctrl+K (Quick global jump modal)                 |
+───────────────────────────+──────────────────────────────────────────────────+
```

---

## 11. Automation Control Center Cockpit Specification

The **Automation Control Center** ([`app/ui/views/automation_view.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/views/automation_view.py)) is engineered as a high-density, real-time execution cockpit. It eliminates oversized card clutter in favor of a fast-scanning, information-dense operational workspace.

### 11.1 Component Hierarchy & Geometry

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ HEADER: Compact Page Header (Title + Subtitle + [⏸ Pause/Resume] [⏹ Stop] [▶ Start Automation])    │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ PLATFORM HEALTH STRIP: ● LinkedIn: Ready   ● Naukri: Ready   ● Indeed: Ready   ● Foundit: Ready  │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ SEGMENTED SWITCHER: [ LinkedIn ]  [ Naukri.com ]  [ Indeed ]  [ Foundit ]  [ All Platforms ]     │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ACTIVE RUN HERO: Platform Name · State Pill · Monotonic Elapsed Stopwatch                        │
│                  Factual Action Phase Indicator · Indeterminate Progress Pulse · Counts Summary  │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ HORIZONTAL PIPELINE: [ DISCOVERED ] ──→ [ EVALUATING ] ──→ [ QUALIFIED ] ──→ [ APPLYING / SUB ] │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ COMPACT METRIC RAIL: Discovered | Evaluated | Qualified | Submitted | Skipped | Errors           │
├────────────────────────────────────────────────┬─────────────────────────────────────────────────┤
│ CURRENT JOB WORKSPACE (50%)                    │ DUAL-MODE ACTIVITY STREAM (50%)                 │
│ Role Title                                     │ [ Activity Feed ] [ Raw Logs ]   Auto-scroll: ON│
│ Company Name (Orange highlight)                │ [All] [Jobs] [Qual] [Submissions] [Errors]      │
│ Location & Platform Badge                      │ ● 22:51:08 [JOBS] Discovered Senior Engineer    │
│ Dynamic Action: [ ↗ Open on LinkedIn ]         │ ✓ 22:51:18 [SUBMISSIONS] Application confirmed  │
│ ────────────────────────────────────────────── │ ─────────────────────────────────────────────── │
│ RUN HISTORY (Recent sessions table)            │ [ ↓ Jump to latest ]                            │
│ Click row → Opens slide-out Diagnostics Drawer │                                                 │
└────────────────────────────────────────────────┴─────────────────────────────────────────────────┘
```

### 11.2 Component Specifications

| Component | Dimensions / Structure | Design Tokens & Behavior |
|---|---|---|
| **Platform Health Strip** | Height: `28px`, Pill radius: `14px` | Real-time status dots (`#2EA043` Ready, `#39C5CF` Running, `#D29922` Paused, `#F85149` Login/Error). Secret-free metadata popover. |
| **Segmented Switcher** | Height: `36px`, Segment radius: `6px` | Container: `#161B22`, Active segment: `#FF5F15` Safety Orange, Inactive: Transparent with `#8B949E` text. Bidirectional test combo sync. |
| **Active Run Hero** | Card radius: `10px`, Padding: `16px` | Monotonic drift-free timer. Indeterminate pulse progress bar (`6px` height) during execution. Honest textual action states. |
| **Horizontal Pipeline** | Single-row bar, Height: `44px` | Linear flow with directional arrows (`→`). Active stage pulses in cyan (`#39C5CF`), completed stages reflect true numbers. |
| **KPI Metric Rail** | 6 columns, Height: `60px` | Numbers: `22px` / `800` weight. Titles: `11px` uppercase slate. Zero fabricated numbers in idle state. |
| **Current Job Panel** | Adaptive half-width card | Contextual action button adapts text to target platform: `↗ Open on LinkedIn`, `↗ Open on Naukri`, `↗ Open on Indeed`, `↗ Open on Foundit`. Disabled if URL missing. |
| **Dual-Mode Activity Stream**| Min height: `240px`, Tabbed header | Mode 1: Structured HTML events with category tags. Mode 2: Raw monospace terminal with search, category filtering, auto-scroll pause, and clipboard copy. |
| **Run Details Drawer** | Slide-out overlay, Width: `340px` | Read-only session forensics: Run ID, exact start/finish timestamps, total duration, full pipeline counts, and stop reason. Zero destructive actions. Dismissable via header `✕`, bottom `✕ Close Drawer` button, or `Escape` key. |

---

## 12. Recruitment Pipeline & Audit Graph UI/UX Specification

### 12.1 Modern Dropdown & Popover Design Standards
All dropdowns (`QComboBox`, `QDateTimeEdit`) throughout JobPilot follow the unified interactive chevron system:
- **Geometry & Padding:** Standard height `34px` / `28px` (compact). Inner padding: `7px 32px 7px 12px`.
- **Chevron Down Indicator:** Crisp standalone SVG icon (`chevron_down.svg`, `10px × 6px`) positioned on the right without box clipping.
- **Hover & Focus Interactions:** Hover border transitions to `#333A46` with Safety Orange chevron glow (`chevron_down_hover.svg`). Focus state renders sharp `#FF5F15` border.
- **Floating Item Popover:** Elevated surface `#161B22` with `#262C36` border, `8px` corner radius, `4px` padding, item min-height `28px`, and high-contrast Safety Orange selection highlight.

### 12.2 Connected Audit Trail Graph View (`AuditTimelineGraphWidget`)
State transitions and lifecycle events are presented in an enterprise-grade connected timeline graph rather than rigid tabular grids:

```
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ [ 📈 Timeline Graph View ]  [ 📋 Tabular Audit View ]                                         │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                               │
│  ●  [ None (Init) ] ──→ [ Submitted ]                             🕒 2026-09-26 23:32         │
│  │  Trigger Source: Creation                                                                  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  │ Applied automatically via Foundit (Run: 6f2b1299-...)                                │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────┘  │
│  │                                                                                            │
│  ●  [ Submitted ] ──→ [ Under Review ]                            🕒 2026-09-27 10:15         │
│     Trigger Source: Recruiter Manual                                                          │
│     ┌──────────────────────────────────────────────────────────────────────────────────────┐  │
│     │ Recruiter reviewed resume; moving to screening.                                      │  │
│     └──────────────────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Node & Spine Anatomy
1. **Milestone Node Dots:** `14px × 14px` circular indicators with stage-aware semantic colors:
   - Emerald Green (`#2EA043`) for `Submitted` and `Offer`
   - Golden Amber (`#D29922`) for `Under Review` and `Pending`
   - Purple (`#A371F7`) for `Interview`, `Assessment`, and `Shortlisted`
   - Coral Red (`#F85149`) for `Rejected`, `Failed`, and `Withdrawn`
   - Cyan (`#39C5CF`) for `Applying` and `Running`
2. **Connecting Spine:** A subtle continuous vertical rail (`2px`, `#262C36`) linking successive nodes chronologically.
3. **Transition Cards:** Elevated container (`#1C2128`) featuring:
   - From/To status pill flow (`StatusBadge` with directional arrow `→`)
   - Monospace timestamp (`🕒 YYYY-MM-DD HH:MM`)
   - Trigger source metadata pill
   - High-contrast commentary callout with a Safety Orange (`#FF5F15`) vertical accent bar for recruiter notes and execution context.


