"""Abstract BrowserAgent interface for universal portal automation.

Shields JobPilot from direct third-party SDK dependencies (Stagehand, Playwright)
and standardizes browser interaction APIs.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BrowserAgent(ABC):
    """Abstract base class representing an automated browser agent session."""

    @abstractmethod
    async def initialize(self, headless: bool = False, **kwargs: Any) -> None:
        """Launches or connects the browser context and page session."""
        pass

    @abstractmethod
    async def navigate(self, url: str, wait_until: str = "domcontentloaded", timeout_ms: int = 30000) -> bool:
        """Navigates to the specified URL and waits for DOM settlement."""
        pass

    @abstractmethod
    async def act(self, action: str) -> Any:
        """Performs a semantic, AI-guided action (e.g. 'click Submit Application')."""
        pass

    @abstractmethod
    async def observe(self, instruction: str) -> List[Any]:
        """Observes actionable candidate elements on the page given an instruction."""
        pass

    @abstractmethod
    async def extract(self, instruction: str, schema: Any = None) -> Any:
        """Extracts structured data from the page DOM matching a schema or prompt."""
        pass

    @abstractmethod
    async def fill(self, selector: str, value: str, timeout_ms: int = 5000) -> bool:
        """Deterministically inputs text into an element matching the selector."""
        pass

    @abstractmethod
    async def click(self, selector: str, timeout_ms: int = 5000) -> bool:
        """Deterministically clicks an element matching the selector."""
        pass

    @abstractmethod
    async def upload_file(self, selector: str, file_path: str, timeout_ms: int = 5000) -> bool:
        """Attaches a local file to an input[type='file'] element."""
        pass

    @abstractmethod
    async def select_option(self, selector: str, value: str, timeout_ms: int = 5000) -> bool:
        """Selects a dropdown option by value or label."""
        pass

    @abstractmethod
    async def get_url(self) -> str:
        """Returns the current URL of the active browser page."""
        pass

    @abstractmethod
    async def get_title(self) -> str:
        """Returns the title of the active browser page."""
        pass

    @abstractmethod
    async def get_content(self) -> str:
        """Returns the raw HTML content of the active page."""
        pass

    @abstractmethod
    async def screenshot(self, path: Optional[str] = None) -> bytes:
        """Captures a screenshot of the active viewport."""
        pass

    @abstractmethod
    async def wait_for_selector(self, selector: str, timeout_ms: int = 5000) -> bool:
        """Waits for an element matching selector to become visible/attached."""
        pass

    @abstractmethod
    async def evaluate(self, expression: str) -> Any:
        """Evaluates a JavaScript expression on the active page context."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Closes the browser session, context, and handles."""
        pass

    async def sync_active_page(self) -> None:
        """Synchronizes active page handle to any newly focused or opened browser tab."""
        pass

    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        """Returns True if the browser agent is active and ready."""
        pass
