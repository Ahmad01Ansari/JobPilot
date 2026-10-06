"""JSON parsing and schema validation engine for JobPilot AI structured output.

Safely handles real-world LLM output quirks:
- Strips markdown code fences (```json ... ```)
- Finds valid JSON boundaries via bracket slicing
- Distinguishes syntax errors from schema mismatches
- Returns structured failure DTOs instead of raising unhandled exceptions
"""

import ast
import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.services.ai.models import StructuredOutputResult

logger = logging.getLogger("JobPilot.AISchemaValidator")


class AISchemaValidator:
    """Parses and validates LLM output against schemas with resilient multi-tier recovery."""

    @staticmethod
    def clean_json_text(text: str) -> str:
        """Strips reasoning blocks, markdown fences, and isolates JSON objects or arrays."""
        clean = (text or "").strip()
        if not clean:
            return ""

        # 1. Strip reasoning and thinking blocks (<think>...</think>, <thought>...</thought>, <reasoning>...</reasoning>)
        clean = re.sub(r"<(think|thought|reasoning)>.*?</\1>", "", clean, flags=re.DOTALL | re.IGNORECASE).strip()

        # 2. Extract markdown code fences if present (```json ... ``` or ``` ... ```)
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean, flags=re.IGNORECASE)
        if fence_match:
            clean = fence_match.group(1).strip()
        else:
            # Strip unclosed opening markdown fence if output was truncated
            clean = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean).strip()

            # Find outermost JSON object or array based on which starts earlier
            start_obj = clean.find("{")
            end_obj = clean.rfind("}")
            start_arr = clean.find("[")
            end_arr = clean.rfind("]")

            if start_obj != -1 and (start_arr == -1 or start_obj < start_arr) and end_obj > start_obj:
                clean = clean[start_obj : end_obj + 1]
            elif start_arr != -1 and end_arr > start_arr:
                clean = clean[start_arr : end_arr + 1]

        return clean

    @classmethod
    def validate(
        cls,
        raw_output: str,
        expected_schema: Optional[Any] = None,
    ) -> StructuredOutputResult:
        """Validates raw text output against expected schema requirements with multi-tier parsing."""
        if not raw_output or not raw_output.strip():
            return StructuredOutputResult(
                success=False,
                raw_response=raw_output or "",
                error_type="empty_response",
                validation_errors=["Output was empty."],
            )

        cleaned = cls.clean_json_text(raw_output)
        parsed = None
        decode_err = None

        # Tier 1: Direct JSON parsing with strict=False (allows literal newlines/control chars inside strings)
        try:
            parsed = json.loads(cleaned, strict=False)
        except Exception as err:
            decode_err = err

        # Tier 2: Trailing comma repair (e.g. {"a": 1,} or [1, 2,])
        if parsed is None and cleaned:
            repaired = re.sub(r",\s*([\]}])", r"\1", cleaned)
            try:
                parsed = json.loads(repaired, strict=False)
            except Exception:
                pass

        # Tier 3: Python-literal parsing fallback (handles single-quoted keys/strings, True/False/None)
        if parsed is None and cleaned:
            try:
                candidate = ast.literal_eval(cleaned)
                if isinstance(candidate, (dict, list)):
                    parsed = candidate
            except Exception:
                pass

        # Tier 4: Python-literal parsing on comma-repaired candidate
        if parsed is None and cleaned:
            try:
                repaired = re.sub(r",\s*([\]}])", r"\1", cleaned)
                candidate = ast.literal_eval(repaired)
                if isinstance(candidate, (dict, list)):
                    parsed = candidate
            except Exception:
                pass

        # If all tiers fail, report invalid_json syntax failure
        if parsed is None:
            return StructuredOutputResult(
                success=False,
                raw_response=raw_output,
                error_type="invalid_json",
                validation_errors=[f"JSON syntax error: {decode_err or 'Failed to parse JSON content'}"],
            )

        if not isinstance(parsed, dict) and not isinstance(parsed, list):
            return StructuredOutputResult(
                success=False,
                data=parsed if isinstance(parsed, dict) else None,
                raw_response=raw_output,
                error_type="invalid_json",
                validation_errors=["Output root must be a JSON object or array."],
            )

        # Schema keys validation if expected_schema is provided
        validation_errors: List[str] = []
        if expected_schema and isinstance(parsed, dict):
            expected_keys: List[str] = []
            if isinstance(expected_schema, dict):
                expected_keys = list(expected_schema.keys())
            elif isinstance(expected_schema, str):
                try:
                    s_dict = json.loads(expected_schema)
                    if isinstance(s_dict, dict):
                        expected_keys = list(s_dict.keys())
                except Exception:
                    pass

            for k in expected_keys:
                if k not in parsed:
                    validation_errors.append(f"Missing required key: '{k}'")

        if validation_errors:
            return StructuredOutputResult(
                success=False,
                data=parsed,
                raw_response=raw_output,
                error_type="schema_mismatch",
                validation_errors=validation_errors,
            )

        return StructuredOutputResult(
            success=True,
            data=parsed,
            raw_response=raw_output,
            error_type="none",
        )

