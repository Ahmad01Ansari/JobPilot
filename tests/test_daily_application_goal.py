"""Unit tests for Daily Application Goal configuration, safety dialog, and timezone conversion."""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import configure_sqlite_pragmas, ensure_sqlite_schema
from app.services.platform_service import PlatformService
from app.utils_time import format_local_datetime, format_local_time, to_local_datetime
from modules.helpers import show_modern_goal_dialog
from platforms.naukri.rotator import SearchRotationConfig


class TestDailyApplicationGoal(unittest.TestCase):
    """Tests for configurable daily application goals and account restriction gates."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "goal_test.db")
        self.db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(self.db_url, future=True)
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(bind=self.engine)
        ensure_sqlite_schema(self.engine)

        self.Session = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self.engine,
            future=True,
        )
        self.platform_service = PlatformService(session_factory=self.Session)
        self.platform_service.seed_default_platforms()

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_default_daily_goal_is_50(self):
        """Verifies that platforms default to 50 applications per day for safety."""
        li_cfg = self.platform_service.get_platform_config("linkedin")
        self.assertEqual(li_cfg.get("daily_application_goal"), 50)

        nk_cfg = self.platform_service.get_platform_config("naukri")
        self.assertEqual(nk_cfg.get("daily_application_goal"), 50)

    def test_save_and_update_daily_goal(self):
        """Verifies updating daily_application_goal persists correctly."""
        success, err = self.platform_service.save_platform_config(
            platform_name="linkedin",
            daily_application_goal=75,
        )
        self.assertTrue(success)
        self.assertIsNone(err)

        updated_cfg = self.platform_service.get_platform_config("linkedin")
        self.assertEqual(updated_cfg.get("daily_application_goal"), 75)

    def test_reject_invalid_daily_goal(self):
        """Verifies that non-positive daily application goals are rejected."""
        success, err = self.platform_service.save_platform_config(
            platform_name="linkedin",
            daily_application_goal=0,
        )
        self.assertFalse(success)
        self.assertIn("greater than 0", str(err))

        success, err = self.platform_service.save_platform_config(
            platform_name="linkedin",
            daily_application_goal=-5,
        )
        self.assertFalse(success)
        self.assertIn("greater than 0", str(err))

    def test_naukri_search_rotation_config_goal(self):
        """Verifies SearchRotationConfig has daily_application_goal loaded."""
        cfg = SearchRotationConfig.from_profile()
        self.assertIsNotNone(cfg.daily_application_goal)
        self.assertGreater(cfg.daily_application_goal, 0)

    def test_modern_goal_dialog_headless_safe(self):
        """Verifies show_modern_goal_dialog safely terminates in headless/testing mode."""
        with patch.dict(os.environ, {"TESTING": "1"}):
            should_cont, add_apps = show_modern_goal_dialog("LinkedIn", 50, 50)
            self.assertFalse(should_cont)
            self.assertEqual(add_apps, 0)


class TestLocalTimezoneUtils(unittest.TestCase):
    """Tests for local timezone conversion and display formatting."""

    def test_to_local_datetime_from_utc_naive(self):
        """Verifies naive UTC datetime from SQLite is converted to local timezone."""
        utc_naive = datetime(2026, 9, 22, 13, 0, 0)
        local_dt = to_local_datetime(utc_naive)
        self.assertIsNotNone(local_dt)
        self.assertIsNotNone(local_dt.tzinfo)

    def test_to_local_datetime_from_aware(self):
        """Verifies aware UTC datetime is converted to local timezone."""
        utc_aware = datetime(2026, 9, 22, 13, 0, 0, tzinfo=timezone.utc)
        local_dt = to_local_datetime(utc_aware)
        self.assertIsNotNone(local_dt)
        self.assertIsNotNone(local_dt.tzinfo)

    def test_format_local_datetime(self):
        """Verifies formatted local string contains valid hour and date."""
        utc_naive = datetime(2026, 9, 22, 7, 30, 0)
        formatted = format_local_datetime(utc_naive, "%b %d, %H:%M")
        self.assertIn("Sep 22", formatted)
        self.assertNotEqual(formatted, "-")

    def test_format_local_datetime_none_returns_dash(self):
        """Verifies None datetime returns fallback dash."""
        self.assertEqual(format_local_datetime(None), "-")

    def test_format_local_time(self):
        """Verifies local time formatting."""
        formatted_now = format_local_time()
        self.assertEqual(len(formatted_now.split(":")), 3)


if __name__ == "__main__":
    unittest.main()
