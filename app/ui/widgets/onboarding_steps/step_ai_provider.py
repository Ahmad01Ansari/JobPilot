"""
Step 2: AI Provider Configuration (Screening & Q&A Engine).
Adheres strictly to DesignUI.md (Obsidian #0F1117, Charcoal #161B22, Safety Orange #FF5F15).
Runs BEFORE resume extraction; supports Ollama local, Groq, NVIDIA, OpenAI, Anthropic, Gemini.
"""

from typing import Dict, Any, Optional

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QFrame,
    QScrollArea
)
from app.ui.theme import COLORS
from app.services.setup.provider_definitions import get_all_providers, get_provider_by_id


class StepAIProviderWidget(QWidget):
    """Step 2: AI Provider configuration with connection test and manual continuation fallback."""
    ai_configured = Signal(bool)  # emits True if AI tested & ready, False if manual
    continue_manually_requested = Signal()

    def __init__(self, setup_service, parent=None):
        super().__init__(parent)
        self.setup_service = setup_service
        self._providers = get_all_providers()
        self.is_ai_tested = False
        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(14)

        # Header
        lbl_badge = QLabel("STEP 2: AI REASONING & EXTRACTION ENGINE")
        lbl_badge.setStyleSheet(f"""
            color: {COLORS['primary']};
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1px;
            background: {COLORS['primary_subtle']};
            padding: 3px 8px;
            border-radius: 4px;
        """)
        layout.addWidget(lbl_badge, alignment=Qt.AlignLeft)

        lbl_title = QLabel("AI Screening & Extraction Setup")
        lbl_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {COLORS['text']};")
        layout.addWidget(lbl_title)

        lbl_sub = QLabel(
            "Choose how JobPilot should process candidate data and screening questions. "
            "Configuring AI now unlocks automatic structured resume extraction in the next step."
        )
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(lbl_sub)

        # Provider Selection Card
        card = QFrame()
        card.setStyleSheet(self._card_qss())
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        lbl_prov = QLabel("Select Provider:")
        lbl_prov.setStyleSheet(self._section_title_qss())
        self.cmb_provider = QComboBox()
        self.cmb_provider.setStyleSheet(self._combo_qss())
        for p in self._providers:
            self.cmb_provider.addItem(p.name, p.id)
        self.cmb_provider.currentIndexChanged.connect(self._on_provider_changed)
        c_layout.addWidget(lbl_prov)
        c_layout.addWidget(self.cmb_provider)

        # Provider Description & External Links
        self.lbl_desc = QLabel("")
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        c_layout.addWidget(self.lbl_desc)

        link_row = QHBoxLayout()
        self.btn_get_key = QPushButton("Get API Key ↗")
        self.btn_get_key.setStyleSheet(self._link_btn_qss())
        self.btn_get_key.clicked.connect(self._open_key_url)

        self.btn_docs = QPushButton("Provider Docs ↗")
        self.btn_docs.setStyleSheet(self._link_btn_qss())
        self.btn_docs.clicked.connect(self._open_docs_url)

        link_row.addWidget(self.btn_get_key)
        link_row.addWidget(self.btn_docs)
        link_row.addStretch()
        c_layout.addLayout(link_row)

        # Model Input
        lbl_mod = QLabel("Model Name:")
        lbl_mod.setStyleSheet(self._section_title_qss())
        self.txt_model = QLineEdit()
        self.txt_model.setStyleSheet(self._input_qss())
        c_layout.addWidget(lbl_mod)
        c_layout.addWidget(self.txt_model)

        # Endpoint Input
        lbl_end = QLabel("API Endpoint:")
        lbl_end.setStyleSheet(self._section_title_qss())
        self.txt_endpoint = QLineEdit()
        self.txt_endpoint.setStyleSheet(self._input_qss())
        c_layout.addWidget(lbl_end)
        c_layout.addWidget(self.txt_endpoint)

        # API Key Input
        self.lbl_key = QLabel("API Key:")
        self.lbl_key.setStyleSheet(self._section_title_qss())
        self.txt_api_key = QLineEdit()
        self.txt_api_key.setEchoMode(QLineEdit.Password)
        self.txt_api_key.setStyleSheet(self._input_qss())
        c_layout.addWidget(self.lbl_key)
        c_layout.addWidget(self.txt_api_key)

        # Test Connection Button
        action_row = QHBoxLayout()
        self.btn_test = QPushButton("⚡ Test Connection")
        self.btn_test.setCursor(Qt.PointingHandCursor)
        self.btn_test.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                border-radius: 6px;
                padding: 7px 16px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        self.btn_test.clicked.connect(self._on_test_clicked)
        action_row.addWidget(self.btn_test)

        self.btn_manual = QPushButton("Continue Manually (Skip AI)")
        self.btn_manual.setCursor(Qt.PointingHandCursor)
        self.btn_manual.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                font-weight: 600;
                font-size: 11px;
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 7px 12px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.btn_manual.clicked.connect(self.continue_manually_requested.emit)
        action_row.addWidget(self.btn_manual)

        action_row.addStretch()
        c_layout.addLayout(action_row)

        # Test Results Frame
        self.result_frame = QFrame()
        self.result_frame.setVisible(False)
        self.result_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        r_layout = QVBoxLayout(self.result_frame)
        r_layout.setSpacing(4)

        self.lbl_res_header = QLabel("")
        self.lbl_res_header.setStyleSheet("font-size: 12px; font-weight: 700;")
        self.lbl_chk_conn = QLabel("")
        self.lbl_chk_conn.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        self.lbl_chk_model = QLabel("")
        self.lbl_chk_model.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")

        r_layout.addWidget(self.lbl_res_header)
        r_layout.addWidget(self.lbl_chk_conn)
        r_layout.addWidget(self.lbl_chk_model)
        c_layout.addWidget(self.result_frame)

        layout.addWidget(card)

        # Transparency Notice
        priv_card = QFrame()
        priv_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 8px;
                padding: 10px 14px;
            }}
        """)
        p_layout = QVBoxLayout(priv_card)
        lbl_p_title = QLabel("🔒 Privacy Notice:")
        lbl_p_title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['text']};")
        lbl_p_body = QLabel(
            "Contact info and credentials are never transmitted. For 100% offline private inference, select Ollama."
        )
        lbl_p_body.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        p_layout.addWidget(lbl_p_title)
        p_layout.addWidget(lbl_p_body)
        layout.addWidget(priv_card)

        scroll.setWidget(container)
        root_layout.addWidget(scroll)

        self._on_provider_changed(0)

    def _on_provider_changed(self, index: int):
        provider_id = self.cmb_provider.currentData()
        meta = get_provider_by_id(provider_id)
        if not meta:
            return

        self.txt_endpoint.setText(meta.default_endpoint)
        self.txt_model.setText(meta.default_model)
        self.lbl_desc.setText(meta.description)
        self.txt_api_key.setEnabled(meta.requires_api_key)
        self.lbl_key.setText("API Key:" if meta.requires_api_key else "API Key: (Not required for Ollama)")
        self.btn_get_key.setVisible(bool(meta.api_key_url))
        self.btn_docs.setVisible(bool(meta.documentation_url))
        self.result_frame.setVisible(False)
        self.is_ai_tested = False

    def _open_key_url(self):
        meta = get_provider_by_id(self.cmb_provider.currentData())
        if meta and meta.api_key_url:
            QDesktopServices.openUrl(QUrl(meta.api_key_url))

    def _open_docs_url(self):
        meta = get_provider_by_id(self.cmb_provider.currentData())
        if meta and meta.documentation_url:
            QDesktopServices.openUrl(QUrl(meta.documentation_url))

    def _on_test_clicked(self):
        provider_id = self.cmb_provider.currentData()
        key = self.txt_api_key.text().strip()
        endpoint = self.txt_endpoint.text().strip()
        model = self.txt_model.text().strip()

        self.btn_test.setEnabled(False)
        self.lbl_res_header.setText("⏳ Connecting and pinging model...")
        self.lbl_res_header.setStyleSheet(f"color: {COLORS['info']};")
        self.lbl_chk_conn.setText("• Validating API endpoint...")
        self.lbl_chk_model.setText("• Testing chat completions...")
        self.result_frame.setVisible(True)

        ok, err, caps = self.setup_service.save_ai_provider_step(
            provider=provider_id,
            api_key=key if key else None,
            endpoint=endpoint if endpoint else None,
            model=model if model else None,
            skip=False
        )
        self.btn_test.setEnabled(True)

        if ok:
            self.lbl_res_header.setText(f"✓ Connection successful ({provider_id})!")
            self.lbl_res_header.setStyleSheet(f"color: {COLORS['success']};")
            self.lbl_chk_conn.setText("✓ Model available & endpoint reached")
            self.lbl_chk_model.setText("✓ Text generation available for resume extraction")
            self.is_ai_tested = True
            self.ai_configured.emit(True)
        else:
            self.lbl_res_header.setText(f"❌ Connection failed: {err or 'Could not reach endpoint'}")
            self.lbl_res_header.setStyleSheet(f"color: {COLORS['danger']};")
            self.lbl_chk_conn.setText("⚠ Please verify endpoint URL, network connectivity, or API key.")
            self.lbl_chk_model.setText("ℹ You can also click 'Continue Manually' to proceed without AI.")
            self.is_ai_tested = False
            self.ai_configured.emit(False)

    def get_ai_payload(self) -> Dict[str, Any]:
        return {
            "provider": self.cmb_provider.currentData(),
            "api_key": self.txt_api_key.text().strip(),
            "endpoint": self.txt_endpoint.text().strip(),
            "model": self.txt_model.text().strip(),
            "is_tested": self.is_ai_tested,
        }

    # Stylesheet Helpers

    def _card_qss(self) -> str:
        return f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """

    def _section_title_qss(self) -> str:
        return f"font-size: 12px; font-weight: 700; color: {COLORS['text']};"

    def _input_qss(self) -> str:
        return f"""
            QLineEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS['primary']};
            }}
        """

    def _combo_qss(self) -> str:
        return f"""
            QComboBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
        """

    def _link_btn_qss(self) -> str:
        return f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['primary']};
                font-size: 11px;
                font-weight: 700;
                border: none;
                text-decoration: underline;
                padding: 0 4px;
            }}
            QPushButton:hover {{
                color: {COLORS['primary_hover']};
            }}
        """
