'''
Normalized Job Model
Unified representation of job postings across all supported platforms (LinkedIn, Naukri, Indeed, etc.).
'''

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Literal


@dataclass
class Job:
    platform: str                                 # "linkedin", "naukri", "indeed", etc.
    job_id: str                                   # Platform-specific unique identifier
    title: str                                    # Job title
    company: str                                  # Organization / Employer name
    location: str                                 # Primary job location / city
    work_style: Optional[str] = None              # "Remote", "Hybrid", "On-site", or None
    required_experience_min: Optional[int] = None  # Lower bound of required experience (None if unspecified)
    required_experience_max: Optional[int] = None  # Upper bound of required experience (None if unspecified)
    salary_min: Optional[int] = None              # Minimum salary / CTC in annual local currency
    salary_max: Optional[int] = None              # Maximum salary / CTC in annual local currency
    salary_currency: str = "INR"                  # Currency code (default: INR)
    description: str = ""                         # Full job description / About the Job
    source_url: str = ""                          # Canonical URL to the job listing
    apply_type: Literal["DIRECT", "QUESTIONNAIRE", "EXTERNAL"] = "DIRECT"
    application_method: str = "EASY_APPLY"        # "EASY_APPLY", "COMPANY_PORTAL", "MANUAL", "UNKNOWN"
    application_url: Optional[str] = None         # Direct link to company career portal or external apply page
    posted_date: Optional[str] = None             # Posted date string / age (e.g. "Past week", "2 days ago")
    raw_metadata: Dict[str, Any] = field(default_factory=dict)  # Platform-specific raw attributes

    def __post_init__(self):
        if self.apply_type == "EXTERNAL" and self.application_method == "EASY_APPLY":
            self.application_method = "COMPANY_PORTAL"
        # Never treat a LinkedIn or Naukri platform job URL as an external company portal URL
        if self.application_url and any(d in self.application_url.lower() for d in ["naukri.com", "linkedin.com"]):
            self.application_url = None

    @property
    def salary_text(self) -> Optional[str]:
        """Returns preserved raw salary text if stored in raw_metadata."""
        if isinstance(self.raw_metadata, dict):
            return self.raw_metadata.get("salary_text")
        return None

    @property
    def experience_text(self) -> Optional[str]:
        """Returns preserved raw experience text if stored in raw_metadata, or computed range."""
        if isinstance(self.raw_metadata, dict) and self.raw_metadata.get("experience_text"):
            return self.raw_metadata.get("experience_text")
        range_str = self.experience_range_str()
        return range_str if range_str != "Not specified" else None

    def experience_range_str(self) -> str:
        """Returns human-readable representation of required experience range."""
        if self.required_experience_min is not None and self.required_experience_max is not None:
            if self.required_experience_min == self.required_experience_max:
                return f"{self.required_experience_min} year{'s' if self.required_experience_min != 1 else ''}"
            return f"{self.required_experience_min}-{self.required_experience_max} years"
        elif self.required_experience_min is not None:
            return f"{self.required_experience_min}+ years"
        elif self.required_experience_max is not None:
            return f"Up to {self.required_experience_max} years"
        return "Not specified"

    def matches_candidate_experience(self, candidate_experience: int, allowance: int = 0) -> bool:
        """Evaluates whether the candidate's experience satisfies this job's requirements.
        Candidate experience and required experience are separate concepts.
        """
        if self.required_experience_min is None:
            return True
        return (candidate_experience + allowance) >= self.required_experience_min

    def to_dict(self) -> Dict[str, Any]:
        """Serializes Job model to dictionary."""
        return {
            "platform": self.platform,
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "work_style": self.work_style,
            "required_experience_min": self.required_experience_min,
            "required_experience_max": self.required_experience_max,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency,
            "description": self.description,
            "source_url": self.source_url,
            "apply_type": self.apply_type,
            "application_method": self.application_method,
            "application_url": self.application_url,
            "posted_date": self.posted_date,
            "raw_metadata": self.raw_metadata,
        }


def job_from_linkedin(
    job_id: str,
    title: str,
    company: str,
    location: str,
    work_style: Optional[str] = None,
    description: str = "",
    experience_required: Optional[int] = None,
    source_url: str = "",
    apply_type: Literal["DIRECT", "QUESTIONNAIRE", "EXTERNAL"] = "DIRECT",
    application_method: Optional[str] = None,
    application_url: Optional[str] = None,
    posted_date: Optional[str] = None,
    raw_metadata: Optional[Dict[str, Any]] = None,
) -> Job:
    """Constructs a normalized Job object from LinkedIn listing data."""
    req_min = experience_required if isinstance(experience_required, int) and experience_required > 0 else None
    resolved_method = application_method or ("COMPANY_PORTAL" if apply_type == "EXTERNAL" else "EASY_APPLY")
    return Job(
        platform="linkedin",
        job_id=str(job_id).strip(),
        title=str(title).strip(),
        company=str(company).strip(),
        location=str(location).strip(),
        work_style=work_style.strip() if work_style else None,
        required_experience_min=req_min,
        required_experience_max=None,
        description=description,
        source_url=source_url or f"https://www.linkedin.com/jobs/view/{job_id}",
        apply_type=apply_type,
        application_method=resolved_method,
        application_url=application_url,
        posted_date=posted_date,
        raw_metadata=raw_metadata or {},
    )


def job_from_naukri(
    job_id: str,
    title: str,
    company: str,
    location: str,
    work_style: Optional[str] = None,
    description: str = "",
    required_experience_min: Optional[int] = None,
    required_experience_max: Optional[int] = None,
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,
    source_url: str = "",
    apply_type: Literal["DIRECT", "QUESTIONNAIRE", "EXTERNAL"] = "DIRECT",
    application_method: Optional[str] = None,
    application_url: Optional[str] = None,
    posted_date: Optional[str] = None,
    raw_metadata: Optional[Dict[str, Any]] = None,
) -> Job:
    """Constructs a normalized Job object from Naukri listing data."""
    resolved_method = application_method or ("COMPANY_PORTAL" if apply_type == "EXTERNAL" else "EASY_APPLY")
    return Job(
        platform="naukri",
        job_id=str(job_id).strip(),
        title=str(title).strip(),
        company=str(company).strip(),
        location=str(location).strip(),
        work_style=work_style.strip() if work_style else None,
        required_experience_min=required_experience_min,
        required_experience_max=required_experience_max,
        salary_min=salary_min,
        salary_max=salary_max,
        description=description,
        source_url=source_url,
        apply_type=apply_type,
        application_method=resolved_method,
        application_url=application_url,
        posted_date=posted_date,
        raw_metadata=raw_metadata or {},
    )


def job_from_foundit(
    job_id: str,
    title: str,
    company: str,
    location: str,
    work_style: Optional[str] = None,
    description: str = "",
    required_experience_min: Optional[int] = None,
    required_experience_max: Optional[int] = None,
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,
    source_url: str = "",
    apply_type: Literal["DIRECT", "QUESTIONNAIRE", "EXTERNAL"] = "DIRECT",
    application_method: Optional[str] = None,
    application_url: Optional[str] = None,
    posted_date: Optional[str] = None,
    raw_metadata: Optional[Dict[str, Any]] = None,
) -> Job:
    """Constructs a normalized Job object from Foundit listing data."""
    resolved_method = application_method or ("COMPANY_PORTAL" if apply_type == "EXTERNAL" else "EASY_APPLY")
    return Job(
        platform="foundit",
        job_id=str(job_id).strip(),
        title=str(title).strip(),
        company=str(company).strip(),
        location=str(location).strip(),
        work_style=work_style.strip() if work_style else None,
        required_experience_min=required_experience_min,
        required_experience_max=required_experience_max,
        salary_min=salary_min,
        salary_max=salary_max,
        description=description,
        source_url=source_url or f"https://www.foundit.in/job/{job_id}",
        apply_type=apply_type,
        application_method=resolved_method,
        application_url=application_url,
        posted_date=posted_date,
        raw_metadata=raw_metadata or {},
    )

