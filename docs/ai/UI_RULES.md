# JobPilot — UI Development Rules
**Specialized UI Guidelines, PySide6 Conventions, and Design System**
*Reference: [Master Constitution](AI_DEVELOPMENT_RULES.md) §7*

---

## 1. UI Philosophy & Design System

The JobPilot desktop application is built with **PySide6 (Qt for Python)**. It features a modern, professional, high-aesthetic interface supporting dynamic Dark and Light theme modes.

Every AI agent modifying or extending the presentation layer **MUST** adhere to the design system established in `app/ui/theme.py` and `app/ui/components/`.

### Core Rules:
1. **Never use ad-hoc inline styles with hardcoded hex colors.** Always use tokens from `ThemeManager`.
2. **Never block the Qt main thread.** Any operation taking > 50ms must run in a background worker thread.
3. **Reuse existing widgets.** Do not duplicate cards, badges, buttons, tables, or dialogs.
4. **Maintain theme parity.** Every view and component must render flawlessly in both Dark and Light modes.

---

## 2. UI Architecture & View Hierarchy

```
app/ui/
├── main_window.py       # Single-window shell with sidebar navigation & QStackedWidget
├── state.py             # AppState: Centralized reactive state & Qt signal dispatcher
├── theme.py             # ThemeManager: Design tokens, palettes, and global QSS generation
├── components/          # Reusable UI widgets
│   ├── stat_card.py     # Metric/KPI cards with icon, value, delta, and subtitle
│   ├── status_badge.py  # Colored badges for statuses (Applied, Skipped, Review, etc.)
│   ├── log_viewer.py    # Structured real-time log stream viewer
│   ├── base_dialog.py   # Standardized modal dialog with consistent header & actions
│   └── ...
└── views/               # The 13 Primary Stacked Views
    ├── dashboard_view.py
    ├── jobs_view.py
    ├── applications_view.py
    ├── analytics_view.py
    ├── settings_view.py
    ├── universal_agent_view.py
    ├── outreach_view.py
    └── ...
```

---

## 3. ThemeManager & Design Tokens

Theme definitions reside in `app/ui/theme.py`. All views and widgets must query colors via the current theme:

```python
from app.ui.theme import ThemeManager

# Accessing theme colors programmatically
theme = ThemeManager.get_instance().current_theme
bg_color = theme.background_primary
accent_color = theme.accent_primary
text_color = theme.text_primary
```

### Color Token Hierarchy:
- **Backgrounds:** `background_primary` (main window), `background_secondary` (cards/containers), `background_tertiary` (inputs, elevated surfaces).
- **Text:** `text_primary` (headings, primary labels), `text_secondary` (subtitles, secondary info), `text_muted` (timestamps, placeholders).
- **Accents:** `accent_primary` (buttons, active tabs, focus states), `accent_hover`, `accent_pressed`.
- **Status Colors:**
  - `status_success` (#10B981): Applied, Connected, Succeeded
  - `status_warning` (#F59E0B): Pending Review, Rate Limited, Warning
  - `status_error` (#EF4444): Failed, Stopped, Crash
  - `status_info` (#3B82F6): In Progress, Observing, Analyzing

---

## 4. Reusable Component Catalog

Before creating custom widgets, inspect and use the existing components in `app/ui/components/`:

| Component | File | Purpose |
|---|---|---|
| `StatCard` | `components/stat_card.py` | Metric card with label, value, trend, and theme-aware icon. |
| `StatusBadge` | `components/status_badge.py` | Rounded chip showing colored status text with proper contrast. |
| `LogViewer` | `components/log_viewer.py` | Virtualized, searchable log container with log level filtering. |
| `BaseDialog` | `components/base_dialog.py` | Modal dialog base class providing standardized chrome, title, and buttons. |
| `DataTable` | `components/data_table.py` | Styled `QTableWidget` with alternating row colors, sorting, and pagination. |

---

## 5. Thread Safety & Signal-Slot Rules

1. **Qt Thread Affinity:**
   - Widgets belong strictly to the main thread.
   - **Never** call widget methods (`setText()`, `setValue()`, `show()`, `hide()`) from background threads or callbacks.
2. **Signal Pattern:**
   - Background workers must emit Qt signals (`pyqtSignal` / `Signal`).
   - Views connect signals to slots running on the main thread:
   ```python
   # Inside View initialization:
   self.bridge.job_status_updated.connect(self._on_job_status_updated)

   @Slot(str, str)
   def _on_job_status_updated(self, job_id: str, status: str):
       # Safe to update widgets here
       self.status_badge.set_status(status)
   ```
3. **AppState Reactive Binding:**
   - Use `AppState` (`app/ui/state.py`) for global reactive states (e.g. active profile, theme mode, global running status).
   - Views subscribe to `AppState` signals on mount and disconnect on destroy.

---

## 6. Long-Running Operations & Progress UI

When triggering an operation that takes longer than 200ms:
1. **Disable Action Controls:** Disable the initiating button to prevent duplicate invocations.
2. **Visual Feedback:** Show a `QProgressBar` or spinner with explicit status text.
3. **Cancel Capability:** Provide a visible "Cancel" / "Stop" button that signals the worker to abort gracefully.
4. **Never Lock Window:** The UI must remain responsive, draggable, and capable of switching views while automation runs.

---

## 7. Dialogs & Human Review Gates

For operations requiring human verification (e.g. Universal Agent `PENDING_HUMAN_REVIEW` or Glassdoor review):
1. **Subclass `BaseDialog`:** Maintain visual consistency with the main window.
2. **Provide Context:** Display candidate field values, provenance source, and review screenshot clearly.
3. **Explicit Action Buttons:** Use unambiguous button text:
   - "Confirm & Submit" (Primary Accent)
   - "Edit Information" (Secondary Outline)
   - "Abort Application" (Destructive / Warning)
4. **Audio / Visual Notification:** If the window is minimized or behind other windows, invoke a non-intrusive alert (`QApplication.alert()`) so the user knows manual intervention is requested.

---

## 8. UI Testing & Pre-Flight Validation

UI changes must be verified using the automated offscreen test runner:
```bash
# Verify UI compiles and launches without crashing in headless offscreen mode:
.venv/bin/python run_desktop.py --offscreen --test-run
```
Any UI code that crashes during offscreen initialization will fail CI and is strictly prohibited.
