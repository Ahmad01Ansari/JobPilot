"""Workday Account Service managing multi-tenant company account registration and lookup."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from sqlalchemy.orm import sessionmaker

from app.db.session import SessionLocal, get_db_session
from app.repositories.settings_repository import SettingsRepository

logger = logging.getLogger(__name__)


class WorkdayAccountService:
    """Manages company-level Workday account credentials and portal registrations."""

    SETTING_KEY = "workday.company_accounts"
    SETTING_CATEGORY = "workday"

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal

    @staticmethod
    def is_workday_portal(url: str, html_snippet: str = "") -> bool:
        """Determines if the given URL or page content belongs to a Workday ATS portal."""
        if not url:
            return False
        clean_url = url.lower()
        if any(w in clean_url for w in ["myworkdayjobs.com", "myworkday.com", ".workday.com"]):
            return True
        if html_snippet:
            clean_html = html_snippet.lower()
            if "myworkdayjobs" in clean_html or "data-automation-id=\"adventurebutton\"" in clean_html:
                return True
        return False

    @staticmethod
    def extract_tenant(url: str) -> Optional[str]:
        """Extracts the tenant identifier from a Workday portal URL.

        Example:
            'https://tranetechnologies.wd12.myworkdayjobs.com/en-US/Trane_Technologies_Careers/job/...'
            -> 'tranetechnologies'
        """
        if not url:
            return None
        try:
            parsed = urlparse(url)
            hostname = (parsed.hostname or "").lower()
            if "myworkdayjobs.com" in hostname or "myworkday.com" in hostname:
                parts = hostname.split(".")
                if parts and parts[0]:
                    return parts[0].strip()
            # Fallback: check path segments or netloc
            if hostname:
                return hostname.split(".")[0].strip()
        except Exception as e:
            logger.debug("Failed to extract tenant from url '%s': %s", url, e)
        return None

    @staticmethod
    def extract_company_display_name(url: str, raw_company: Optional[str] = None) -> str:
        """Derives a human-readable company name from URL or fallback string."""
        if raw_company and raw_company.strip():
            return raw_company.strip()
        tenant = WorkdayAccountService.extract_tenant(url)
        if tenant:
            cleaned = tenant.replace("-", " ").replace("_", " ")
            return cleaned.title()
        return "Workday Employer"

    def list_accounts(self) -> List[Dict[str, Any]]:
        """Returns all registered company accounts on Workday."""
        with get_db_session(self._session_factory) as session:
            repo = SettingsRepository(session)
            raw = repo.get(self.SETTING_KEY, default=[])
            if isinstance(raw, list):
                return raw
            return []

    def has_account(self, url: str, company_name: Optional[str] = None) -> bool:
        """Checks if an account exists in the database for the given portal URL or company."""
        tenant = self.extract_tenant(url)
        company_clean = (company_name or "").strip().lower()

        accounts = self.list_accounts()
        for acct in accounts:
            if tenant and acct.get("tenant") == tenant:
                return True
            if company_clean and acct.get("company_name", "").strip().lower() == company_clean:
                return True
        return False

    def get_account(self, url: str, company_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves account details for a specific Workday portal."""
        tenant = self.extract_tenant(url)
        company_clean = (company_name or "").strip().lower()

        accounts = self.list_accounts()
        for acct in accounts:
            if tenant and acct.get("tenant") == tenant:
                return acct
            if company_clean and acct.get("company_name", "").strip().lower() == company_clean:
                return acct
        return None

    def record_account(
        self,
        url: str,
        company_name: Optional[str] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Saves or updates a company account registration record."""
        tenant = self.extract_tenant(url) or "unknown"
        display_name = self.extract_company_display_name(url, company_name)
        now_iso = datetime.now(timezone.utc).isoformat()

        with get_db_session(self._session_factory) as session:
            repo = SettingsRepository(session)
            accounts: List[Dict[str, Any]] = repo.get(self.SETTING_KEY, default=[])
            if not isinstance(accounts, list):
                accounts = []

            found = False
            for acct in accounts:
                if acct.get("tenant") == tenant or (company_name and acct.get("company_name") == display_name):
                    acct["last_used_at"] = now_iso
                    if username and not acct.get("username"):
                        acct["username"] = username
                    if company_name and not acct.get("company_name"):
                        acct["company_name"] = display_name
                    found = True
                    break

            if not found:
                record = {
                    "tenant": tenant,
                    "company_name": display_name,
                    "portal_url": url,
                    "username": username or "",
                    "created_at": now_iso,
                    "last_used_at": now_iso,
                    "status": "ACTIVE",
                }
                accounts.append(record)

            repo.set(self.SETTING_KEY, accounts, category=self.SETTING_CATEGORY)
            session.commit()
            logger.info("Recorded Workday company account for '%s' (tenant=%s)", display_name, tenant)

            return next(
                (a for a in accounts if a.get("tenant") == tenant),
                {"tenant": tenant, "company_name": display_name},
            )

    def delete_account(self, tenant_or_key: str) -> bool:
        """Removes a company registration record by tenant or company name."""
        target = tenant_or_key.strip().lower()
        with get_db_session(self._session_factory) as session:
            repo = SettingsRepository(session)
            accounts = repo.get(self.SETTING_KEY, default=[])
            if not isinstance(accounts, list):
                return False

            initial_len = len(accounts)
            updated = [
                a for a in accounts
                if a.get("tenant", "").lower() != target and a.get("company_name", "").lower() != target
            ]

            if len(updated) < initial_len:
                repo.set(self.SETTING_KEY, updated, category=self.SETTING_CATEGORY)
                session.commit()
                logger.info("Removed Workday company account for '%s'", tenant_or_key)
                return True

        return False
