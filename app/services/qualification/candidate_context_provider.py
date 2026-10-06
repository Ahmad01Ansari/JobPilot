"""Candidate Qualification Context Provider.

Extracts verified facts from ProfileService, ResumeService, and central configuration
into an immutable, framework-agnostic CandidateQualificationContext.
"""

import logging
from typing import List, Optional, Set, Tuple

from sqlalchemy.orm import sessionmaker

from app.db.session import SessionLocal, get_db_session
from app.services.dto.qualification_dto import CandidateQualificationContext
from app.services.profile_service import ProfileService
from app.services.qna_service import QnAService
from app.services.resume_service import ResumeService

logger = logging.getLogger("JobPilot.CandidateContextProvider")


class CandidateContextProvider:
    """Builds canonical CandidateQualificationContext from verified local facts."""

    def __init__(
        self,
        profile_service: Optional[ProfileService] = None,
        resume_service: Optional[ResumeService] = None,
        qna_service: Optional[QnAService] = None,
        session_factory: Optional[sessionmaker] = None,
    ):
        self._session_factory = session_factory or SessionLocal
        self.profile_service = profile_service or ProfileService(session_factory=self._session_factory)
        self.resume_service = resume_service or ResumeService(session_factory=self._session_factory)
        self.qna_service = qna_service or QnAService(session_factory=self._session_factory)

    def build_context(self, user_id: Optional[int] = None) -> CandidateQualificationContext:
        """Constructs an immutable CandidateQualificationContext for deterministic evaluation."""
        with get_db_session(self._session_factory) as session:
            from app.repositories.resume_repository import ResumeRepository
            from app.repositories.user_repository import UserRepository

            user_repo = UserRepository(session)
            resume_repo = ResumeRepository(session)

            if user_id:
                user = user_repo.get_by_id(user_id)
            else:
                user = user_repo.get_primary_user()

            if not user and not user_id:
                # Ensure primary user exists via profile_service fallback
                self.profile_service.get_primary_user_profile()
                user = user_repo.get_primary_user()

            profile = user_repo.get_profile(user.id) if user else None
            pro_profile = user_repo.get_professional_profile(user.id) if user else None
            cid = user.id if user else 1

            # 1. Experience & Titles
            curr_title = (pro_profile.current_title.strip() if pro_profile and pro_profile.current_title else "").strip() or "Software Engineer"
            yoe = float(pro_profile.years_of_experience) if (pro_profile and pro_profile.years_of_experience is not None) else 0.0

            target_titles: List[str] = []
            if curr_title:
                target_titles.append(curr_title)

            # 2. Resumes & parsed skills
            resume = resume_repo.get_default_resume(cid)
            resume_skills: List[str] = []
            if resume:
                if resume.role_target and resume.role_target.strip():
                    rt = resume.role_target.strip()
                    if rt.lower() not in [t.lower() for t in target_titles]:
                        target_titles.append(rt)
                if resume.parsed_metadata and isinstance(resume.parsed_metadata, dict):
                    r_skills = resume.parsed_metadata.get("skills", [])
                    if isinstance(r_skills, list):
                        resume_skills = [str(s).strip() for s in r_skills if str(s).strip()]

            # 3. Skills aggregation
            raw_pri = (pro_profile.primary_skills or []) if pro_profile else []
            raw_sec = (pro_profile.secondary_skills or []) if pro_profile else []
            raw_gen = (pro_profile.skills or []) if pro_profile else []

            pri_skills = [str(s).strip() for s in raw_pri if str(s).strip()]
            sec_skills = [str(s).strip() for s in raw_sec if str(s).strip()]

            seen_skills: Set[str] = set()
            all_skills_list: List[str] = []
            for s in pri_skills + sec_skills + [str(x).strip() for x in raw_gen if str(x).strip()] + resume_skills:
                low = s.lower()
                if low not in seen_skills:
                    seen_skills.add(low)
                    all_skills_list.append(s)

            # 4. Location & Relocation
            curr_city = (profile.current_city.strip() if profile and profile.current_city else "").strip()
            pref_locs = [str(l).strip() for l in (profile.preferred_locations or []) if str(l).strip()] if profile else []
            relocate = bool(profile.willing_to_relocate) if profile else False

            # 5. Compensation & Notice
            exp_ctc = pro_profile.expected_ctc if pro_profile else None
            cur_ctc = pro_profile.current_ctc if pro_profile else None
            notice = pro_profile.notice_period_days if pro_profile else 30

        # 6. Negative keywords and company blacklist from central configuration
        blacklisted_comps: List[str] = []
        negative_title_kws: List[str] = [
            "mechanical", "electrical", "civil", "hardware", "chemical",
            "structural", "technician", "machinist", "maintenance", "site engineer",
            "plc programmer", "intern", "tutor", "sales executive", "telecaller"
        ]

        try:
            from modules.config_loader import get_platform, get_professional
            prof_cfg = get_professional()
            if prof_cfg:
                cfg_bl = prof_cfg.get("blacklisted_companies", [])
                if isinstance(cfg_bl, list):
                    blacklisted_comps.extend([str(c).strip() for c in cfg_bl if str(c).strip()])

            for p_name in ("linkedin", "naukri", "indeed", "glassdoor"):
                p_cfg = get_platform(p_name)
                if p_cfg:
                    bl = p_cfg.get("blacklisted_companies") or p_cfg.get("company_blacklist", [])
                    if isinstance(bl, list):
                        blacklisted_comps.extend([str(c).strip() for c in bl if str(c).strip()])
                    neg = p_cfg.get("negative_title_words", [])
                    if isinstance(neg, list):
                        negative_title_kws.extend([str(w).strip().lower() for w in neg if str(w).strip()])
        except Exception as e:
            logger.debug("Config loader fallback for blacklist: %s", e)

        # Deduplicate
        final_bl = tuple(sorted(list({c.lower(): c for c in blacklisted_comps}.values())))
        final_neg = tuple(sorted(list(set(w.lower() for w in negative_title_kws))))

        return CandidateQualificationContext(
            candidate_id=cid,
            target_titles=tuple(target_titles),
            current_title=curr_title,
            years_of_experience=yoe,
            primary_skills=tuple(pri_skills),
            secondary_skills=tuple(sec_skills),
            all_skills=tuple(all_skills_list),
            preferred_locations=tuple(pref_locs),
            current_city=curr_city,
            willing_to_relocate=relocate,
            expected_ctc=exp_ctc,
            current_ctc=cur_ctc,
            notice_period_days=notice,
            blacklisted_companies=final_bl,
            negative_title_keywords=final_neg,
        )
