"""Registry package for modular SearchProviders."""

from app.services.search.providers.job_provider import JobSearchProvider
from app.services.search.providers.application_provider import ApplicationSearchProvider
from app.services.search.providers.company_provider import CompanySearchProvider
from app.services.search.providers.contact_provider import ContactSearchProvider
from app.services.search.providers.interview_provider import InterviewSearchProvider
from app.services.search.providers.followup_provider import FollowUpSearchProvider
from app.services.search.providers.outreach_provider import OutreachSearchProvider
from app.services.search.providers.resume_provider import ResumeSearchProvider
from app.services.search.providers.qna_provider import QnASearchProvider
from app.services.search.providers.platform_provider import PlatformSearchProvider

__all__ = [
    "JobSearchProvider",
    "ApplicationSearchProvider",
    "CompanySearchProvider",
    "ContactSearchProvider",
    "InterviewSearchProvider",
    "FollowUpSearchProvider",
    "OutreachSearchProvider",
    "ResumeSearchProvider",
    "QnASearchProvider",
    "PlatformSearchProvider",
]
