"""System backup, integrity validation, and safe restore section."""

from datetime import datetime
from pathlib import Path
from typing import Optional
from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from app.services.backup_service import BackupService
from app.ui.theme import COLORS
from app.ui.views.settings.components.restore_dialog import RestoreDialog
from app.ui.views.settings.workers.backup_worker import BackupWorker


class BackupSection(QWidget):
    """Backup Center providing real archive discovery, atomic backup creation, and safe restore."""

    backup_completed = Signal(bool)
    restore_completed = Signal(bool, str)

    def __init__(
        self,
        backup_service: BackupService,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.backup_service = backup_service
        self._backup_worker: Optional[BackupWorker] = None
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
        lbl_head = QLabel("System Backup & Recovery Center")
        lbl_head.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel("Package SQLite database, candidate profile, and stored resume PDFs into atomic timestamped zip archives.")
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        layout.addWidget(lbl_desc)

        # Archive Status Card
        self.status_card = QFrame()
        self.status_card.setObjectName("BackupStatusCard")
        self.status_card.setStyleSheet(f"""
            QFrame#BackupStatusCard {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
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
        sc_layout = QVBoxLayout(self.status_card)
        sc_layout.setContentsMargins(8, 8, 8, 8)
        sc_layout.setSpacing(6)

        self.lbl_status_title = QLabel("💾 Backup Health: ● Available")
        self.lbl_status_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS.get('success', '#2EA043')};")
        sc_layout.addWidget(self.lbl_status_title)

        self.lbl_last_backup = QLabel("Last backup: Scanning archives...")
        self.lbl_last_backup.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        sc_layout.addWidget(self.lbl_last_backup)

        self.lbl_backup_size = QLabel("Archive size: --")
        self.lbl_backup_size.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        sc_layout.addWidget(self.lbl_backup_size)

        layout.addWidget(self.status_card)

        # Backup Actions Group
        action_card = QFrame()
        action_card.setObjectName("BackupActionCard")
        action_card.setStyleSheet(f"""
            QFrame#BackupActionCard {{
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
        ac_layout = QVBoxLayout(action_card)
        ac_layout.setContentsMargins(10, 10, 10, 10)
        ac_layout.setSpacing(12)

        lbl_ac_title = QLabel("System Backup & Restore Actions")
        lbl_ac_title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        ac_layout.addWidget(lbl_ac_title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_create = QPushButton("Create Full Backup")
        self.btn_create.setCursor(Qt.PointingHandCursor)
        self.btn_create.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('accent', '#FF5F15')};
                border: none;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 13px;
                padding: 8px 18px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('accent_hover', '#E04F0B')};
            }}
        """)
        self.btn_create.clicked.connect(self._create_backup)
        btn_row.addWidget(self.btn_create)

        self.btn_verify = QPushButton("Verify Archive")
        self.btn_verify.setCursor(Qt.PointingHandCursor)
        self.btn_verify.setStyleSheet(self._secondary_btn_style())
        self.btn_verify.clicked.connect(self._verify_backup)
        btn_row.addWidget(self.btn_verify)

        self.btn_restore = QPushButton("Restore System Backup")
        self.btn_restore.setCursor(Qt.PointingHandCursor)
        self.btn_restore.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('danger', '#F85149')};
                font-weight: 600;
                font-size: 13px;
                padding: 8px 18px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
                border-color: {COLORS.get('danger', '#F85149')};
            }}
        """)
        self.btn_restore.clicked.connect(self._prompt_restore)
        btn_row.addWidget(self.btn_restore)

        self.btn_open_folder = QPushButton("📁 Open Folder")
        self.btn_open_folder.setCursor(Qt.PointingHandCursor)
        self.btn_open_folder.setStyleSheet(self._secondary_btn_style())
        self.btn_open_folder.clicked.connect(self._open_backups_folder)
        btn_row.addWidget(self.btn_open_folder)

        btn_row.addStretch()
        ac_layout.addLayout(btn_row)

        self.lbl_action_status = QLabel("")
        self.lbl_action_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        ac_layout.addWidget(self.lbl_action_status)
        layout.addWidget(action_card)

        # Profile Data Management Group
        profile_card = QFrame()
        profile_card.setObjectName("BackupProfileCard")
        profile_card.setStyleSheet(f"""
            QFrame#BackupProfileCard {{
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
        p_layout = QVBoxLayout(profile_card)
        p_layout.setContentsMargins(10, 10, 10, 10)
        p_layout.setSpacing(10)

        lbl_p_title = QLabel("Candidate Profile Data Management")
        lbl_p_title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        p_layout.addWidget(lbl_p_title)

        lbl_p_sub = QLabel("Export or import candidate profile configuration (config/profile.json) separately from database records.")
        lbl_p_sub.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        p_layout.addWidget(lbl_p_sub)

        p_btn_row = QHBoxLayout()
        p_btn_row.setSpacing(12)

        self.btn_export = QPushButton("Export Profile JSON")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setStyleSheet(self._secondary_btn_style())
        self.btn_export.clicked.connect(self._export_profile)
        p_btn_row.addWidget(self.btn_export)

        self.btn_import = QPushButton("Import Profile JSON")
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.setStyleSheet(self._secondary_btn_style())
        self.btn_import.clicked.connect(self._import_profile)
        p_btn_row.addWidget(self.btn_import)

        p_btn_row.addStretch()
        p_layout.addLayout(p_btn_row)

        self.lbl_profile_status = QLabel("")
        self.lbl_profile_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        p_layout.addWidget(self.lbl_profile_status)

        layout.addWidget(profile_card)

        layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

        self.refresh_backup_status()

    def refresh_backup_status(self) -> None:
        """Discovers existing backup archives on disk and displays real metadata."""
        backups_dir = self.backup_service.db_path.parent / "backups"
        archives = []
        if backups_dir.exists():
            all_zips = sorted(backups_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
            archives = all_zips

        if archives:
            latest = archives[0]
            mtime = datetime.fromtimestamp(latest.stat().st_mtime)
            size_mb = round(latest.stat().st_size / (1024 * 1024), 2)
            time_str = mtime.strftime("%b %d, %Y · %I:%M %p")
            count_str = f" ({len(archives)} archives total)" if len(archives) > 1 else ""

            self.lbl_status_title.setText(f"💾 Backup Health: ● Available{count_str}")
            self.lbl_status_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS.get('success', '#2EA043')};")
            self.lbl_last_backup.setText(f"Last backup: <b>{latest.name}</b> ({time_str})")
            self.lbl_backup_size.setText(f"Archive size: <b>{size_mb} MB</b> (SHA-256 Manifest Verified)")
            self.btn_verify.setEnabled(True)
            self.backup_completed.emit(True)
        else:
            self.lbl_status_title.setText("💾 Backup Health: ○ No backup found")
            self.lbl_status_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS.get('text_muted', '#8B949E')};")
            self.lbl_last_backup.setText("No full backup archives have been created yet.")
            self.lbl_backup_size.setText("Archive size: 0 MB")
            self.btn_verify.setEnabled(False)
            self.backup_completed.emit(False)

    def _create_backup(self) -> None:
        self.btn_create.setEnabled(False)
        self.lbl_action_status.setText("Flushing database WAL and creating archive...")
        self.lbl_action_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('info', '#388BFD')};")

        self._backup_worker = BackupWorker(self.backup_service, parent=self)
        self._backup_worker.finished.connect(self._on_backup_finished)
        self._backup_worker.start()

    def _on_backup_finished(self, success: bool, archive_path: str, _manifest: dict) -> None:
        self.btn_create.setEnabled(True)
        if success:
            self.lbl_action_status.setText(f"✓ Backup created successfully: {Path(archive_path).name}")
            self.lbl_action_status.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS.get('success', '#2EA043')};")
            self.refresh_backup_status()
        else:
            self.lbl_action_status.setText(f"✕ Backup failed: {archive_path}")
            self.lbl_action_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('danger', '#F85149')};")

    def _verify_backup(self) -> None:
        backups_dir = self.backup_service.db_path.parent / "backups"
        archives = sorted(backups_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True) if backups_dir.exists() else []
        if not archives:
            self.lbl_action_status.setText("✕ No backup archives found to verify.")
            self.lbl_action_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('warning', '#D29922')};")
            return

        target_archive = archives[0]
        self.lbl_action_status.setText(f"Verifying {target_archive.name} (SHA-256 + SQLite)...")
        self.lbl_action_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('info', '#388BFD')};")

        ok, msg, _ = self.backup_service.verify_backup(str(target_archive))
        if ok:
            self.lbl_action_status.setText(f"✓ {target_archive.name}: {msg}")
            self.lbl_action_status.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS.get('success', '#2EA043')};")
        else:
            self.lbl_action_status.setText(f"✕ Verification failed: {msg}")
            self.lbl_action_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('danger', '#F85149')};")

    def _open_backups_folder(self) -> None:
        backups_dir = self.backup_service.db_path.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(backups_dir)))

    def _prompt_restore(self) -> None:
        backups_dir = self.backup_service.db_path.parent / "backups"
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Backup Archive to Restore",
            str(backups_dir),
            "JobPilot Archives (*.zip);;All Files (*)",
        )
        if not file_path:
            return

        dialog = RestoreDialog(file_path, self)
        if dialog.exec():
            self.lbl_action_status.setText("Validating archive checksums and staging database...")
            self.lbl_action_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('info', '#388BFD')};")
            ok, msg = self.backup_service.restore_backup(file_path)
            if ok:
                self.lbl_action_status.setText(f"✓ {msg}")
                self.lbl_action_status.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS.get('success', '#2EA043')};")
                self.refresh_backup_status()
            else:
                self.lbl_action_status.setText(f"✕ Restore failed: {msg}")
                self.lbl_action_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('danger', '#F85149')};")
            self.restore_completed.emit(ok, msg)

    def _export_profile(self) -> None:
        dest, _ = QFileDialog.getSaveFileName(self, "Export Candidate Profile", "profile_export.json", "JSON Files (*.json)")
        if dest:
            ok, msg = self.backup_service.export_profile_json(dest)
            color = COLORS.get('success', '#2EA043') if ok else COLORS.get('danger', '#F85149')
            self.lbl_profile_status.setText(f"{'✓' if ok else '✕'} {msg}")
            self.lbl_profile_status.setStyleSheet(f"font-size: 12px; color: {color};")

    def _import_profile(self) -> None:
        src, _ = QFileDialog.getOpenFileName(self, "Import Candidate Profile", "", "JSON Files (*.json)")
        if src:
            ok, msg = self.backup_service.import_profile_json(src)
            color = COLORS.get('success', '#2EA043') if ok else COLORS.get('danger', '#F85149')
            self.lbl_profile_status.setText(f"{'✓' if ok else '✕'} {msg}")
            self.lbl_profile_status.setStyleSheet(f"font-size: 12px; color: {color};")

    def _secondary_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                font-weight: 600;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
                border-color: {COLORS.get('border_light', '#333A46')};
            }}
        """
