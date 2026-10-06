"""Repository for User, Profile, and ProfessionalProfile management."""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import ProfessionalProfile, Profile, User
from app.repositories.base import BaseRepository
from app.repositories.dto import ProfessionalProfileUpdateDTO, ProfileUpdateDTO


class UserRepository(BaseRepository):
    """Data access operations for candidate user profiles."""

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Fetches a user by ID."""
        return self.session.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()

    def get_profile(self, user_id: int) -> Optional[Profile]:
        """Fetches the candidate personal profile for a user."""
        return self.session.execute(
            select(Profile).where(Profile.user_id == user_id)
        ).scalar_one_or_none()

    def get_professional_profile(self, user_id: int) -> Optional[ProfessionalProfile]:
        """Fetches the candidate professional profile for a user."""
        return self.session.execute(
            select(ProfessionalProfile).where(ProfessionalProfile.user_id == user_id)
        ).scalar_one_or_none()

    def get_by_email(self, email: str) -> Optional[User]:
        """Fetches a user by email address."""
        if not email:
            return None
        return self.session.execute(
            select(User).where(User.email == email.strip().lower())
        ).scalar_one_or_none()

    def get_primary_user(self) -> Optional[User]:
        """Returns the primary active candidate user in the system."""
        stmt = (
            select(User)
            .where(User.is_active == True)  # noqa: E712
            .options(
                joinedload(User.profile),
                joinedload(User.professional_profile),
            )
            .order_by(User.id.desc())
        )
        users = self.session.execute(stmt).unique().scalars().all()
        if not users:
            return None
        # Prefer user with populated profile
        for u in users:
            if u.profile is not None:
                return u
        return users[0]

    def get_or_create_primary_user(
        self,
        name: str,
        email: str,
        phone: Optional[str] = None,
    ) -> User:
        """Finds user by email or creates a new primary candidate user."""
        existing = self.get_by_email(email)
        if existing:
            if name and existing.name != name:
                existing.name = name
            if phone and not existing.phone:
                existing.phone = phone
            self.session.flush()
            return existing

        user = User(
            name=name.strip(),
            email=email.strip().lower(),
            phone=phone.strip() if phone else None,
            is_active=True,
        )
        self.session.add(user)
        self.session.flush()
        return user

    def save_profile(self, user_id: int, dto: ProfileUpdateDTO) -> Profile:
        """Creates or updates personal profile for a user."""
        profile = self.session.execute(
            select(Profile).where(Profile.user_id == user_id)
        ).scalar_one_or_none()

        if profile:
            profile.first_name = dto.first_name.strip()
            profile.middle_name = dto.middle_name.strip() if dto.middle_name else None
            profile.last_name = dto.last_name.strip()
            profile.current_city = dto.current_city.strip()
            profile.state = dto.state.strip() if dto.state else None
            profile.country = dto.country.strip() if dto.country else "India"
            profile.zipcode = dto.zipcode.strip() if dto.zipcode else None
            profile.address = dto.address.strip() if dto.address else None
            profile.preferred_locations = dto.preferred_locations
            profile.willing_to_relocate = dto.willing_to_relocate
        else:
            profile = Profile(
                user_id=user_id,
                first_name=dto.first_name.strip(),
                middle_name=dto.middle_name.strip() if dto.middle_name else None,
                last_name=dto.last_name.strip(),
                current_city=dto.current_city.strip(),
                state=dto.state.strip() if dto.state else None,
                country=dto.country.strip() if dto.country else "India",
                zipcode=dto.zipcode.strip() if dto.zipcode else None,
                address=dto.address.strip() if dto.address else None,
                preferred_locations=dto.preferred_locations,
                willing_to_relocate=dto.willing_to_relocate,
            )
            self.session.add(profile)

        self.session.flush()
        return profile

    def save_professional_profile(
        self,
        user_id: int,
        dto: ProfessionalProfileUpdateDTO,
    ) -> ProfessionalProfile:
        """Creates or updates professional background profile for a user."""
        prof = self.session.execute(
            select(ProfessionalProfile).where(ProfessionalProfile.user_id == user_id)
        ).scalar_one_or_none()

        if prof:
            prof.current_title = dto.current_title.strip()
            prof.current_employer = dto.current_employer.strip() if dto.current_employer else None
            prof.years_of_experience = dto.years_of_experience
            prof.current_ctc = dto.current_ctc
            prof.expected_ctc = dto.expected_ctc
            prof.notice_period_days = dto.notice_period_days
            prof.skills = dto.skills
            prof.primary_skills = dto.primary_skills
            prof.secondary_skills = dto.secondary_skills
            prof.linkedin_url = dto.linkedin_url.strip() if dto.linkedin_url else None
            prof.github_url = dto.github_url.strip() if dto.github_url else None
            prof.portfolio_url = dto.portfolio_url.strip() if dto.portfolio_url else None
            prof.headline = dto.headline.strip() if dto.headline else None
            prof.summary = dto.summary
            prof.cover_letter = dto.cover_letter
        else:
            prof = ProfessionalProfile(
                user_id=user_id,
                current_title=dto.current_title.strip(),
                current_employer=dto.current_employer.strip() if dto.current_employer else None,
                years_of_experience=dto.years_of_experience,
                current_ctc=dto.current_ctc,
                expected_ctc=dto.expected_ctc,
                notice_period_days=dto.notice_period_days,
                skills=dto.skills,
                primary_skills=dto.primary_skills,
                secondary_skills=dto.secondary_skills,
                linkedin_url=dto.linkedin_url.strip() if dto.linkedin_url else None,
                github_url=dto.github_url.strip() if dto.github_url else None,
                portfolio_url=dto.portfolio_url.strip() if dto.portfolio_url else None,
                headline=dto.headline.strip() if dto.headline else None,
                summary=dto.summary,
                cover_letter=dto.cover_letter,
            )
            self.session.add(prof)

        self.session.flush()
        return prof

    # Aliases for compatibility
    update_profile = save_profile
    update_professional_profile = save_professional_profile
