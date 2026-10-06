"""Abstract Base Class for Outreach Email Providers."""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.services.dto.outreach_dto import (
    ConnectionStatusDTO,
    EmailMessageDTO,
    ExpandedInboundEmailDTO,
    SendResultDTO,
    SyncCheckpointDTO,
)


class EmailProvider(ABC):
    """Protocol defining outbound dispatch and inbound synchronization for email providers."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Returns the human-readable unique identifier for this provider adapter."""
        pass

    @abstractmethod
    def test_connection(self) -> ConnectionStatusDTO:
        """Validates network connectivity and authentication credentials with the provider."""
        pass

    @abstractmethod
    def send_email(self, message: EmailMessageDTO) -> SendResultDTO:
        """Dispatches an outbound message to the target recipient(s).

        Must handle idempotent delivery keyed on `message.send_token` where supported,
        or preserve the send_token in headers/metadata.
        """
        pass

    @abstractmethod
    def fetch_inbound(
        self,
        checkpoint: SyncCheckpointDTO,
        folder: Optional[str] = None,
    ) -> List[ExpandedInboundEmailDTO]:
        """Fetches messages received or labeled in the specified folder/label since the given checkpoint cursor."""
        pass

    @abstractmethod
    def check_send_status(self, send_token: str) -> Optional[SendResultDTO]:
        """Checks if a message with the given send_token was already dispatched by the provider."""
        pass

    def append_to_label(self, message: EmailMessageDTO, label_name: str) -> bool:
        """Appends/saves the message to the specified folder/label on the mail server. Returns True if successful."""
        return True

