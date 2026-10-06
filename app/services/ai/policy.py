"""Execution policies, timeouts, and bounded retry rules for AI operations."""

from dataclasses import dataclass
import time
from typing import Optional


@dataclass
class AIRequestPolicy:
    """Configurable execution parameters for network operations."""
    connect_timeout: float = 5.0
    read_timeout: float = 30.0
    warmup_timeout: float = 60.0          # Allowance for local model weight loading
    max_retries: int = 2                  # Maximum automatic retries for transient errors
    backoff_factor: float = 1.5           # Exponential backoff base
    max_retry_delay: float = 10.0         # Upper cap on any single retry sleep
    respect_retry_after: bool = True      # Honors HTTP 429 Retry-After header

    def get_timeout(self, is_local: bool = False) -> float:
        """Returns the appropriate read timeout based on local vs. cloud execution."""
        return self.warmup_timeout if is_local else self.read_timeout

    def compute_backoff(self, attempt: int, retry_after_header: Optional[float] = None) -> float:
        """Calculates bounded sleep seconds before the next retry attempt."""
        if self.respect_retry_after and retry_after_header is not None:
            return min(self.max_retry_delay, max(0.5, retry_after_header))

        delay = self.backoff_factor ** attempt
        return min(self.max_retry_delay, max(0.5, delay))
