"""Typed Data Transfer Objects (DTOs) for repository inputs."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class JobCreateDTO:
    """Input parameters for creating or updating a Job entity."""

    platform: str
    company_raw: str
    title: str
    source_url: str
    external_job_id: Optional[str] = None
    location: Optional[str] = None
    work_style: Optional[str] = None
    experience_text: Optional[str] = None
    required_experience_min: Optional[int] = None
    required_experience_max: Optional[int] = None
    salary_text: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_period: str = "YEAR"
    salary_currency: str = "INR"
    apply_type: str = "DIRECT"
    application_method: str = "EASY_APPLY"
    application_url: Optional[str] = None
    description: Optional[str] = None
    raw_metadata: Optional[Dict[str, Any]] = None
    company_id: Optional[int] = None


@dataclass
class ProfileUpdateDTO:
    """Input parameters for updating Candidate Personal Profile."""

    first_name: str
    last_name: str
    current_city: str
    middle_name: Optional[str] = None
    state: Optional[str] = None
    country: str = "India"
    zipcode: Optional[str] = None
    address: Optional[str] = None
    preferred_locations: Optional[List[str]] = None
    willing_to_relocate: bool = False


@dataclass
class ProfessionalProfileUpdateDTO:
    """Input parameters for updating Candidate Professional Profile."""

    current_title: str
    current_employer: Optional[str] = None
    years_of_experience: float = 0.0
    current_ctc: Optional[int] = None
    expected_ctc: Optional[int] = None
    notice_period_days: int = 30
    skills: Optional[List[str]] = None
    primary_skills: Optional[List[str]] = None
    secondary_skills: Optional[List[str]] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    cover_letter: Optional[str] = None


@dataclass
class ApplicationCreateDTO:
    """Input parameters for creating an Application record."""

    job_id: int
    user_id: Optional[int] = None
    resume_id: Optional[int] = None
    contact_id: Optional[int] = None
    status: str = "APPLYING"
    automation_status: Optional[str] = None
    application_type: str = "EASY_APPLY"
    external_job_link: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class QnACreateDTO:
    """Input parameters for creating or upserting a Screening Q&A entry."""

    question_text: str
    answer_text: str
    category: str = "general"
    source: str = "PROFILE"
    confidence: float = 1.0
    validation_status: Optional[str] = None  # If None, determined by provenance rules
    platform: Optional[str] = None
    answer_type: str = "text"
