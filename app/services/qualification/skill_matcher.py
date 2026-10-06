"""Extensible Skill Matching Abstraction for Job Qualification.

Supports exact keyword matching, alias/synonym expansion, and future semantic AI matching.
"""

from abc import ABC, abstractmethod
import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

from app.services.dto.qualification_dto import SkillMatchResult


# Curated standard tech synonyms / canonical mappings
CANONICAL_SKILL_SYNONYMS: Dict[str, Set[str]] = {
    "rpa": {"rpa", "robotic process automation", "robotic automation"},
    "uipath": {"uipath", "ui path", "ui-path"},
    "automation anywhere": {"automation anywhere", "automationanywhere", "aa"},
    "blue prism": {"blue prism", "blueprism"},
    "python": {"python", "python3", "py"},
    "react": {"react", "reactjs", "react.js"},
    "node": {"node", "nodejs", "node.js"},
    "javascript": {"javascript", "js", "ecmascript"},
    "typescript": {"typescript", "ts"},
    "aws": {"aws", "amazon web services"},
    "azure": {"azure", "microsoft azure"},
    "gcp": {"gcp", "google cloud", "google cloud platform"},
    "docker": {"docker", "containerization"},
    "kubernetes": {"kubernetes", "k8s"},
    "sql": {"sql", "mysql", "postgresql", "postgres", "t-sql", "pl/sql", "relational database"},
    "nosql": {"nosql", "mongodb", "mongo", "dynamodb", "cassandra"},
    "rest api": {"rest", "restful", "rest api", "rest apis", "restful api", "web services"},
    "git": {"git", "github", "gitlab", "version control"},
    "ci/cd": {"ci/cd", "cicd", "continuous integration", "jenkins", "github actions"},
    "selenium": {"selenium", "selenium webdriver", "browser automation"},
    "playwright": {"playwright"},
}

NEGATION_PATTERNS = [
    re.compile(r"(?:no|not|neither|without|don't need|no experience with)\s+([a-zA-Z0-9\+\#\.\s]{1,25})", re.IGNORECASE),
    re.compile(r"(?:optional|plus|nice to have|preferred,?\s+not required)\s*:\s*([^\n\.]+)", re.IGNORECASE),
]


class BaseSkillMatcher(ABC):
    """Abstract base class for all skill matching implementations."""

    @abstractmethod
    def match_skills(
        self,
        candidate_skills: Iterable[str],
        job_text: str,
        job_title: str = "",
    ) -> SkillMatchResult:
        """Evaluates skill alignment between candidate skills and job posting text."""
        pass


class ExactSkillMatcher(BaseSkillMatcher):
    """Matches candidate skills directly in text using word-boundary regex and negation suppression."""

    def match_skills(
        self,
        candidate_skills: Iterable[str],
        job_text: str,
        job_title: str = "",
    ) -> SkillMatchResult:
        full_text = f"{job_title}\n{job_text}".lower()
        cleaned_skills = [s.strip() for s in candidate_skills if s and s.strip()]

        if not cleaned_skills or not full_text.strip():
            return SkillMatchResult(matched_skills=[], missing_skills=cleaned_skills, score=0.0)

        matched: List[str] = []
        missing: List[str] = []

        for skill in cleaned_skills:
            pattern = rf"(?<!\w){re.escape(skill.lower())}(?!\w)"
            if re.search(pattern, full_text):
                # Ensure it's not a negated mention
                is_negated = False
                for neg_regex in NEGATION_PATTERNS:
                    m = neg_regex.search(full_text)
                    if m and skill.lower() in m.group(0).lower():
                        is_negated = True
                        break
                if not is_negated:
                    matched.append(skill)
                else:
                    missing.append(skill)
            else:
                missing.append(skill)

        score = (len(matched) / len(cleaned_skills) * 100.0) if cleaned_skills else 0.0
        return SkillMatchResult(matched_skills=matched, missing_skills=missing, score=round(score, 1))


class SynonymSkillMatcher(ExactSkillMatcher):
    """Enhanced matcher that checks aliases and canonical tech synonyms."""

    def __init__(self, custom_synonyms: Optional[Dict[str, Set[str]]] = None):
        self.synonyms = dict(CANONICAL_SKILL_SYNONYMS)
        if custom_synonyms:
            for k, vals in custom_synonyms.items():
                self.synonyms[k.lower()] = {v.lower() for v in vals}

    def _get_synonym_group(self, skill: str) -> Set[str]:
        low = skill.lower().strip()
        for canonical, aliases in self.synonyms.items():
            if low == canonical or low in aliases:
                return aliases | {canonical}
        return {low}

    def match_skills(
        self,
        candidate_skills: Iterable[str],
        job_text: str,
        job_title: str = "",
    ) -> SkillMatchResult:
        full_text = f"{job_title}\n{job_text}".lower()
        cleaned_skills = [s.strip() for s in candidate_skills if s and s.strip()]

        if not cleaned_skills or not full_text.strip():
            return SkillMatchResult(matched_skills=[], missing_skills=cleaned_skills, score=0.0)

        matched: List[str] = []
        missing: List[str] = []

        for skill in cleaned_skills:
            aliases = self._get_synonym_group(skill)
            found = False
            for alias in aliases:
                pattern = rf"(?<!\w){re.escape(alias)}(?!\w)"
                if re.search(pattern, full_text):
                    found = True
                    break

            if found:
                matched.append(skill)
            else:
                missing.append(skill)

        # Baseline coverage score against candidate skills
        score = (len(matched) / len(cleaned_skills) * 100.0) if cleaned_skills else 0.0
        return SkillMatchResult(matched_skills=matched, missing_skills=missing, score=round(score, 1))
