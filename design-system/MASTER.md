# JobPilot Desktop Design System (`MASTER.md`)

> **Target Stack:** PySide6 (Qt for Python / `QWidget` + QSS)
> **Source of Truth:** `app/ui/theme.py` (`ThemeManager`) + `docs/ai/UI_RULES.md`
> **Design Intelligence:** Synthesized from `ui-ux-pro-max` (`Data-Dense Dashboard`, `ux-guidelines.csv`, `charts.csv`, desktop accessibility rules) mapped onto JobPilot's Obsidian Dark & Crisp Light themes.

---

## 1. Visual Direction & Layout Density

* **Style:** Data-Dense Desktop ATS / Productivity Command Center (minimal chrome, clear card hierarchy, grid alignment, explicit empty/loading/error states).
* **Spacing Scale (`4/8px` rhythm):**
  * Micro gap (badge/icon padding): `4px` / `6px`
  * Tight control spacing (inline buttons, rows): `8px`–`10px`
  * Card internal padding: `12px`–`16px`
  * Section / grid gutter: `14px`–`16px`
  * Page canvas margins: `20px`–`24px` (`DashboardView` / `AnalyticsView` standard: `24, 16, 24, 16`)
* **Radius Scale:**
  * Small chips / status pills / badges: `4px`–`9px` (`StatusBadge` pill height `24px`)
  * Inputs / standard buttons / tabs: `8px`
  * Cards / panels / tables: `10px`–`12px`
  * Hero banners / modal containers: `14px`
* **Scrolling Policy:** Lock horizontal scrolling (`Qt.ScrollBarAlwaysOff`) on vertical card/page `QScrollArea` containers; enforce text eliding/word-wrap and proportional column sizing so controls never clip horizontally.

---

## 2. Color Tokens & Contrast Standards (`ThemeManager`)

All widgets and views **must** resolve colors through `ThemeManager` (`DARK_COLORS` / `LIGHT_COLORS` / `COLORS`) rather than hardcoding hex literals in views or widgets.

### Core Canvas & Brand Tokens (`app/ui/theme.py`)
| Token | Dark Canvas | Light Canvas | Usage |
|---|---|---|---|
| `background` | `#0F1117` | `#F6F8FA` | Main window & workspace backdrop |
| `surface` | `#161B22` | `#FFFFFF` | Primary cards, tables, panels, dialogs |
| `surface_alt` | `#1C2128` | `#F0F2F5` | Table headers, inactive tabs, recessed tracks |
| `surface_elevated` | `#22272E` | `#EAEEF2` | Popovers, elevated headers |
| `surface_hover` | `#262C36` | `#EAEFF5` | Interactive hover & selected table row fill |
| `border` | `#262C36` | `#D0D7DE` | Card & panel hairlines |
| `border_light` | `#333A46` | `#AFB8C1` | Hover/active borders and input framing |
| `primary` | `#FF5F15` | `#FF5F15` | Primary brand accent & focus highlight |
| `primary_hover` | `#E04F0B` | `#E04F0B` | Primary hover fill |
| `text` | `#F0F6FC` | `#1F2328` | Primary headings & body text |
| `text_muted` | `#8B949E` | `#656D76` | Secondary labels & metadata |
| `text_dark` | `#6E7681` | `#8C959F` | **Disabled text only** (below 4.5:1 on surfaces) |

### WCAG Contrast Guardrails (from `ui-ux-pro-max` Audit)
1. **Normal text (`11–14px`):** Maintain `>= 4.5:1` contrast against its real surface background in **both** Dark and Light themes.
2. **Table selection / hover contrast:** Never hardcode `color: #FFFFFF` for `QTableWidget::item:hover` or `:selected`; use `tokens["text"]` so Light Mode selection stays legible on `#EAEFF5`.
3. **Orange `primary` (`#FF5F15`) text:** `#FFFFFF` on `#FF5F15` measures `3.04:1`, and `#FF5F15` text on `#FFFFFF` measures `3.04:1`. Reserve `#FF5F15` for accents, borders, large emphasis, or bold primary fills (`primary_hover` `#E04F0B` / darker readable variants where small text requires `4.5:1`), and never pair light-mode `primary` text with tiny muted metadata.
4. **`text_dark` restriction:** Use `text_dark` strictly for disabled/inactive states; use `text_muted` (`#8B949E` dark / `#656D76` light) for hints, timestamps, and subtitles.

---

## 3. Interaction, Keyboard Focus & Accessibility

1. **Visible Focus States (Required):** Never leave `QPushButton:focus { outline: none; }` without a replacement indicator. Every focusable `QPushButton`, `QLineEdit`, `QComboBox`, `QCheckBox`, and table control must render a distinct focus border (`border: 2px solid {tokens["primary"]}` or high-contrast focus ring) when tabbed.
2. **Cursor Semantics:** Interactive buttons, tabs, and clickable cards/links must set `Qt.PointingHandCursor`.
3. **Disabled Semantics:** Disabled controls must use native `.setEnabled(False)` plus distinct disabled palette styling.
4. **Long-Running Operations (>200ms):** Never block the Qt GUI thread (`QThread` workers only); disable duplicate triggers, display progress/status feedback, and provide a visible Cancel/Stop control.
5. **Modals & Human Review Gates:** Subclass `BaseDialog` (`docs/ai/UI_RULES.md`), display provenance/context clearly, and use unambiguous action labels (`Confirm & Submit`, `Edit Information`, `Abort Application`).

---

## 4. Iconography & Data Visualization

1. **Vector Icons Only (Zero Structural Emojis):** Replace Unicode emojis in navigation, buttons, table actions, empty states, and badges with painted vector paths (`app/ui/sidebar_icons.py`) or themed SVG assets (`app/ui/assets/icons/`).
2. **Consistent Stroke & Sizing:** Stick to `1.8px`–`2.0px` stroke weight with uniform badge boxes (`16px`–`18px` inline, `28px`–`32px` card badges).
3. **Charts & Pipeline Funnels (`charts.csv` rules):**
   * Always pair color encoding with explicit text labels, counts, and conversion percentages (never rely on color alone).
   * Keep funnel stages ordered sequentially (`Discovered` -> `Applied` -> `Under Review` -> `Interview` -> `Offer`) with real non-zero baseline scaling.

---

## 5. Theme Parity Checklist (Before Shipping UI Changes)

* [ ] Zero hardcoded 6-digit hex colors in view/widget stylesheets outside `app/ui/theme.py` (or explicitly bound to `ThemeManager` listener updates).
* [ ] View/widget implements `apply_theme()` / `update_theme()` if it builds dynamic widget-level QSS from `COLORS`.
* [ ] Focus indicator visible when navigating controls with `Tab` / `Shift+Tab`.
* [ ] Verified both Dark and Light theme legibility (borders, hover rows, dropdown popups, tooltips).
* [ ] Headless verification passes: `.venv/bin/python run_desktop.py --offscreen --test-run`.

