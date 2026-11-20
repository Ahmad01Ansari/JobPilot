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
    stage: Optional[str] = None  # e.g. "ALREADY_APPLIED", "COMPANY_BLACKLIST", "TITLE_FILTER", "OUT_OF_DOMAIN", "ABOUT_COMPANY", "BAD_WORDS", "CLEARANCE", "SKILL_MISMATCH", "EXPERIENCE"

    def __bool__(self) -> bool:
        return self.accepted


GENERIC_ROLE_NOUNS: Set[str] = {
    "developer", "engineer", "specialist", "consultant", "analyst", "manager", "lead",
    "architect", "programmer", "coder", "associate", "officer", "executive", "administrator",
    "coordinator", "expert", "practitioner", "scientist", "designer", "head", "director", "vp"
}

STOP_WORDS: Set[str] = {
    "in", "and", "or", "for", "the", "of", "to", "at", "a", "an", "with", "senior", "junior",
    "lead", "sr", "jr", "ii", "iii", "iv", "level", "mid", "entry", "fresher", "intern", "trainee"
}

OUT_OF_DOMAIN_KEYWORDS: List[str] = [
    # HR & Recruitment
    "hr", "human resources", "recruiter", "recruitment", "talent acquisition", "staffing",
    "headhunter", "people operations", "hrbp", "talent partner", "payroll", "sourcer",
    # Sales, Marketing & BPO
    "sales", "marketing", "telecaller", "telemarketing", "inside sales", "bpo", "call center",
    "customer support", "customer care", "customer service", "csr", "business development", "bde", "bdm",
    # Finance, Accounting & Legal
    "accountant", "accounting", "auditor", "bookkeeper", "finance executive", "tax consultant",
    "billing", "legal counsel", "advocate", "lawyer",
    # Healthcare & Medical
    "nurse", "nursing", "pharmacist", "doctor", "physician", "therapist", "dentist",
    # Education & Training
    "teacher", "professor", "lecturer", "trainer", "counselor", "faculty",
    # Administrative & Clerical
    "receptionist", "admin executive", "office assistant", "clerk", "front desk",
    # Operations, Trades & Logistics
    "procurement", "supply chain", "logistics", "warehouse", "store keeper", "driver",
    "security guard", "housekeeping", "cook", "chef", "carpenter", "plumber", "electrician",
    # Creative / Content
    "content writer", "copywriter", "graphic designer", "video editor", "seo executive",
]


def is_job_relevant(
    job_title: str,
    search_term: str,
    core_skills: Optional[List[str]] = None,
    negative_words: Optional[List[str]] = None,
) -> bool:
    """Verifies that the job title has meaningful domain relevance to the search term.

    Prevents generic role noun collisions (e.g. 'HR Developer' matching 'RPA Developer',
    or 'Civil Engineer' matching 'Automation Engineer').
    """
    if not job_title or not search_term:
        return False

    title_lower = job_title.strip().lower()
    term_lower = search_term.strip().lower()

    if not title_lower or not term_lower:
        return False

    # 1. Exact phrase substring match
    if term_lower in title_lower:
        return True

    # 2. Check negative words if provided
    if negative_words:
        for nw in negative_words:
            nw_clean = nw.strip().lower()
            if nw_clean and re.search(r'\b' + re.escape(nw_clean) + r'\b', title_lower):
                return False

    # 3. Check out-of-domain words (reject non-target domains like HR, Sales, Accountant, etc.)
    # unless the search term itself explicitly targeted that domain
    for ood in OUT_OF_DOMAIN_KEYWORDS:
        if re.search(r'\b' + re.escape(ood) + r'\b', title_lower):
            # If search term contains this out-of-domain word, allow it
            if re.search(r'\b' + re.escape(ood) + r'\b', term_lower):
                continue
            # If title contains candidate core skills (e.g. 'HR Automation Engineer'), allow it
            if core_skills and any(re.search(r'\b' + re.escape(cs.lower()) + r'\b', title_lower) for cs in core_skills):
                continue
            return False

    # 4. Tokenize
    term_tokens = [w for w in re.findall(r'\b[a-zA-Z0-9\+\#\.]+\b', term_lower) if w not in STOP_WORDS]
    title_tokens = [w for w in re.findall(r'\b[a-zA-Z0-9\+\#\.]+\b', title_lower) if w not in STOP_WORDS]

    if not term_tokens or not title_tokens:
        return False

    # 5. Partition term tokens into domain keywords and generic role nouns
    domain_term_tokens = [w for w in term_tokens if w not in GENERIC_ROLE_NOUNS]
    role_term_tokens = [w for w in term_tokens if w in GENERIC_ROLE_NOUNS]

    # If the search term has domain-specific keywords (e.g. 'rpa', 'automation', 'python', 'uipath')
    if domain_term_tokens:
        has_domain_match = False
        for dt in domain_term_tokens:
            for tt in title_tokens:
                if dt == tt:
                    has_domain_match = True
                    break
                # Stem / prefix matching of at least 4 chars (e.g. automa -> automation)
                if len(dt) >= 4 and len(tt) >= 4 and (dt.startswith(tt) or tt.startswith(dt)):
                    has_domain_match = True
                    break
            if has_domain_match:
                break

        # Also check candidate core_skills if no direct term domain token match
        if not has_domain_match and core_skills:
            for cs in core_skills:
                cs_clean = cs.strip().lower()
                if cs_clean and re.search(r'\b' + re.escape(cs_clean) + r'\b', title_lower):
                    has_domain_match = True
                    break

        if not has_domain_match:
            # Domain keyword was completely missing from job title!
            # E.g. search term is 'RPA Developer', job title is 'HR Developer' or 'PHP Developer'
            return False

        return True

    # If search term only consists of generic role words (e.g. 'Developer', 'Software Engineer')
    for rt in role_term_tokens:
        for tt in title_tokens:
            if rt == tt:
                return True
            if len(rt) >= 4 and len(tt) >= 4 and (rt.startswith(tt) or tt.startswith(rt)):
                return True

    return False


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
        out_of_domain_words: Optional[List[str]] = None,
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

        # Configurable core domain skills
        default_core = ["rpa", "automation", "python", "uipath", "blue prism", "automation anywhere", "selenium", "playwright", "process automation", "bot", "ai"]
        if core_skills is not None:
            self.core_skills = [w.lower() for w in core_skills]
        else:
            self.core_skills = [w.lower() for w in default_core]

        cand_core_set = set(self.core_skills)

        # Configurable out-of-domain words (reject non-target domains like HR, Sales, Accountant, etc.)
        raw_ood = out_of_domain_words if out_of_domain_words is not None else OUT_OF_DOMAIN_KEYWORDS
        self.out_of_domain_words = [w.lower() for w in raw_ood if w.lower() not in cand_core_set]

        # Configurable irrelevant tech stacks (e.g. Golang, Ruby, PHP, Java, React when not in core skills)
        default_irrelevant = [
            "java", "angular", "react", "vue", "php", "ruby", "c++", ".net", "dotnet", "golang", "rust",
            "android", "ios", "swift", "flutter", "salesforce", "sap abap", "mainframe",
            "embedded", "devops engineer", "cloud architect", "data engineer"
        ]
        if irrelevant_tech_words is not None:
            raw_irrelevant = [w.lower() for w in irrelevant_tech_words]
        else:
            raw_irrelevant = [w.lower() for w in default_irrelevant]

        # Filter out candidate's verified skills so they are never classified as irrelevant
        self.irrelevant_tech_words = [w for w in raw_irrelevant if w not in cand_core_set]

        self.blacklisted_companies = set(c.lower() for c in (blacklisted_companies or set()))
        self.about_company_bad_words = [w.lower() for w in (about_company_bad_words if about_company_bad_words is not None else ln_plat.get("about_company_bad_words", ["crossover"]))]
        self.about_company_good_words = [w.lower() for w in (about_company_good_words if about_company_good_words is not None else ln_plat.get("about_company_good_words", []))]
        self.applied_job_ids = set(str(jid) for jid in (applied_job_ids or set()))

    def qualify_title(self, title: str, company: str = "", job_id: Optional[str] = None) -> QualificationResult:
        """Fast Pre-Filter: checks applied status, company blacklist, negative title words, out-of-domain professions, and irrelevant tech stacks."""
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

        # 4. Out-of-domain Professions (e.g. HR, Recruiter, Sales, Accountant, Nurse)
        if title and self.out_of_domain_words:
            lower_title = title.lower()
            has_core_in_title = any(re.search(r'\b' + re.escape(cs) + r'\b', lower_title) for cs in self.core_skills) if self.core_skills else False
            if not has_core_in_title:
                for ood in self.out_of_domain_words:
                    pattern = r'\b' + re.escape(ood) + r'\b'
                    if re.search(pattern, lower_title):
                        return QualificationResult(
                            accepted=False,
                            reason=f"Title belongs to out-of-domain profession: '{ood}'",
                            stage="OUT_OF_DOMAIN",
                        )

        # 5. Configurable Irrelevant Tech Stack Check
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
            # If description is empty and title lacks core skills, reject
            if title and self.core_skills:
                lower_title = title.lower()
                has_core_in_title = any(re.search(r'\b' + re.escape(cs) + r'\b', lower_title) for cs in self.core_skills)
                if not has_core_in_title:
                    return QualificationResult(
                        accepted=False,
                        reason="Job description is empty and title lacks candidate core domain skills",
                        stage="SKILL_MISMATCH",
                    )
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

        # 3. Domain Skill Relevance Check
        if title and self.core_skills:
            lower_title = title.lower()
            has_core_in_title = any(re.search(r'\b' + re.escape(cs) + r'\b', lower_title) for cs in self.core_skills)
            if not has_core_in_title:
                if not any(re.search(r'\b' + re.escape(cs) + r'\b', desc_lower) for cs in self.core_skills):
                    return QualificationResult(
                        accepted=False,
                        reason="Job description does not contain candidate core domain skills",
                        stage="SKILL_MISMATCH",
                    )

        # 3. Experience Requirement Check
        return self._evaluate_experience(
            description=description,
            required_experience_min=required_experience_min,
            title=title,
        )

    def _evaluate_experience(
        self,
        description: str,
        required_experience_min: Optional[int] = None,
        title: Optional[str] = None,
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

        # If required experience is not stated in text, infer conservative lower bound from title
        if req_exp is None and title:
            lower_title = title.lower()
            if any(re.search(r'\b' + re.escape(w) + r'\b', lower_title) for w in ["principal", "director", "vice president", "head of", "chief", "fellow"]):
                req_exp = 8
            elif any(re.search(r'\b' + re.escape(w) + r'\b', lower_title) for w in ["staff", "architect", "lead", "tech lead", "sde 3", "sde iii", "sde-3", "sde-iii"]):
                req_exp = 5
            elif any(re.search(r'\b' + re.escape(w) + r'\b', lower_title) for w in ["senior", "sr", "sr.", "sde 2", "sde ii", "sde-2", "sde-ii"]):
                req_exp = 3

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
