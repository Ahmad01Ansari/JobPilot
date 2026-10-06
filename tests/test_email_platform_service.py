"""Unit tests for Email Outreach platform configuration and template management."""

import os
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.repositories.email_template_repository import EmailTemplateRepository
from app.services.platform_service import PlatformService
from app.services.template_renderer import TemplateRenderer


class TestEmailPlatformService(unittest.TestCase):
    """Verifies Email Outreach platform configuration, seeding, and template operations."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.platform_service = PlatformService(session_factory=self.Session)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_seed_email_platform(self):
        """Verifies email platform is properly seeded with default extra_settings."""
        plats = self.platform_service.list_platforms()
        names = [p.name for p in plats]
        self.assertIn("email", names)

        cfg = self.platform_service.get_platform_config("email")
        self.assertEqual(cfg["name"], "email")
        self.assertEqual(cfg["display_name"], "Email Outreach")
        self.assertTrue(cfg["is_enabled"])
        self.assertEqual(cfg["apply_mode"], "DIRECT_EMAIL")

        extra = cfg.get("extra_settings", {})
        self.assertEqual(extra.get("sync_label"), "RPA-Developer-Application")
        self.assertEqual(extra.get("reply_folder"), "INBOX")
        self.assertEqual(extra.get("followup_cadence_days"), [3, 7, 14])
        self.assertTrue(extra.get("auto_pause_on_reply"))
        self.assertTrue(extra.get("auto_followup_enabled"))

    def test_update_email_platform_extra_settings(self):
        """Verifies saving extra_settings updates cadence, labels, and limits."""
        self.platform_service.seed_default_platforms()

        new_extra = {
            "sync_label": "Custom-Job-Pitch",
            "followup_cadence_days": [2, 5, 10, 20],
            "auto_pause_on_reply": False,
            "sender_name": "Test Candidate",
            "signature": "--\nBest regards,\nCandidate",
        }
        success, err = self.platform_service.save_platform_config(
            platform_name="email",
            daily_application_goal=40,
            extra_settings=new_extra,
        )
        self.assertTrue(success)
        self.assertIsNone(err)

        cfg = self.platform_service.get_platform_config("email")
        self.assertEqual(cfg["daily_application_goal"], 40)
        extra = cfg.get("extra_settings", {})
        self.assertEqual(extra.get("sync_label"), "Custom-Job-Pitch")
        self.assertEqual(extra.get("followup_cadence_days"), [2, 5, 10, 20])
        self.assertFalse(extra.get("auto_pause_on_reply"))
        self.assertEqual(extra.get("sender_name"), "Test Candidate")

    def test_email_template_repository_crud(self):
        """Verifies creating, duplicating, and deleting email templates."""
        with self.Session() as session:
            repo = EmailTemplateRepository(session)
            repo.seed_defaults_if_empty()

            initial_tmpls = repo.list_all()
            self.assertEqual(len(initial_tmpls), 4)

            # Create custom template
            created = repo.create(
                key="custom_pitch",
                name="Custom Pitch",
                subject_template="Pitch: {{job_title}}",
                body_template="Hi {{recruiter_name}},\nPortfolio: {{portfolio_url}}",
                category="JOB_APPLICATION",
            )
            session.commit()
            self.assertIsNotNone(created.id)

            # Duplicate template
            duplicated = repo.duplicate(created.id)
            session.commit()
            self.assertIsNotNone(duplicated)
            self.assertEqual(duplicated.name, "Custom Pitch (Copy)")
            self.assertIn("portfolio_url", duplicated.variables_json)

            # Verify count
            self.assertEqual(len(repo.list_all()), 6)

            # Delete custom template
            del_res = repo.delete(created.id)
            session.commit()
            self.assertTrue(del_res)

            # Verify template no longer exists
            self.assertIsNone(repo.get_by_id(created.id))
            self.assertEqual(len(repo.list_all()), 5)

    def test_template_renderer_preview_sample_data(self):
        """Verifies variable interpolation in template rendering."""
        sample_context = {
            "candidate_name": "Mohd Ahmad Raza Ansari",
            "recruiter_name": "Sarah Jenkins",
            "company_name": "Acme Innovations",
            "job_title": "Senior RPA Developer",
            "skills": "UiPath, Python",
            "portfolio_url": "https://github.com/ahmad10raza",
        }
        raw_subj = "Application for {{job_title}} - {{candidate_name}}"
        raw_body = "Hi {{recruiter_name}}, I want to join {{company_name}} as a {{job_title}}."

        rendered_subj, _ = TemplateRenderer.render(raw_subj, sample_context, strict=False)
        rendered_body, _ = TemplateRenderer.render(raw_body, sample_context, strict=False)

        self.assertEqual(rendered_subj, "Application for Senior RPA Developer - Mohd Ahmad Raza Ansari")
        self.assertEqual(rendered_body, "Hi Sarah Jenkins, I want to join Acme Innovations as a Senior RPA Developer.")

    def test_template_edit_dialog_variable_insertion_and_preview(self):
        """Verifies TemplateEditDialog inserts tokens at cursor and updates preview."""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication([])

        from app.ui.views.email_platform_dialog import TemplateEditDialog
        dlg = TemplateEditDialog(template=None)
        self.assertIsNotNone(dlg)

        # Test variable insertion
        dlg.txt_subject.setText("Application: ")
        dlg.last_focused_input = dlg.txt_subject
        dlg._insert_variable("{{job_title}}")
        self.assertEqual(dlg.txt_subject.text(), "Application: {{job_title}}")

        # Test body and preview
        dlg.txt_body.setPlainText("Hello {{recruiter_name}}")
        dlg._update_preview()
        self.assertIn("Sarah Jenkins", dlg.txt_preview_body.text())
        self.assertIn("Senior RPA / Python Automation Engineer", dlg.lbl_preview_subject.text())
        dlg.close()

    def test_email_outreach_config_dialog_tabs_and_cadence(self):
        """Verifies EmailOutreachConfigDialog renders all 4 tabs and supports cadence modifications."""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication([])

        from app.ui.views.email_platform_dialog import EmailOutreachConfigDialog
        dlg = EmailOutreachConfigDialog(service=self.platform_service)
        self.assertEqual(dlg.tabs.count(), 4)
        self.assertEqual(dlg.tabs.tabText(0), "📬 Account & Gmail Sync")
        self.assertEqual(dlg.tabs.tabText(1), "📝 Email Templates")
        self.assertEqual(dlg.tabs.tabText(2), "⏱️ Follow-Up Schedule")
        self.assertEqual(dlg.tabs.tabText(3), "👤 Sender Defaults")

        # Verify cadence steps manipulation
        initial_steps = dlg._get_cadence_days_from_ui()
        self.assertEqual(initial_steps, [3, 7, 14])

        dlg._add_cadence_step()
        added_steps = dlg._get_cadence_days_from_ui()
        self.assertEqual(added_steps, [3, 7, 14, 21])

        dlg._remove_cadence_step(3)
        restored_steps = dlg._get_cadence_days_from_ui()
        self.assertEqual(restored_steps, [3, 7, 14])
        dlg.close()

    def test_platform_card_for_email_rendering(self):
        """Verifies PlatformCard displays customized email metrics and sync hints."""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication([])

        from app.ui.views.platforms_view import PlatformCard
        card = PlatformCard(
            platform_name="email",
            service=self.platform_service,
            on_changed_callback=None,
        )
        self.assertEqual(card.lbl_icon.text(), "✉️")
        self.assertIn("sync_label", card.chip_val_labels)
        self.assertIn("account", card.chip_val_labels)
        self.assertIn("templates", card.chip_val_labels)
        self.assertIn("cadence", card.chip_val_labels)
        card.close()


if __name__ == "__main__":
    unittest.main()

