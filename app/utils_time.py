"""Time and timezone utilities for JobPilot.
Handles conversion between UTC (storage format) and local timezone (display format).
"""
import os
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Optional, Tuple, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Default fallback timezone for JobPilot: Asia/Kolkata (IST: UTC+05:30)
DEFAULT_TIMEZONE_NAME = "Asia/Kolkata"
DEFAULT_FALLBACK_TZ = timezone(timedelta(hours=5, minutes=30))


def get_application_timezone() -> tzinfo:
    """Returns the application-level timezone.

    Priority:
    1. APP_TIMEZONE environment variable (e.g., 'Asia/Kolkata', 'UTC')
    2. System local timezone (datetime.now().astimezone().tzinfo)
    3. Default fallback: Asia/Kolkata (UTC+05:30)
    """
    env_tz = os.getenv("APP_TIMEZONE", "").strip()
    if env_tz:
        try:
            return ZoneInfo(env_tz)
        except ZoneInfoNotFoundError:
            pass

    sys_tz = datetime.now().astimezone().tzinfo
    if sys_tz is not None:
        return sys_tz

    try:
        return ZoneInfo(DEFAULT_TIMEZONE_NAME)
    except Exception:
        return DEFAULT_FALLBACK_TZ


def get_local_day_utc_range(
    target_date: Optional[Union[date, datetime]] = None,
    tz: Optional[tzinfo] = None,
) -> Tuple[datetime, datetime]:
    """Calculates the UTC start and end timestamps representing a full calendar day
    in the application or specified timezone.

    Returns:
        (utc_start, utc_end): Timezone-aware UTC datetimes for:
            00:00:00.000000 local -> UTC
            23:59:59.999999 local -> UTC
    """
    app_tz = tz or get_application_timezone()

    if target_date is None:
        now_local = datetime.now(app_tz)
        local_date = now_local.date()
    elif isinstance(target_date, datetime):
        if target_date.tzinfo is None:
            # Naive datetime is assumed to be in app_tz
            local_date = target_date.date()
        else:
            local_date = target_date.astimezone(app_tz).date()
    elif isinstance(target_date, date):
        local_date = target_date
    else:
        raise TypeError(f"Expected date or datetime, got {type(target_date)}")

    dt_start_loc = datetime.combine(local_date, time.min, tzinfo=app_tz)
    dt_end_loc = datetime.combine(local_date, time.max, tzinfo=app_tz)

    utc_start = dt_start_loc.astimezone(timezone.utc)
    utc_end = dt_end_loc.astimezone(timezone.utc)

    return utc_start, utc_end


def get_local_date_bounds(
    preset: str,
    tz: Optional[tzinfo] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Calculates UTC start and end bounds based on user's local calendar days
    for preset ranges (TODAY, 7D, 30D, 90D, 6M, 1Y, ALL).
    """
    p = (preset or "30D").strip().upper()
    if p == "ALL":
        return None, None

    app_tz = tz or get_application_timezone()
    today_start_utc, today_end_utc = get_local_day_utc_range(tz=app_tz)

    days_map = {
        "TODAY": 0,
        "7D": 6,
        "30D": 29,
        "90D": 89,
        "6M": 179,
        "1Y": 364,
    }
    days_back = days_map.get(p, 29)

    period_start_utc = today_start_utc - timedelta(days=days_back)
    return period_start_utc, today_end_utc


def to_local_datetime(dt: Optional[datetime], tz: Optional[tzinfo] = None) -> Optional[datetime]:
    """Converts a UTC or naive datetime to the user's local or specified timezone."""
    if dt is None:
        return None
    if not isinstance(dt, datetime):
        return dt
    target_tz = tz or get_application_timezone()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(target_tz)


def format_local_datetime(
    dt: Optional[datetime],
    fmt: str = "%b %d, %H:%M",
    tz: Optional[tzinfo] = None,
) -> str:
    """Formats a datetime in the user's local timezone."""
    if dt is None:
        return "-"
    loc_dt = to_local_datetime(dt, tz=tz)
    if loc_dt is None:
        return "-"
    return loc_dt.strftime(fmt)


def format_local_time(
    dt: Optional[datetime] = None,
    fmt: str = "%H:%M:%S",
    tz: Optional[tzinfo] = None,
) -> str:
    """Formats current or specified time in local timezone."""
    target_tz = tz or get_application_timezone()
    if dt is None:
        return datetime.now(target_tz).strftime(fmt)
    loc_dt = to_local_datetime(dt, tz=target_tz)
    if loc_dt is None:
        return "-"
    return loc_dt.strftime(fmt)

