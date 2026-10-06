"""Settings registry providing searchable metadata and keywords for predictable search navigation."""

from typing import Any, Dict, List

SETTINGS_REGISTRY: Dict[str, Dict[str, Any]] = {
    # General
    "click_gap": {
        "section": "general",
        "title": "Interaction delay",
        "keywords": ["delay", "click", "speed", "timing", "wait", "throttle", "cadence"],
    },
    "smooth_scroll": {
        "section": "general",
        "title": "Smooth scrolling",
        "keywords": ["scroll", "mouse", "page", "human", "gesture"],
    },
    "alternate_sortby": {
        "section": "general",
        "title": "Alternate Recent and Relevant sort",
        "keywords": ["sort", "recent", "relevant", "order", "search", "filter"],
    },
    "cycle_date_posted": {
        "section": "general",
        "title": "Cycle posted-date filters",
        "keywords": ["date", "posted", "cycle", "past 24 hours", "week", "month", "filter"],
    },
    "run_non_stop": {
        "section": "general",
        "title": "Run continuously",
        "keywords": ["non-stop", "continuous", "loop", "infinite", "caution"],
    },

    # Browser
    "run_in_background": {
        "section": "browser",
        "title": "Run in background (Headless)",
        "keywords": ["headless", "background", "visible", "window", "hidden", "minimize"],
    },
    "stealth_mode": {
        "section": "browser",
        "title": "Browser compatibility mode (Stealth)",
        "keywords": ["stealth", "compatibility", "undetected", "flags", "bot", "chrome"],
    },
    "safe_mode": {
        "section": "browser",
        "title": "Safe profile isolation",
        "keywords": ["safe", "profile", "guest", "isolated", "session"],
    },
    "keep_screen_awake": {
        "section": "browser",
        "title": "Prevent system sleep (Wakelock)",
        "keywords": ["wakelock", "sleep", "screen", "power", "display", "awake"],
    },
    "disable_extensions": {
        "section": "browser",
        "title": "Disable extensions",
        "keywords": ["extensions", "plugins", "performance", "chrome"],
    },

    # Automation
    "pause_before_submit": {
        "section": "automation",
        "title": "Pause before final submission",
        "keywords": ["pause", "submit", "review", "human", "easy apply", "safeguard"],
    },
    "pause_at_failed_question": {
        "section": "automation",
        "title": "Pause on unresolved screening question",
        "keywords": ["screening", "question", "pause", "failed", "unresolved", "qna"],
    },
    "follow_companies": {
        "section": "automation",
        "title": "Follow companies automatically",
        "keywords": ["follow", "company", "feed", "linkedin"],
    },
    "close_tabs": {
        "section": "automation",
        "title": "Close external job tabs",
        "keywords": ["close", "tabs", "external", "redirects", "cleanup"],
    },

    # AI & Screening
    "ai_engine": {
        "section": "ai",
        "title": "AI Screening & QnA Provider",
        "keywords": ["ai", "ollama", "openai", "gemini", "deepseek", "llm", "screening", "qna"],
    },
    "ai_model": {
        "section": "ai",
        "title": "AI Model Selection",
        "keywords": ["model", "llama", "gpt", "gemini", "refresh", "discovery"],
    },
    "ai_endpoint": {
        "section": "ai",
        "title": "AI Endpoint URL",
        "keywords": ["endpoint", "url", "localhost", "11434", "api"],
    },
    "ai_api_key": {
        "section": "ai",
        "title": "AI API Key",
        "keywords": ["api key", "secret", "token", "auth"],
    },

    # Credentials & Security
    "linkedin_credentials": {
        "section": "credentials",
        "title": "LinkedIn Account",
        "keywords": ["linkedin", "account", "username", "password", "login", "credentials"],
    },
    "naukri_credentials": {
        "section": "credentials",
        "title": "Naukri.com Account",
        "keywords": ["naukri", "account", "username", "password", "login", "credentials"],
    },
    "recruiter_email": {
        "section": "credentials",
        "title": "Recruiter Outreach Email (SMTP / IMAP)",
        "keywords": ["email", "smtp", "imap", "gmail", "outlook", "mail", "outreach", "app password"],
    },
    "encryption_health": {
        "section": "credentials",
        "title": "Machine-Local Key Encryption Health",
        "keywords": ["encryption", "fernet", "key", "aes", "security", "permissions"],
    },

    # Backup & Restore
    "system_backup": {
        "section": "backup",
        "title": "System Backup Archive",
        "keywords": ["backup", "create", "archive", "zip", "database", "resumes"],
    },
    "system_restore": {
        "section": "backup",
        "title": "Safe System Restore",
        "keywords": ["restore", "recover", "snapshot", "sha256", "manifest"],
    },
    "profile_management": {
        "section": "backup",
        "title": "Candidate Profile Import / Export",
        "keywords": ["profile", "export", "import", "json", "candidate"],
    },
}


def search_settings(query: str) -> List[Dict[str, Any]]:
    """Searches setting items matching the query keywords, title, or section."""
    clean_q = query.strip().lower()
    if not clean_q:
        return []

    results = []
    for key, meta in SETTINGS_REGISTRY.items():
        score = 0
        if clean_q in meta["title"].lower():
            score += 10
        if clean_q == meta["section"]:
            score += 8
        for kw in meta["keywords"]:
            if clean_q in kw or kw in clean_q:
                score += 5
        if score > 0:
            results.append({
                "key": key,
                "section": meta["section"],
                "title": meta["title"],
                "score": score,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
