"""
JobPilot Setup Wizard (v2.1) — Adaptive Setup Orchestrator.
Adheres strictly to DesignUI.md (Obsidian #0F1117, Charcoal #161B22, Safety Orange #FF5F15).
Correct 10-step sequence: Welcome -> AI -> Resume -> Extraction -> Profile -> Q&A -> Strategy -> Platforms -> Safety -> Readiness.
"""

import logging
from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QStackedWidget, QMessageBox
)

from app.ui.theme import COLORS
from app.services.setup.setup_service import SetupService
from app.services.setup.setup_requirements import RequirementStatus
from app.ui.widgets.onboarding_steps import (
    StepWelcomeWidget,
    StepAIProviderWidget,
    StepResumeWidget,
    StepExtractionProgressWidget,
    StepProfileWidget,
    StepQnAKnowledgeWidget,
    StepPreferencesWidget,
    StepPlatformsWidget,
    StepSafetyWidget,
    StepReadinessSummaryWidget,
)

logger = logging.getLogger(__name__)

STEP_KEYS = [
    "welcome",
    "ai_provider",
    "resume_ingest",
    "ai_extraction",
    "profile_review",
    "qna_knowledge",
    "job_strategy",
    "platforms",
    "safety",
    "readiness",
]

STEP_TITLES = [
    "1. Welcome",
    "2. AI Provider",
    "3. Resume Ingest",
    "4. AI Extraction",
    "5. Profile Review",
    "6. Q&A Knowledge",
    "7. Job Strategy",
    "8. Job Platforms",
    "9. Safety Limits",
    "10. Readiness",
]


class CompactRailItem(QFrame):
    """Compact navigation item on the left progress rail."""
    clicked = Signal(int)

    def __init__(self, step_idx: int, title: str, parent=None):
        super().__init__(parent)
        self.step_idx = step_idx
        self.title = title
        self.is_active = False
        self.is_completed = False
        self.is_skipped = False
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("compact_rail_item")
        self.setCursor(Qt.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        self.lbl_node = QLabel("○")
        self.lbl_node.setFixedWidth(16)
        self.lbl_node.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_node)

        self.lbl_title = QLabel(self.title)
        layout.addWidget(self.lbl_title)
        layout.addStretch()

        self.update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.step_idx)

    def set_state(self, active: bool, completed: bool, skipped: bool = False):
        self.is_active = active
        self.is_completed = completed
        self.is_skipped = skipped
        self.update_style()

    def update_style(self):
        if self.is_active:
            self.setStyleSheet(f"""
                #compact_rail_item {{
                    background-color: {COLORS['surface_alt']};
                    border-left: 3px solid {COLORS['primary']};
                    border-radius: 4px;
                }}
                #compact_rail_item QLabel {{
                    border: none;
                    background: transparent;
                    padding: 0;
                }}
            """)
            self.lbl_node.setText("●")
            self.lbl_node.setStyleSheet(f"color: {COLORS['primary']}; font-size: 11px;")
            self.lbl_title.setStyleSheet(f"color: {COLORS['text']}; font-weight: 700; font-size: 11px;")
        elif self.is_completed:
            self.setStyleSheet(f"""
                #compact_rail_item {{
                    background-color: transparent;
                    border: none;
                }}
                #compact_rail_item QLabel {{
                    border: none;
                    background: transparent;
                    padding: 0;
                }}
            """)
            self.lbl_node.setText("✓")
            self.lbl_node.setStyleSheet(f"color: {COLORS['success']}; font-size: 11px; font-weight: 800;")
            self.lbl_title.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        elif self.is_skipped:
            self.setStyleSheet(f"""
                #compact_rail_item {{
                    background-color: transparent;
                    border: none;
                }}
                #compact_rail_item QLabel {{
                    border: none;
                    background: transparent;
                    padding: 0;
                }}
            """)
            self.lbl_node.setText("—")
            self.lbl_node.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 11px;")
            self.lbl_title.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 11px;")
        else:
            self.setStyleSheet(f"""
                #compact_rail_item {{
                    background-color: transparent;
                    border: none;
                }}
                #compact_rail_item QLabel {{
                    border: none;
                    background: transparent;
                    padding: 0;
                }}
            """)
            self.lbl_node.setText("○")
            self.lbl_node.setStyleSheet(f"color: {COLORS['border_light']}; font-size: 11px;")
            self.lbl_title.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 11px;")


class OnboardingWizardDialog(QDialog):
    """The master 10-step adaptive setup wizard modal orchestrating setup domain capabilities."""
    onboarding_completed = Signal(dict)

    def __init__(self, setup_service: Optional[SetupService] = None, parent=None):
        super().__init__(parent)
        self.setup_service = setup_service or SetupService()
        self.current_step_idx = 0
        self.rail_items: List[CompactRailItem] = []
        self._current_resume_path: Optional[str] = None
        self._latest_extracted_profile: Dict[str, Any] = {}

        # Geometry per DesignUI.md
        self.setWindowTitle("JobPilot — Workspace Setup")
        self.resize(940, 680)
        self.setMinimumSize(880, 600)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
            }}
        """)

        self._init_ui()
        self._discover_and_adapt()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Header Bar
        top_bar = QFrame()
        top_bar.setFixedHeight(48)
        top_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(18, 0, 18, 0)

        lbl_logo = QLabel("⚡ JobPilot Setup Wizard")
        lbl_logo.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {COLORS['text']};")
        tb_layout.addWidget(lbl_logo)
        tb_layout.addStretch()

        self.lbl_step_counter = QLabel("Step 1 of 10")
        self.lbl_step_counter.setStyleSheet(f"""
            color: {COLORS['primary']};
            font-size: 11px;
            font-weight: 700;
            background: {COLORS['primary_subtle']};
            padding: 3px 10px;
            border-radius: 4px;
        """)
        tb_layout.addWidget(self.lbl_step_counter)
        root_layout.addWidget(top_bar)

        # 2. Main Body Split (Left Rail + Right Viewport)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Left Compact Progress Stepper Rail (200px fixed)
        self.rail_frame = QFrame()
        self.rail_frame.setFixedWidth(200)
        self.rail_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)
        rail_layout = QVBoxLayout(self.rail_frame)
        rail_layout.setContentsMargins(10, 16, 10, 16)
        rail_layout.setSpacing(2)

        lbl_rail_header = QLabel("SETUP PROGRESS")
        lbl_rail_header.setStyleSheet(f"font-size: 9px; font-weight: 800; color: {COLORS['text_muted']}; letter-spacing: 1px;")
        rail_layout.addWidget(lbl_rail_header)
        rail_layout.addSpacing(6)

        for idx, title in enumerate(STEP_TITLES):
            item = CompactRailItem(idx, title, self.rail_frame)
            item.clicked.connect(self._on_rail_item_clicked)
            self.rail_items.append(item)
            rail_layout.addWidget(item)

        rail_layout.addStretch()

        btn_reset = QPushButton("↺ Restart Setup")
        btn_reset.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_dark']};
                font-size: 10px;
                border: none;
                text-align: left;
                padding-left: 8px;
            }}
            QPushButton:hover {{
                color: {COLORS['warning']};
            }}
        """)
        btn_reset.clicked.connect(self._on_reset_wizard)
        rail_layout.addWidget(btn_reset)

        body.addWidget(self.rail_frame)

        # Right Step Content Stack (740px)
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {COLORS['background']};")

        # Instantiate Step Widgets in Correct Order
        self.step_welcome = StepWelcomeWidget()                               # 0
        self.step_ai = StepAIProviderWidget(self.setup_service)               # 1
        self.step_resume = StepResumeWidget(self.setup_service)               # 2
        self.step_extract = StepExtractionProgressWidget(self.setup_service)  # 3
        self.step_profile = StepProfileWidget(self.setup_service)             # 4
        self.step_qna = StepQnAKnowledgeWidget(self.setup_service)            # 5
        self.step_prefs = StepPreferencesWidget()                             # 6
        self.step_platforms = StepPlatformsWidget(self.setup_service)         # 7
        self.step_safety = StepSafetyWidget()                                 # 8
        self.step_readiness = StepReadinessSummaryWidget()                    # 9

        # Connect Step Signals
        self.step_ai.continue_manually_requested.connect(lambda: self._navigate_to_step(2))
        self.step_resume.resume_selected.connect(self._on_resume_selected)
        self.step_extract.extraction_completed.connect(self._on_extraction_completed)
        self.step_readiness.finish_requested.connect(self._on_finish_confirmed)
        self.step_readiness.tour_requested.connect(self._on_tour_requested)
        self.step_qna.qna_verified_completed.connect(self._discover_and_adapt)

        self.stack.addWidget(self.step_welcome)
        self.stack.addWidget(self.step_ai)
        self.stack.addWidget(self.step_resume)
        self.stack.addWidget(self.step_extract)
        self.stack.addWidget(self.step_profile)
        self.stack.addWidget(self.step_qna)
        self.stack.addWidget(self.step_prefs)
        self.stack.addWidget(self.step_platforms)
        self.stack.addWidget(self.step_safety)
        self.stack.addWidget(self.step_readiness)

        body.addWidget(self.stack)
        root_layout.addLayout(body)

        # 3. Bottom Navigation Dock (54px)
        dock = QFrame()
        dock.setFixedHeight(54)
        dock.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        d_layout = QHBoxLayout(dock)
        d_layout.setContentsMargins(18, 8, 18, 8)

        self.btn_exit = QPushButton("Exit and Save Progress")
        self.btn_exit.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.btn_exit.clicked.connect(self.close)
        d_layout.addWidget(self.btn_exit)

        d_layout.addStretch()

        self.btn_back = QPushButton("< Back")
        self.btn_back.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 11px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['primary']};
            }}
        """)
        self.btn_back.clicked.connect(self._go_back)
        d_layout.addWidget(self.btn_back)

        self.btn_skip = QPushButton("Skip Step")
        self.btn_skip.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: none;
                padding: 6px 10px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.btn_skip.clicked.connect(self._skip_current_step)
        d_layout.addWidget(self.btn_skip)

        self.btn_next = QPushButton("Continue →")
        self.btn_next.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                border-radius: 6px;
                padding: 7px 20px;
                font-weight: 800;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        self.btn_next.clicked.connect(self._go_next)
        d_layout.addWidget(self.btn_next)

        root_layout.addWidget(dock)

    # Adaptive State & Progress Synchronization

    def _discover_and_adapt(self):
        """Discovers existing database data and marks already-completed steps."""
        eval_report = self.setup_service.discover_current_state()

        completed_set = set(self.setup_service.state.completed_steps)
        if eval_report.requirements.get("candidate_profile", {}).status == RequirementStatus.READY:
            completed_set.add("profile_review")
        if eval_report.requirements.get("primary_resume", {}).status == RequirementStatus.READY:
            completed_set.add("resume_ingest")
        if eval_report.requirements.get("job_preferences", {}).status == RequirementStatus.READY:
            completed_set.add("job_strategy")
        if eval_report.requirements.get("ai_provider", {}).status == RequirementStatus.READY:
            completed_set.add("ai_provider")
        if eval_report.requirements.get("screening_qna", {}).status == RequirementStatus.READY:
            completed_set.add("qna_knowledge")

        skipped_set = set(self.setup_service.state.skipped_steps)

        for idx, key in enumerate(STEP_KEYS):
            is_comp = (key in completed_set)
            is_skip = (key in skipped_set)
            self.rail_items[idx].set_state(active=(idx == self.current_step_idx), completed=is_comp, skipped=is_skip)

        self._update_navigation_buttons()

    def _on_rail_item_clicked(self, step_idx: int):
        self._navigate_to_step(step_idx)

    def _navigate_to_step(self, step_idx: int):
        if 0 <= step_idx < len(STEP_KEYS):
            self.current_step_idx = step_idx
            self.stack.setCurrentIndex(step_idx)
            self.lbl_step_counter.setText(f"Step {step_idx + 1} of {len(STEP_KEYS)}")

            completed_set = set(self.setup_service.state.completed_steps)
            skipped_set = set(self.setup_service.state.skipped_steps)
            for idx, item in enumerate(self.rail_items):
                item.set_state(
                    active=(idx == step_idx),
                    completed=(STEP_KEYS[idx] in completed_set),
                    skipped=(STEP_KEYS[idx] in skipped_set)
                )

            self._update_navigation_buttons()

            # Trigger step-specific data loading
            if step_idx == 4:  # Candidate Profile Review
                self.step_profile.load_initial_data(self._latest_extracted_profile)
            elif step_idx == 5:  # Q&A Knowledge
                self.step_qna.load_knowledge_base()
            elif step_idx == 6:  # Job Strategy
                existing_prefs = self.setup_service._get_settings_service().get("search_preferences", {})
                self.step_prefs.load_preferences(
                    existing_prefs if isinstance(existing_prefs, dict) else {},
                    extracted_data=self._latest_extracted_profile
                )
            elif step_idx == 7:  # Platforms
                self.step_platforms.load_platforms()
            elif step_idx == 9:  # Readiness Summary
                evaluation = self.setup_service.readiness_service.evaluate()
                self.step_readiness.update_evaluation(evaluation, self.setup_service.get_change_summary())

    def _update_navigation_buttons(self):
        self.btn_back.setEnabled(self.current_step_idx > 0)

        # Skip allowed on optional/recommended steps
        optional_steps = {1, 7, 8}  # AI, Platforms, Safety
        self.btn_skip.setVisible(self.current_step_idx in optional_steps)

        # On the final step, hide Continue (Readiness has its own action button)
        self.btn_next.setVisible(self.current_step_idx != len(STEP_KEYS) - 1)

    def _go_back(self):
        if self.current_step_idx > 0:
            self._navigate_to_step(self.current_step_idx - 1)

    def _skip_current_step(self):
        current_key = STEP_KEYS[self.current_step_idx]
        self.setup_service.state.mark_step_skipped(current_key)
        self._go_next()

    def _go_next(self):
        idx = self.current_step_idx

        if idx == 0:  # Welcome
            mode = self.step_welcome.get_selected_mode()
            self.setup_service.start_setup(mode=mode)
            self._navigate_to_step(1)

        elif idx == 1:  # AI Setup
            ai_data = self.step_ai.get_ai_payload()
            if ai_data.get("api_key") or ai_data.get("provider") == "ollama":
                self.setup_service.save_ai_provider_step(
                    provider=ai_data["provider"],
                    api_key=ai_data["api_key"],
                    endpoint=ai_data["endpoint"],
                    model=ai_data["model"],
                )
            self._navigate_to_step(2)

        elif idx == 2:  # Resume Ingestion
            resume_path = self.step_resume.get_selected_resume_path()
            if resume_path:
                self._current_resume_path = resume_path
                self._navigate_to_step(3)
                # Auto-start staged extraction
                self.step_extract.start_extraction(resume_path)
            else:
                # If no new resume was uploaded, check if one already exists in DB
                user_id = self.setup_service.get_primary_user_id()
                existing_resumes = self.setup_service._get_resume_service().list_resumes(user_id=user_id)
                if existing_resumes:
                    self._navigate_to_step(4)
                else:
                    QMessageBox.information(self, "Resume Required", "Please choose a resume file to continue or skip.")

        elif idx == 3:  # Staged AI Extraction
            self._navigate_to_step(4)

        elif idx == 4:  # Profile Review
            profile_payload = self.step_profile.get_profile_payload()
            ok, err = self.setup_service.save_profile_step(profile_payload)
            if ok:
                self._navigate_to_step(5)
            else:
                QMessageBox.warning(self, "Profile Validation", f"Please check profile fields: {err}")

        elif idx == 5:  # Screening Q&A Knowledge Base
            self.setup_service.state.mark_step_completed("qna_knowledge")
            self.setup_service.state.save(self.setup_service._state_path)
            self._navigate_to_step(6)

        elif idx == 6:  # Job Strategy
            prefs_payload = self.step_prefs.get_preferences_payload()
            self.setup_service.save_preferences_step(prefs_payload)
            self._navigate_to_step(7)

        elif idx == 7:  # Supported Platforms
            platforms_payload = self.step_platforms.get_platforms_payload()
            if platforms_payload:
                self.setup_service.save_platforms_step(platforms_payload)
            self._navigate_to_step(8)

        elif idx == 8:  # Safety Limits
            safety_data = self.step_safety.get_safety_payload()
            self.setup_service.save_safety_step(safety_data)
            self._navigate_to_step(9)

    def _on_resume_selected(self, file_path: str):
        self._current_resume_path = file_path

    def _on_extraction_completed(self, data: dict):
        self._latest_extracted_profile = data

    def _on_reset_wizard(self):
        reply = QMessageBox.question(
            self,
            "Restart Setup Progress",
            "This resets your setup wizard progress and restarts from Step 1.\n\n"
            "Your existing candidate profile, 398 Q&A records, uploaded resumes, and credentials will NOT be deleted.\n\n"
            "Do you wish to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.setup_service.reset_wizard_progress()
            self._discover_and_adapt()
            self._navigate_to_step(0)

    def _on_tour_requested(self):
        self.accept()
        parent_win = self.parent()
        if parent_win and hasattr(parent_win, "launch_product_tour"):
            parent_win.launch_product_tour()

    def _on_finish_confirmed(self):
        ok, change_log = self.setup_service.complete_setup()
        self.onboarding_completed.emit({"changes": change_log})
        self.accept()
        parent_win = self.parent()
        if parent_win and hasattr(parent_win, "launch_product_tour"):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(400, parent_win.launch_product_tour)
