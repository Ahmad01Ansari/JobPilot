"""Browser agent abstraction layer for universal automation."""

from .base import BrowserAgent
from .llm_adapter import StagehandLLMAdapter
from .session_manager import UniversalSessionManager
from .stagehand_agent import StagehandBrowserAgent

__all__ = ["BrowserAgent", "StagehandLLMAdapter", "UniversalSessionManager", "StagehandBrowserAgent"]
