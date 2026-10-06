"""Repository for Resume metadata and default selection management."""

from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Resume, calculate_file_sha256
from app.repositories.base import BaseRepository


class ResumeRepository(BaseRepository):
    """Data access operations for resumes."""

    def get_by_id(self, resume_id: int) -> Optional[Resume]:
        """Fetches a resume by internal primary key."""
        return self.session.execute(
            select(Resume).where(Resume.id == resume_id)
        ).scalar_one_or_none()

    def get_default_resume(self, user_id: int) -> Optional[Resume]:
        """Fetches the default resume for a user."""
        stmt = select(Resume).where(
            Resume.user_id == user_id,
            Resume.is_default == True,  # noqa: E712
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def set_default_resume(self, resume_id: int, user_id: int) -> Resume:
        """Atomically unsets existing default resumes and designates the target resume as default."""
        target = self.get_by_id(resume_id)
        if not target or target.user_id != user_id:
            raise ValueError(f"Resume {resume_id} not found for user {user_id}.")

        # Unset all default flags for this user
        self.session.execute(
            update(Resume)
            .where(Resume.user_id == user_id)
            .values(is_default=False)
        )

        target.is_default = True
        self.session.flush()
        return target

    def add_resume(
        self,
        user_id: int,
        name: str,
        file_path: str,
        role_target: Optional[str] = None,
        is_default: bool = False,
        version: str = "1.0",
        lineage_id: Optional[str] = None,
        notes: Optional[str] = None,
        parsed_metadata: Optional[dict] = None,
    ) -> Resume:
        """Adds a new resume record. If is_default is True, unsets other defaults for user."""
        file_hash = calculate_file_sha256(file_path)

        if is_default:
            self.session.execute(
                update(Resume)
                .where(Resume.user_id == user_id)
                .values(is_default=False)
            )

        import uuid
        effective_lineage = lineage_id or uuid.uuid4().hex

        resume = Resume(
            user_id=user_id,
            name=name.strip(),
            file_path=file_path.strip(),
            file_hash=file_hash,
            role_target=role_target.strip() if role_target else None,
            is_default=is_default,
            version=version,
            lineage_id=effective_lineage,
            is_archived=False,
            notes=notes.strip() if notes else None,
            parsed_metadata=parsed_metadata,
        )
        self.session.add(resume)
        self.session.flush()
        return resume

    def list_by_user(
        self,
        user_id: int,
        include_archived: bool = False,
        role: Optional[str] = None,
    ) -> List[Resume]:
        """Lists resumes uploaded by a user, with optional archive and role filtering."""
        stmt = select(Resume).where(Resume.user_id == user_id)
        if not include_archived:
            stmt = stmt.where(Resume.is_archived == False)  # noqa: E712
        if role and role.strip() and role.strip().lower() != "all":
            if role.strip().lower() == "general":
                stmt = stmt.where((Resume.role_target == None) | (Resume.role_target == "General"))  # noqa: E711
            else:
                stmt = stmt.where(Resume.role_target.ilike(f"%{role.strip()}%"))

        stmt = stmt.order_by(Resume.is_default.desc(), Resume.updated_at.desc())
        return list(self.session.execute(stmt).scalars().all())

    def get_lineage_resumes(self, lineage_id: str, user_id: int) -> List[Resume]:
        """Returns all resume revisions belonging to a lineage ordered by version/creation."""
        stmt = (
            select(Resume)
            .where(Resume.user_id == user_id, Resume.lineage_id == lineage_id)
            .order_by(Resume.created_at.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def find_by_hash_for_user(self, user_id: int, file_hash: str) -> Optional[Resume]:
        """Looks up an existing resume by SHA-256 file hash for a user to detect duplicates."""
        stmt = select(Resume).where(
            Resume.user_id == user_id,
            Resume.file_hash == file_hash,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def is_referenced_by_application(self, resume_id: int) -> bool:
        """Checks if any application references this resume."""
        from app.db.models import Application

        stmt = select(Application.id).where(Application.resume_id == resume_id).limit(1)
        return self.session.execute(stmt).scalar_one_or_none() is not None

    def promote_next_default(
        self,
        user_id: int,
        preferred_role: Optional[str] = None,
    ) -> Optional[Resume]:
        """Promotes next default resume following strict deterministic precedence:
        1. Active resume in same target role (most recently updated).
        2. Active General resume (most recently updated).
        3. Any active resume (most recently updated).
        4. If no active resumes remain, returns None.
        """
        current_default = self.get_default_resume(user_id)
        if current_default and not current_default.is_archived:
            return current_default

        # 1. Same target role first
        if preferred_role and preferred_role.strip():
            stmt1 = (
                select(Resume)
                .where(
                    Resume.user_id == user_id,
                    Resume.is_archived == False,  # noqa: E712
                    Resume.role_target.ilike(preferred_role.strip()),
                )
                .order_by(Resume.updated_at.desc())
                .limit(1)
            )
            cand1 = self.session.execute(stmt1).scalar_one_or_none()
            if cand1:
                cand1.is_default = True
                self.session.flush()
                return cand1

        # 2. General resume next
        stmt2 = (
            select(Resume)
            .where(
                Resume.user_id == user_id,
                Resume.is_archived == False,  # noqa: E712
                (Resume.role_target == None) | (Resume.role_target == "General"),  # noqa: E711
            )
            .order_by(Resume.updated_at.desc())
            .limit(1)
        )
        cand2 = self.session.execute(stmt2).scalar_one_or_none()
        if cand2:
            cand2.is_default = True
            self.session.flush()
            return cand2

        # 3. Any active resume
        stmt3 = (
            select(Resume)
            .where(
                Resume.user_id == user_id,
                Resume.is_archived == False,  # noqa: E712
            )
            .order_by(Resume.updated_at.desc())
            .limit(1)
        )
        cand3 = self.session.execute(stmt3).scalar_one_or_none()
        if cand3:
            cand3.is_default = True
            self.session.flush()
            return cand3

        return None

    def archive_resume(self, resume_id: int, user_id: int) -> Optional[Resume]:
        """Archives a resume and unsets default if active."""
        target = self.get_by_id(resume_id)
        if not target or target.user_id != user_id:
            return None

        target.is_archived = True
        self.session.flush()
        return target

    def unarchive_resume(self, resume_id: int, user_id: int) -> Optional[Resume]:
        """Restores an archived resume."""
        target = self.get_by_id(resume_id)
        if not target or target.user_id != user_id:
            return None

        target.is_archived = False
        self.session.flush()
        return target

    def delete_resume(self, resume_id: int) -> bool:
        """Deletes a resume record."""
        resume = self.get_by_id(resume_id)
        if not resume:
            return False
        self.session.delete(resume)
        self.session.flush()
        return True
