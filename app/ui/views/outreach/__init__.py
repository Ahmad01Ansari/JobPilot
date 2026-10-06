"""Outreach Center — Modular UI Component Package.

Replaces the monolithic outreach_view.py with a component-driven architecture:

    command_header        — Top bar with metrics, sync button, and New Outreach action.
    conversation_inbox    — Searchable, filterable conversation card list.
    thread_view           — Clean email thread with attachment chips and resume badges.
    inline_reply_composer — Restart-safe reply editor with autosave.
    context_panel         — Right drawer: Next Action, Application, Contact, Cadence.
    composer_dialog       — Modern ATS-style New Outreach composer dialog.
    workspace             — 3-zone QSplitter orchestrator (the new OutreachView).
"""

from app.ui.views.outreach.command_header import CommandHeader
from app.ui.views.outreach.composer_dialog import OutreachComposerDialog
from app.ui.views.outreach.context_panel import ContextPanel
from app.ui.views.outreach.conversation_inbox import ConversationInbox
from app.ui.views.outreach.inline_reply_composer import InlineReplyComposer
from app.ui.views.outreach.modern_popup import ModernPopup
from app.ui.views.outreach.thread_view import ThreadView
from app.ui.views.outreach.workspace import OutreachWorkspace

__all__ = [
    "CommandHeader",
    "OutreachComposerDialog",
    "ContextPanel",
    "ConversationInbox",
    "InlineReplyComposer",
    "ModernPopup",
    "ThreadView",
    "OutreachWorkspace",
]
