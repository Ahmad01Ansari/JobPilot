"""Unit and UI test suite for QnAService and QnAView (Phase 8)."""

import os
import shutil
import tempfile
import unittest

from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import configure_sqlite_pragmas
from app.services.qna_service import QnAService


class TestQnAService(unittest.TestCase):
    """Unit tests for QnAService business logic, CRUD, and question matching."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "qna_test.db")
        self.db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(self.db_url, future=True)
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(bind=self.engine)

        self.Session = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self.engine,
            future=True,
        )
        self.service = QnAService(session_factory=self.Session)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_and_list_qna_entries(self):
        """Verifies adding entries and filtering by category and search text."""
        # Add two entries in different categories
        e1, err1 = self.service.add_entry(
            question="What is your notice period in days?",
            answer="30",
            category="notice_period",
            answer_type="numeric",
        )
        self.assertIsNotNone(e1)
        self.assertIsNone(err1)

        e2, err2 = self.service.add_entry(
            question="What is your current CTC?",
            answer="1500000",
            category="salary",
            answer_type="numeric",
        )
        self.assertIsNotNone(e2)
        self.assertIsNone(err2)

        # List all — should have 2
        all_entries = self.service.list_entries()
        self.assertEqual(len(all_entries), 2)

        # Filter by category
        salary_entries = self.service.list_entries(category="salary")
        self.assertEqual(len(salary_entries), 1)
        self.assertIn("CTC", salary_entries[0].question_text)

        # Search by text
        notice_entries = self.service.list_entries(search="notice")
        self.assertEqual(len(notice_entries), 1)
        self.assertEqual(notice_entries[0].answer_text, "30")

    def test_add_entry_validation_rejects_empty(self):
        """Verifies empty question or answer is rejected with error message."""
        _, err_q = self.service.add_entry(question="", answer="30")
        self.assertIn("Question prompt cannot be empty", err_q)

        _, err_a = self.service.add_entry(question="Valid question?", answer="")
        self.assertIn("Answer value cannot be empty", err_a)

    def test_update_and_delete_entry(self):
        """Verifies editing and deleting an existing entry."""
        entry, _ = self.service.add_entry(
            question="Are you authorized to work in India?",
            answer="Yes",
            category="work_auth",
            answer_type="boolean",
        )
        entry_id = entry.id

        # Update question text and answer
        updated, err = self.service.update_entry(
            entry_id=entry_id,
            answer="No",
            category="background",
        )
        self.assertIsNotNone(updated)
        self.assertIsNone(err)
        self.assertEqual(updated.answer_text, "No")
        self.assertEqual(updated.category, "background")

        # Delete
        success, err = self.service.delete_entry(entry_id)
        self.assertTrue(success)
        self.assertIsNone(err)

        # Verify gone
        remaining = self.service.list_entries()
        self.assertEqual(len(remaining), 0)

    def test_update_nonexistent_entry_returns_error(self):
        """Verifies updating a non-existent entry returns a clear error."""
        updated, err = self.service.update_entry(entry_id=99999, answer="test")
        self.assertIsNone(updated)
        self.assertIn("not found", err)

    def test_toggle_active_status(self):
        """Verifies toggling is_active flag on/off."""
        entry, _ = self.service.add_entry(
            question="Do you have a valid passport?",
            answer="Yes",
        )
        self.assertTrue(entry.is_active)

        # Toggle off
        new_state, err = self.service.toggle_active(entry.id)
        self.assertIsNone(err)
        self.assertFalse(new_state)

        # Toggle back on
        new_state, err = self.service.toggle_active(entry.id)
        self.assertIsNone(err)
        self.assertTrue(new_state)

    def test_toggle_nonexistent_entry_returns_error(self):
        """Verifies toggling a non-existent entry returns error."""
        result, err = self.service.toggle_active(99999)
        self.assertFalse(result)
        self.assertIn("not found", err)

    def test_test_question_match_found(self):
        """Verifies the question matcher finds a matching knowledge base entry."""
        self.service.add_entry(
            question="How many years of experience do you have in Python?",
            answer="5",
            category="experience",
            answer_type="numeric",
            source="MANUAL",
        )

        # Exact match
        result = self.service.test_question_match(
            "How many years of experience do you have in Python?"
        )
        self.assertTrue(result["matched"])
        self.assertEqual(result["answer"], "5")
        self.assertEqual(result["category"], "experience")
        self.assertEqual(result["source"], "MANUAL")

    def test_test_question_match_normalized(self):
        """Verifies matching works with normalized question (case/punctuation insensitive)."""
        self.service.add_entry(
            question="What is your expected CTC?",
            answer="2000000",
            category="salary",
        )

        # Query with different casing and punctuation
        result = self.service.test_question_match("what  IS  your  expected  ctc")
        self.assertTrue(result["matched"])
        self.assertEqual(result["answer"], "2000000")

    def test_test_question_match_not_found(self):
        """Verifies matcher returns no match for unknown question."""
        result = self.service.test_question_match("Completely unrelated question?")
        self.assertFalse(result["matched"])
        self.assertIn("normalized_query", result)

    def test_test_question_match_empty_returns_message(self):
        """Verifies empty question test returns appropriate message."""
        result = self.service.test_question_match("")
        self.assertFalse(result["matched"])
        self.assertIn("Please provide", result["message"])

    def test_test_question_match_platform_specific(self):
        """Verifies platform-specific match takes priority over universal."""
        self.service.add_entry(
            question="Are you willing to relocate?",
            answer="Yes (Universal)",
            category="relocation",
        )
        self.service.add_entry(
            question="Are you willing to relocate?",
            answer="Yes, within India (Naukri)",
            category="relocation",
            platform="naukri",
        )

        # Platform-specific query should return Naukri-specific answer
        result = self.service.test_question_match(
            "Are you willing to relocate?", platform="naukri"
        )
        self.assertTrue(result["matched"])
        self.assertIn("Naukri", result["answer"])

        # Universal query should return universal answer
        result_universal = self.service.test_question_match(
            "Are you willing to relocate?"
        )
        self.assertTrue(result_universal["matched"])
        self.assertIn("Universal", result_universal["answer"])

    def test_get_stats(self):
        """Verifies summary statistics are computed correctly."""
        self.service.add_entry(
            question="Q1?", answer="A1", category="salary"
        )
        self.service.add_entry(
            question="Q2?", answer="A2", category="experience"
        )
        self.service.add_entry(
            question="Q3?", answer="A3", category="salary"
        )

        stats = self.service.get_stats()
        self.assertEqual(stats["total_entries"], 3)
        self.assertEqual(stats["active_entries"], 3)
        self.assertEqual(stats["verified_entries"], 3)
        self.assertEqual(stats["unreviewed_entries"], 0)
        self.assertEqual(stats["categories"]["salary"], 2)
        self.assertEqual(stats["categories"]["experience"], 1)

    def test_list_entries_active_only_filter(self):
        """Verifies only_active filter hides disabled entries."""
        e1, _ = self.service.add_entry(question="Active Q?", answer="Yes")
        e2, _ = self.service.add_entry(question="Disabled Q?", answer="No")

        # Disable e2
        self.service.toggle_active(e2.id)

        active_only = self.service.list_entries(only_active=True)
        self.assertEqual(len(active_only), 1)
        self.assertEqual(active_only[0].question_text, "Active Q?")

    def test_upsert_updates_existing_on_duplicate_question(self):
        """Verifies adding the same question again updates the existing entry."""
        self.service.add_entry(
            question="What is your notice period?",
            answer="30 days",
        )
        self.service.add_entry(
            question="What is your notice period?",
            answer="60 days",
        )

        entries = self.service.list_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].answer_text, "60 days")

    def test_delete_nonexistent_entry_returns_error(self):
        """Verifies deleting a non-existent entry returns error."""
        success, err = self.service.delete_entry(99999)
        self.assertFalse(success)
        self.assertIn("not found", err)


class TestQnAView(unittest.TestCase):
    """Headless UI tests for PySide6 QnAView component."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "qna_view_test.db")
        self.db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(self.db_url, future=True)
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(bind=self.engine)

        self.Session = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self.engine,
            future=True,
        )
        self.service = QnAService(session_factory=self.Session)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_qna_view_rendering_and_table_population(self):
        """Verifies QnAView renders and populates table from database entries."""
        from app.ui.views.qna_view import QnAView

        # Seed entries
        self.service.add_entry(question="What is your CTC?", answer="1500000", category="salary")
        self.service.add_entry(question="Notice period?", answer="30", category="notice_period")

        view = QnAView(service=self.service)
        view.show()

        # Table should have 2 rows
        self.assertEqual(view.table.rowCount(), 2)
        self.assertIn("2 entries", view.lbl_stats.text())

        # Verify header exists
        self.assertIn("Knowledge Base", view.header.title_label.text())

    def test_qna_view_search_filter(self):
        """Verifies text search filter narrows table results."""
        from app.ui.views.qna_view import QnAView

        self.service.add_entry(question="Notice period in days?", answer="30")
        self.service.add_entry(question="Current CTC?", answer="1500000")

        view = QnAView(service=self.service)
        view.show()

        self.assertEqual(view.table.rowCount(), 2)

        # Apply search filter
        view.txt_search.setText("CTC")
        self.assertEqual(view.table.rowCount(), 1)


if __name__ == "__main__":
    unittest.main()
