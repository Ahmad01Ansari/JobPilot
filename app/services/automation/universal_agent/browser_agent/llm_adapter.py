"""Adapter bridging Stagehand's LLMGenerateCallback to JobPilot's UniversalAIService."""

import json
from typing import Any, Callable, Dict, List, Optional, Union

from stagehand import (
    LLMMessageGenerateParams,
    LLMMessageGenerateResult,
    LLMStructuredGenerateParams,
    LLMStructuredGenerateResult,
    LLMTextContent,
    LLMUsage,
)
from stagehand.client_types import LLMGenerateCallback, LLMGenerateInput, LLMGenerateOutput

from app.services.ai_service import UniversalAIService


class StagehandLLMAdapter:
    """Bridges Stagehand SDK structured/text generation requests to JobPilot AI engines."""

    def __init__(
        self,
        ai_service: Optional[UniversalAIService] = None,
        mock_generator: Optional[Callable[[LLMGenerateInput], Any]] = None,
    ) -> None:
        self.ai_service = ai_service or UniversalAIService()
        self.mock_generator = mock_generator
        self.total_invocations: int = 0
        self.last_input: Optional[LLMGenerateInput] = None
        self.last_output: Optional[LLMGenerateOutput] = None

    def get_callback(self) -> LLMGenerateCallback:
        """Returns the async callback conforming to Stagehand's LLMGenerateCallback."""
        return self.generate

    async def generate(self, input_params: LLMGenerateInput) -> LLMGenerateOutput:
        """Dispatches LLM generation requests to JobPilot AI service or mock generator."""
        self.total_invocations += 1
        self.last_input = input_params

        # 1. Mock Generator Path (for tests & offline fixture evaluations)
        if self.mock_generator:
            mock_res = self.mock_generator(input_params)
            if isinstance(mock_res, (LLMStructuredGenerateResult, LLMMessageGenerateResult)):
                self.last_output = mock_res
                return mock_res
            # If mock returned a dict, wrap in LLMStructuredGenerateResult
            if isinstance(mock_res, dict):
                output = LLMStructuredGenerateResult(
                    role="assistant",
                    content=[LLMTextContent(type="text", text=json.dumps(mock_res))],
                    structured_content=mock_res,
                    output_format="json_schema",
                    usage=LLMUsage(input_tokens=10, output_tokens=10, total_tokens=20),
                )
                self.last_output = output
                return output
            # If mock returned a string, wrap in LLMMessageGenerateResult
            output = LLMMessageGenerateResult(
                role="assistant",
                content=[LLMTextContent(type="text", text=str(mock_res))],
                output_format="text",
                usage=LLMUsage(input_tokens=10, output_tokens=10, total_tokens=20),
            )
            self.last_output = output
            return output

        # 2. Production Path: Bridge to UniversalAIService
        system_prompt = input_params.system_prompt
        prompt_text = self._extract_prompt_text(input_params.messages)

        if isinstance(input_params, LLMStructuredGenerateParams):
            schema_dict = {}
            if hasattr(input_params, "response_format") and input_params.response_format:
                schema_dict = getattr(input_params.response_format, "schema_", {}) or {}
            schema_str = json.dumps(schema_dict) if schema_dict else "JSON Object"

            # Execute structured extraction via UniversalAIService
            result_dict = self.ai_service.extract_structured_json(
                prompt=prompt_text,
                schema_description=schema_str,
                system_prompt=system_prompt,
            )

            output = LLMStructuredGenerateResult(
                role="assistant",
                content=[LLMTextContent(type="text", text=json.dumps(result_dict))],
                structured_content=result_dict,
                output_format="json_schema",
                usage=LLMUsage(input_tokens=len(prompt_text) // 4, output_tokens=len(json.dumps(result_dict)) // 4, total_tokens=(len(prompt_text) + len(json.dumps(result_dict))) // 4),
            )
            self.last_output = output
            return output

        # Otherwise LLMMessageGenerateParams: generate plain text
        temp = float(input_params.temperature) if input_params.temperature is not None else 0.0
        text_result = self.ai_service.generate_text(
            prompt=prompt_text,
            system_prompt=system_prompt,
            temperature=temp,
        )

        output = LLMMessageGenerateResult(
            role="assistant",
            content=[LLMTextContent(type="text", text=text_result)],
            output_format="text",
            usage=LLMUsage(input_tokens=len(prompt_text) // 4, output_tokens=len(text_result) // 4, total_tokens=(len(prompt_text) + len(text_result)) // 4),
        )
        self.last_output = output
        return output

    def _extract_prompt_text(self, messages: Any) -> str:
        """Extracts text content across user, system, and assistant messages."""
        if not messages:
            return ""

        parts: List[str] = []
        for msg in messages:
            content = getattr(msg, "content", msg)
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    text_val = getattr(block, "text", None)
                    if text_val is not None:
                        parts.append(str(text_val))
                    else:
                        parts.append(str(block))
            else:
                text_val = getattr(content, "text", str(content))
                parts.append(str(text_val))

        return "\n".join(parts)
