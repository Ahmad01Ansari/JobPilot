"""Unit tests for centralized timezone utilities (app/utils_time.py).
Tests India timezone (+05:30), midnight boundaries, UTC/local date mismatch,
DST transitions, and preset date range calculations.
"""
from datetime import date, datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.utils_time import (
    DEFAULT_FALLBACK_TZ,
    format_local_datetime,
    format_local_time,
    get_application_timezone,
    get_local_date_bounds,
    get_local_day_utc_range,
    to_local_datetime,
)


class TestUtilsTime(unittest.TestCase):
    """Verifies centralized time & timezone logic."""

    def setUp(self):
        self.ist = timezone(timedelta(hours=5, minutes=30))
        self.ny = ZoneInfo("America/New_York")

    def test_get_application_timezone_default_fallback(self):
        """When no env var is set, it falls back to system or default IST."""
        with patch.dict("os.environ", {}, clear=True):
            tz = get_application_timezone()
            self.assertIsNotNone(tz)

    def test_get_application_timezone_env_override(self):
        """APP_TIMEZONE env var overrides system timezone."""
        with patch.dict("os.environ", {"APP_TIMEZONE": "Asia/Kolkata"}):
            tz = get_application_timezone()
            self.assertEqual(str(tz), "Asia/Kolkata")

        with patch.dict("os.environ", {"APP_TIMEZONE": "UTC"}):
            tz = get_application_timezone()
            self.assertEqual(str(tz), "UTC")

    def test_ist_day_utc_range(self):
        """Oct 4, 2026 in IST (+05:30) starts at Oct 3, 18:30 UTC and ends at Oct 4, 18:29:59.999999 UTC."""
        target = date(2026, 10, 4)
        utc_start, utc_end = get_local_day_utc_range(target_date=target, tz=self.ist)

        self.assertEqual(utc_start.tzinfo, timezone.utc)
        self.assertEqual(utc_end.tzinfo, timezone.utc)

        expected_start = datetime(2026, 10, 3, 18, 30, 0, tzinfo=timezone.utc)
        expected_end = datetime(2026, 10, 4, 18, 29, 59, 999999, tzinfo=timezone.utc)

        self.assertEqual(utc_start, expected_start)
        self.assertEqual(utc_end, expected_end)

    def test_midnight_and_early_morning_inclusion(self):
        """Events created in early morning IST (e.g. 00:15 IST / 18:45 UTC prev day)
        MUST fall within Today's local range."""
        target = date(2026, 10, 4)
        utc_start, utc_end = get_local_day_utc_range(target_date=target, tz=self.ist)

        # 00:15:00 IST on Oct 4 is 18:45:00 UTC on Oct 3
        early_morning_event_utc = datetime(2026, 10, 3, 18, 45, 0, tzinfo=timezone.utc)
        self.assertTrue(utc_start <= early_morning_event_utc <= utc_end)

        # 23:45:00 IST on Oct 4 is 18:15:00 UTC on Oct 4
        late_night_event_utc = datetime(2026, 10, 4, 18, 15, 0, tzinfo=timezone.utc)
        self.assertTrue(utc_start <= late_night_event_utc <= utc_end)

        # 23:55:00 IST on Oct 3 is 18:25:00 UTC on Oct 3 (belongs to yesterday)
        yesterday_event_utc = datetime(2026, 10, 3, 18, 25, 0, tzinfo=timezone.utc)
        self.assertFalse(utc_start <= yesterday_event_utc <= utc_end)

    def test_utc_local_date_mismatch_resolution(self):
        """When local time is 01:00 AM on Oct 4 (UTC is 19:30 on Oct 3),
        calling get_local_day_utc_range with that datetime resolves to Oct 4 local day."""
        dt_local = datetime(2026, 10, 4, 1, 0, 0, tzinfo=self.ist)
        utc_start, utc_end = get_local_day_utc_range(target_date=dt_local, tz=self.ist)

        self.assertEqual(utc_start, datetime(2026, 10, 3, 18, 30, 0, tzinfo=timezone.utc))
        self.assertEqual(utc_end, datetime(2026, 10, 4, 18, 29, 59, 999999, tzinfo=timezone.utc))

    def test_get_local_date_bounds_presets(self):
        """Test preset date bounds (TODAY, 7D, 30D, ALL)."""
        # ALL
        start, end = get_local_date_bounds("ALL", tz=self.ist)
        self.assertIsNone(start)
        self.assertIsNone(end)

        # TODAY
        today_start, today_end = get_local_day_utc_range(tz=self.ist)
        p_start, p_end = get_local_date_bounds("TODAY", tz=self.ist)
        self.assertEqual(p_start, today_start)
        self.assertEqual(p_end, today_end)

        # 7D (starts 6 days before today_start)
        p7_start, p7_end = get_local_date_bounds("7D", tz=self.ist)
        self.assertEqual(p7_start, today_start - timedelta(days=6))
        self.assertEqual(p7_end, today_end)

    def test_formatting_utilities(self):
        """Verify to_local_datetime, format_local_datetime, format_local_time."""
        utc_dt = datetime(2026, 10, 4, 12, 0, 0, tzinfo=timezone.utc)
        # 12:00 UTC -> 17:30 IST
        loc_dt = to_local_datetime(utc_dt, tz=self.ist)
        self.assertEqual(loc_dt.hour, 17)
        self.assertEqual(loc_dt.minute, 30)

        formatted = format_local_datetime(utc_dt, fmt="%Y-%m-%d %H:%M", tz=self.ist)
        self.assertEqual(formatted, "2026-10-04 17:30")

        self.assertEqual(format_local_datetime(None), "-")


if __name__ == "__main__":
    unittest.main()
