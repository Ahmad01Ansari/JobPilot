"""Interactive Release Update Dialog for JobPilot AI."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.services.os.system_service import SystemService
from app.services.update_service import (
    ReleaseAsset,
    UpdateDownloadWorker,
    UpdateInfo,
    UpdateService,
)
from app.ui.theme import COLORS
from app.version import __version__ as CURRENT_VERSION


class UpdateDialog(QDialog):
    """Modern modal dialog presenting release notes, download progress, and one-click installation."""

    def __init__(
        self,
        update_info: UpdateInfo,
        update_service: Optional[UpdateService] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.update_info = update_info
        self.update_service = update_service or UpdateService()
        self.download_worker: Optional[UpdateDownloadWorker] = None
        self.downloaded_path: Optional[Path] = None

        self.setWindowTitle(f"JobPilot Update — v{self.update_info.version}")
        self.setFixedSize(580, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS.get('background', '#0F1117')};
                color: {COLORS.get('text', '#F0F6FC')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # 1. Header Card with Version Comparison Badge
        header_card = QFrame()
        header_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#30363D')};
                border-radius: 8px;
            }}
        """)
        h_layout = QVBoxLayout(header_card)
        h_layout.setContentsMargins(16, 14, 16, 14)
        h_layout.setSpacing(6)

        title_lbl = QLabel("New Version Available")
        title_lbl.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 800;
            color: {COLORS.get('text', '#F0F6FC')};
        """)
        h_layout.addWidget(title_lbl)

        version_badge_row = QHBoxLayout()
        version_badge_row.setSpacing(8)

        cur_badge = QLabel(f"Installed: v{CURRENT_VERSION}")
        cur_badge.setStyleSheet(f"""
            background-color: #21262D;
            color: {COLORS.get('text_muted', '#8B949E')};
            border-radius: 4px;
            padding: 3px 8px;
            font-size: 11px;
            font-weight: 600;
        """)
        version_badge_row.addWidget(cur_badge)

        arrow_lbl = QLabel("➔")
        arrow_lbl.setStyleSheet(f"color: {COLORS.get('primary', '#FF5F15')}; font-weight: bold;")
        version_badge_row.addWidget(arrow_lbl)

        new_badge = QLabel(f"Latest: v{self.update_info.version}")
        new_badge.setStyleSheet(f"""
            background-color: #1A3626;
            color: {COLORS.get('success', '#2EA043')};
            border: 1px solid #238636;
            border-radius: 4px;
            padding: 3px 8px;
            font-size: 11px;
            font-weight: 700;
        """)
        version_badge_row.addWidget(new_badge)
        version_badge_row.addStretch()

        if self.update_info.published_at:
            pub_date = self.update_info.published_at.split("T")[0]
            date_lbl = QLabel(f"Released: {pub_date}")
            date_lbl.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 11px;")
            version_badge_row.addWidget(date_lbl)

        h_layout.addLayout(version_badge_row)
        layout.addWidget(header_card)

        # 2. Release Notes / Changelog Viewer
        notes_title = QLabel("What's New in this Release:")
        notes_title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS.get('text_muted', '#8B949E')};")
        layout.addWidget(notes_title)

        self.notes_browser = QTextBrowser()
        self.notes_browser.setOpenExternalLinks(True)
        self.notes_browser.setMarkdown(self.update_info.release_notes or "Bug fixes, performance improvements, and stability enhancements.")
        self.notes_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: #090D12;
                color: {COLORS.get('text', '#F0F6FC')};
                border: 1px solid {COLORS.get('border', '#30363D')};
                border-radius: 6px;
                padding: 10px;
                font-size: 12px;
                line-height: 1.5;
            }}
        """)
        layout.addWidget(self.notes_browser, 1)

        # 3. Download Progress Bar & Status (Initially hidden)
        self.progress_container = QWidget()
        self.progress_container.setVisible(False)
        p_layout = QVBoxLayout(self.progress_container)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(4)

        self.status_lbl = QLabel("Downloading update package...")
        self.status_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS.get('text_muted', '#8B949E')};")
        p_layout.addWidget(self.status_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #21262D;
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS.get('primary', '#FF5F15')};
                border-radius: 4px;
            }}
        """)
        p_layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_container)

        # 4. Action Buttons Footer
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)

        self.btn_github = QPushButton("View on GitHub")
        self.btn_github.setCursor(Qt.PointingHandCursor)
        self.btn_github.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS.get('text_muted', '#8B949E')};
                border: 1px solid {COLORS.get('border', '#30363D')};
                border-radius: 6px;
                padding: 7px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS.get('text', '#F0F6FC')};
                border-color: #8B949E;
            }}
        """)
        self.btn_github.clicked.connect(self._on_view_github)
        actions_row.addWidget(self.btn_github)

        actions_row.addStretch()

        self.btn_cancel = QPushButton("Remind Me Later")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS.get('text_muted', '#8B949E')};
                border: none;
                padding: 7px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS.get('text', '#F0F6FC')};
            }}
        """)
        self.btn_cancel.clicked.connect(self.reject)
        actions_row.addWidget(self.btn_cancel)

        self.btn_action = QPushButton("Update Now")
        self.btn_action.setCursor(Qt.PointingHandCursor)
        self.btn_action.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('primary', '#FF5F15')};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 7px 18px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #E04D0B;
            }}
            QPushButton:disabled {{
                background-color: #383D47;
                color: #8B949E;
            }}
        """)
        self.btn_action.clicked.connect(self._on_primary_action)
        actions_row.addWidget(self.btn_action)

        layout.addLayout(actions_row)

    def _on_view_github(self) -> None:
        """Opens GitHub release page in system default web browser."""
        url = self.update_info.html_url or f"https://github.com/{self.update_service.repo}/releases"
        QDesktopServices.openUrl(QUrl(url))

    def _on_primary_action(self) -> None:
        """Handles single-click download and restart installation."""
        if self.downloaded_path and self.downloaded_path.exists():
            # Apply and restart
            self.btn_action.setEnabled(False)
            self.status_lbl.setText("Applying update and restarting...")
            success, msg = self.update_service.apply_update(self.downloaded_path)
            if success:
                self.accept()
            else:
                self.status_lbl.setText(f"Notice: {msg}")
                self.btn_action.setEnabled(True)
            return

        # Start downloading matched platform asset
        asset = self.update_info.asset
        if not asset:
            # Fallback to browser if no direct binary match
            self._on_view_github()
            self.accept()
            return

        self.btn_action.setEnabled(False)
        self.btn_action.setText("Downloading...")
        self.btn_cancel.setText("Cancel")
        self.progress_container.setVisible(True)

        self.download_worker = UpdateDownloadWorker(
            service=self.update_service,
            asset=asset,
            parent=self,
        )
        self.download_worker.download_progress.connect(self._on_progress)
        self.download_worker.download_finished.connect(self._on_download_complete)
        self.download_worker.download_error.connect(self._on_download_error)
        self.download_worker.start()

    def _on_progress(self, downloaded: int, total: int, pct: float) -> None:
        self.progress_bar.setValue(int(pct))
        down_mb = downloaded / (1024 * 1024)
        tot_mb = total / (1024 * 1024)
        if total > 0:
            self.status_lbl.setText(f"Downloading {self.update_info.asset.name} ({down_mb:.1f} MB / {tot_mb:.1f} MB — {pct:.0f}%)")
        else:
            self.status_lbl.setText(f"Downloading {self.update_info.asset.name} ({down_mb:.1f} MB)...")

    def _on_download_complete(self, target_path: Path) -> None:
        self.downloaded_path = target_path
        self.progress_bar.setValue(100)
        self.status_lbl.setText("Download complete! Ready to apply and restart.")
        self.btn_action.setEnabled(True)
        self.btn_action.setText("Restart & Update")

    def _on_download_error(self, err_msg: str) -> None:
        self.status_lbl.setText(f"Download failed: {err_msg}")
        self.btn_action.setEnabled(True)
        self.btn_action.setText("Retry Download")

    def reject(self) -> None:
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.cancel()
            self.download_worker.wait(1000)
        super().reject()

