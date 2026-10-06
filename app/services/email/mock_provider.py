"""Mock Email Provider implementation for testing and offline environments."""

from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from app.services.dto.outreach_dto import (
    ConnectionStatusDTO,
    EmailMessageDTO,
    ExpandedInboundEmailDTO,
    SendResultDTO,
    SyncCheckpointDTO,
)
from app.services.dto.outreach_enums import MessageStatus
from app.services.email.provider import EmailProvider


class MockEmailProvider(EmailProvider):
    """In-memory email provider with fault injection, idempotency simulation, and inbox queuing."""

    def __init__(
        self,
        account_email: str = "candidate@jobpilot.mock",
        connection_should_succeed: bool = True,
    ):
        self.account_email = account_email
        self.connection_should_succeed = connection_should_succeed
        self.connection_error_message: str = "Simulated authentication failure"

        # State storage
        self.sent_messages: List[EmailMessageDTO] = []
        self.dispatched_tokens: Dict[str, SendResultDTO] = {}
        self.inbound_queue: List[ExpandedInboundEmailDTO] = []
        self.folder_queues: Dict[str, List[ExpandedInboundEmailDTO]] = {}
        self.appended_labels: List[Tuple[EmailMessageDTO, str]] = []

        # Fault injection flags
        self.fail_next_send: bool = False
        self.error_message_to_fail: str = "Simulated provider dispatch timeout"

    def get_provider_name(self) -> str:
        return "mock"

    def test_connection(self) -> ConnectionStatusDTO:
        if not self.connection_should_succeed:
            return ConnectionStatusDTO(
                success=False,
                provider_name="mock",
                message=self.connection_error_message,
                account_email=self.account_email,
                tested_at=datetime.now(timezone.utc),
            )
        return ConnectionStatusDTO(
            success=True,
            provider_name="mock",
            message="Mock provider connection active",
            account_email=self.account_email,
            tested_at=datetime.now(timezone.utc),
        )

    def send_email(self, message: EmailMessageDTO) -> SendResultDTO:
        # Idempotency check: if token was already dispatched successfully, return existing result
        if message.send_token in self.dispatched_tokens:
            return self.dispatched_tokens[message.send_token]

        # Fault injection
        if self.fail_next_send:
            self.fail_next_send = False
            return SendResultDTO(
                success=False,
                send_token=message.send_token,
                status=MessageStatus.FAILED,
                error_message=self.error_message_to_fail,
                timestamp=datetime.now(timezone.utc),
            )

        now = datetime.now(timezone.utc)
        domain = message.from_address.split("@")[-1] if "@" in message.from_address else "jobpilot.mock"
        provider_msg_id = f"mock-{uuid.uuid4().hex[:12]}@{domain}"
        provider_thread_id = message.provider_thread_id or f"thread-{uuid.uuid4().hex[:8]}"

        result = SendResultDTO(
            success=True,
            send_token=message.send_token,
            status=MessageStatus.SENT,
            provider_message_id=provider_msg_id,
            provider_thread_id=provider_thread_id,
            timestamp=now,
        )

        self.sent_messages.append(message)
        self.dispatched_tokens[message.send_token] = result
        return result

    def fetch_inbound(
        self,
        checkpoint: SyncCheckpointDTO,
        folder: Optional[str] = None,
    ) -> List[ExpandedInboundEmailDTO]:
        queue = self.folder_queues.get(folder, self.inbound_queue) if folder else self.inbound_queue
        if not queue:
            return []

        # Filter by checkpoint last_sync_at if specified
        results = []
        for msg in queue:
            if checkpoint.last_sync_at:
                if msg.received_at > checkpoint.last_sync_at:
                    results.append(msg)
            else:
                results.append(msg)
        return results

    def check_send_status(self, send_token: str) -> Optional[SendResultDTO]:
        """Returns the send result for the given token if already dispatched."""
        return self.dispatched_tokens.get(send_token)

    def append_to_label(self, message: EmailMessageDTO, label_name: str) -> bool:
        """Records appended label message for testing."""
        self.appended_labels.append((message, label_name))
        return True

    def enqueue_inbound(self, message: ExpandedInboundEmailDTO, folder: Optional[str] = None) -> None:
        """Helper for tests to simulate receipt of an inbound or folder-labeled message."""
        if folder:
            if folder not in self.folder_queues:
                self.folder_queues[folder] = []
            self.folder_queues[folder].append(message)
        else:
            self.inbound_queue.append(message)

    def reset(self) -> None:
        """Clears all in-memory records and flags."""
        self.sent_messages.clear()
        self.dispatched_tokens.clear()
        self.inbound_queue.clear()
        self.folder_queues.clear()
        self.appended_labels.clear()
        self.fail_next_send = False
