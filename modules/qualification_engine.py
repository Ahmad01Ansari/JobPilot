'''
Common Qualification Engine
Centralized, platform-agnostic job qualification filter for LinkedIn, Naukri, and future platforms.
Preserves 100% behavioral equivalence with existing LinkedIn qualification rules while operating on normalized Job objects.
'''

import re
from dataclasses import dataclass, field
from typing import Optional, Set, List, Dict, Any, Tuple
from modules.models import Job
from modules.config_loader import (
    get_candidate_experience,
    get_platform,
    get_qna,
    get_professional,
)


@dataclass
class QualificationResult:
    """Represents the qualification decision for a Job."""
    accepted: bool
    reason: Optional[str] = None
    stage: Optional[str] = None  # e.g. "ALREADY_APPLIED", "COMPANY_BLACKLIST", "TITLE_FILTER", "ABOUT_COMPANY", "BAD_WORDS", "CLEARANCE", "EXPERIENCE"

    def __bool__(self) -> bool:
        return self.accepted


def extract_experience_bounds(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Extracts minimum and maximum years of required experience from job description or text.
    Returns (min_years, max_years) as Optional[int].
    """
    if not text:
        return (None, None)

    # 1. Match range patterns like '1-5 years', '1–5 Years', '3 to 5 years', '1/3 years', '2-4 yrs'
    range_pattern = re.compile(r'(\d+)\s*(?:[-–—/]|to)\s*(\d+)\s*\+?\s*(?:years?|yrs?)', re.IGNORECASE)
    range_matches = range_pattern.findall(text)
    valid_ranges = [(int(m[0]), int(m[1])) for m in range_matches if int(m[0]) <= 20 and int(m[1]) <= 30]

    # 2. Match single patterns like '5+ years', '3 years', '2 yrs'
    single_pattern = re.compile(r'(\d+)\s*\+?\s*(?:years?|yrs?)', re.IGNORECASE)
    single_matches = single_pattern.findall(text)
    single_vals = [int(m) for m in single_matches if int(m) <= 20]

    if valid_ranges:
        # Take the lowest required range min and max
        min_val = min(r[0] for r in valid_ranges)
        max_val = max(r[1] for r in valid_ranges)
        return (min_val, max_val)
    elif single_vals:
        return (min(single_vals), None)

    return (None, None)


def extract_years_of_experience(text: str) -> int:
    """Legacy helper returning lower-bound integer (matches runAiBot.py behavior)."""
    min_exp, _ = extract_experience_bounds(text)
    return min_exp if min_exp is not None else 0


class QualificationEngine:
    """Evaluates whether a Job listing satisfies the candidate's criteria and constraints."""

    def __init__(
        self,
        candidate_experience: Optional[int] = None,
        did_masters: Optional[bool] = None,
        security_clearance: Optional[bool] = None,
        bad_words: Optional[List[str]] = None,
        negative_title_words: Optional[List[str]] = None,
        irrelevant_tech_words: Optional[List[str]] = None,
        core_skills: Optional[List[str]] = None,
        blacklisted_companies: Optional[Set[str]] = None,
        about_company_bad_words: Optional[List[str]] = None,
        about_company_good_words: Optional[List[str]] = None,
        applied_job_ids: Optional[Set[str]] = None,
    ):
        # Load from central config if not explicitly provided
        prof = get_professional()
        qna = get_qna().get("standard_answers", {})
        ln_plat = get_platform("linkedin")
        nk_plat = get_platform("naukri")
        ind_plat = get_platform("indeed")
        gd_plat = get_platform("glassdoor")

        self.candidate_experience = candidate_experience if candidate_experience is not None else get_candidate_experience()
        self.did_masters = did_masters if did_masters is not None else bool(qna.get("did_masters", False))
        self.security_clearance = security_clearance if security_clearance is not None else bool(qna.get("security_clearance", False))

        self.bad_words = [w.lower() for w in (bad_words if bad_words is not None else (gd_plat.get("bad_words") or ind_plat.get("bad_words") or nk_plat.get("bad_words") or ln_plat.get("bad_words", [])))]

        # Combine or fallback negative title words from platform configs
        cfg_neg = gd_plat.get("negative_title_words") or ind_plat.get("negative_title_words") or nk_plat.get("negative_title_words") or ln_plat.get("negative_title_words", [])
        self.negative_title_words = [w.lower() for w in (negative_title_words if negative_title_words is not None else cfg_neg)]

        # Configurable irrelevant tech stacks (e.g. Java, React, Vue, PHP for an RPA/Python engineer)
        default_irrelevant = [
            "java", "angular", "react", "vue", "php", "ruby", "c++", ".net", "dotnet",
            "android", "ios", "swift", "flutter", "salesforce", "sap abap", "mainframe",
            "embedded", "devops engineer", "cloud architect", "data engineer"
        ]
        cfg_irrel = ind_plat.get("irrelevant_tech_words") or nk_plat.get("irrelevant_tech_words") or ln_plat.get("irrelevant_tech_words", default_irrelevant)
        self.irrelevant_tech_words = [w.lower() for w in (irrelevant_tech_words if irrelevant_tech_words is not None else cfg_irrel)]

        # Configurable core domain skills
        default_core = ["rpa", "automation", "python", "uipath", "blue prism", "automation anywhere", "selenium", "playwright", "process automation", "bot", "ai"]
        cfg_core = ind_plat.get("core_skills") or nk_plat.get("core_skills") or ln_plat.get("core_skills", default_core)
        self.core_skills = [w.lower() for w in (core_skills if core_skills is not None else cfg_core)]

        self.blacklisted_companies = set(c.lower() for c in (blacklisted_companies or set()))
        self.about_company_bad_words = [w.lower() for w in (about_company_bad_words if about_company_bad_words is not None else ln_plat.get("about_company_bad_words", ["crossover"]))]
        self.about_company_good_words = [w.lower() for w in (about_company_good_words if about_company_good_words is not None else ln_plat.get("about_company_good_words", []))]
        self.applied_job_ids = set(str(jid) for jid in (applied_job_ids or set()))

    def qualify_title(self, title: str, company: str = "", job_id: Optional[str] = None) -> QualificationResult:
        """Fast Pre-Filter: checks applied status, company blacklist, and negative title words."""
        # 1. Already Applied Check
        if job_id and str(job_id) in self.applied_job_ids:
            return QualificationResult(accepted=False, reason=f"Already applied to job ID: {job_id}", stage="ALREADY_APPLIED")

        # 2. Company Blacklist Check
        if company and company.strip().lower() in self.blacklisted_companies:
            return QualificationResult(accepted=False, reason=f"Blacklisted Company: {company}", stage="COMPANY_BLACKLIST")

        # 3. Negative Title Words (exact word boundaries)
        if title and self.negative_title_words:
            lower_title = title.lower()
            for neg_word in self.negative_title_words:
                pattern = r'\b' + re.escape(neg_word) + r'\b'
                if re.search(pattern, lower_title):
                    return QualificationResult(accepted=False, reason=f"Irrelevant title keyword: '{neg_word}'", stage="TITLE_FILTER")

        # 4. Configurable Irrelevant Tech Stack Check
        # Reject titles containing unrelated tech stacks unless title explicitly mentions candidate core skills
        if title and self.irrelevant_tech_words:
            lower_title = title.lower()
            has_core_skill = any(cs in lower_title for cs in self.core_skills) if self.core_skills else False
            if not has_core_skill:
                for itech in self.irrelevant_tech_words:
                    pattern = r'\b' + re.escape(itech) + r'\b'
                    if re.search(pattern, lower_title):
                        return QualificationResult(
                            accepted=False,
                            reason=f"Title contains irrelevant tech stack: '{itech}'",
                            stage="TITLE_FILTER",
                        )

        return QualificationResult(accepted=True, reason=None, stage="TITLE_FILTER")

    def qualify_company(self, about_company_text: str) -> QualificationResult:
        """Evaluates About Company section against good/bad word lists."""
        if not about_company_text:
            return QualificationResult(accepted=True, reason=None, stage="ABOUT_COMPANY")

        about_lower = about_company_text.lower()

        # If any good word matches, bypass bad word check (exact legacy behavior)
        for good_word in self.about_company_good_words:
            if good_word in about_lower:
                return QualificationResult(accepted=True, reason=f"Matched good company keyword: '{good_word}'", stage="ABOUT_COMPANY")

        # Check bad company words
        for bad_word in self.about_company_bad_words:
            if bad_word in about_lower:
                return QualificationResult(accepted=False, reason=f"About Company contains blacklisted word: '{bad_word}'", stage="ABOUT_COMPANY")

        return QualificationResult(accepted=True, reason=None, stage="ABOUT_COMPANY")

    def qualify_description(
        self,
        description: str,
        required_experience_min: Optional[int] = None,
        title: Optional[str] = None,
    ) -> QualificationResult:
        """Evaluates job description for bad words, security clearance, domain relevance, and experience."""
        if not description:
            # If description is empty, evaluate experience bounds if available
            return self._evaluate_experience(description="", required_experience_min=required_experience_min)

        desc_lower = description.lower()

        # 1. Bad Words Check
        for word in self.bad_words:
            if word in desc_lower:
                return QualificationResult(accepted=False, reason=f"Description contains bad word: '{word}'", stage="BAD_WORDS")

        # 2. Security Clearance Check
        if not self.security_clearance:
            if any(term in desc_lower for term in ["polygraph", "clearance", "secret"]):
                return QualificationResult(accepted=False, reason="Job requires security clearance / polygraph", stage="CLEARANCE")

        # 3. Domain Skill Relevance Check for Generic Titles
        if title and self.core_skills:
            lower_title = title.lower()
            generic_indicators = ["software engineer", "application developer", "developer", "consultant", "associate", "analyst"]
            has_core_in_title = any(cs in lower_title for cs in self.core_skills)
            if any(gi in lower_title for gi in generic_indicators) and not has_core_in_title:
                if not any(cs in desc_lower for cs in self.core_skills):
                    return QualificationResult(
                        accepted=False,
                        reason="Job description does not contain candidate core domain skills",
                        stage="SKILL_MISMATCH",
                    )

        # 3. Experience Requirement Check
        return self._evaluate_experience(description=description, required_experience_min=required_experience_min)

    def _evaluate_experience(
        self,
        description: str,
        required_experience_min: Optional[int] = None
    ) -> QualificationResult:
        """Compares required experience with candidate experience, including Masters allowance."""
        # Calculate masters degree allowance (+2 years if candidate has masters and job mentions 'master')
        allowance = 0
        if self.did_masters and "master" in description.lower():
            allowance = 2

        req_exp = required_experience_min
        if req_exp is None and description:
            extracted_min, _ = extract_experience_bounds(description)
            req_exp = extracted_min

        # If required experience is specified and exceeds candidate's qualifications
        if req_exp is not None and self.candidate_experience > -1:
            effective_experience = self.candidate_experience + allowance
            if req_exp > effective_experience:
                return QualificationResult(
                    accepted=False,
                    reason=f"Required experience ({req_exp} yrs) exceeds candidate qualifications ({effective_experience} yrs)",
                    stage="EXPERIENCE"
                )

        return QualificationResult(accepted=True, reason=None, stage="EXPERIENCE")

    def qualify_job_pre_click(self, job: Job) -> QualificationResult:
        """Fast Pre-Click Filter (Stage 1): Evaluates title, company blacklist, negative keywords, and applied status."""
        return self.qualify_title(title=job.title, company=job.company, job_id=job.job_id)

    def qualify_job_post_click(self, job: Job, about_company_text: Optional[str] = None) -> QualificationResult:
        """Full Post-Click Filter (Stage 2): Evaluates full job description, experience bounds, bad words, and clearance."""
        return self.qualify(job=job, about_company_text=about_company_text)

    def qualify(self, job: Job, about_company_text: Optional[str] = None) -> QualificationResult:
        """Executes the full qualification pipeline in strict order on a normalized Job."""
        # 1. Title & Metadata Fast Filter
        title_res = self.qualify_title(title=job.title, company=job.company, job_id=job.job_id)
        if not title_res:
            return title_res

        # 2. About Company Check
        comp_text = about_company_text or job.raw_metadata.get("about_company", "")
        if comp_text:
            comp_res = self.qualify_company(comp_text)
            if not comp_res:
                return comp_res

        # 3. Description & Experience Check
        desc_res = self.qualify_description(
            description=job.description,
            required_experience_min=job.required_experience_min,
            title=job.title
        )
        if not desc_res:
            return desc_res

        return QualificationResult(accepted=True, reason=None, stage="ACCEPTED")
