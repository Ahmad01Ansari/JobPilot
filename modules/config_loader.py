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

def get_personal() -> Dict[str, Any]:
    """Returns personal information (name, contact, location, demographics)."""
    return load_profile().get("personal", {})

def get_professional() -> Dict[str, Any]:
    """Returns professional information (experience, salary, title, links)."""
    return load_profile().get("professional", {})

def get_resume(role: Optional[str] = None) -> str:
    """Returns resume path for a specific role or the default resume."""
    resumes = load_profile().get("resumes", {})
    default_path = resumes.get("default", "all resumes/default/resume.pdf")
    if role and "roles" in resumes:
        role_lower = role.lower()
        for key, path in resumes["roles"].items():
            if key.lower() in role_lower or role_lower in key.lower():
                if os.path.exists(path):
                    return path
    return default_path

def get_qna() -> Dict[str, Any]:
    """Returns Q&A configuration, standard answers, custom questions, and AI context."""
    return load_profile().get("qna", {})

def get_platform(name: str) -> Dict[str, Any]:
    """Returns platform-specific preferences (e.g. linkedin, indeed, naukri)."""
    platforms = load_profile().get("platforms", {})
    return platforms.get(name.lower(), {})

def get_ai() -> Dict[str, Any]:
    """Returns AI model and endpoint configuration."""
    return load_profile().get("ai", {})
