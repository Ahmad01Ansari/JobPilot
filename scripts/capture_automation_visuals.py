"""Visual test script to capture high-resolution screenshots of AutomationView

Generates screenshots for:
1. Dark Idle (1920x1080)
2. Dark Running (1920x1080)
3. Dark Intervention (1920x1080)
4. Dark Completed (1920x1080)
5. Light Idle (1920x1080)
6. Light Running (1920x1080)
7. Responsive Narrow (1366x768)
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.services.automation_events import (
    ApplicationSubmittedEvent,
    AutomationInterventionEvent,
    AutomationProgressEvent,
    AutomationRunResult,
    AutomationState,
    InterventionType,
    JobDiscoveredEvent,
    JobEvaluatedEvent,
)
from app.services.automation_service import AutomationManager
from app.ui.theme import ThemeManager
from app.ui.views.automation_view import AutomationView

OUTPUT_DIR = "/home/ahmad10raza/.gemini/antigravity-ide/brain/5769525d-10f9-4fec-86fb-507bc5aed12e"


def capture_all():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication(sys.argv + ["-platform", "offscreen"])

    manager = AutomationManager()

    def render_and_save(view, w, h, filename):
        view.resize(w, h)
        view.show()
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        pixmap = view.grab()
        path = os.path.join(OUTPUT_DIR, filename)
        pixmap.save(path, "PNG")
        print(f"Saved: {path} ({w}x{h})")

    # 1. Dark Idle (1920x1080)
    ThemeManager.notify_listeners("dark")
    view_dark_idle = AutomationView(automation_manager=manager)
    render_and_save(view_dark_idle, 1920, 1080, "automation_dark_idle.png")
    view_dark_idle.close()

    # 2. Dark Running (1920x1080)
    ThemeManager.notify_listeners("dark")
    view_dark_run = AutomationView(automation_manager=manager)
    view_dark_run._on_state_changed("run-test-1", "RUNNING")
    view_dark_run._on_progress_updated(
        AutomationProgressEvent(
            run_id="run-test-1",
            platform="linkedin",
            current_term="Senior RPA Engineer",
            current_job="Lead Automation Architect @ Enterprise Global",
            jobs_discovered=24,
            jobs_evaluated=18,
            jobs_qualified=11,
            jobs_skipped=7,
            applications_submitted=8,
            errors_count=0,
        )
    )
    view_dark_run._on_job_discovered(
        JobDiscoveredEvent(
            run_id="run-test-1",
            platform="linkedin",
            title="Lead Automation Architect",
            company="Enterprise Global",
            location="Bangalore, India (Hybrid)",
            url="https://www.linkedin.com/jobs/view/987654321",
        )
    )
    view_dark_run._on_activity_logged("14:20:12", "Discovered: Lead Automation Architect @ Enterprise Global")
    view_dark_run._on_activity_logged("14:20:15", "Qualified: Experience match (5+ yrs Automation Anywhere)")
    view_dark_run._on_activity_logged("14:20:22", "Application Submitted: Lead Automation Architect @ Enterprise Global")
    render_and_save(view_dark_run, 1920, 1080, "automation_dark_running.png")
    view_dark_run.close()

    # 3. Dark Intervention (1920x1080)
    view_dark_int = AutomationView(automation_manager=manager)
    view_dark_int._on_state_changed("run-test-2", "RUNNING")
    view_dark_int._on_intervention_required(
        AutomationInterventionEvent(
            run_id="run-test-2",
            platform="linkedin",
            intervention_type=InterventionType.CAPTCHA_DETECTED,
            message="Security challenge detected. Please solve the puzzle in the opened browser window to continue.",
        )
    )
    render_and_save(view_dark_int, 1920, 1080, "automation_dark_intervention.png")
    view_dark_int.close()

    # 4. Dark Completed (1920x1080)
    view_dark_comp = AutomationView(automation_manager=manager)
    now = datetime.now(timezone.utc)
    view_dark_comp._on_run_finished(
        AutomationRunResult(
            run_id="run-test-3",
            platform="linkedin",
            status=AutomationState.COMPLETED,
            started_at=now,
            finished_at=now,
            jobs_discovered=32,
            jobs_evaluated=26,
            jobs_qualified=16,
            jobs_skipped=10,
            applications_submitted=14,
            errors_count=0,
            stop_reason="Completed naturally",
        )
    )
    render_and_save(view_dark_comp, 1920, 1080, "automation_dark_completed.png")
    view_dark_comp.close()

    # 5. Light Idle (1920x1080)
    ThemeManager.notify_listeners("light")
    view_light_idle = AutomationView(automation_manager=manager)
    render_and_save(view_light_idle, 1920, 1080, "automation_light_idle.png")
    view_light_idle.close()

    # 6. Light Running (1920x1080)
    view_light_run = AutomationView(automation_manager=manager)
    view_light_run._on_state_changed("run-test-4", "RUNNING")
    view_light_run._on_progress_updated(
        AutomationProgressEvent(
            run_id="run-test-4",
            platform="naukri",
            current_term="Python RPA Specialist",
            current_job="RPA Consultant @ Accenture",
            jobs_discovered=15,
            jobs_evaluated=12,
            jobs_qualified=8,
            jobs_skipped=4,
            applications_submitted=6,
            errors_count=0,
        )
    )
    view_light_run._on_job_discovered(
        JobDiscoveredEvent(
            run_id="run-test-4",
            platform="naukri",
            title="RPA Consultant",
            company="Accenture",
            location="Noida, India",
            url="https://www.naukri.com/job-listings-12345",
        )
    )
    view_light_run._on_activity_logged("15:02:01", "Discovered: RPA Consultant @ Accenture")
    view_light_run._on_activity_logged("15:02:08", "Qualified: Meets notice period and CTC requirements")
    view_light_run._on_activity_logged("15:02:19", "Application Submitted: RPA Consultant @ Accenture")
    render_and_save(view_light_run, 1920, 1080, "automation_light_running.png")
    view_light_run.close()

    # 7. Responsive Narrow (1366x768)
    ThemeManager.notify_listeners("dark")
    view_narrow = AutomationView(automation_manager=manager)
    view_narrow._on_state_changed("run-test-5", "RUNNING")
    view_narrow._on_progress_updated(
        AutomationProgressEvent(
            run_id="run-test-5",
            platform="linkedin",
            current_term="RPA Developer",
            current_job="Senior RPA Dev @ Wipro",
            jobs_discovered=18,
            jobs_evaluated=14,
            jobs_qualified=9,
            jobs_skipped=5,
            applications_submitted=7,
            errors_count=0,
        )
    )
    render_and_save(view_narrow, 1366, 768, "automation_responsive_narrow.png")
    view_narrow.close()

    # Reset back to dark mode
    ThemeManager.notify_listeners("dark")
    print("All captures completed successfully!")


if __name__ == "__main__":
    capture_all()
