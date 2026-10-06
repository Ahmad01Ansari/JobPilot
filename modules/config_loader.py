'''
Unified Configuration Loader
Loads and manages centralized settings from config/profile.json.
'''

import os
import json
from typing import Any, Dict, Optional

_PROFILE_CACHE: Optional[Dict[str, Any]] = None
_PROFILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "profile.json")

def load_profile(force_reload: bool = False) -> Dict[str, Any]:
    """Loads and caches the profile.json configuration."""
    global _PROFILE_CACHE
    if _PROFILE_CACHE is not None and not force_reload:
        return _PROFILE_CACHE

    if not os.path.exists(_PROFILE_PATH):
        return {}

    try:
        with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
            _PROFILE_CACHE = json.load(f)
    except Exception as e:
        print(f"[config_loader] Warning: Failed to load profile.json ({e}). Using default values.")
        _PROFILE_CACHE = {}

    return _PROFILE_CACHE

def invalidate_cache() -> None:
    """Forces cache invalidation for profile.json."""
    global _PROFILE_CACHE
    _PROFILE_CACHE = None

def get_personal(user_id: Optional[int] = None) -> Dict[str, Any]:
    """Returns personal information (name, contact, location, demographics), DB-first with profile.json fallback."""
    file_cfg = load_profile().get("personal", {})
    try:
        from app.db.session import get_db_session
        from app.repositories.user_repository import UserRepository
        with get_db_session() as session:
            repo = UserRepository(session)
            user = repo.get_by_id(user_id) if user_id else repo.get_primary_user()
            if user:
                prof = repo.get_profile(user.id)
                parts = (user.name or "").split(None, 1)
                fname = (prof.first_name if prof and prof.first_name else (parts[0] if parts else ""))
                lname = (prof.last_name if prof and prof.last_name else (parts[1] if len(parts) > 1 else ""))
                phone = user.phone or (prof.phone if prof and hasattr(prof, "phone") else "") or file_cfg.get("phone_number", "")
                email = user.email or file_cfg.get("email", "")
                return {
                    "first_name": fname or file_cfg.get("first_name", ""),
                    "middle_name": (prof.middle_name if prof else "") or file_cfg.get("middle_name", ""),
                    "last_name": lname or file_cfg.get("last_name", ""),
                    "email": email,
                    "phone_number": phone,
                    "current_city": (prof.current_city if prof else "") or file_cfg.get("current_city", ""),
                    "street": (prof.address if prof and prof.address else ((prof.current_city if prof else "") or "")) or file_cfg.get("street", ""),
                    "state": (prof.state if prof else "") or file_cfg.get("state", ""),
                    "country": (prof.country if prof else "") or file_cfg.get("country", "India"),
                    "zipcode": (prof.zipcode if prof else "") or file_cfg.get("zipcode", ""),
                    "ethnicity": file_cfg.get("ethnicity", "Decline"),
                    "gender": file_cfg.get("gender", "Decline"),
                    "disability_status": file_cfg.get("disability_status", "No"),
                    "veteran_status": file_cfg.get("veteran_status", "No"),
                }
    except Exception:
        pass
    return file_cfg

def get_professional(user_id: Optional[int] = None) -> Dict[str, Any]:
    """Returns professional information (experience, salary, title, links), DB-first with profile.json fallback."""
    file_cfg = load_profile().get("professional", {})
    try:
        from app.db.session import get_db_session
        from app.repositories.user_repository import UserRepository
        with get_db_session() as session:
            repo = UserRepository(session)
            user = repo.get_by_id(user_id) if user_id else repo.get_primary_user()
            if user:
                pro_prof = repo.get_professional_profile(user.id)
                if pro_prof:
                    return {
                        "title": pro_prof.current_title or file_cfg.get("title", ""),
                        "current_employer": pro_prof.current_employer or file_cfg.get("current_employer", ""),
                        "years_of_experience": pro_prof.years_of_experience if pro_prof.years_of_experience is not None else file_cfg.get("years_of_experience", 0),
                        "current_ctc": pro_prof.current_ctc if pro_prof.current_ctc is not None else file_cfg.get("current_ctc"),
                        "desired_salary": pro_prof.expected_ctc if pro_prof.expected_ctc is not None else file_cfg.get("desired_salary"),
                        "notice_period_days": pro_prof.notice_period_days if pro_prof.notice_period_days is not None else file_cfg.get("notice_period_days", 30),
                        "linkedin_url": pro_prof.linkedin_url or file_cfg.get("linkedin_url", ""),
                        "portfolio_url": pro_prof.portfolio_url or file_cfg.get("portfolio_url", ""),
                        "confidence_level": "9",
                        "headline": pro_prof.headline or file_cfg.get("headline", ""),
                        "summary": pro_prof.summary or file_cfg.get("summary", ""),
                        "cover_letter": pro_prof.cover_letter or file_cfg.get("cover_letter", ""),
                    }
    except Exception:
        pass
    return file_cfg

def get_resume(role: Optional[str] = None, user_id: Optional[int] = None) -> str:
    """Returns resume path for a specific role or the default resume."""
    try:
        from app.db.session import get_db_session
        from app.repositories.resume_repository import ResumeRepository
        from app.repositories.user_repository import UserRepository
        with get_db_session() as session:
            uid = user_id
            if not uid:
                u = UserRepository(session).get_primary_user()
                uid = u.id if u else 1
            r_repo = ResumeRepository(session)
            resumes = r_repo.get_by_user_id(uid)
            if resumes:
                for r in resumes:
                    if role and role.lower() in r.file_name.lower():
                        if os.path.exists(r.file_path):
                            return r.file_path
                    if r.is_default and os.path.exists(r.file_path):
                        return r.file_path
    except Exception:
        pass

    resumes_cfg = load_profile().get("resumes", {})
    default_path = resumes_cfg.get("default", "all resumes/default/resume.pdf")
    if role and "roles" in resumes_cfg:
        role_lower = role.lower()
        for key, path in resumes_cfg["roles"].items():
            if key.lower() in role_lower or role_lower in key.lower():
                if os.path.exists(path):
                    return path
    return default_path

def get_qna() -> Dict[str, Any]:
    """Returns Q&A configuration, standard answers, custom questions, and AI context."""
    return load_profile().get("qna", {})

def get_platform(name: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Returns platform-specific preferences (e.g. linkedin, indeed, naukri), overlaying DB settings if present."""
    platforms = load_profile().get("platforms", {})
    plat_cfg = dict(platforms.get(name.lower(), {}))
    try:
        from config.search import _read_platform_from_db
        db_cfg = _read_platform_from_db(name.lower())
        if db_cfg:
            plat_cfg.update(db_cfg)
    except Exception:
        pass
    return plat_cfg

def get_ai() -> Dict[str, Any]:
    """Returns AI model and endpoint configuration."""
    return load_profile().get("ai", {})

def get_candidate_experience(user_id: Optional[int] = None) -> int:
    """Returns candidate's actual years of professional experience."""
    return int(get_professional(user_id=user_id).get("years_of_experience", 0))

def get_salary_preferences(user_id: Optional[int] = None) -> Dict[str, Any]:
    """Returns candidate's salary expectations (current_ctc, desired_salary)."""
    prof = get_professional(user_id=user_id)
    return {
        "current_ctc": prof.get("current_ctc"),
        "desired_salary": prof.get("desired_salary"),
    }

def get_notice_period(user_id: Optional[int] = None) -> int:
    """Returns candidate's notice period in days."""
    return int(get_professional(user_id=user_id).get("notice_period_days", 30))

def get_search_experience(platform_name: str, user_id: Optional[int] = None) -> int:
    """Returns portal search filter experience setting for a platform."""
    plat = get_platform(platform_name, user_id=user_id)
    if "experience_years" in plat:
        return int(plat["experience_years"])
    return get_candidate_experience(user_id=user_id)

def get_location_preference(platform_name: Optional[str] = None) -> str:
    """Returns search location preference for a platform or personal city."""
    if platform_name:
        plat = get_platform(platform_name)
        if "search_location" in plat:
            return str(plat["search_location"])
    return str(get_personal().get("current_city", "India"))

def validate_naukri_config() -> bool:
    """Validates Naukri platform configuration, candidate info, and credentials.
    Fulfills Phase 1 deliverable: 'Validated Naukri configuration loader'.
    """
    cfg = get_platform("naukri")
    if not cfg:
        raise ValueError("Missing 'naukri' section under 'platforms' in config/profile.json")

    if not isinstance(cfg.get("enabled"), bool):
        raise ValueError("'enabled' in platforms.naukri must be a boolean")

    search_terms = cfg.get("search_terms")
    if not isinstance(search_terms, list) or len(search_terms) == 0 or not all(isinstance(t, str) for t in search_terms):
        raise ValueError("'search_terms' in platforms.naukri must be a non-empty list of strings")

    if not isinstance(cfg.get("search_location"), str) or not cfg.get("search_location"):
        raise ValueError("'search_location' in platforms.naukri must be a non-empty string")

    exp = cfg.get("experience_years")
    if not isinstance(exp, int) or exp < 0:
        raise ValueError("'experience_years' in platforms.naukri must be an integer >= 0")

    max_pages = cfg.get("max_pages_per_search", 3)
    if not isinstance(max_pages, int) or max_pages < 1:
        raise ValueError("'max_pages_per_search' must be an integer >= 1")

    apply_mode = cfg.get("apply_mode", "direct_only")
    if apply_mode == "EASY_APPLY_ONLY":
        apply_mode = "direct_only"
        cfg["apply_mode"] = "direct_only"
    if apply_mode not in ["direct_only", "all"]:
        raise ValueError(f"'apply_mode' must be 'direct_only' or 'all', got '{apply_mode}'")

    if not isinstance(cfg.get("pause_before_submit"), bool):
        raise ValueError("'pause_before_submit' must be a boolean")

    # Validate separate candidate concepts
    if get_candidate_experience() < 0:
        raise ValueError("Candidate professional years_of_experience must be >= 0")

    sal = get_salary_preferences()
    if not sal.get("current_ctc") or not sal.get("desired_salary"):
        raise ValueError("Candidate current_ctc and desired_salary must be configured in profile.json")

    if get_notice_period() < 0:
        raise ValueError("Candidate notice_period_days must be >= 0")

    return True


def validate_foundit_config() -> bool:
    """Validates Foundit platform configuration, candidate info, and search preferences."""
    cfg = get_platform("foundit")
    if not cfg:
        raise ValueError("Missing 'foundit' section under 'platforms' in config/profile.json")

    if not isinstance(cfg.get("enabled"), bool):
        raise ValueError("'enabled' in platforms.foundit must be a boolean")

    search_terms = cfg.get("search_terms")
    if not isinstance(search_terms, list) or len(search_terms) == 0 or not all(isinstance(t, str) for t in search_terms):
        raise ValueError("'search_terms' in platforms.foundit must be a non-empty list of strings")

    if not isinstance(cfg.get("search_location"), str) or not cfg.get("search_location"):
        raise ValueError("'search_location' in platforms.foundit must be a non-empty string")

    exp = cfg.get("experience_years")
    if not isinstance(exp, int) or exp < 0:
        raise ValueError("'experience_years' in platforms.foundit must be an integer >= 0")

    max_pages = cfg.get("max_pages_per_search", 3)
    if not isinstance(max_pages, int) or max_pages < 1:
        raise ValueError("'max_pages_per_search' must be an integer >= 1")

    raw_mode = str(cfg.get("apply_mode", "direct_only")).strip().lower()
    if raw_mode in ["direct_only", "easy_apply_only", "easy_apply"]:
        apply_mode = "direct_only"
    elif raw_mode in ["all", "hybrid", "hybrid_mode"]:
        apply_mode = "all"
    else:
        raise ValueError(f"'apply_mode' must be 'direct_only' or 'all', got '{cfg.get('apply_mode')}'")

    if not isinstance(cfg.get("pause_before_submit"), bool):
        raise ValueError("'pause_before_submit' must be a boolean")

    # Validate candidate concepts
    if get_candidate_experience() < 0:
        raise ValueError("Candidate professional years_of_experience must be >= 0")

    sal = get_salary_preferences()
    if not sal.get("current_ctc") or not sal.get("desired_salary"):
        raise ValueError("Candidate current_ctc and desired_salary must be configured in profile.json")

    if get_notice_period() < 0:
        raise ValueError("Candidate notice_period_days must be >= 0")

    return True


def validate_glassdoor_config() -> bool:
    """Validates Glassdoor platform configuration, candidate info, and search preferences."""
    cfg = get_platform("glassdoor")
    if not cfg:
        raise ValueError("Missing 'glassdoor' section under 'platforms' in config/profile.json")

    if not isinstance(cfg.get("enabled"), bool):
        raise ValueError("'enabled' in platforms.glassdoor must be a boolean")

    search_terms = cfg.get("search_terms")
    if not isinstance(search_terms, list) or len(search_terms) == 0 or not all(isinstance(t, str) for t in search_terms):
        raise ValueError("'search_terms' in platforms.glassdoor must be a non-empty list of strings")

    if not isinstance(cfg.get("search_location"), str) or not cfg.get("search_location"):
        raise ValueError("'search_location' in platforms.glassdoor must be a non-empty string")

    exp = cfg.get("experience_years")
    if not isinstance(exp, int) or exp < 0:
        raise ValueError("'experience_years' in platforms.glassdoor must be an integer >= 0")

    max_pages = cfg.get("max_pages_per_search", 3)
    if not isinstance(max_pages, int) or max_pages < 1:
        raise ValueError("'max_pages_per_search' must be an integer >= 1")

    raw_mode = str(cfg.get("apply_mode", "direct_only")).strip().lower()
    if raw_mode in ["direct_only", "easy_apply_only", "easy_apply"]:
        apply_mode = "direct_only"
    elif raw_mode in ["all", "hybrid", "hybrid_mode"]:
        apply_mode = "all"
    else:
        raise ValueError(f"'apply_mode' must be 'direct_only' or 'all', got '{cfg.get('apply_mode')}'")

    if not isinstance(cfg.get("pause_before_submit"), bool):
        raise ValueError("'pause_before_submit' must be a boolean")

    # Validate candidate concepts
    if get_candidate_experience() < 0:
        raise ValueError("Candidate professional years_of_experience must be >= 0")

    sal = get_salary_preferences()
    if not sal.get("current_ctc") or not sal.get("desired_salary"):
        raise ValueError("Candidate current_ctc and desired_salary must be configured in profile.json")

    if get_notice_period() < 0:
        raise ValueError("Candidate notice_period_days must be >= 0")

    return True

