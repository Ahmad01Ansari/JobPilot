"""AI screening, LLM provider cards, model discovery, and connection diagnostics section."""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.ai.provider_registry import AIProviderRegistry, ProviderDefinition
from app.services.ai_service import DEFAULT_OLLAMA_URL, UniversalAIService
from app.services.secrets_service import SecretsService
from app.ui.theme import COLORS
from app.ui.views.settings.dialogs.provider_setup_dialog import ProviderSetupDialog
from app.ui.views.settings.workers.ai_test_worker import AITestWorker
from app.ui.views.settings.workers.model_discovery_worker import ModelDiscoveryWorker


class ProviderCard(QFrame):
    """Selectable provider card for local, cloud, or custom inference engines."""

    clicked = Signal(str)

    def __init__(
        self,
        provider: ProviderDefinition,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.provider = provider
        self.provider_id = provider.id
        self._is_selected = False
        self._is_default = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("ProviderCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(130, 82)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        lbl_title = QLabel(self.provider.display_name.split(" ")[0])
        lbl_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        layout.addWidget(lbl_title)

        if self.provider.is_local:
            badge_text = "● Local"
            badge_color = COLORS.get('success', '#2EA043')
        elif self.provider.category == "custom":
            badge_text = "Self-Hosted"
            badge_color = COLORS.get('warning', '#D29922')
        else:
            badge_text = "Cloud API"
            badge_color = COLORS.get('info', '#388BFD')

        lbl_badge = QLabel(badge_text)
        lbl_badge.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {badge_color};")
        layout.addWidget(lbl_badge)

        self.lbl_default_badge = QLabel("★ Default Engine")
        self.lbl_default_badge.setStyleSheet(f"""
            background-color: #2EA04322;
            color: {COLORS.get('success', '#2EA043')};
            border: 1px solid {COLORS.get('success', '#2EA043')};
            border-radius: 4px;
            font-size: 9px;
            font-weight: 700;
            padding: 1px 4px;
        """)
        self.lbl_default_badge.setVisible(False)
        layout.addWidget(self.lbl_default_badge)

        layout.addStretch()
        self.update_style()

    def set_selected(self, selected: bool) -> None:
        self._is_selected = selected
        self.update_style()

    def set_is_default(self, is_default: bool) -> None:
        self._is_default = is_default
        self.lbl_default_badge.setVisible(is_default)
        self.update_style()

    def update_style(self) -> None:
        if self._is_selected:
            self.setStyleSheet(f"""
                QFrame#ProviderCard {{
                    background-color: {COLORS.get('surface_active', '#FF5F1522')};
                    border: 2px solid {COLORS.get('accent', '#FF5F15')};
                    border-radius: 8px;
                }}
            """)
        elif self._is_default:
            self.setStyleSheet(f"""
                QFrame#ProviderCard {{
                    background-color: {COLORS.get('surface_alt', '#1C2128')};
                    border: 1.5px solid {COLORS.get('success', '#2EA043')};
                    border-radius: 8px;
                }}
                QFrame#ProviderCard:hover {{
                    border-color: {COLORS.get('border_light', '#333A46')};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#ProviderCard {{
                    background-color: {COLORS.get('surface_alt', '#1C2128')};
                    border: 1px solid {COLORS.get('border', '#262C36')};
                    border-radius: 8px;
                }}
                QFrame#ProviderCard:hover {{
                    border-color: {COLORS.get('border_light', '#333A46')};
                }}
            """)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.provider_id)
        super().mousePressEvent(event)


class AISection(QWidget):
    """Universal AI configuration section supporting local, cloud, and self-hosted inference."""

    changed = Signal()
    saved = Signal()
    test_completed = Signal(bool, float)  # (success: bool, latency_ms: float)
    wizard_requested = Signal()

    def __init__(
        self,
        ai_service: UniversalAIService,
        secrets_service: SecretsService,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.ai_service = ai_service
        self.secrets_service = secrets_service
        self._cards: Dict[str, ProviderCard] = {}
        self._test_worker: Optional[AITestWorker] = None
        self._discovery_worker: Optional[ModelDiscoveryWorker] = None
        self._current_filter = "all"

        self._mask_timer = QTimer(self)
        self._mask_timer.setSingleShot(True)
        self._mask_timer.timeout.connect(self._auto_mask_api_key)

        self._active_provider = ""
        self._default_provider = "ollama"
        self._provider_drafts: Dict[str, Dict[str, Any]] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 24, 16)
        layout.setSpacing(16)

        # Header
        lbl_head = QLabel("AI Screening & Q&A Engine")
        lbl_head.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel(
            "Configure local inference (Ollama), cloud LLM providers (Groq, xAI, OpenAI, Gemini, NVIDIA NIM, OpenRouter, DeepSeek), "
            "or self-hosted OpenAI-compatible endpoints."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        layout.addWidget(lbl_desc)

        # Category Filter Row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.btn_filter_all = QPushButton("All Providers")
        self.btn_filter_local = QPushButton("Local (Ollama)")
        self.btn_filter_cloud = QPushButton("Cloud APIs")
        self.btn_filter_custom = QPushButton("Custom Server")

        for b, cat in [
            (self.btn_filter_all, "all"),
            (self.btn_filter_local, "local"),
            (self.btn_filter_cloud, "cloud"),
            (self.btn_filter_custom, "custom"),
        ]:
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, c=cat: self._apply_category_filter(c))
            filter_row.addWidget(b)

        filter_row.addStretch()
        layout.addLayout(filter_row)
        self._update_filter_button_styles()

        # Provider Cards Scroll Row
        cards_scroll = QScrollArea()
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setFixedHeight(102)
        cards_scroll.setFrameShape(QFrame.NoFrame)
        cards_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        cards_container = QWidget()
        cards_container.setStyleSheet("background: transparent;")
        cards_layout = QHBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(10)

        for provider_def in AIProviderRegistry.list_providers():
            card = ProviderCard(provider_def, self)
            card.clicked.connect(self._select_provider)
            cards_layout.addWidget(card)
            self._cards[provider_def.id] = card

        cards_layout.addStretch()
        cards_scroll.setWidget(cards_container)
        layout.addWidget(cards_scroll)

        # Active Provider Banner & Action Links
        banner_card = QFrame()
        banner_card.setStyleSheet(f"""
            background-color: {COLORS.get('surface_alt', '#1C2128')};
            border: 1px solid {COLORS.get('border', '#262C36')};
            border-radius: 8px;
            padding: 8px 12px;
        """)
        b_layout = QHBoxLayout(banner_card)
        b_layout.setContentsMargins(8, 6, 8, 6)
        b_layout.setSpacing(10)

        self.lbl_active_provider_title = QLabel("Provider: Ollama")
        self.lbl_active_provider_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        b_layout.addWidget(self.lbl_active_provider_title)

        self.lbl_capability_badge = QLabel("Verified Chat & Structured Output")
        self.lbl_capability_badge.setStyleSheet(f"""
            background-color: {COLORS.get('surface', '#161B22')};
            color: {COLORS.get('info', '#388BFD')};
            border: 1px solid {COLORS.get('border', '#262C36')};
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
            padding: 2px 6px;
        """)
        b_layout.addWidget(self.lbl_capability_badge)

        self.lbl_default_badge = QLabel("○ Standby Provider")
        self.lbl_default_badge.setStyleSheet(f"""
            background-color: {COLORS.get('surface', '#161B22')};
            color: {COLORS.get('text_muted', '#8B949E')};
            border: 1px solid {COLORS.get('border', '#262C36')};
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
            padding: 2px 6px;
        """)
        b_layout.addWidget(self.lbl_default_badge)
        b_layout.addStretch()

        self.btn_pricing_link = QPushButton("💳 View Official Pricing")
        self.btn_pricing_link.setCursor(Qt.PointingHandCursor)
        self.btn_pricing_link.setStyleSheet(self._secondary_btn_style())
        self.btn_pricing_link.clicked.connect(self._open_pricing_link)
        b_layout.addWidget(self.btn_pricing_link)

        self.btn_setup_guide = QPushButton("📖 Setup Guide")
        self.btn_setup_guide.setCursor(Qt.PointingHandCursor)
        self.btn_setup_guide.setStyleSheet(self._secondary_btn_style())
        self.btn_setup_guide.clicked.connect(self._open_setup_guide)
        b_layout.addWidget(self.btn_setup_guide)

        layout.addWidget(banner_card)

        # Configuration Card
        config_card = QFrame()
        config_card.setObjectName("AIConfigCard")
        config_card.setStyleSheet(f"""
            QFrame#AIConfigCard {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
                padding: 14px 16px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                padding: 0;
            }}
        """)
        c_layout = QVBoxLayout(config_card)
        c_layout.setContentsMargins(10, 10, 10, 10)
        c_layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(12)

        # Hidden or sync provider combo
        self.combo_ai_provider = QComboBox()
        self.combo_ai_provider.addItems([p.id for p in AIProviderRegistry.list_providers()])
        self.combo_ai_provider.setVisible(False)
        self.combo_ai_provider.currentTextChanged.connect(self._on_provider_combo_changed)

        # Model row with Copy + Discover buttons
        model_container = QWidget()
        m_layout = QHBoxLayout(model_container)
        m_layout.setContentsMargins(0, 0, 0, 0)
        m_layout.setSpacing(8)

        self.combo_ai_model = QComboBox()
        self.combo_ai_model.setEditable(True)
        self.combo_ai_model.setFixedHeight(34)
        self.combo_ai_model.setStyleSheet(self._input_style())
        self.combo_ai_model.currentTextChanged.connect(lambda _: self.changed.emit())
        m_layout.addWidget(self.combo_ai_model, 1)

        self.btn_copy_model = QPushButton("📋 Copy Model")
        self.btn_copy_model.setToolTip("Copy active model name to clipboard")
        self.btn_copy_model.setCursor(Qt.PointingHandCursor)
        self.btn_copy_model.setFixedSize(115, 34)
        self.btn_copy_model.setStyleSheet(self._secondary_btn_style())
        self.btn_copy_model.clicked.connect(self._copy_model_name)
        m_layout.addWidget(self.btn_copy_model)

        self.btn_refresh = QPushButton("⟳ Discover Models")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setFixedSize(135, 34)
        self.btn_refresh.setStyleSheet(self._secondary_btn_style())
        self.btn_refresh.clicked.connect(self._discover_models)
        m_layout.addWidget(self.btn_refresh)
        form.addRow("<b>Model Name:</b>", model_container)

        # Endpoint URL with Copy + Reset buttons
        url_container = QWidget()
        u_layout = QHBoxLayout(url_container)
        u_layout.setContentsMargins(0, 0, 0, 0)
        u_layout.setSpacing(8)

        self.txt_ai_url = QLineEdit(DEFAULT_OLLAMA_URL)
        self.txt_ai_url.setFixedHeight(34)
        self.txt_ai_url.setPlaceholderText("e.g. http://localhost:11434/v1")
        self.txt_ai_url.setStyleSheet(self._input_style())
        self.txt_ai_url.textChanged.connect(lambda _: self.changed.emit())
        u_layout.addWidget(self.txt_ai_url, 1)

        self.btn_copy_url = QPushButton("📋 Copy URL")
        self.btn_copy_url.setToolTip("Copy endpoint URL to clipboard")
        self.btn_copy_url.setCursor(Qt.PointingHandCursor)
        self.btn_copy_url.setFixedSize(115, 34)
        self.btn_copy_url.setStyleSheet(self._secondary_btn_style())
        self.btn_copy_url.clicked.connect(self._copy_endpoint_url)
        u_layout.addWidget(self.btn_copy_url)

        self.btn_reset_url = QPushButton("↺ Reset URL")
        self.btn_reset_url.setToolTip("Reset to provider default URL")
        self.btn_reset_url.setCursor(Qt.PointingHandCursor)
        self.btn_reset_url.setFixedSize(135, 34)
        self.btn_reset_url.setStyleSheet(self._secondary_btn_style())
        self.btn_reset_url.clicked.connect(self._reset_provider_url)
        u_layout.addWidget(self.btn_reset_url)
        form.addRow("<b>Endpoint URL:</b>", url_container)

        # API Key with Show + Clear buttons (identical button widths to preserve input box symmetry)
        key_container = QWidget()
        k_layout = QHBoxLayout(key_container)
        k_layout.setContentsMargins(0, 0, 0, 0)
        k_layout.setSpacing(8)

        self.txt_ai_key = QLineEdit()
        self.txt_ai_key.setFixedHeight(34)
        self.txt_ai_key.setEchoMode(QLineEdit.Password)
        self.txt_ai_key.setPlaceholderText("Leave empty for Ollama or enter API key")
        self.txt_ai_key.setStyleSheet(self._input_style())
        self.txt_ai_key.textChanged.connect(lambda _: self.changed.emit())
        k_layout.addWidget(self.txt_ai_key, 1)

        self.btn_toggle_key = QPushButton("👁 Show Key")
        self.btn_toggle_key.setToolTip("Show API key temporarily for 10 seconds")
        self.btn_toggle_key.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_key.setFixedSize(115, 34)
        self.btn_toggle_key.setStyleSheet(self._secondary_btn_style())
        self.btn_toggle_key.clicked.connect(self._toggle_api_key_visibility)
        k_layout.addWidget(self.btn_toggle_key)

        self.btn_clear_key = QPushButton("🗑 Clear Key")
        self.btn_clear_key.setToolTip("Clear the API key field for this provider")
        self.btn_clear_key.setCursor(Qt.PointingHandCursor)
        self.btn_clear_key.setFixedSize(135, 34)
        self.btn_clear_key.setStyleSheet(self._secondary_btn_style())
        self.btn_clear_key.clicked.connect(self._clear_api_key)
        k_layout.addWidget(self.btn_clear_key)
        form.addRow("<b>API Key:</b>", key_container)

        c_layout.addLayout(form)

        # Action Buttons Row: same row, uniform height, equal spacing
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)

        self.btn_test = QPushButton("⚡ Test Connection")
        self.btn_test.setCursor(Qt.PointingHandCursor)
        self.btn_test.setFixedHeight(36)
        self.btn_test.setMinimumWidth(150)
        self.btn_test.setStyleSheet(self._primary_btn_style())
        self.btn_test.clicked.connect(self._test_connection)
        actions_row.addWidget(self.btn_test)

        self.btn_save_provider = QPushButton("💾 Save Provider Settings")
        self.btn_save_provider.setToolTip("Save configuration and credentials for the current provider")
        self.btn_save_provider.setCursor(Qt.PointingHandCursor)
        self.btn_save_provider.setFixedHeight(36)
        self.btn_save_provider.setMinimumWidth(170)
        self.btn_save_provider.setStyleSheet(self._accent_btn_style())
        self.btn_save_provider.clicked.connect(self._save_provider_settings)
        actions_row.addWidget(self.btn_save_provider)

        self.btn_set_default = QPushButton("★ Set as Default Engine")
        self.btn_set_default.setToolTip("Set this provider and model as the system-wide default AI engine for all JobPilot applications")
        self.btn_set_default.setCursor(Qt.PointingHandCursor)
        self.btn_set_default.setFixedHeight(36)
        self.btn_set_default.setMinimumWidth(185)
        self.btn_set_default.clicked.connect(self._set_as_default_engine)
        actions_row.addWidget(self.btn_set_default)

        self.btn_reset_provider = QPushButton("↺ Reset Provider Defaults")
        self.btn_reset_provider.setToolTip("Reset model and URL to registry defaults for this provider")
        self.btn_reset_provider.setCursor(Qt.PointingHandCursor)
        self.btn_reset_provider.setFixedHeight(36)
        self.btn_reset_provider.setMinimumWidth(170)
        self.btn_reset_provider.setStyleSheet(self._secondary_btn_style())
        self.btn_reset_provider.clicked.connect(self._reset_provider_defaults)
        actions_row.addWidget(self.btn_reset_provider)

        actions_row.addStretch()
        c_layout.addLayout(actions_row)

        # Status Message Container: visible just below the action row at equal distance
        status_box = QFrame()
        status_box.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                padding: 6px 12px;
                margin-top: 4px;
            }}
        """)
        s_layout = QHBoxLayout(status_box)
        s_layout.setContentsMargins(6, 4, 6, 4)

        self.lbl_diag_status = QLabel("Status: Not tested")
        self.lbl_diag_status.setWordWrap(True)
        self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        s_layout.addWidget(self.lbl_diag_status, 1)

        c_layout.addWidget(status_box)
        layout.addWidget(config_card)

        # Transparent Data Notice Card
        self.privacy_card = QFrame()
        self.privacy_card.setStyleSheet(f"""
            background-color: {COLORS.get('surface_alt', '#1C2128')};
            border: 1px solid {COLORS.get('border', '#262C36')};
            border-radius: 8px;
            padding: 10px 14px;
        """)
        p_layout = QVBoxLayout(self.privacy_card)
        p_layout.setContentsMargins(8, 6, 8, 6)
        p_layout.setSpacing(4)

        self.lbl_privacy_title = QLabel("🔒 Local Privacy Guarantee")
        self.lbl_privacy_title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        p_layout.addWidget(self.lbl_privacy_title)

        self.lbl_privacy_desc = QLabel(
            "Local inference executes entirely on your computer. Zero prompt or resume data is transmitted over the internet."
        )
        self.lbl_privacy_desc.setWordWrap(True)
        self.lbl_privacy_desc.setStyleSheet(f"font-size: 11px; color: {COLORS.get('text_muted', '#8B949E')};")
        p_layout.addWidget(self.lbl_privacy_desc)
        layout.addWidget(self.privacy_card)

        # Candidate Onboarding Setup Wizard Banner
        wizard_card = QFrame()
        wizard_card.setObjectName("AIWizardCard")
        wizard_card.setStyleSheet(f"""
            QFrame#AIWizardCard {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
                padding: 12px 14px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                padding: 0;
            }}
        """)
        w_layout = QHBoxLayout(wizard_card)
        w_layout.setContentsMargins(8, 8, 8, 8)
        w_layout.setSpacing(14)

        w_text_layout = QVBoxLayout()
        lbl_w_title = QLabel("Candidate Profile & Setup Wizard")
        lbl_w_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        w_text_layout.addWidget(lbl_w_title)

        lbl_w_desc = QLabel("Re-run the initial onboarding wizard to calibrate AI screening defaults from your resume.")
        lbl_w_desc.setStyleSheet(f"font-size: 11px; color: {COLORS.get('text_muted', '#8B949E')};")
        w_text_layout.addWidget(lbl_w_desc)
        w_layout.addLayout(w_text_layout, 1)

        btn_launch = QPushButton("🚀 Open Setup Wizard")
        btn_launch.setCursor(Qt.PointingHandCursor)
        btn_launch.setStyleSheet(self._accent_btn_style())
        btn_launch.clicked.connect(self.wizard_requested.emit)
        w_layout.addWidget(btn_launch)
        layout.addWidget(wizard_card)

        layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

        # Initialize with Ollama
        self._select_provider("ollama")

    # -------------------------------------------------------------------------
    # Filtering & Selection
    # -------------------------------------------------------------------------
    def _apply_category_filter(self, category: str) -> None:
        self._current_filter = category
        self._update_filter_button_styles()

        for pid, card in self._cards.items():
            if category == "all":
                card.setVisible(True)
            elif category == "local":
                card.setVisible(card.provider.is_local)
            elif category == "cloud":
                card.setVisible(card.provider.category == "cloud")
            elif category == "custom":
                card.setVisible(card.provider.category == "custom")

    def _update_filter_button_styles(self) -> None:
        btns = [
            (self.btn_filter_all, "all"),
            (self.btn_filter_local, "local"),
            (self.btn_filter_cloud, "cloud"),
            (self.btn_filter_custom, "custom"),
        ]
        for b, cat in btns:
            if self._current_filter == cat:
                b.setStyleSheet(f"""
                    background-color: {COLORS.get('accent', '#FF5F15')};
                    color: #FFFFFF;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 5px 12px;
                    border: none;
                    border-radius: 6px;
                """)
            else:
                b.setStyleSheet(f"""
                    background-color: {COLORS.get('surface_alt', '#1C2128')};
                    color: {COLORS.get('text_muted', '#8B949E')};
                    font-size: 11px;
                    font-weight: 600;
                    padding: 5px 12px;
                    border: 1px solid {COLORS.get('border', '#262C36')};
                    border-radius: 6px;
                """)

    def _update_default_badges(self) -> None:
        for pid, card in self._cards.items():
            card.set_is_default(pid == self._default_provider)

        is_def = (self._active_provider == self._default_provider)
        if is_def:
            self.lbl_default_badge.setText("★ Active Default Engine")
            self.lbl_default_badge.setStyleSheet(f"""
                background-color: #2EA04322;
                color: {COLORS.get('success', '#2EA043')};
                border: 1px solid {COLORS.get('success', '#2EA043')};
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 6px;
            """)
            self.btn_set_default.setText("★ Active Default Engine")
            self.btn_set_default.setEnabled(False)
            self.btn_set_default.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS.get('surface_alt', '#1C2128')};
                    color: {COLORS.get('success', '#2EA043')};
                    font-weight: 700;
                    font-size: 12px;
                    border: 1px solid {COLORS.get('success', '#2EA043')};
                    border-radius: 6px;
                    padding: 0 14px;
                }}
            """)
        else:
            self.lbl_default_badge.setText("○ Standby Provider")
            self.lbl_default_badge.setStyleSheet(f"""
                background-color: {COLORS.get('surface', '#161B22')};
                color: {COLORS.get('text_muted', '#8B949E')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 2px 6px;
            """)
            self.btn_set_default.setText("★ Set as Default Engine")
            self.btn_set_default.setEnabled(True)
            self.btn_set_default.setStyleSheet(f"""
                QPushButton {{
                    background-color: #238636;
                    color: #FFFFFF;
                    font-weight: 700;
                    font-size: 12px;
                    border-radius: 6px;
                    padding: 0 14px;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: #2EA043;
                }}
                QPushButton:pressed {{
                    background-color: #1F7F32;
                }}
            """)

    def _set_as_default_engine(self) -> None:
        """Sets current provider and model as the system-wide default AI engine for JobPilot applications."""
        provider = self._active_provider
        preset = AIProviderRegistry.get_provider(provider)
        api_url = self.txt_ai_url.text().strip()
        model = self.combo_ai_model.currentText().strip()
        raw_key = self.txt_ai_key.text().strip()

        if not (api_url.startswith("http://") or api_url.startswith("https://")):
            def_url = preset.default_base_url if preset else DEFAULT_OLLAMA_URL
            self.lbl_diag_status.setText(
                f"✕ Cannot set default: Invalid Endpoint URL '{api_url}'. "
                f"Must start with 'http://' or 'https://'. Default for {preset.display_name if preset else provider} is '{def_url}'."
            )
            self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('danger', '#F85149')};")
            return

        self.save_all_drafts()
        self._default_provider = provider

        clean_key = None if raw_key == "••••••••" else (raw_key if raw_key else None)
        self.ai_service.save_config(
            enabled=True,
            provider=provider,
            model=model,
            api_url=api_url,
            api_key=clean_key,
        )

        has_key = bool(clean_key or raw_key == "••••••••")
        self._provider_drafts[provider] = {
            "model": model,
            "api_url": api_url,
            "api_key": "••••••••" if has_key else "",
        }

        if clean_key:
            self.txt_ai_key.setText("••••••••")

        self._update_default_badges()

        display_name = preset.display_name if preset else provider.capitalize()
        self.lbl_diag_status.setText(
            f"★ {display_name} ({model}) is now the system default AI engine for JobPilot applications."
        )
        self.lbl_diag_status.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS.get('success', '#2EA043')};")
        self.saved.emit()

    def _select_provider(self, provider_id: str) -> None:
        new_prov = provider_id.lower().strip()
        if new_prov == self._active_provider and self.combo_ai_provider.currentText() == new_prov:
            return

        # 0. Ensure password masking is restored before switching away
        self._auto_mask_api_key()

        # 1. Snapshot current fields for old active provider
        if self._active_provider:
            self._provider_drafts[self._active_provider] = {
                "model": self.combo_ai_model.currentText().strip(),
                "api_url": self.txt_ai_url.text().strip(),
                "api_key": self.txt_ai_key.text().strip(),
            }

        # 2. Update active provider and card highlights
        self._active_provider = new_prov
        for pid, card in self._cards.items():
            card.set_selected(pid == new_prov)

        # 3. Block signals while repopulating form
        self.combo_ai_provider.blockSignals(True)
        self.combo_ai_provider.setCurrentText(new_prov)
        self.combo_ai_provider.blockSignals(False)

        # 4. Load draft or stored configuration for new provider
        self._load_provider_fields(new_prov)
        self._update_default_badges()

        # 5. Reset status message for fresh provider view
        self.lbl_diag_status.setText("Status: Not tested")
        self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")

    def _on_provider_combo_changed(self, provider: str) -> None:
        self._select_provider(provider)

    def _load_provider_fields(self, provider_id: str) -> None:
        prov = provider_id.lower().strip()
        preset = AIProviderRegistry.get_provider(prov)
        if not preset:
            return

        self.lbl_active_provider_title.setText(f"Provider: {preset.display_name}")

        # Check if we have an in-memory draft first
        if prov in self._provider_drafts:
            draft = self._provider_drafts[prov]
            model_val = draft.get("model") or preset.default_model
            url_val = draft.get("api_url") or preset.default_base_url
            key_val = draft.get("api_key", "")
            if not key_val:
                saved_key = self.secrets_service.get_ai_secret(prov)
                key_val = "••••••••" if saved_key else ""
        else:
            # Query per-provider saved settings from DB and SecretsService
            prov_cfg = self.ai_service.get_provider_config(prov)
            model_val = prov_cfg.get("model") or preset.default_model
            url_val = prov_cfg.get("api_url") or preset.default_base_url
            saved_key = prov_cfg.get("api_key")
            key_val = "••••••••" if saved_key else ""

        # Populate suggested models
        self.combo_ai_model.blockSignals(True)
        self.combo_ai_model.clear()
        if preset.suggested_models:
            self.combo_ai_model.addItems(preset.suggested_models)
        elif preset.default_model:
            self.combo_ai_model.addItem(preset.default_model)

        model_str = str(model_val) if model_val is not None else ""
        idx = self.combo_ai_model.findData(model_str)
        if idx >= 0:
            self.combo_ai_model.setCurrentIndex(idx)
        else:
            idx = self.combo_ai_model.findText(model_str)
            if idx >= 0:
                self.combo_ai_model.setCurrentIndex(idx)
            else:
                self.combo_ai_model.setEditText(model_str)
        self.combo_ai_model.blockSignals(False)

        # Endpoint URL
        self.txt_ai_url.blockSignals(True)
        self.txt_ai_url.setText(url_val)
        if prov == "gemini":
            self.txt_ai_url.setEnabled(False)
            self.btn_refresh.setEnabled(False)
        else:
            self.txt_ai_url.setEnabled(True)
            self.btn_refresh.setEnabled(True)
        self.txt_ai_url.blockSignals(False)

        # Pricing button visibility
        self.btn_pricing_link.setVisible(bool(preset.pricing_url))

        # API Key field styling and value
        self.txt_ai_key.blockSignals(True)
        self.txt_ai_key.setText(key_val)
        if preset.requires_api_key:
            self.txt_ai_key.setPlaceholderText(f"Enter {preset.display_name} API key")
            self.txt_ai_key.setEnabled(True)
        else:
            self.txt_ai_key.setPlaceholderText("Optional / Not required for local inference")
            self.txt_ai_key.setEnabled(True)
        self.txt_ai_key.blockSignals(False)

        # Update privacy notice
        if preset.is_local:
            self.lbl_privacy_title.setText("🔒 Local Privacy Guarantee")
            self.lbl_privacy_desc.setText(
                "Local inference executes entirely on your computer. Zero prompt or resume data is transmitted over the internet."
            )
        else:
            self.lbl_privacy_title.setText("🌐 Third-Party Data Transmission Notice")
            self.lbl_privacy_desc.setText(
                f"Prompts and Q&A texts will be transmitted via encrypted HTTPS to {preset.display_name}. "
                "Consult the provider's privacy policy for details on inference data handling."
            )

    # -------------------------------------------------------------------------
    # Dialogs & Copy Helpers
    # -------------------------------------------------------------------------
    def _open_setup_guide(self) -> None:
        prov = self._active_provider
        preset = AIProviderRegistry.get_provider(prov)
        if preset:
            dialog = ProviderSetupDialog(preset, parent=self)
            dialog.exec_()

    def _open_pricing_link(self) -> None:
        prov = self._active_provider
        preset = AIProviderRegistry.get_provider(prov)
        if preset and preset.pricing_url:
            QDesktopServices.openUrl(QUrl(preset.pricing_url))

    def _copy_model_name(self) -> None:
        model = self.combo_ai_model.currentText().strip()
        if model:
            QGuiApplication.clipboard().setText(model)
            self.lbl_diag_status.setText(f"Copied model '{model}' to clipboard")
            self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('info', '#388BFD')};")

    def _copy_endpoint_url(self) -> None:
        url = self.txt_ai_url.text().strip()
        if url:
            QGuiApplication.clipboard().setText(url)
            self.lbl_diag_status.setText("Copied endpoint URL to clipboard")
            self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('info', '#388BFD')};")

    def _reset_provider_url(self) -> None:
        prov = self._active_provider
        preset = AIProviderRegistry.get_provider(prov)
        if preset:
            self.txt_ai_url.setText(preset.default_base_url)

    def _reset_provider_defaults(self) -> None:
        prov = self._active_provider
        preset = AIProviderRegistry.get_provider(prov)
        if preset:
            if prov in self._provider_drafts:
                del self._provider_drafts[prov]
            self.txt_ai_url.setText(preset.default_base_url)
            self.combo_ai_model.clear()
            if preset.suggested_models:
                self.combo_ai_model.addItems(preset.suggested_models)
            elif preset.default_model:
                self.combo_ai_model.addItem(preset.default_model)
            self.txt_ai_key.clear()
            self.lbl_diag_status.setText(f"Reset {preset.display_name} defaults")
            self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('info', '#388BFD')};")
            self.changed.emit()

    # -------------------------------------------------------------------------
    # Secret Key Masking & Worker Interactions
    # -------------------------------------------------------------------------
    def _clear_api_key(self) -> None:
        self.txt_ai_key.clear()
        self.txt_ai_key.setPlaceholderText(f"Enter API key for {self._active_provider}")
        if self._active_provider in self._provider_drafts:
            self._provider_drafts[self._active_provider]["api_key"] = ""
        self.lbl_diag_status.setText(f"Cleared API key for {self._active_provider}. Click 'Save Provider Settings' to commit.")
        self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('warning', '#D29922')};")
        self.changed.emit()

    def _toggle_api_key_visibility(self) -> None:
        if self.txt_ai_key.echoMode() == QLineEdit.Password:
            current_text = self.txt_ai_key.text().strip()
            if current_text == "••••••••" or not current_text:
                real_key = self.secrets_service.get_ai_secret(self._active_provider)
                if real_key:
                    self.txt_ai_key.blockSignals(True)
                    self.txt_ai_key.setText(real_key)
                    self.txt_ai_key.blockSignals(False)
            self.txt_ai_key.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_key.setText("👁 Hide Key")
            self.btn_toggle_key.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS.get('accent', '#FF5F15')}22;
                    border: 1px solid {COLORS.get('accent', '#FF5F15')};
                    color: {COLORS.get('accent', '#FF5F15')};
                    font-size: 12px;
                    font-weight: 600;
                    padding: 4px 8px;
                    border-radius: 6px;
                }}
            """)
            self._mask_timer.start(10000)
        else:
            self._auto_mask_api_key()

    def _auto_mask_api_key(self) -> None:
        current_text = self.txt_ai_key.text().strip()
        saved_key = self.secrets_service.get_ai_secret(self._active_provider)
        if current_text and (current_text == saved_key or current_text == "••••••••"):
            self.txt_ai_key.blockSignals(True)
            self.txt_ai_key.setText("••••••••")
            self.txt_ai_key.blockSignals(False)
        self.txt_ai_key.setEchoMode(QLineEdit.Password)
        self.btn_toggle_key.setText("👁 Show Key")
        self.btn_toggle_key.setStyleSheet(self._secondary_btn_style())
        self._mask_timer.stop()

    def _save_provider_settings(self) -> None:
        """Persists current provider settings and all session drafts immediately."""
        provider = self._active_provider
        preset = AIProviderRegistry.get_provider(provider)
        api_url = self.txt_ai_url.text().strip()
        model = self.combo_ai_model.currentText().strip()
        raw_key = self.txt_ai_key.text().strip()

        if not (api_url.startswith("http://") or api_url.startswith("https://")):
            def_url = preset.default_base_url if preset else DEFAULT_OLLAMA_URL
            self.lbl_diag_status.setText(
                f"✕ Cannot save: Invalid Endpoint URL '{api_url}'. "
                f"Must start with 'http://' or 'https://'. Default for {preset.display_name if preset else provider} is '{def_url}'."
            )
            self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('danger', '#F85149')};")
            return

        # 1. Persist background drafts first
        self.save_all_drafts()

        # 2. Persist provider settings
        clean_key = None if raw_key == "••••••••" else (raw_key if raw_key else None)
        if provider == self._default_provider:
            self.ai_service.save_config(
                enabled=True,
                provider=provider,
                model=model,
                api_url=api_url,
                api_key=clean_key,
            )
        else:
            if hasattr(self.ai_service, "save_provider_config"):
                self.ai_service.save_provider_config(
                    provider=provider,
                    model=model,
                    api_url=api_url,
                    api_key=clean_key,
                )
            else:
                self.ai_service.save_config(
                    enabled=True,
                    provider=self._default_provider,
                    model=model,
                    api_url=api_url,
                    api_key=clean_key,
                )

        # 3. Update in-memory draft
        has_key = bool(clean_key or raw_key == "••••••••")
        self._provider_drafts[provider] = {
            "model": model,
            "api_url": api_url,
            "api_key": "••••••••" if has_key else "",
        }

        if clean_key:
            self.txt_ai_key.setText("••••••••")

        display_name = preset.display_name if preset else provider.capitalize()
        self.lbl_diag_status.setText(f"✓ Configuration for {display_name} saved successfully.")
        self.lbl_diag_status.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS.get('success', '#2EA043')};")
        self.saved.emit()

    def _discover_models(self) -> None:
        provider = self._active_provider
        raw_key = self.txt_ai_key.text().strip()
        if raw_key == "••••••••":
            api_key = self.secrets_service.get_ai_secret(provider)
        else:
            api_key = raw_key if raw_key else None

        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("Discovering...")
        self.lbl_diag_status.setText("Querying model discovery endpoint...")
        self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('info', '#388BFD')};")

        self._discovery_worker = ModelDiscoveryWorker(
            endpoint_url=self.txt_ai_url.text().strip(),
            provider_id=provider,
            api_key=api_key,
            gateway=self.ai_service.gateway,
            parent=self,
        )
        self._discovery_worker.result.connect(self._on_models_discovered)
        self._discovery_worker.start()

    def _on_models_discovered(self, models: List[Dict[str, Any]], error: str) -> None:
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("⟳ Discover Models")
        if error:
            self.lbl_diag_status.setText(f"Discovery notice: {error}")
            self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('warning', '#D29922')};")
            return

        if models:
            self.combo_ai_model.clear()
            for m in models:
                label = f"{m['name']} ({m['size']})" if m.get("size") else m["name"]
                self.combo_ai_model.addItem(label, m["name"])
            self.lbl_diag_status.setText(f"Found {len(models)} models.")
            self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('success', '#2EA043')};")

    def _test_connection(self) -> None:
        provider = self._active_provider
        preset = AIProviderRegistry.get_provider(provider)
        api_url = self.txt_ai_url.text().strip()
        raw_key = self.txt_ai_key.text().strip()

        # Validate URL
        if not (api_url.startswith("http://") or api_url.startswith("https://")):
            def_url = preset.default_base_url if preset else DEFAULT_OLLAMA_URL
            self.lbl_diag_status.setText(
                f"✕ Cannot connect: Invalid Endpoint URL '{api_url}'. "
                f"Must start with 'http://' or 'https://'. For {preset.display_name if preset else provider}, the official URL is '{def_url}'. "
                "Did you accidentally paste a model name into the URL field?"
            )
            self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('danger', '#F85149')};")
            return

        if raw_key == "••••••••":
            api_key = self.secrets_service.get_ai_secret(provider)
        else:
            api_key = raw_key if raw_key else None

        if preset and preset.requires_api_key and not api_key:
            self.lbl_diag_status.setText(f"✕ {preset.display_name} requires an API key. Please enter your API key.")
            self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('danger', '#F85149')};")
            return

        model = self.combo_ai_model.currentText().strip()

        self.btn_test.setEnabled(False)
        self.lbl_diag_status.setText("Testing reachability & latency...")
        self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('info', '#388BFD')};")

        self._test_worker = AITestWorker(
            ai_service=self.ai_service,
            provider=provider,
            api_key=api_key,
            api_url=api_url,
            model=model,
            parent=self,
        )
        self._test_worker.result.connect(self._on_test_completed)
        self._test_worker.start()

    def _on_test_completed(self, success: bool, message: str, latency_ms: float) -> None:
        self.btn_test.setEnabled(True)
        lat_text = f" · {round(latency_ms)}ms" if latency_ms > 0 else ""
        if success:
            self.lbl_diag_status.setText(f"✓ Connected{lat_text}")
            self.lbl_diag_status.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS.get('success', '#2EA043')};")
        else:
            self.lbl_diag_status.setText(f"✕ {message}")
            self.lbl_diag_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('danger', '#F85149')};")
        self.test_completed.emit(success, latency_ms)

    # -------------------------------------------------------------------------
    # Values Serialization / Deserialization
    # -------------------------------------------------------------------------
    def save_all_drafts(self) -> None:
        """Persists any modified drafts across other providers configured in this session."""
        for pid, draft in self._provider_drafts.items():
            if pid == self._active_provider:
                continue
            key = draft.get("api_key", "").strip()
            self.ai_service.save_provider_config(
                provider=pid,
                model=draft.get("model"),
                api_url=draft.get("api_url"),
                api_key=key if key and key != "••••••••" else None,
            )

    def get_values(self) -> Dict[str, Any]:
        return {
            "provider": self._active_provider,
            "default_provider": self._default_provider,
            "model": self.combo_ai_model.currentText().strip(),
            "api_url": self.txt_ai_url.text().strip(),
            "api_key": self.txt_ai_key.text().strip(),
        }

    def load_values(self, config: Dict[str, Any]) -> None:
        self.blockSignals(True)
        self._provider_drafts.clear()
        prov = config.get("provider", "ollama").lower()
        self._default_provider = prov
        self._active_provider = prov
        for pid, card in self._cards.items():
            card.set_selected(pid == prov)

        self._load_provider_fields(prov)
        self._update_default_badges()

        if "api_url" in config and config["api_url"]:
            self.txt_ai_url.setText(config["api_url"])

        if "model" in config and config["model"]:
            model_name = config["model"]
            idx = self.combo_ai_model.findData(model_name)
            if idx >= 0:
                self.combo_ai_model.setCurrentIndex(idx)
            else:
                self.combo_ai_model.setEditText(model_name)

        if config.get("api_key"):
            self.txt_ai_key.setText("••••••••")
        else:
            saved_key = self.secrets_service.get_ai_secret(prov)
            self.txt_ai_key.setText("••••••••" if saved_key else "")

        self.blockSignals(False)

    def reset_to_defaults(self) -> None:
        self._provider_drafts.clear()
        self._default_provider = "ollama"
        self.load_values({
            "provider": "ollama",
            "model": "llama3.1:8b",
            "api_url": DEFAULT_OLLAMA_URL,
            "api_key": "",
        })
        self.changed.emit()

    # -------------------------------------------------------------------------
    # Styles
    # -------------------------------------------------------------------------
    def _input_style(self) -> str:
        return f"""
            QLineEdit, QComboBox {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                color: {COLORS.get('text', '#F0F6FC')};
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {COLORS.get('accent', '#FF5F15')};
            }}
        """

    def _primary_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS.get('accent', '#FF5F15')};
                border: none;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('accent_hover', '#E04F0B')};
            }}
        """

    def _accent_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS.get('accent', '#FF5F15')};
                border: none;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('accent_hover', '#E04F0B')};
            }}
        """

    def _secondary_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                font-weight: 600;
                font-size: 12px;
                padding: 6px 12px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
                border-color: {COLORS.get('border_light', '#333A46')};
            }}
        """
