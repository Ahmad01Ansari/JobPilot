"""Platform and search configuration service.

Encapsulates business logic for managing job search platforms (LinkedIn, Naukri, Indeed, Glassdoor),
runtime platform accounts, execution parameters, and search query filters.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import Platform, PlatformAccount
from app.db.session import SessionLocal, get_db_session
from app.repositories.platform_repository import PlatformRepository

logger = logging.getLogger(__name__)


class PlatformService:
    """Service layer for platform connection management and search criteria configuration."""

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        import os
        self._session_factory = session_factory or SessionLocal
        self.is_test = (
            session_factory is not None and session_factory != SessionLocal
        ) or os.environ.get("TESTING") == "1"

    def seed_default_platforms(self) -> List[Platform]:
        """Idempotently seeds the 4 core platforms (LinkedIn, Naukri, Indeed, Glassdoor).

        LinkedIn and Naukri are enabled by default with initial configs;
        Indeed and Glassdoor are disabled placeholders for future expansion.
        """
        with get_db_session(self._session_factory) as session:
            repo = PlatformRepository(session)

            platforms_data = [
                {
                    "name": "linkedin",
                    "display_name": "LinkedIn",
                    "description": "LinkedIn Easy Apply & Standard Job Search Automation",
                    "is_enabled": True,
                    "default_location": "India",
                    "experience_years": 5,
                    "max_applications": 30,
                    "daily_application_goal": 50,
                    "apply_mode": "EASY_APPLY_ONLY",
                    "pause_before_submit": False,
                    "stealth_mode": True,
                    "safe_mode": True,
                    "extra_settings": {
                        "search_terms": [
                            "RPA Developer",
                            "Automation Anywhere Developer",
                            "Python Automation Engineer",
                            "AI Automation Engineer",
                            "Automation Engineer",
                        ],
                        "date_posted": "Past week",
                        "max_pages_per_search": 3,
                        "consecutive_skips_limit": 10,
                        "bad_words": [
                            "US Citizen Only",
                            "Active Security Clearance",
                            "Polygraph",
                            "CNC Operator",
                        ],
                        "negative_title_words": [
                            "electrical",
                            "mechanical",
                            "civil",
                            "hardware",
                            "chemical",
                            "structural",
                            "technician",
                            "machinist",
                            "maintenance",
                            "site engineer",
                            "eplan",
                            "plc programmer",
                        ],
                    },
                },
                {
                    "name": "naukri",
                    "display_name": "Naukri.com",
                    "description": "Naukri India Job Search & Quick Apply Automation",
                    "is_enabled": True,
                    "default_location": "India",
                    "experience_years": 5,
                    "max_applications": 30,
                    "daily_application_goal": 50,
                    "apply_mode": "EASY_APPLY_ONLY",
                    "pause_before_submit": False,
                    "stealth_mode": True,
                    "safe_mode": True,
                    "extra_settings": {
                        "search_terms": [
                            "Python Automation Engineer",
                            "QA Automation Engineer",
                            "SDET",
                        ],
                        "date_posted": "Past week",
                        "max_pages_per_search": 3,
                        "consecutive_skips_limit": 10,
                        "bad_words": ["US Citizen Only", "Security Clearance"],
                        "negative_title_words": ["intern", "trainee", "lead", "architect"],
                    },
                },
                {
                    "name": "indeed",
                    "display_name": "Indeed",
                    "description": "Indeed Job Search Automation (Planned integration)",
                    "is_enabled": False,
                    "default_location": "India",
                    "experience_years": 3,
                    "max_applications": 20,
                    "daily_application_goal": 50,
                    "apply_mode": "EASY_APPLY_ONLY",
                    "pause_before_submit": False,
                    "stealth_mode": True,
                    "safe_mode": True,
                    "extra_settings": {
                        "search_terms": ["Python Developer"],
                        "date_posted": "Past month",
                        "max_pages_per_search": 2,
                        "consecutive_skips_limit": 5,
                        "bad_words": [],
                        "negative_title_words": [],
                    },
                },
                {
                    "name": "glassdoor",
                    "display_name": "Glassdoor",
                    "description": "Glassdoor Job Search & Easy Apply Automation",
                    "is_enabled": True,
                    "default_location": "India",
                    "experience_years": 3,
                    "max_applications": 20,
                    "daily_application_goal": 50,
                    "apply_mode": "EASY_APPLY_ONLY",
                    "pause_before_submit": True,
                    "stealth_mode": True,
                    "safe_mode": True,
                    "extra_settings": {
                        "search_terms": ["Python Engineer"],
                        "date_posted": "Past month",
                        "max_pages_per_search": 2,
                        "consecutive_skips_limit": 5,
                        "bad_words": [],
                        "negative_title_words": [],
                    },
                },
                {
                    "name": "foundit",
                    "display_name": "Foundit",
                    "description": "Foundit (Monster India) Job Search Automation",
                    "is_enabled": True,
                    "default_location": "India",
                    "experience_years": 2,
                    "max_applications": 50,
                    "daily_application_goal": 30,
                    "apply_mode": "EASY_APPLY_ONLY",
                    "pause_before_submit": False,
                    "stealth_mode": True,
                    "safe_mode": True,
                    "extra_settings": {
                        "search_terms": ["RPA Developer", "Automation Anywhere Developer", "Python Automation Engineer"],
                        "date_posted": "Past week",
                        "max_pages_per_search": 3,
                        "consecutive_skips_limit": 20,
                        "bad_words": ["US Citizen Only", "Active Security Clearance"],
                        "negative_title_words": ["android", "ios", "frontend", "react"],
                    },
                },
                {
                    "name": "email",
                    "display_name": "Email Outreach",
                    "description": "Direct recruiter email outreach, 2-way Gmail sync & automated follow-ups",
                    "is_enabled": True,
                    "default_location": "Remote",
                    "experience_years": 2,
                    "max_applications": 30,
                    "daily_application_goal": 30,
                    "apply_mode": "DIRECT_EMAIL",
                    "pause_before_submit": False,
                    "stealth_mode": False,
                    "safe_mode": True,
                    "extra_settings": {
                        "sync_label": "RPA-Developer-Application",
                        "reply_folder": "INBOX",
                        "followup_cadence_days": [3, 7, 14],
                        "auto_pause_on_reply": True,
                        "auto_followup_enabled": True,
                        "daily_send_limit": 30,
                        "sender_name": "Mohd Ahmad Raza Ansari",
                        "default_resume_path": "",
                        "signature": "--\nBest regards,\nMohd Ahmad Raza Ansari",
                    },
                },
            ]

            seeded = []
            for item in platforms_data:
                plat = repo.get_platform_by_name(item["name"])
                if not plat:
                    plat = repo.get_or_create_platform(
                        name=item["name"],
                        display_name=item["display_name"],
                        description=item["description"],
                    )
                    plat.is_enabled = item["is_enabled"]
                    session.flush()

                # Ensure default account exists
                account = repo.get_account(item["name"])
                if not account:
                    repo.save_account(
                        platform_name=item["name"],
                        display_name=item["display_name"],
                        account_name="Default Profile",
                        default_location=item["default_location"],
                        experience_years=item["experience_years"],
                        max_applications=item["max_applications"],
                        daily_application_goal=item.get("daily_application_goal", 50),
                        apply_mode=item["apply_mode"],
                        pause_before_submit=item["pause_before_submit"],
                        stealth_mode=item["stealth_mode"],
                        safe_mode=item["safe_mode"],
                        extra_settings=item["extra_settings"],
                    )
                seeded.append(plat)

            session.commit()
            seeded_plats = repo.list_platforms()
            session.expunge_all()
            return seeded_plats

    def list_platforms(self) -> List[Platform]:
        """Lists all registered platforms and account parameters, auto-seeding if empty."""
        with get_db_session(self._session_factory) as session:
            repo = PlatformRepository(session)
            platforms = repo.list_platforms()
            needs_seed = not platforms or not any(p.name == "email" for p in platforms)
            if not needs_seed:
                session.expunge_all()
                return platforms

        return self.seed_default_platforms()

    def get_platform_by_name(self, name: str) -> Optional[Platform]:
        """Fetches a specific platform by identifier name."""
        with get_db_session(self._session_factory) as session:
            repo = PlatformRepository(session)
            return repo.get_platform_by_name(name)

    def toggle_platform(self, name: str) -> Tuple[bool, Optional[str]]:
        """Toggles the is_enabled status of a platform."""
        try:
            with get_db_session(self._session_factory) as session:
                repo = PlatformRepository(session)
                plat = repo.get_platform_by_name(name)
                if not plat:
                    return False, f"Platform '{name}' not found."
                plat.is_enabled = not plat.is_enabled
                new_state = plat.is_enabled
                session.commit()
                return new_state, None
        except Exception as e:
            return False, f"Error toggling platform: {e}"

    def get_platform_config(self, platform_name: str) -> Dict[str, Any]:
        """Returns unified configuration parameters for a platform and its default account."""
        with get_db_session(self._session_factory) as session:
            repo = PlatformRepository(session)
            plat = repo.get_platform_by_name(platform_name)
            if not plat:
                self.seed_default_platforms()
                plat = repo.get_platform_by_name(platform_name)

            if not plat:
                return {}

            account = repo.get_account(platform_name)
            extra = (account.extra_settings if account else {}) or {}

            return {
                "name": plat.name,
                "display_name": plat.display_name,
                "description": plat.description,
                "is_enabled": plat.is_enabled,
                "status": account.status if account else "READY",
                "last_run_at": account.last_run_at if account else None,
                "default_location": account.default_location if account else "India",
                "experience_years": account.experience_years if account else 5,
                "max_applications": account.max_applications if account else 75,
                "daily_application_goal": getattr(account, "daily_application_goal", 50) if account else 50,
                "max_pages_per_search": extra.get("max_pages_per_search", 5),
                "consecutive_skips_limit": extra.get("consecutive_skips_limit", 20),
                "sleep_duration_minutes": extra.get("sleep_duration_minutes", 10),
                "sleep_mode_enabled": extra.get("sleep_mode_enabled", True),
                "apply_mode": account.apply_mode if account else "EASY_APPLY_ONLY",
                "pause_before_submit": account.pause_before_submit if account else False,
                "stealth_mode": account.stealth_mode if account else True,
                "safe_mode": account.safe_mode if account else True,
                "extra_settings": extra,
            }

    def save_platform_config(
        self,
        platform_name: str,
        display_name: Optional[str] = None,
        default_location: Optional[str] = None,
        experience_years: Optional[int] = None,
        max_applications: Optional[int] = None,
        daily_application_goal: Optional[int] = None,
        apply_mode: Optional[str] = None,
        pause_before_submit: Optional[bool] = None,
        stealth_mode: Optional[bool] = None,
        safe_mode: Optional[bool] = None,
        is_enabled: Optional[bool] = None,
        max_pages_per_search: Optional[int] = None,
        consecutive_skips_limit: Optional[int] = None,
        sleep_duration_minutes: Optional[int] = None,
        sleep_mode_enabled: Optional[bool] = None,
        extra_settings: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Updates runtime platform account execution configuration."""
        try:
            with get_db_session(self._session_factory) as session:
                repo = PlatformRepository(session)
                plat = repo.get_platform_by_name(platform_name)
                if not plat:
                    return False, f"Platform '{platform_name}' not found."

                account = repo.get_account(platform_name)
                if not account:
                    account = repo.save_account(
                        platform_name=platform_name,
                        display_name=plat.display_name,
                    )

                if is_enabled is not None:
                    plat.is_enabled = bool(is_enabled)
                if display_name:
                    plat.display_name = display_name
                if default_location is not None:
                    account.default_location = default_location.strip()
                if experience_years is not None:
                    if experience_years < 0 and experience_years != -1:
                        return False, "Experience years cannot be negative (use -1 to ignore)."
                    account.experience_years = experience_years
                if max_applications is not None:
                    if max_applications <= 0:
                        return False, "Maximum applications must be greater than 0."
                    account.max_applications = max_applications
                if daily_application_goal is not None:
                    if daily_application_goal <= 0:
                        return False, "Daily application goal must be greater than 0."
                    account.daily_application_goal = daily_application_goal
                if apply_mode is not None:
                    account.apply_mode = apply_mode
                if pause_before_submit is not None:
                    account.pause_before_submit = bool(pause_before_submit)
                if stealth_mode is not None:
                    account.stealth_mode = bool(stealth_mode)
                if safe_mode is not None:
                    account.safe_mode = bool(safe_mode)

                if max_pages_per_search is not None or consecutive_skips_limit is not None or sleep_duration_minutes is not None or sleep_mode_enabled is not None or extra_settings is not None:
                    curr_extra = dict(account.extra_settings or {})
                    if max_pages_per_search is not None:
                        curr_extra["max_pages_per_search"] = max(1, int(max_pages_per_search))
                    if consecutive_skips_limit is not None:
                        curr_extra["consecutive_skips_limit"] = max(1, int(consecutive_skips_limit))
                    if sleep_duration_minutes is not None:
                        curr_extra["sleep_duration_minutes"] = max(0, int(sleep_duration_minutes))
                    if sleep_mode_enabled is not None:
                        curr_extra["sleep_mode_enabled"] = bool(sleep_mode_enabled)
                    if extra_settings:
                        curr_extra.update(extra_settings)
                    account.extra_settings = curr_extra
                    flag_modified(account, "extra_settings")

                session.commit()

            # Synchronize daily goal and switch limits to profile.json if present (skip in test mode)
            if not self.is_test and os.environ.get("TESTING") != "1":
                try:
                    import json
                    from pathlib import Path
                    profile_path = Path(__file__).resolve().parent.parent.parent / "config" / "profile.json"
                    if profile_path.exists():
                        with open(profile_path, "r", encoding="utf-8") as f:
                            p_data = json.load(f)
                        p_key = platform_name.strip().lower()
                        if "platforms" in p_data and p_key in p_data["platforms"]:
                            if max_applications is not None:
                                p_data["platforms"][p_key]["switch_number"] = max_applications
                            if daily_application_goal is not None:
                                p_data["platforms"][p_key]["daily_application_goal"] = daily_application_goal
                            if pause_before_submit is not None:
                                p_data["platforms"][p_key]["pause_before_submit"] = bool(pause_before_submit)
                            if experience_years is not None:
                                p_data["platforms"][p_key]["experience_years"] = experience_years
                            if default_location is not None:
                                p_data["platforms"][p_key]["search_location"] = default_location.strip()
                            if apply_mode is not None:
                                is_easy = "direct" in apply_mode.lower() or "easy" in apply_mode.lower()
                                p_data["platforms"][p_key]["apply_mode"] = "direct_only" if is_easy else "all"
                                p_data["platforms"][p_key]["easy_apply_only"] = is_easy
                            if stealth_mode is not None:
                                p_data["platforms"][p_key]["stealth_mode"] = bool(stealth_mode)
                            if max_pages_per_search is not None:
                                p_data["platforms"][p_key]["max_pages_per_search"] = max_pages_per_search
                            if consecutive_skips_limit is not None:
                                p_data["platforms"][p_key]["consecutive_skips_limit"] = consecutive_skips_limit
                            if sleep_duration_minutes is not None:
                                p_data["platforms"][p_key]["sleep_duration_minutes"] = max(0, int(sleep_duration_minutes))
                            if sleep_mode_enabled is not None:
                                p_data["platforms"][p_key]["sleep_mode_enabled"] = bool(sleep_mode_enabled)
                            if extra_settings:
                                p_data["platforms"][p_key].update(extra_settings)
                            with open(profile_path, "w", encoding="utf-8") as f:
                                json.dump(p_data, f, indent=2, ensure_ascii=False)
                            try:
                                from modules.config_loader import load_profile
                                load_profile(force_reload=True)
                            except Exception:
                                pass
                except Exception:
                    pass

            return True, None
        except Exception as e:
            return False, f"Error saving platform config: {e}"

    def get_search_config(self, platform_name: str) -> Dict[str, Any]:
        """Retrieves search queries, filters, cycle controls, and skip keywords for a platform."""
        cfg = self.get_platform_config(platform_name)
        extra = cfg.get("extra_settings", {}) or {}
        return {
            "platform_name": platform_name,
            "search_location": cfg.get("default_location", "India"),
            "experience_years": cfg.get("experience_years", 5),
            "search_terms": extra.get("search_terms", []),
            "date_posted": extra.get("date_posted", "Past week"),
            "max_pages_per_search": extra.get("max_pages_per_search", 3),
            "consecutive_skips_limit": extra.get("consecutive_skips_limit", 10),
            "bad_words": extra.get("bad_words", []),
            "negative_title_words": extra.get("negative_title_words", []),
            "easy_apply_only": cfg.get("apply_mode", "EASY_APPLY_ONLY") == "EASY_APPLY_ONLY",
            "switch_number": cfg.get("max_applications", 30),
            "daily_application_goal": cfg.get("daily_application_goal", 50),
            # Continuous Cycle Automation parameters
            "run_non_stop": extra.get("run_non_stop", False),
            "cycle_date_posted": extra.get("cycle_date_posted", True),
            "alternate_sortby": extra.get("alternate_sortby", True),
            "stop_date_cycle_at_24hr": extra.get("stop_date_cycle_at_24hr", True),
            "sleep_duration_minutes": extra.get("sleep_duration_minutes", 10),
            "sleep_mode_enabled": extra.get("sleep_mode_enabled", True),
        }

    def save_search_config(
        self,
        platform_name: str,
        search_terms: List[str],
        search_location: str,
        experience_years: int = 5,
        date_posted: str = "Past week",
        easy_apply_only: bool = True,
        max_pages_per_search: int = 3,
        switch_number: int = 30,
        consecutive_skips_limit: int = 10,
        bad_words: Optional[List[str]] = None,
        negative_title_words: Optional[List[str]] = None,
        run_non_stop: bool = False,
        cycle_date_posted: bool = True,
        alternate_sortby: bool = True,
        stop_date_cycle_at_24hr: bool = True,
        sync_to_all_platforms: bool = False,
        daily_application_goal: Optional[int] = None,
        sleep_duration_minutes: Optional[int] = None,
        sleep_mode_enabled: Optional[bool] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Saves search terms, filters, cycle options, and skip parameters for a platform or all platforms."""
        clean_terms = [t.strip() for t in search_terms if t.strip()]
        if not clean_terms:
            return False, "At least one search keyword is required."

        clean_bad_words = [w.strip() for w in (bad_words or []) if w.strip()]
        clean_negative_words = [
            w.strip().lower() for w in (negative_title_words or []) if w.strip()
        ]

        target_platforms = (
            ["linkedin", "naukri", "indeed", "glassdoor", "foundit"]
            if sync_to_all_platforms
            else [platform_name.strip().lower()]
        )

        try:
            with get_db_session(self._session_factory) as session:
                repo = PlatformRepository(session)
                for plat_key in target_platforms:
                    account = repo.get_account(plat_key)
                    if not account:
                        # Ensure platform and account exist
                        plat_obj = repo.get_or_create_platform(
                            name=plat_key,
                            display_name=plat_key.title(),
                        )
                        account = repo.save_account(
                            platform_name=plat_key,
                            display_name=plat_key.title(),
                            default_location=search_location.strip(),
                            experience_years=experience_years,
                            max_applications=switch_number,
                            daily_application_goal=daily_application_goal if daily_application_goal is not None else 50,
                            apply_mode="EASY_APPLY_ONLY" if easy_apply_only else "ALL",
                        )

                    account.default_location = search_location.strip()
                    account.experience_years = experience_years
                    account.max_applications = switch_number
                    if daily_application_goal is not None:
                        account.daily_application_goal = daily_application_goal
                    account.apply_mode = "EASY_APPLY_ONLY" if easy_apply_only else "ALL"

                    current_extra = dict(account.extra_settings or {})
                    current_extra["search_terms"] = clean_terms
                    current_extra["date_posted"] = date_posted
                    current_extra["max_pages_per_search"] = max_pages_per_search
                    current_extra["consecutive_skips_limit"] = consecutive_skips_limit
                    current_extra["bad_words"] = clean_bad_words
                    current_extra["negative_title_words"] = clean_negative_words
                    current_extra["run_non_stop"] = run_non_stop
                    current_extra["cycle_date_posted"] = cycle_date_posted
                    current_extra["alternate_sortby"] = alternate_sortby
                    current_extra["stop_date_cycle_at_24hr"] = stop_date_cycle_at_24hr
                    if sleep_duration_minutes is not None:
                        current_extra["sleep_duration_minutes"] = max(0, int(sleep_duration_minutes))
                    if sleep_mode_enabled is not None:
                        current_extra["sleep_mode_enabled"] = bool(sleep_mode_enabled)

                    account.extra_settings = current_extra
                    flag_modified(account, "extra_settings")

                session.commit()

            # Synchronize to config/profile.json and flush cache (skip in test mode)
            if not self.is_test and os.environ.get("TESTING") != "1":
                for plat_key in target_platforms:
                    self._sync_search_to_profile_json(
                        platform_name=plat_key,
                        search_terms=clean_terms,
                        search_location=search_location,
                        switch_number=switch_number,
                        experience_years=experience_years,
                        easy_apply_only=easy_apply_only,
                        date_posted=date_posted,
                        max_pages_per_search=max_pages_per_search,
                        consecutive_skips_limit=consecutive_skips_limit,
                        bad_words=clean_bad_words,
                        negative_title_words=clean_negative_words,
                        run_non_stop=run_non_stop,
                        cycle_date_posted=cycle_date_posted,
                        alternate_sortby=alternate_sortby,
                        stop_date_cycle_at_24hr=stop_date_cycle_at_24hr,
                        daily_application_goal=daily_application_goal,
                        sleep_duration_minutes=sleep_duration_minutes,
                        sleep_mode_enabled=sleep_mode_enabled,
                    )
            return True, None
        except Exception as e:
            return False, f"Error saving search config: {e}"

    def _sync_search_to_profile_json(
        self,
        platform_name: str,
        search_terms: List[str],
        search_location: str,
        switch_number: int,
        experience_years: int,
        easy_apply_only: bool,
        date_posted: str,
        max_pages_per_search: int = 3,
        consecutive_skips_limit: int = 10,
        bad_words: Optional[List[str]] = None,
        negative_title_words: Optional[List[str]] = None,
        run_non_stop: bool = False,
        cycle_date_posted: bool = True,
        alternate_sortby: bool = True,
        stop_date_cycle_at_24hr: bool = True,
        daily_application_goal: Optional[int] = None,
        sleep_duration_minutes: Optional[int] = None,
        sleep_mode_enabled: Optional[bool] = None,
    ) -> None:
        """Synchronizes updated platform search criteria into config/profile.json."""
        if self.is_test or os.environ.get("TESTING") == "1":
            return

        try:
            import json
            import logging
            from pathlib import Path

            profile_path = Path(__file__).resolve().parent.parent.parent / "config" / "profile.json"
            if not profile_path.exists():
                return

            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "platforms" not in data or not isinstance(data["platforms"], dict):
                data["platforms"] = {}

            p_key = platform_name.strip().lower()
            if p_key not in data["platforms"] or not isinstance(data["platforms"][p_key], dict):
                data["platforms"][p_key] = {}

            data["platforms"][p_key]["search_terms"] = search_terms
            data["platforms"][p_key]["search_location"] = search_location
            data["platforms"][p_key]["switch_number"] = switch_number
            if daily_application_goal is not None:
                data["platforms"][p_key]["daily_application_goal"] = daily_application_goal
            data["platforms"][p_key]["experience_years"] = experience_years
            data["platforms"][p_key]["current_experience"] = experience_years
            data["platforms"][p_key]["easy_apply_only"] = easy_apply_only
            data["platforms"][p_key]["apply_mode"] = "direct_only" if easy_apply_only else "all"
            data["platforms"][p_key]["date_posted"] = date_posted
            data["platforms"][p_key]["max_pages_per_search"] = max_pages_per_search
            data["platforms"][p_key]["consecutive_skips_limit"] = consecutive_skips_limit

            if bad_words is not None:
                data["platforms"][p_key]["bad_words"] = bad_words
            if negative_title_words is not None:
                data["platforms"][p_key]["negative_title_words"] = negative_title_words

            # Cycle controls
            data["platforms"][p_key]["run_non_stop"] = run_non_stop
            data["platforms"][p_key]["cycle_date_posted"] = cycle_date_posted
            data["platforms"][p_key]["alternate_sortby"] = alternate_sortby
            data["platforms"][p_key]["stop_date_cycle_at_24hr"] = stop_date_cycle_at_24hr
            if sleep_duration_minutes is not None:
                data["platforms"][p_key]["sleep_duration_minutes"] = max(0, int(sleep_duration_minutes))
            if sleep_mode_enabled is not None:
                data["platforms"][p_key]["sleep_mode_enabled"] = bool(sleep_mode_enabled)

            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Invalidate config cache
            try:
                import modules.config_loader as cfg_ldr
                cfg_ldr._PROFILE_CACHE = None
            except Exception:
                pass
        except Exception as exc:
            logger = logging.getLogger(__name__)
            logger.warning("Failed to synchronize search config to profile.json: %s", exc)

    def sync_profile_json_to_db(self) -> None:
        """Startup synchronization between SQLite DB and config/profile.json.

        The SQLite DB is the undisputed single source of truth:
        - If the DB already has search_terms configured for a platform, the DB is PRESERVED.
          config/profile.json is synchronized from DB to ensure consistency.
        - If the DB has NO search_terms for a platform (e.g. unseeded fresh install),
          search criteria are seeded from profile.json into the DB.
        """
        if self.is_test or os.environ.get("TESTING") == "1":
            return

        import json
        import logging
        from pathlib import Path

        logger = logging.getLogger(__name__)
        profile_path = Path(__file__).resolve().parent.parent.parent / "config" / "profile.json"
        if not profile_path.exists():
            return

        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            logger.warning("sync_profile_json_to_db: cannot read profile.json: %s", exc)
            return

        platforms_cfg = data.get("platforms", {})
        if not platforms_cfg:
            return

        for plat_key in ["linkedin", "naukri", "indeed", "glassdoor", "foundit"]:
            plat_cfg = platforms_cfg.get(plat_key, {})
            file_terms = plat_cfg.get("search_terms", [])
            db_cfg = self.get_search_config(plat_key)
            db_terms = db_cfg.get("search_terms", [])

            if db_terms:
                # DB has search terms -> DB is authoritative!
                # Ensure profile.json stays aligned with DB
                if file_terms != db_terms:
                    logger.info(
                        "Startup sync: DB is master for %s. Updating profile.json (%s -> %s).",
                        plat_key, file_terms, db_terms,
                    )
                    self._sync_search_to_profile_json(
                        platform_name=plat_key,
                        search_terms=db_terms,
                        search_location=db_cfg.get("search_location", "India"),
                        switch_number=db_cfg.get("switch_number", 30),
                        experience_years=db_cfg.get("experience_years", 5),
                        easy_apply_only=db_cfg.get("easy_apply_only", True),
                        date_posted=db_cfg.get("date_posted", "Past week"),
                        max_pages_per_search=db_cfg.get("max_pages_per_search", 3),
                        consecutive_skips_limit=db_cfg.get("consecutive_skips_limit", 10),
                        bad_words=db_cfg.get("bad_words", []),
                        negative_title_words=db_cfg.get("negative_title_words", []),
                        run_non_stop=db_cfg.get("run_non_stop", False),
                        cycle_date_posted=db_cfg.get("cycle_date_posted", True),
                        alternate_sortby=db_cfg.get("alternate_sortby", True),
                        stop_date_cycle_at_24hr=db_cfg.get("stop_date_cycle_at_24hr", True),
                        daily_application_goal=db_cfg.get("daily_application_goal", 50),
                    )
            elif file_terms:
                # DB has NO search terms -> seed DB from profile.json
                logger.info(
                    "Startup sync: seeding empty DB for %s from profile.json (%s).",
                    plat_key, file_terms,
                )
                self.save_search_config(
                    platform_name=plat_key,
                    search_terms=file_terms,
                    search_location=plat_cfg.get("search_location", db_cfg.get("search_location", "India")),
                    experience_years=plat_cfg.get("experience_years", db_cfg.get("experience_years", 5)),
                    date_posted=plat_cfg.get("date_posted", db_cfg.get("date_posted", "Past week")),
                    easy_apply_only=plat_cfg.get("easy_apply_only", db_cfg.get("easy_apply_only", True)),
                    max_pages_per_search=plat_cfg.get("max_pages_per_search", db_cfg.get("max_pages_per_search", 3)),
                    switch_number=plat_cfg.get("switch_number", db_cfg.get("switch_number", 30)),
                    consecutive_skips_limit=plat_cfg.get("consecutive_skips_limit", db_cfg.get("consecutive_skips_limit", 10)),
                    bad_words=plat_cfg.get("bad_words", db_cfg.get("bad_words", [])),
                    negative_title_words=plat_cfg.get("negative_title_words", db_cfg.get("negative_title_words", [])),
                    run_non_stop=plat_cfg.get("run_non_stop", False),
                    cycle_date_posted=plat_cfg.get("cycle_date_posted", True),
                    alternate_sortby=plat_cfg.get("alternate_sortby", True),
                    stop_date_cycle_at_24hr=plat_cfg.get("stop_date_cycle_at_24hr", True),
                    daily_application_goal=plat_cfg.get("daily_application_goal", db_cfg.get("daily_application_goal", 50)),
                )

