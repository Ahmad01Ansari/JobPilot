"""Regression test suite for canonical job lifecycle stages, interview transitions, and dashboard actions."""

import os
import shutil
import tempfile
import unittest
from datetime import timedelta

from PySide6.QtWidgets import QApplication, QLabel
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, utc_now
from app.db.models import Job, JobEvaluation
from app.db.session import configure_sqlite_pragmas
from app.repositories.validators import normalize_display_status
from app.services.analytics_service import AnalyticsFilter, AnalyticsService
from app.services.application_service import ApplicationService
from app.services.dashboard_service import DashboardService
from app.services.job_service import JobFilter, JobService
from app.services.recruitment_service import RecruitmentService
from app.ui.views.applications_view import ApplicationsView
from app.ui.views.dashboard_view import DashboardView
from app.ui.views.interviews_view import InterviewsView
from app.ui.views.jobs_view import JobsView
from app.ui.widgets.dashboard.all_actions_dialog import AllActionsDialog
from app.ui.widgets.dashboard.needs_attention import NeedsAttentionRow
from app.ui.widgets.dashboard.next_best_action import NextBestActionWidget
from app.ui.widgets.dashboard.todays_job_hunt import ActionCard
from app.ui.widgets.status_badge import StatusDropdownButton
from app.ui.widgets.upcoming_schedules import ScheduleItemWidget
from app.services.dto.dashboard_dto import TodaysHuntItemDTO

app = QApplication.instance() or QApplication(["--platform", "offscreen"])


class TestJobStageLifecycleConsistency(unittest.TestCase):
    """Verifies end-to-end stage consistency from discovery through interview and offer/rejection."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "lifecycle_test.db")
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )

        self.job_service = JobService(session_factory=self.Session)
        self.app_service = ApplicationService(session_factory=self.Session)
        self.recruitment_service = RecruitmentService(session_factory=self.Session)
        self.dashboard_service = DashboardService(session_factory=self.Session)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_unapplied_statuses_normalize_consistently(self):
        """DISCOVERED, EXTERNAL, QUALIFIED, and None all normalize to NOT_APPLIED."""
        for raw in (None, "", "DISCOVERED", "EXTERNAL", "QUALIFIED", "NOT_APPLIED"):
            self.assertEqual(normalize_display_status(raw), "NOT_APPLIED")
        self.assertEqual(normalize_display_status("ALREADY_APPLIED"), "SKIPPED")
        self.assertEqual(normalize_display_status("SUBMITTED"), "SUBMITTED")

    def test_not_applied_filter_includes_legacy_external_and_discovered_rows(self):
        """JobFilter(status='NOT_APPLIED') returns unapplied jobs plus legacy DISCOVERED/EXTERNAL rows."""
        j_clean, _ = self.job_service.create_manual_job(title="Clean Role", company="Acme", platform="linkedin")
        j_ext, _ = self.job_service.create_manual_job(title="Portal Role", company="Beta", platform="naukri")
        j_disc, _ = self.job_service.create_manual_job(title="Discovered Role", company="Gamma", platform="indeed")
        j_sub, _ = self.job_service.create_manual_job(title="Applied Role", company="Delta", platform="linkedin")

        # Simulate legacy rows created by older builds
        self.app_service.create_application(job_id=j_ext.id, status="EXTERNAL", application_type="EXTERNAL")
        self.app_service.create_application(job_id=j_disc.id, status="DISCOVERED", application_type="DIRECT")
        self.app_service.create_application(job_id=j_sub.id, status="SUBMITTED", application_type="EASY_APPLY")

        unapplied = self.job_service.list_jobs(JobFilter(status="NOT_APPLIED"), limit=20)
        titles = {j.title for j in unapplied}
        self.assertEqual(titles, {"Clean Role", "Portal Role", "Discovered Role"})

        # Applications Pipeline default view excludes unapplied legacy rows
        pipeline_apps = self.app_service.list_applications(limit=20)
        self.assertEqual(len(pipeline_apps), 1)
        self.assertEqual(pipeline_apps[0].status, "SUBMITTED")

        # JobsView renders legacy DISCOVERED/EXTERNAL as Not Applied in table & toolbar has no dead filters
        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()
        toolbar_items = [view.toolbar.cmb_status.itemText(i) for i in range(view.toolbar.cmb_status.count())]
        self.assertNotIn("External", toolbar_items)
        self.assertNotIn("Already Applied", toolbar_items)
        self.assertIn("Manual Check", toolbar_items)

        view.toolbar.cmb_status.setCurrentText("Manual Check")
        self.assertEqual(view.toolbar.get_filters()["status"], "MANUAL_REQUIRED")

        view.toolbar.cmb_status.setCurrentIndex(0)
        view.refresh()
        for row in range(view.table.rowCount()):
            if view.table.item(row, 1).text() in ("Portal Role", "Discovered Role", "Clean Role"):
                btn_container = view.table.cellWidget(row, 8)
                btn = btn_container.layout().itemAt(0).widget()
                self.assertEqual(btn.text(), "Not Applied ▾")
        view.close()

    def test_completed_interview_moves_to_history_tab(self):
        """Completing an interview moves it from Active/Scheduled to Completed & History."""
        job, _ = self.job_service.create_manual_job(title="ML Systems Eng", company="Anthropic", platform="linkedin")
        app_rec, _ = self.app_service.create_application(job_id=job.id, status="INTERVIEW")

        view = InterviewsView(service=self.recruitment_service, app_service=self.app_service)
        view.show()

        # Auto-provisioned Round 1 appears in Active / Scheduled tab (tab 0)
        self.assertEqual(view.tabs.currentIndex(), 0)
        self.assertEqual(view.table.rowCount(), 1)
        self.assertIn("Scheduled", view.table.item(0, 1).text())

        iv_id = view._current_interviews[0].id
        self.recruitment_service.update_interview_status(iv_id, status="COMPLETED", feedback="Strong technical round")
        view.refresh()

        # Active / Scheduled is now empty; Completed & History (tab 1) holds the round
        self.assertEqual(view.table.rowCount(), 0)
        view.tabs.setCurrentIndex(1)
        self.assertEqual(view.table.rowCount(), 1)
        self.assertIn("Completed", view.table.item(0, 1).text())
        view.close()

    def test_rejecting_or_offering_application_closes_scheduled_interview_everywhere(self):
        """Updating job stage to REJECTED or OFFER closes pending scheduled rounds and hides them from Active & Dashboard."""
        j_rej, _ = self.job_service.create_manual_job(title="Backend Dev", company="Stripe", platform="linkedin")
        a_rej, _ = self.app_service.create_application(job_id=j_rej.id, status="INTERVIEW")
        dt = utc_now() + timedelta(hours=3)
        iv_rej, _ = self.recruitment_service.schedule_interview(
            application_id=a_rej.id,
            round_name="System Design",
            scheduled_at=dt,
        )

        j_off, _ = self.job_service.create_manual_job(title="Staff Eng", company="Linear", platform="linkedin")
        a_off, _ = self.app_service.create_application(job_id=j_off.id, status="INTERVIEW")
        iv_off, _ = self.recruitment_service.schedule_interview(
            application_id=a_off.id,
            round_name="Final",
            scheduled_at=dt,
        )

        # Before transition: both applications' rounds (including auto-provisioned + scheduled) are SCHEDULED
        self.assertGreaterEqual(len(self.recruitment_service.list_interviews(status="SCHEDULED")), 2)

        # Reject first application, Offer second application
        self.app_service.transition_status(a_rej.id, "REJECTED", source="interviews_view", allow_override=True)
        self.app_service.transition_status(a_off.id, "OFFER", source="interviews_view", allow_override=True)

        # Neither remains SCHEDULED or active
        self.assertEqual(len(self.recruitment_service.list_interviews(status="SCHEDULED")), 0)
        self.assertEqual(len(self.recruitment_service.list_interviews(active_only=True)), 0)
        self.assertEqual(self.recruitment_service.get_metrics()["upcoming_interviews"], 0)

        # Verify interview statuses in history
        history_ivs = {iv.id: iv.status for iv in self.recruitment_service.list_interviews(active_only=False)}
        self.assertEqual(history_ivs[iv_rej.id], "CANCELLED")
        self.assertEqual(history_ivs[iv_off.id], "COMPLETED")

    def test_dashboard_uses_update_stage_instead_of_prepare_and_safe_dismiss(self):
        """Dashboard cards show 'Update Stage' instead of misleading 'Prepare' and dismiss does not wipe status."""
        job, _ = self.job_service.create_manual_job(title="Platform Engineer", company="Datadog", platform="linkedin")
        app_rec, _ = self.app_service.create_application(job_id=job.id, status="INTERVIEW")
        dt = utc_now() + timedelta(hours=2)
        iv, _ = self.recruitment_service.schedule_interview(
            application_id=app_rec.id,
            round_name="Hiring Manager",
            scheduled_at=dt,
        )

        # 1. DashboardService Hunt items & NBA should deduplicate and label "Update Stage"
        items = self.dashboard_service.get_todays_job_hunt_items(limit=10)
        iv_items = [it for it in items if app_rec.id in (it.action_payload.get("application_id"),)]
        self.assertEqual(len(iv_items), 1)
        self.assertNotIn("prepare", iv_items[0].reason.lower())

        nba = self.dashboard_service.get_next_best_action()
        self.assertEqual(nba.button_label, "Update Stage")
        self.assertNotIn("prepare", nba.reason.lower())

        # 2. Dashboard widgets display "Update Stage →"
        sched_widget = ScheduleItemWidget("Hiring Manager", "Platform Engineer — Datadog", "Today 5:00 PM")
        hunt_card = ActionCard(iv_items[0])
        attn_card = NeedsAttentionRow(iv_items[0])

        self.assertIn("Update Stage", hunt_card.btn_action.text())
        self.assertIn("Update Stage", attn_card.btn_act.text())
        sched_buttons = [b.text() for b in sched_widget.findChildren(type(hunt_card.btn_action))]
        self.assertTrue(any("Update Stage" in t for t in sched_buttons))

        # 3. Dismissing an interview reminder marks the round COMPLETED and preserves Application status INTERVIEW
        dash_view = DashboardView(service=self.dashboard_service, recruitment_service=self.recruitment_service)
        dash_view._on_dashboard_action(
            "DISMISS_ITEM",
            {
                "source_type": "interview",
                "source_id": iv.id,
                "application_id": app_rec.id,
            },
        )
        updated_app = self.app_service.get_application(app_rec.id)
        self.assertEqual(updated_app.status, "INTERVIEW")
        ivs = self.recruitment_service.list_interviews(application_id=app_rec.id)
        target_iv = next(x for x in ivs if x.id == iv.id)
        self.assertEqual(target_iv.status, "COMPLETED")
        dash_view.close()

    def test_applications_table_status_cell_has_no_bleedthrough_text(self):
        """Applications table cell under StatusDropdownButton stays empty and hover uses opaque background."""
        job, _ = self.job_service.create_manual_job(title="AI Engineer", company="UniversalCo", platform="universal")
        self.app_service.create_application(job_id=job.id, status="SUBMITTED")

        apps_view = ApplicationsView(service=self.app_service, recruitment_service=self.recruitment_service)
        apps_view.show()
        self.assertEqual(apps_view.table.rowCount(), 1)
        # Underlying QTableWidgetItem text must be empty so hover doesn't reveal raw enum text
        self.assertEqual(apps_view.table.item(0, 3).text(), "")

        btn = StatusDropdownButton("SUBMITTED")
        ss = btn.styleSheet()
        self.assertIn("QPushButton:hover", ss)
        self.assertNotIn("#05966940", ss)
        apps_view.close()

    def test_offer_and_universal_platform_counted_consistently_in_dashboard_and_analytics(self):
        """An OFFER application on universal platform is reflected accurately across Dashboard, Funnel, and Analytics."""
        job, _ = self.job_service.create_manual_job(title="Staff AI", company="OpenCo", platform="universal")
        app_rec, _ = self.app_service.create_application(job_id=job.id, status="SUBMITTED")
        self.app_service.transition_status(app_rec.id, "OFFER", source="USER", allow_override=True)

        analytics = AnalyticsService(session_factory=self.Session)
        dash_svc = DashboardService(session_factory=self.Session)

        # 1. Analytics summary & funnel count the offer and universal platform
        f_all = AnalyticsFilter(date_preset="ALL")
        summary = analytics.get_summary_metrics(f_all)
        self.assertEqual(summary["offer_applications"], 1)

        funnel = analytics.get_funnel_flow(f_all)
        stage_map = {s["stage_id"]: s["count"] for s in funnel["stages"]}
        self.assertEqual(stage_map["offers"], 1)

        plat_rows = analytics.get_platform_performance(f_all)
        uni_row = next((p for p in plat_rows if p["platform_key"] == "universal"), None)
        self.assertIsNotNone(uni_row)
        self.assertEqual(uni_row["applications"], 1)
        self.assertEqual(uni_row["offers"], 1)

        # 2. Dashboard snapshot defaults to ALL matching SearchPerformanceWidget and counts 1 offer everywhere
        snapshot = dash_svc.get_dashboard_snapshot()
        self.assertEqual(snapshot.pipeline_summary["offers"], 1)
        self.assertEqual(snapshot.search_performance.total_offers, 1)
        self.assertEqual(snapshot.search_performance.total_applied, 1)

        # 3. DashboardView queuing prevents dropped real-time refreshes
        dash_view = DashboardView(service=dash_svc, recruitment_service=self.recruitment_service)
        dash_view.stop_workers()
        dash_view._on_snapshot_loaded(snapshot)
        self.assertEqual(dash_view.kpi_bar.card_offers.lbl_val.text(), "1")
        self.assertEqual(dash_view.search_perf_widget.row_offr.lbl_count.text(), "1")
        dash_view.close()

    def test_completed_or_cancelled_interview_removes_phantom_nba_and_hunt_item(self):
        """When all interview rounds are Completed/Cancelled (0 Scheduled), Dashboard must not show Scheduled Interview."""
        job, _ = self.job_service.create_manual_job(title="Backend Developer 65047b", company="Gamma Labs 65047b", platform="linkedin")
        app_rec, _ = self.app_service.create_application(job_id=job.id, status="INTERVIEW")

        # Auto-provisioned Round 1 is initially SCHEDULED -> surfaces on NBA and Today's Hunt
        nba_before = self.dashboard_service.get_next_best_action()
        self.assertEqual(nba_before.action_type, "INTERVIEW_TODAY")

        # Complete all rounds via InterviewsView / RecruitmentService (leaving 0 Scheduled Rounds)
        ivs = self.recruitment_service.list_interviews(application_id=app_rec.id)
        for iv in ivs:
            self.recruitment_service.update_interview_status(iv.id, status="COMPLETED")

        iv_view = InterviewsView(service=self.recruitment_service, app_service=self.app_service)
        self.assertEqual(iv_view.tabs.tabText(1), "Completed && History")
        self.assertEqual(iv_view.table.rowCount(), 0)
        iv_view.close()

        # Dashboard Next Best Action and Today's Hunt must no longer show a phantom scheduled interview for Gamma Labs
        nba_after = self.dashboard_service.get_next_best_action()
        self.assertNotEqual(nba_after.company, "Gamma Labs 65047b")

        hunt_after = self.dashboard_service.get_todays_job_hunt_items(limit=10)
        gamma_items = [it for it in hunt_after if it.company == "Gamma Labs 65047b"]
        self.assertEqual(gamma_items, [])

    def test_see_all_actions_button_and_dialog_workflow(self):
        """Verifies See All Actions button on NBA and AllActionsDialog filtering + live updates."""
        dt = utc_now() + timedelta(hours=2)
        j1, _ = self.job_service.create_manual_job(title="Backend Eng", company="Stripe", platform="linkedin")
        a1, _ = self.app_service.create_application(job_id=j1.id, status="INTERVIEW")
        self.recruitment_service.schedule_interview(a1.id, round_name="Tech", scheduled_at=dt)

        j2, _ = self.job_service.create_manual_job(title="Platform Eng", company="Photon", platform="naukri")
        self.app_service.create_application(job_id=j2.id, status="MANUAL_REQUIRED")

        j3, _ = self.job_service.create_manual_job(title="AI Architect", company="Databricks", platform="linkedin")
        with self.Session() as s:
            s.add(JobEvaluation(
                job_id=j3.id,
                score=92,
                decision="STRONG_MATCH",
                status="QUALIFIED",
                evaluation_status="SUCCESS",
                evaluated_at=utc_now(),
            ))
            s.commit()

        # 1. NextBestActionWidget has See All Actions button & signal
        nba_widget = NextBestActionWidget()
        nba_widget.set_total_actions_count(3)
        self.assertIn("See All Actions (3)", nba_widget.btn_see_all.text())
        triggered = []
        nba_widget.see_all_requested.connect(lambda: triggered.append(True))
        nba_widget.btn_see_all.click()
        self.assertEqual(triggered, [True])
        nba_widget.close()

        # 2. DashboardService.get_all_pending_actions includes operational actions AND top opportunities
        all_items = self.dashboard_service.get_all_pending_actions(limit=100)
        companies = {it.company for it in all_items}
        self.assertTrue({"Stripe", "Photon", "Databricks"}.issubset(companies))

        # 3. AllActionsDialog filters by category and search
        dlg = AllActionsDialog(
            fetch_items_fn=lambda: self.dashboard_service.get_all_pending_actions(limit=100),
            initial_items=all_items,
        )
        self.assertIn("3 actions", dlg.lbl_count.text())

        idx_manual = dlg.cmb_category.findData("MANUAL")
        dlg.cmb_category.setCurrentIndex(idx_manual)
        self.assertIn("1 of 3", dlg.lbl_count.text())

        idx_all = dlg.cmb_category.findData("ALL")
        dlg.cmb_category.setCurrentIndex(idx_all)
        dlg.txt_search.setText("Databricks")
        self.assertIn("1 of 3", dlg.lbl_count.text())

        # Fixed X-axis layout: horizontal scrollbar disabled / zero overflow
        dlg.show()
        self.assertEqual(dlg.minimumWidth(), dlg.maximumWidth())
        self.assertEqual(dlg.scroll.horizontalScrollBar().maximum(), 0)
        dlg.close()

    def test_interviewing_kpi_excludes_cancelled_completed_and_assessment(self):
        """INTERVIEWING KPI card must stay synced with active interviews (exclude CANCELLED/COMPLETED-only and ASSESSMENT)."""
        j1, _ = self.job_service.create_manual_job(title="Role A", company="Alpha", platform="linkedin")
        a1, _ = self.app_service.create_application(job_id=j1.id, status="INTERVIEW")

        j2, _ = self.job_service.create_manual_job(title="Role B", company="Beta", platform="naukri")
        a2, _ = self.app_service.create_application(job_id=j2.id, status="INTERVIEW")

        # Initially both auto-provisioned Round 1s are SCHEDULED -> KPI = 2
        self.assertEqual(self.dashboard_service.get_summary_metrics()["interviews"], 2)

        # Cancel a1's round (stays INTERVIEW stage with CANCELLED round) and complete a2 -> move to ASSESSMENT
        for iv in self.recruitment_service.list_interviews(application_id=a1.id):
            self.recruitment_service.update_interview_status(iv.id, status="CANCELLED")
        for iv in self.recruitment_service.list_interviews(application_id=a2.id):
            self.recruitment_service.update_interview_status(iv.id, status="COMPLETED")
        self.app_service.transition_status(a2.id, "ASSESSMENT", source="USER", allow_override=True)

        metrics = self.dashboard_service.get_summary_metrics()
        self.assertEqual(metrics["interviews"], 0)
        snap = self.dashboard_service.get_dashboard_snapshot()
        self.assertEqual(snap.pipeline_summary["interviews"], 0)

    def test_reentering_interview_stage_provisions_next_round_and_syncs_views(self):
        """Transitioning an app back to INTERVIEW after COMPLETED/CANCELLED round must provision Round 2 and update KPI & InterviewsView."""
        job, _ = self.job_service.create_manual_job(title="Senior Backend", company="Stripe", platform="linkedin")
        app_rec, _ = self.app_service.create_application(job_id=job.id, status="INTERVIEW")

        # Complete Round 1 and move to ASSESSMENT
        ivs = self.recruitment_service.list_interviews(application_id=app_rec.id)
        self.assertEqual(len(ivs), 1)
        self.recruitment_service.update_interview_status(ivs[0].id, status="COMPLETED")
        self.app_service.transition_status(app_rec.id, "ASSESSMENT", source="USER", allow_override=True)
        self.assertEqual(self.dashboard_service.get_summary_metrics()["interviews"], 0)

        # Wire real views via ApplicationsView -> MainWindow._on_data_updated semantics
        apps_view = ApplicationsView(service=self.app_service, recruitment_service=self.recruitment_service)
        iv_view = InterviewsView(service=self.recruitment_service, app_service=self.app_service)
        dash_view = DashboardView(service=self.dashboard_service, recruitment_service=self.recruitment_service)
        dash_view.stop_workers()
        apps_view.data_updated.connect(lambda _: (iv_view.refresh(), dash_view._on_snapshot_loaded(self.dashboard_service.get_dashboard_snapshot())))

        # Trigger inline StatusDropdownButton on ApplicationsView row 0 back to INTERVIEW (exact user flow)
        from app.ui.widgets.status_badge import StatusDropdownButton
        cell_widget = apps_view.table.cellWidget(0, 3)
        self.assertIsNotNone(cell_widget)
        btn_status = cell_widget.findChild(StatusDropdownButton)
        self.assertIsNotNone(btn_status)
        btn_status._on_action_triggered("INTERVIEW")
        QApplication.processEvents()

        updated_ivs = self.recruitment_service.list_interviews(application_id=app_rec.id)
        scheduled_ivs = [iv for iv in updated_ivs if iv.status == "SCHEDULED"]
        self.assertEqual(len(scheduled_ivs), 1)
        self.assertEqual(scheduled_ivs[0].round_number, 2)
        self.assertEqual(iv_view.table.rowCount(), 1)
        self.assertEqual(dash_view.kpi_bar.card_interviewing.lbl_val.text(), "1")

        apps_view.close()
        iv_view.close()
        dash_view.close()

    def test_kpi_cards_stay_synced_across_dashboard_applications_and_interviews(self):
        """Dashboard KPIs, Applications KPIs, and Interviews scheduled count must always match."""
        j1, _ = self.job_service.create_manual_job(title="Role 1", company="Infosys", platform="naukri")
        a1, _ = self.app_service.create_application(job_id=j1.id, status="INTERVIEW")

        j2, _ = self.job_service.create_manual_job(title="Role 2", company="StaleCo", platform="linkedin")
        a2, _ = self.app_service.create_application(job_id=j2.id, status="INTERVIEW")
        # Cancel Round 1 on StaleCo while leaving Application.status == INTERVIEW
        for iv in self.recruitment_service.list_interviews(application_id=a2.id):
            self.recruitment_service.update_interview_status(iv.id, status="CANCELLED")

        j3, _ = self.job_service.create_manual_job(title="Role 3", company="OfferCo", platform="indeed")
        self.app_service.create_application(job_id=j3.id, status="OFFER")

        j4, _ = self.job_service.create_manual_job(title="Role 4", company="SubCo", platform="linkedin")
        self.app_service.create_application(job_id=j4.id, status="SUBMITTED")

        apps_view = ApplicationsView(service=self.app_service, recruitment_service=self.recruitment_service)
        iv_view = InterviewsView(service=self.recruitment_service, app_service=self.app_service)
        dash_view = DashboardView(service=self.dashboard_service, recruitment_service=self.recruitment_service)
        dash_view.stop_workers()
        dash_view._on_snapshot_loaded(self.dashboard_service.get_dashboard_snapshot())

        # Both Dashboard and Applications must match 100% on every shared KPI card
        self.assertEqual(apps_view.lbl_card_submitted.findChild(QLabel).text(), dash_view.kpi_bar.card_submitted.lbl_val.text())
        self.assertEqual(apps_view.lbl_card_review.findChild(QLabel).text(), dash_view.kpi_bar.card_review.lbl_val.text())
        self.assertEqual(apps_view.lbl_card_interview.findChild(QLabel).text(), dash_view.kpi_bar.card_interviewing.lbl_val.text())
        self.assertEqual(apps_view.lbl_card_offers.findChild(QLabel).text(), dash_view.kpi_bar.card_offers.lbl_val.text())
        self.assertEqual(apps_view.lbl_card_rejected.findChild(QLabel).text(), dash_view.kpi_bar.card_rejected.lbl_val.text())

        # And Interviewing (1) matches InterviewsView Scheduled Rounds (1)
        self.assertEqual(apps_view.lbl_card_interview.findChild(QLabel).text(), "1")
        self.assertEqual(iv_view.lbl_card_scheduled.findChild(QLabel).text(), "1")

        apps_view.close()
        iv_view.close()
        dash_view.close()


if __name__ == "__main__":
    unittest.main()
