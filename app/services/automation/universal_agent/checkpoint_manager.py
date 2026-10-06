"""
Universal AI Application Agent — Execution Checkpoint Manager
Persists and restores execution checkpoints across browser disruptions and human interventions.
"""

from __future__ import annotations
import json
import os
import time
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionCheckpoint:
    application_id: Optional[int]
    job_id: Optional[str]
    current_url: str
    page_role: str
    execution_state: str
    current_step: int
    completed_steps: List[str] = field(default_factory=list)
    pending_action: Optional[str] = None
    intervention_reason: Optional[str] = None
    facts_used: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionCheckpoint:
        return cls(
            application_id=data.get("application_id"),
            job_id=data.get("job_id"),
            current_url=data.get("current_url", ""),
            page_role=data.get("page_role", "UNKNOWN"),
            execution_state=data.get("execution_state", "IDLE"),
            current_step=data.get("current_step", 0),
            completed_steps=data.get("completed_steps", []),
            pending_action=data.get("pending_action"),
            intervention_reason=data.get("intervention_reason"),
            facts_used=data.get("facts_used", {}),
            timestamp=data.get("timestamp", time.time()),
        )


class CheckpointManager:
    """Saves and restores execution checkpoints so runs can resume without restarting from scratch."""

    def __init__(self, storage_dir: Optional[str] = None) -> None:
        self.storage_dir = storage_dir or os.path.join("debug", "checkpoints")
        os.makedirs(self.storage_dir, exist_ok=True)

    def save_checkpoint(self, checkpoint: ExecutionCheckpoint) -> str:
        """Persists the checkpoint to disk and returns the file path."""
        key = checkpoint.job_id or f"checkpoint_{int(checkpoint.timestamp)}"
        clean_key = "".join(c for c in str(key) if c.isalnum() or c in ("-", "_"))
        file_path = os.path.join(self.storage_dir, f"{clean_key}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, indent=2)
            logger.debug("Saved execution checkpoint to: %s", file_path)
            return file_path
        except Exception as e:
            logger.warning("Failed to save execution checkpoint: %s", e)
            return ""

    def load_checkpoint(self, job_id_or_key: str) -> Optional[ExecutionCheckpoint]:
        """Loads a stored checkpoint from disk if present."""
        clean_key = "".join(c for c in str(job_id_or_key) if c.isalnum() or c in ("-", "_"))
        file_path = os.path.join(self.storage_dir, f"{clean_key}.json")
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ExecutionCheckpoint.from_dict(data)
        except Exception as e:
            logger.warning("Failed to load execution checkpoint: %s", e)
            return None

    def clear_checkpoint(self, job_id_or_key: str) -> bool:
        """Removes the checkpoint file after successful completion."""
        clean_key = "".join(c for c in str(job_id_or_key) if c.isalnum() or c in ("-", "_"))
        file_path = os.path.join(self.storage_dir, f"{clean_key}.json")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                return True
            except Exception:
                pass
        return False
