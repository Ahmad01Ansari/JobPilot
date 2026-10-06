"""Template rendering engine with strict variable validation and placeholder detection."""

import re
from typing import Any, Dict, List, Set, Tuple

SUPPORTED_VARIABLES: Set[str] = {
    "candidate_name",
    "candidate_email",
    "candidate_phone",
    "recruiter_name",
    "company_name",
    "job_title",
    "platform",
    "skills",
    "years_of_experience",
    "portfolio_url",
    "notice_period",
}

VARIABLE_REGEX = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


class TemplateRenderError(Exception):
    """Raised when required template placeholders cannot be resolved."""
    pass


class TemplateRenderer:
    """Safely interpolates variables into email templates, preventing unrendered tokens."""

    @classmethod
    def extract_variables(cls, text: str) -> List[str]:
        """Returns all distinct variable placeholder keys present in text."""
        if not text:
            return []
        matches = VARIABLE_REGEX.findall(text)
        return sorted(list(set(matches)))

    @classmethod
    def render(
        cls,
        text: str,
        context: Dict[str, Any],
        strict: bool = True,
        default_fallback: str = "",
    ) -> Tuple[str, List[str]]:
        """Replaces {{key}} variables with values from context.

        Args:
            text: Raw template string with {{variable}} placeholders.
            context: Mapping of variable keys to values.
            strict: If True, raises TemplateRenderError when a placeholder cannot be resolved.
            default_fallback: String to use for missing variables when strict is False.

        Returns:
            Tuple of (rendered_string, list_of_missing_keys)
        """
        if not text:
            return "", []

        missing_keys: List[str] = []

        def replace_match(match: re.Match) -> str:
            var_name = match.group(1).strip()
            val = context.get(var_name)
            if val is not None and str(val).strip():
                return str(val).strip()

            missing_keys.append(var_name)
            if strict:
                return match.group(0)  # leave unreplaced for error inspection
            return default_fallback

        rendered = VARIABLE_REGEX.sub(replace_match, text)

        if strict and missing_keys:
            unique_missing = sorted(list(set(missing_keys)))
            raise TemplateRenderError(
                f"Template contains unresolvable variables: {', '.join(unique_missing)}"
            )

        return rendered, sorted(list(set(missing_keys)))

    @classmethod
    def preview(cls, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Provides a safe preview representation highlighting resolved and unresolved tokens."""
        if not text:
            return {"preview": "", "missing_variables": [], "variables": []}

        vars_in_text = cls.extract_variables(text)
        rendered, missing = cls.render(text, context, strict=False, default_fallback="[NOT PROVIDED]")

        return {
            "preview": rendered,
            "variables": vars_in_text,
            "missing_variables": missing,
            "is_ready_to_send": len(missing) == 0,
        }
