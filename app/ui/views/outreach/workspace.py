"""Outreach Workspace — 3-Zone QSplitter orchestrator.

The main Outreach Center widget that replaces the monolithic OutreachView.
Composes:
  - CommandHeader (top bar with metrics and actions)
  - ConversationInbox (left, searchable card list)
  - ThreadView + InlineReplyComposer (center, email thread + reply)
  - ContextPanel (right, collapsible recruitment context)

Wires all signals between components and the service layer.
"""

import logging
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.services.dto.outreach_viewmodels import PresentationConversationState
from app.services.followup_scheduler import FollowUpScheduler
from app.services.inbound_sync_service import InboundSyncService
from app.services.outreach_service import OutreachService
from app.services.search.search_result import NavigationAction, NavigationRequest
from app.ui.theme import COLORS
from app.ui.views.outreach.command_header import CommandHeader
from app.ui.views.outreach.context_panel import ContextPanel
from app.ui.views.outreach.conversation_inbox import ConversationInbox
from app.ui.views.outreach.inline_reply_composer import InlineReplyComposer
from app.ui.views.outreach.modern_popup import ModernPopup
from app.ui.views.outreach.thread_view import ThreadView

logger = logging.getLogger("JobPilot.Outreach.Workspace")


# ---------------------------------------------------------------------------
# Background Workers
# ---------------------------------------------------------------------------

class _InboxLoadWorker(QThread):
    """Loads conversation list on a background thread."""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, service: OutreachService, state_filter=None, search_query=None, limit=50, offset=0):
        super().__init__()
        self._svc = service
        self._filter = state_filter
        self._search = search_query
        self._limit = limit
        self._offset = offset

    def run(self):
        try:
            results = self._svc.list_conversations_vm(
                state_filter=self._filter,
                search_query=self._search,
                limit=self._limit,
                offset=self._offset,
            )
            self.finished.emit(results)
        except Exception as e:
            logger.exception("Failed to load conversations")
            self.error.emit(str(e))


class _DetailLoadWorker(QThread):
    """Loads conversation detail on a background thread."""
    finished = Signal(object)  # ConversationDetailViewModel or None
    error = Signal(str)

    def __init__(self, service: OutreachService, app_id: int):
        super().__init__()
        self._svc = service
        self._app_id = app_id

    def run(self):
        try:
            detail = self._svc.get_conversation_detail_vm(self._app_id)
            self.finished.emit(detail)
        except Exception as e:
            logger.exception("Failed to load conversation detail")
            self.error.emit(str(e))


class _StatsLoadWorker(QThread):
    """Loads stats on a background thread."""
    finished = Signal(dict)

    def __init__(self, service: OutreachService):
        super().__init__()
        self._svc = service

    def run(self):
        try:
            stats = self._svc.get_outreach_stats()
            self.finished.emit(stats)
        except Exception:
            self.finished.emit({})


class _ReplySendWorker(QThread):
    """Sends a threaded reply on a background thread."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        service: OutreachService,
        app_id: int,
        body: str,
        attachment_path: Optional[str] = None,
        resume_id: Optional[int] = None,
    ):
        super().__init__()
        self._svc = service
        self._app_id = app_id
        self._body = body
        self._attachment_path = attachment_path
        self._resume_id = resume_id

    def run(self):
        try:
            result = self._svc.send_reply(
                self._app_id,
                self._body,
                attachment_path=self._attachment_path,
                resume_id=self._resume_id,
            )
            self.finished.emit(result)
        except Exception as e:
            logger.exception("Reply send failed")
            self.error.emit(str(e))


class _MailSyncWorker(QThread):
    """Syncs mailbox on a background thread."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, inbound_service: InboundSyncService):
        super().__init__()
        self._svc = inbound_service

    def run(self):
        try:
            result = self._svc.sync_mailbox()
            self.finished.emit(result)
        except Exception as e:
            logger.exception("Mail sync failed")
            self.error.emit(str(e))


class _AICopilotWorker(QThread):
    """Generates RAG reply based on conversation history and candidate profile."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, service: OutreachService, app_id: int, prompt: Optional[str] = None):
        super().__init__()
        self._svc = service
        self._app_id = app_id
        self._prompt = prompt

    def run(self):
        try:
            result = self._svc.generate_rag_reply(self._app_id, user_prompt=self._prompt)
            self.finished.emit(result)
        except Exception as e:
            logger.exception("AI Copilot RAG generation failed")
            self.error.emit(str(e))


# ---------------------------------------------------------------------------
# Main Workspace Widget
# ---------------------------------------------------------------------------

class OutreachWorkspace(QWidget):
    """3-zone recruitment conversation workspace — replaces monolithic OutreachView."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._outreach_svc = OutreachService()
        self._inbound_svc = InboundSyncService()
        self._followup_scheduler = FollowUpScheduler()

        self._current_app_id: Optional[int] = None
        self._active_filter: Optional[str] = None
        self._active_search: Optional[str] = None
        self._pending_navigation_request: Optional[NavigationRequest] = None

        # Worker references (prevent GC)
        self._inbox_worker: Optional[_InboxLoadWorker] = None
        self._detail_worker: Optional[_DetailLoadWorker] = None
        self._stats_worker: Optional[_StatsLoadWorker] = None
        self._reply_worker: Optional[_ReplySendWorker] = None
        self._sync_worker: Optional[_MailSyncWorker] = None
        self._copilot_worker: Optional[_AICopilotWorker] = None

        self._setup_ui()
        self._connect_signals()
        self.refresh_data()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Command Header
        self._header = CommandHeader()
        outer.addWidget(self._header)

        # 3-Zone Splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(4)
        self._splitter.setStyleSheet(f"""
            QSplitter::handle:horizontal {{
                background: {COLORS['border']};
                width: 4px;
            }}
            QSplitter::handle:horizontal:hover {{
                background: {COLORS['primary']};
            }}
        """)

        # Left: Inbox
        self._inbox = ConversationInbox()
        self._inbox.setMinimumWidth(260)
        self._inbox.setMaximumWidth(420)
        self._splitter.addWidget(self._inbox)

        # Center: Thread + Reply Composer
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self._thread_view = ThreadView()
        center_layout.addWidget(self._thread_view, 1)

        self._composer = InlineReplyComposer()
        center_layout.addWidget(self._composer)

        self._splitter.addWidget(center)

        # Right: Context Panel
        self._context = ContextPanel()
        self._context.setMinimumWidth(260)
        self._context.setMaximumWidth(700)
        self._splitter.addWidget(self._context)

        # Set initial splitter sizes (proportional)
        self._splitter.setSizes([300, 500, 360])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)

        outer.addWidget(self._splitter, 1)

        self.setStyleSheet(f"""
            OutreachWorkspace {{
                background: {COLORS['background']};
            }}
        """)

    def _connect_signals(self):
        # Header
        self._header.filter_changed.connect(self._on_filter_changed)
        self._header.sync_requested.connect(self._on_sync)
        self._header.bulk_outreach_requested.connect(self._on_bulk_outreach)
        self._header.new_outreach_requested.connect(self._on_new_outreach)

        # Inbox
        self._inbox.conversation_selected.connect(self._on_conversation_selected)
        self._inbox.search_changed.connect(self._on_search_changed)
        self._inbox.priority_toggled.connect(self._on_priority_toggled)
        self._inbox.mark_read_requested.connect(self._on_mark_read_requested)

        # Composer
        self._composer.send_requested.connect(self._on_send_reply)
        self._composer.draft_save_requested.connect(self._on_save_draft)
        self._composer.draft_discard_requested.connect(self._on_discard_draft)
        self._composer.ai_copilot_prompt_requested.connect(self._on_ai_copilot_prompt)

        # Context panel
        self._context.pause_cadence.connect(self._on_pause_cadence)
        self._context.resume_cadence.connect(self._on_resume_cadence)
        self._context.stop_cadence.connect(self._on_stop_cadence)
        self._context.execute_followup.connect(self._on_execute_followup)
        self._context.cta_clicked.connect(self._on_cta_clicked)

    # ---------------------------------------------------------------
    # Public API (called by navigation system)
    # ---------------------------------------------------------------

    def refresh(self):
        """Invoked by MainWindow tab switching."""
        self.refresh_data()

    def refresh_data(self):
        """Called when the Outreach tab is activated or needs refresh."""
        self._load_stats()
        self._load_inbox()

    # ---------------------------------------------------------------
    # Data Loading
    # ---------------------------------------------------------------

    def _load_stats(self):
        self._stats_worker = _StatsLoadWorker(self._outreach_svc)
        self._stats_worker.finished.connect(self._on_stats_loaded)
        self._stats_worker.start()

    def _on_stats_loaded(self, stats: dict):
        self._header.update_stats(stats)

    def _load_inbox(self):
        self._inbox_worker = _InboxLoadWorker(
            self._outreach_svc,
            state_filter=self._active_filter or None,
            search_query=self._active_search or None,
        )
        self._inbox_worker.finished.connect(self._on_inbox_loaded)
        self._inbox_worker.error.connect(self._on_inbox_error)
        self._inbox_worker.start()

    def _on_inbox_loaded(self, conversations):
        self._inbox.set_conversations(conversations)

        # Compute action count (Action Today: needs action, follow up due, or review)
        action_count = sum(
            1 for c in conversations
            if c.state in (
                PresentationConversationState.NEEDS_ACTION,
                PresentationConversationState.FOLLOW_UP_DUE,
                PresentationConversationState.NEEDS_REVIEW,
                PresentationConversationState.REPLIED,
            )
        )
        self._header.set_action_count(action_count)

        if self._pending_navigation_request:
            req = self._pending_navigation_request
            self._pending_navigation_request = None
            self.handle_navigation_request(req)
        # Auto-select first if nothing selected
        elif conversations and self._current_app_id is None:
            self._on_conversation_selected(conversations[0].application_id)

    def arm_navigation_request(self, request: NavigationRequest) -> None:
        """Stores request to be applied safely during or after inbox load."""
        self._pending_navigation_request = request

    def handle_navigation_request(self, request: NavigationRequest) -> None:
        """Navigates to conversation matching request entity_id."""
        if request.entity_id:
            self.select_conversation(request.entity_id)

    def open_record(self, entity_id: int) -> None:
        self.select_conversation(entity_id)

    def focus_record(self, entity_id: int) -> None:
        self.select_conversation(entity_id)

    def _on_inbox_error(self, err: str):
        logger.error("Inbox load error: %s", err)

    def _load_detail(self, app_id: int):
        self._detail_worker = _DetailLoadWorker(self._outreach_svc, app_id)
        self._detail_worker.finished.connect(self._on_detail_loaded)
        self._detail_worker.error.connect(self._on_detail_error)
        self._detail_worker.start()

    def _on_detail_loaded(self, detail):
        if detail is None:
            self._thread_view.clear()
            self._composer.clear()
            self._context.clear()
            return

        self._thread_view.load_conversation(detail)
        self._context.load_detail(detail)

        # Load composer with draft if exists
        recipient_name = detail.contact.name if detail.contact else detail.company_name
        self._composer.load_for_conversation(
            app_id=detail.application_id,
            recipient_name=recipient_name,
            draft_body=detail.active_draft_body,
        )

        # Populate templates for the reply composer
        try:
            templates = self._outreach_svc.list_templates()
            self._composer.set_templates(templates)
        except Exception as e:
            logger.debug("Failed to list templates for composer: %s", e)

        # Mark conversation as read upon opening
        try:
            self._outreach_svc.mark_conversation_read(detail.application_id, True)
            for c in self._inbox._conversations:
                if c.application_id == detail.application_id and c.unread_count > 0:
                    c.unread_count = 0
                    self._inbox._render_cards()
                    break
        except Exception as e:
            logger.debug("Failed to auto-mark conversation as read: %s", e)

        # Scroll smoothly to bottom so latest inbound/outbound messages are in view
        from PySide6.QtCore import QTimer
        QTimer.singleShot(60, self._thread_view.scroll_to_bottom)

    def _on_detail_error(self, err: str):
        logger.error("Detail load error: %s", err)

    # ---------------------------------------------------------------
    # Event Handlers
    # ---------------------------------------------------------------

    def _on_priority_toggled(self, app_id: int):
        try:
            self._outreach_svc.toggle_conversation_priority(app_id)
            self._load_inbox()
        except Exception as e:
            logger.error("Failed to toggle priority for %s: %s", app_id, e)

    def _on_mark_read_requested(self, app_id: int, is_read: bool):
        try:
            self._outreach_svc.mark_conversation_read(app_id, is_read)
            self._load_inbox()
        except Exception as e:
            logger.error("Failed to mark read for %s: %s", app_id, e)

    def select_conversation(self, app_id: int) -> None:
        """Public router method: selects and loads the conversation for the given application ID."""
        self._on_conversation_selected(app_id)

    def _on_conversation_selected(self, app_id: int):
        self._current_app_id = app_id
        self._inbox.select_conversation(app_id)
        self._load_detail(app_id)

    def _on_filter_changed(self, filter_val: str):
        self._active_filter = filter_val or None
        self._load_inbox()

    def _on_search_changed(self, query: str):
        self._active_search = query or None
        self._load_inbox()

    def _on_sync(self):
        self._header.set_syncing(True)
        self._sync_worker = _MailSyncWorker(self._inbound_svc)
        self._sync_worker.finished.connect(self._on_sync_finished)
        self._sync_worker.error.connect(self._on_sync_error)
        self._sync_worker.start()

    def _on_sync_finished(self, result: dict):
        self._header.set_syncing(False)
        self.refresh_data()

        # Instantly refresh the currently open conversation so fetched responses appear immediately behind popup
        if self._current_app_id:
            self._load_detail(self._current_app_id)

        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()

        if not result.get("success", True):
            err = result.get("error", "Unknown sync issue")
            ModernPopup.error(self, "Sync Issue", f"Mail sync encountered an issue:\n\n{err}")
            return

        synced = result.get("synced_count", 0) or result.get("total_fetched", 0)
        matched = result.get("matched_count", 0)
        if matched > 0:
            ModernPopup.success(
                self,
                "New Recruiter Replies Synced",
                f"Successfully polled your email account.\n\n"
                f"• {matched} recruiter replies matched to conversation threads.\n"
                f"• Automated follow-up cadences paused for active replies.",
                button_text="Done",
            )
        elif synced > 0:
            ModernPopup.information(
                self,
                "Mailbox Checked",
                f"Checked {synced} recent messages.\n\nNo new recruiter replies were detected.",
                button_text="OK",
            )
        else:
            ModernPopup.information(
                self,
                "Mailbox Up to Date",
                "Your mailbox is completely synchronized. No new incoming messages found since last check.",
                button_text="OK",
            )
        logger.info("Mail sync complete: %d messages synced, %d matched", synced, matched)

    def _on_sync_error(self, err: str):
        self._header.set_syncing(False)
        logger.error("Mail sync error: %s", err)
        ModernPopup.error(
            self,
            "Sync Connection Error",
            f"Could not connect to your configured email provider:\n\n{err}\n\n"
            f"Please verify your email credentials in config/secrets.py or Settings.",
        )

    def _on_new_outreach(self):
        """Opens the modern New Outreach composer dialog."""
        from app.ui.views.outreach.composer_dialog import OutreachComposerDialog
        dialog = OutreachComposerDialog(
            outreach_service=self._outreach_svc,
            parent=self,
        )
        if dialog.exec():
            self.refresh_data()

    def _on_bulk_outreach(self):
        """Opens the Bulk Outreach campaign dialog."""
        from app.services.resume_service import ResumeService
        from app.ui.views.bulk_outreach_dialog import BulkOutreachDialog
        try:
            val_res = self._outreach_svc.validate_bulk_targets(None)
            targets = val_res.items
        except Exception as e:
            logger.error("Failed to pre-validate bulk targets: %s", e)
            targets = None

        dialog = BulkOutreachDialog(
            outreach_service=self._outreach_svc,
            resume_service=ResumeService(),
            initial_targets=targets,
            parent=self,
        )
        dialog.campaign_dispatched.connect(self.refresh_data)
        dialog.exec()
        self.refresh_data()

    def _on_send_reply(self, app_id: int, body: str, attachment_path: Optional[str] = None, resume_id: Optional[int] = None):
        self._reply_worker = _ReplySendWorker(
            self._outreach_svc,
            app_id,
            body,
            attachment_path=attachment_path,
            resume_id=resume_id,
        )
        self._reply_worker.finished.connect(self._on_reply_sent)
        self._reply_worker.error.connect(self._on_reply_error)
        self._reply_worker.start()

    def _on_reply_sent(self, result: dict):
        if result.get("success"):
            self._composer.on_send_success()
            # Delete the draft since it's been sent
            if self._current_app_id:
                self._outreach_svc.delete_draft(self._current_app_id)
            self.refresh_data()
            if self._current_app_id:
                self._load_detail(self._current_app_id)
        else:
            err_msg = result.get("error", "Unknown error")
            self._composer.on_send_error(err_msg)
            ModernPopup.error(
                self,
                "Send Reply Failed",
                f"Failed to dispatch reply:\n\n{err_msg}\n\nYour draft and attachments have been preserved so you can retry.",
            )

    def _on_reply_error(self, err: str):
        self._composer.on_send_error(err)
        ModernPopup.error(
            self,
            "Send Reply Failed",
            f"Network or connection error while sending reply:\n\n{err}\n\nYour draft and attachments have been preserved so you can retry.",
        )

    def _on_save_draft(self, app_id: int, body: str):
        """Handles debounced autosave from the composer."""
        try:
            self._outreach_svc.save_draft(app_id, body)
        except Exception as e:
            logger.error("Draft save failed: %s", e)

    def _on_discard_draft(self, app_id: int):
        """Handles draft discard from the composer."""
        try:
            self._outreach_svc.delete_draft(app_id)
        except Exception as e:
            logger.error("Draft discard failed: %s", e)

    def _on_pause_cadence(self, app_id: int):
        try:
            self._outreach_svc.pause_followups(app_id, reason="Manually paused")
            self.refresh_data()
            if self._current_app_id == app_id:
                self._load_detail(app_id)
        except Exception as e:
            logger.error("Pause cadence failed: %s", e)

    def _on_resume_cadence(self, app_id: int):
        try:
            self._outreach_svc.resume_followups(app_id)
            self.refresh_data()
            if self._current_app_id == app_id:
                self._load_detail(app_id)
        except Exception as e:
            logger.error("Resume cadence failed: %s", e)

    def _on_stop_cadence(self, app_id: int):
        confirmed = ModernPopup.confirm(
            self,
            "Stop Follow-Up Sequence",
            "This will permanently cancel all remaining automated follow-ups for this candidate application.\n\nAre you sure you want to stop the sequence?",
            confirm_text="Stop Sequence",
            cancel_text="Keep Sequence Active",
            is_danger=True,
        )
        if confirmed:
            try:
                self._outreach_svc.stop_followups(app_id, reason="Sequence stopped by user")
                self.refresh_data()
                if self._current_app_id == app_id:
                    self._load_detail(app_id)
                ModernPopup.information(
                    self,
                    "Sequence Stopped",
                    "The automated follow-up cadence has been permanently stopped.",
                )
            except Exception as e:
                logger.error("Stop cadence failed: %s", e)
                ModernPopup.error(self, "Action Failed", f"Could not stop cadence: {e}")

    def _on_execute_followup(self, fu_id: int):
        try:
            self._followup_scheduler.execute_followup(fu_id)
            self.refresh_data()
            if self._current_app_id:
                self._load_detail(self._current_app_id)
            ModernPopup.success(
                self,
                "Follow-Up Sent",
                "The scheduled follow-up email has been dispatched and added to the conversation thread.",
            )
        except Exception as e:
            logger.error("Execute follow-up failed: %s", e)
            ModernPopup.error(self, "Follow-Up Error", f"Failed to execute follow-up:\n\n{e}")

    def _on_cta_clicked(self, action_type: str):
        """Routes CTA clicks from the Next Action card."""
        if action_type in ("REPLY", "SCHEDULE_INTERVIEW"):
            # Focus the composer
            self._composer.focus_editor()
        elif action_type in ("WAIT", "VIEW_THREAD"):
            self._thread_view.scroll_to_bottom()
            self._composer.focus_editor()
        elif action_type == "EXECUTE_FOLLOWUP":
            if self._current_app_id:
                try:
                    timeline = self._outreach_svc.get_conversation_timeline(self._current_app_id)
                    due_fu = next((f for f in timeline.get("follow_ups", []) if f.get("status") in ("DUE", "PENDING")), None)
                    if due_fu and due_fu.get("id"):
                        self._on_execute_followup(due_fu["id"])
                    else:
                        self._composer.focus_editor()
                except Exception as e:
                    logger.error("Failed executing followup from CTA: %s", e)
        elif action_type == "RESUME_CADENCE":
            if self._current_app_id:
                self._on_resume_cadence(self._current_app_id)
        elif action_type == "PAUSE_CADENCE":
            if self._current_app_id:
                self._on_pause_cadence(self._current_app_id)
        elif action_type == "REVIEW_ATTACHMENT":
            pass

    def _on_ai_copilot_prompt(self, app_id: int, prompt: str):
        """Generates RAG reply based on conversation history and candidate profile."""
        self._copilot_worker = _AICopilotWorker(self._outreach_svc, app_id, prompt)
        self._copilot_worker.finished.connect(self._on_copilot_finished)
        self._copilot_worker.error.connect(self._on_copilot_error)
        self._copilot_worker.start()

    def _on_copilot_finished(self, result: dict):
        body = result.get("body_text", "")
        if body:
            self._composer.set_reply_text(body)
        else:
            self._composer.set_ai_generating(False)

    def _on_copilot_error(self, err: str):
        self._composer.set_ai_generating(False)
        self._composer.on_send_error(f"AI Copilot failed: {err}")
