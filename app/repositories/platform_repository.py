"""Repository for Platform and PlatformAccount settings management."""

from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import Platform, PlatformAccount
from app.repositories.base import BaseRepository


class PlatformRepository(BaseRepository):
    """Data access operations for platforms and platform configurations."""

    def get_platform_by_name(self, name: str) -> Optional[Platform]:
        """Fetches a platform by unique key (e.g. 'linkedin', 'naukri')."""
        return self.session.execute(
            select(Platform).where(Platform.name == name.strip().lower())
        ).scalar_one_or_none()

    def get_or_create_platform(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None,
    ) -> Platform:
        """Finds or creates a registered platform."""
        existing = self.get_platform_by_name(name)
        if existing:
            return existing

        plat = Platform(
            name=name.strip().lower(),
            display_name=display_name.strip(),
            is_enabled=True,
            description=description,
        )
        self.session.add(plat)
        self.session.flush()
        return plat

    def get_account(
        self,
        platform_name: str,
        account_name: str = "Default Profile",
    ) -> Optional[PlatformAccount]:
        """Fetches a platform account by platform name and account identifier."""
        stmt = (
            select(PlatformAccount)
            .join(Platform)
            .where(
                Platform.name == platform_name.strip().lower(),
                PlatformAccount.account_name == account_name.strip(),
            )
            .options(joinedload(PlatformAccount.platform))
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def save_account(
        self,
        platform_name: str,
        display_name: str,
        account_name: str = "Default Profile",
        default_location: Optional[str] = None,
        experience_years: Optional[int] = None,
        max_applications: int = 30,
        daily_application_goal: int = 50,
        apply_mode: str = "EASY_APPLY_ONLY",
        pause_before_submit: bool = True,
        stealth_mode: bool = True,
        safe_mode: bool = True,
        extra_settings: Optional[Dict[str, Any]] = None,
    ) -> PlatformAccount:
        """Creates or updates platform configuration parameters without storing credentials."""
        platform = self.get_or_create_platform(platform_name, display_name)
        account = self.get_account(platform_name, account_name)

        if account:
            account.default_location = default_location
            account.experience_years = experience_years
            account.max_applications = max_applications
            account.daily_application_goal = daily_application_goal
            account.apply_mode = apply_mode
            account.pause_before_submit = pause_before_submit
            account.stealth_mode = stealth_mode
            account.safe_mode = safe_mode
            if extra_settings:
                account.extra_settings = extra_settings
        else:
            account = PlatformAccount(
                platform_id=platform.id,
                account_name=account_name.strip(),
                default_location=default_location,
                experience_years=experience_years,
                max_applications=max_applications,
                daily_application_goal=daily_application_goal,
                apply_mode=apply_mode,
                pause_before_submit=pause_before_submit,
                stealth_mode=stealth_mode,
                safe_mode=safe_mode,
                extra_settings=extra_settings,
            )
            self.session.add(account)

        self.session.flush()
        return account

    def list_platforms(self) -> List[Platform]:
        """Lists all registered platforms with their configured accounts."""
        stmt = select(Platform).options(joinedload(Platform.accounts)).order_by(Platform.is_enabled.desc(), Platform.id.asc())
        return list(self.session.execute(stmt).unique().scalars().all())
