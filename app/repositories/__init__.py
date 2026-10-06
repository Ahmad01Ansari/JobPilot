"""Public API for the JobPilot Repository Layer."""

from app.repositories.application_repository import (
    BLOCKING_APPLICATION_STATES,
    ApplicationRepository,
)
from app.repositories.base import BaseRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.dto import (
    ApplicationCreateDTO,
    JobCreateDTO,
    ProfessionalProfileUpdateDTO,
    ProfileUpdateDTO,
    QnACreateDTO,
)
from app.repositories.job_evaluation_repo import (
    JobEvaluationRepository,
    JobQualificationRepository,
)
from app.repositories.job_repository import JobRepository
from app.repositories.platform_repository import PlatformRepository
from app.repositories.qna_repository import QnARepository, normalize_question_text
from app.repositories.recruitment_repository import RecruitmentRepository
from app.repositories.resume_repository import ResumeRepository
from app.repositories.settings_repository import SettingsRepository
from app.repositories.user_repository import UserRepository
from app.repositories.validators import (
    ALLOWED_TRANSITIONS,
    normalize_company_name,
    validate_status_transition,
)

__all__ = [
    "BaseRepository",
    # DTOs
    "JobCreateDTO",
    "ProfileUpdateDTO",
    "ProfessionalProfileUpdateDTO",
    "ApplicationCreateDTO",
    "QnACreateDTO",
    # Validators & Normalizers
    "normalize_company_name",
    "normalize_question_text",
    "validate_status_transition",
    "ALLOWED_TRANSITIONS",
    "BLOCKING_APPLICATION_STATES",
    # Repositories
    "CompanyRepository",
    "ContactRepository",
    "JobRepository",
    "JobEvaluationRepository",
    "JobQualificationRepository",
    "ApplicationRepository",
    "RecruitmentRepository",
    "UserRepository",
    "ResumeRepository",
    "PlatformRepository",
    "QnARepository",
    "SettingsRepository",
]
