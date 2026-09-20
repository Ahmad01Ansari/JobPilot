'''
Base Platform Interface
Standard abstract class for all job board automation appliers (LinkedIn, Indeed, Naukri, etc.).
'''

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from modules.config_loader import get_personal, get_professional, get_resume, get_platform
from modules.qna_engine import QnAEngine

class BasePlatformApplier(ABC):
    def __init__(self, platform_name: str, ai_client: Optional[Any] = None):
        self.platform_name = platform_name.lower()
        self.platform_config = get_platform(self.platform_name)
        self.personal_info = get_personal()
        self.prof_info = get_professional()
        self.resume_path = get_resume()
        self.qna_engine = QnAEngine(ai_client=ai_client)

    @abstractmethod
    def initialize(self) -> None:
        """Initializes browser driver and sets up session."""
        pass

    @abstractmethod
    def login(self) -> bool:
        """Handles logging into the job portal."""
        pass

    @abstractmethod
    def search_and_apply(self) -> Dict[str, int]:
        """Executes search and runs the auto-apply loop. Returns stats dict."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Cleans up browser and background sessions."""
        pass


SUPPORTED_PLATFORMS = ["linkedin", "indeed", "naukri"]

def list_supported_platforms():
    """Returns a list of all supported platform identifiers."""
    return list(SUPPORTED_PLATFORMS)

