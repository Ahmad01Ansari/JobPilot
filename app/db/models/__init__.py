"""Relational models registry for JobPilot."""

from app.db.models.company import Company
from app.db.models.contact import Contact
from app.db.models.job import Job, generate_job_fingerprint
from app.db.models.job_opportunity import (
    JobOpportunity,
    JobDeduplicationEvidence,
    OpportunityStatus,
    ConfidenceLevel,
    DedupDecision,
)
from app.db.models.job_evaluation import JobEvaluation
from app.db.models.application import Application
from app.db.models.status_history import ApplicationStatusHistory
from app.db.models.communication import Communication
from app.db.models.interview import Interview
from app.db.models.follow_up import FollowUp
from app.db.models.offer import Offer
from app.db.models.user import User, Profile, ProfessionalProfile
from app.db.models.resume import Resume, calculate_file_sha256
from app.db.models.platform import Platform, PlatformAccount
from app.db.models.qna import QnAEntry
from app.db.models.setting import AppSetting
from app.db.models.automation_run import AutomationRun
from app.db.models.email_template import EmailTemplate
from app.db.models.sync_checkpoint import EmailSyncCheckpoint

__all__ = [
    "Company",
    "Contact",
    "Job",
    "generate_job_fingerprint",
    "JobOpportunity",
    "JobDeduplicationEvidence",
    "OpportunityStatus",
    "ConfidenceLevel",
    "DedupDecision",
    "JobEvaluation",
    "Application",
    "ApplicationStatusHistory",
    "Communication",
    "Interview",
    "FollowUp",
    "Offer",
    "User",
    "Profile",
    "ProfessionalProfile",
    "Resume",
    "calculate_file_sha256",
    "Platform",
    "PlatformAccount",
    "QnAEntry",
    "AppSetting",
    "AutomationRun",
    "EmailTemplate",
    "EmailSyncCheckpoint",
]


