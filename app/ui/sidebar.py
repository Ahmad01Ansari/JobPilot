"""
Sidebar navigation component for JobPilot Desktop.
Modern SaaS ATS-style sidebar with data-driven sections, vector icons,
smooth collapse/expand, and theme-aware styling.
"""

from typing import Dict, Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import (
    Qt,
    Signal,
    QPropertyAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QRectF,
    QSize,
)
from PySide6.QtGui import QPainter, QColor, QPen, QFont

from app.ui.theme import COLORS, ThemeManager
from app.ui.navigation import NAV_ITEMS, SIDEBAR_SECTIONS, SidebarNavEntry
from app.ui.sidebar_icons import SidebarIconPainter, ICON_NAME_MAP

# ── Layout Constants ────────────────────────────────────────────────────
EXPANDED_WIDTH = 240
COLLAPSED_WIDTH = 68
ITEM_HEIGHT = 33
ICON_SIZE = 17
ICON_COL_WIDTH = 26        # fixed column for icon alignment
LABEL_LEFT_PAD = 40        # icon_col(26) + pad(14)
ANIM_DURATION_MS = 180
ACCENT_BAR_WIDTH = 3


# ── Collapse / Expand Button ────────────────────────────────────────────

class CollapseButton(QPushButton):
    """Panel-collapse chevron button (< in expanded, > in collapsed)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(26, 26)
        self.setCursor(Qt.PointingHandCursor)
        self._is_collapsed = False
        self.setToolTip("Collapse Sidebar")
        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: %(hover)s;
            }
        """ % {"hover": COLORS.get("surface_hover", "#262C36")})

    def set_collapsed(self, collapsed: bool):
        self._is_collapsed = collapsed
        self.setToolTip("Expand Sidebar" if collapsed else "Collapse Sidebar")
        self.setFixedSize(24, 24) if collapsed else self.setFixedSize(26, 26)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(COLORS.get("primary", "#FF5F15")) if self.underMouse() else QColor(COLORS.get("text_muted", "#8B949E"))
        pen = QPen(color)
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)

        cx = self.width() / 2.0
        cy = self.height() / 2.0
        size = 4.0

        if self._is_collapsed:
            # Right chevron > (expand)
            painter.drawLine(cx - 2.5, cy - size, cx + 2.0, cy)
            painter.drawLine(cx + 2.0, cy, cx - 2.5, cy + size)
        else:
            # Left chevron < (collapse)
            painter.drawLine(cx + 2.0, cy - size, cx - 2.5, cy)
            painter.drawLine(cx - 2.5, cy, cx + 2.0, cy + size)

        painter.end()


# ── Sidebar Nav Item Widget ─────────────────────────────────────────────

class SidebarNavItem(QWidget):
    """Single navigation item: icon + label with active/hover states and accent bar."""

    clicked = Signal(str)  # emits entry.id

    def __init__(self, entry: SidebarNavEntry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self._is_active = False
        self._is_collapsed = False
        self._is_hovered = False
        self.setFixedHeight(ITEM_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setToolTip("")

    # ── State ────────────────────────────────────────────────────────

    def set_active(self, active: bool):
        self._is_active = active
        self.update()

    def set_collapsed(self, collapsed: bool):
        self._is_collapsed = collapsed
        if collapsed:
            self.setToolTip(self.entry.tooltip or self.entry.label)
        else:
            self.setToolTip("")
        self.update()

    # ── Events ───────────────────────────────────────────────────────

    def enterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.entry.id)
        super().mousePressEvent(event)

    # ── Paint ────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        accent = QColor(COLORS.get("primary", "#FF5F15"))
        text_color = QColor(COLORS.get("text", "#F0F6FC"))
        text_muted = QColor(COLORS.get("text_muted", "#8B949E"))
        hover_bg = QColor(COLORS.get("surface_hover", "#262C36"))
        active_bg = QColor(COLORS.get("surface_active", "#FF5F1522"))

        # ── Background ──
        if self._is_active:
            painter.setPen(Qt.NoPen)
            painter.setBrush(active_bg)
            painter.drawRoundedRect(QRectF(0, 1, w, h - 2), 6, 6)

            # Left accent bar
            painter.setBrush(accent)
            painter.drawRoundedRect(QRectF(0, 4, ACCENT_BAR_WIDTH, h - 8), 1.5, 1.5)

        elif self._is_hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(hover_bg)
            painter.drawRoundedRect(QRectF(0, 1, w, h - 2), 6, 6)

        # ── Icon ──
        icon_name = ICON_NAME_MAP.get(self.entry.id, self.entry.icon)
        if self._is_active:
            icon_color = accent
        elif self._is_hovered:
            icon_color = text_color
        else:
            icon_color = text_muted

        if self._is_collapsed:
            icon_x = (w - ICON_SIZE) / 2.0
        else:
            icon_x = 9.0 + (ICON_COL_WIDTH - ICON_SIZE) / 2.0

        icon_y = (h - ICON_SIZE) / 2.0
        icon_rect = QRectF(icon_x, icon_y, ICON_SIZE, ICON_SIZE)
        SidebarIconPainter.draw(painter, icon_name, icon_rect, icon_color)

        # ── Label (Expanded only) ──
        if not self._is_collapsed:
            if self._is_active:
                label_color = text_color
                font_weight = QFont.DemiBold
            elif self._is_hovered:
                label_color = text_color
                font_weight = QFont.Medium
            else:
                label_color = text_muted
                font_weight = QFont.Medium

            font = painter.font()
            font.setPixelSize(13)
            font.setWeight(font_weight)
            painter.setFont(font)
            painter.setPen(label_color)

            label_rect = QRectF(LABEL_LEFT_PAD, 0, w - LABEL_LEFT_PAD - 4, h)
            painter.drawText(label_rect, Qt.AlignLeft | Qt.AlignVCenter, self.entry.label)

        painter.end()


# ── Sidebar Section Header ──────────────────────────────────────────────

class SidebarSectionHeader(QWidget):
    """Section header: uppercase label in expanded mode, subtle centered divider in collapsed mode."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self._is_collapsed = False
        self.setFixedHeight(18)

    def set_collapsed(self, collapsed: bool):
        self._is_collapsed = collapsed
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        if self._is_collapsed:
            # Draw subtle centered divider line in collapsed mode
            border_color = QColor(COLORS.get("border_light", "#333A46"))
            border_color.setAlpha(70)
            painter.setPen(QPen(border_color, 1.0))
            line_w = 26.0
            x1 = (w - line_w) / 2.0
            x2 = x1 + line_w
            y = h / 2.0
            painter.drawLine(x1, y, x2, y)
        else:
            # Draw uppercase letter-spaced section title
            text_dark = QColor(COLORS.get("text_dark", "#6E7681"))
            font = painter.font()
            font.setPixelSize(10)
            font.setWeight(QFont.Bold)
            font.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
            painter.setFont(font)
            painter.setPen(text_dark)
            painter.drawText(QRectF(9, 0, w - 18, h), Qt.AlignLeft | Qt.AlignVCenter, self.title)

        painter.end()


# ── Sidebar Brand Header ────────────────────────────────────────────────

class SidebarHeader(QWidget):
    """Header containing brand badge, title, and collapse/expand button."""

    expand_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_collapsed = False
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        # JP Logo Badge
        self.logo_badge = QLabel()
        self.logo_badge.setFixedSize(30, 30)
        self.logo_badge.setAlignment(Qt.AlignCenter)
        self.logo_badge.setCursor(Qt.PointingHandCursor)
        self._apply_badge_style()
        self.logo_badge.mousePressEvent = self._on_logo_clicked

        # Text column (JobPilot / JOB AUTOMATION)
        self.text_widget = QWidget()
        self.text_widget.setStyleSheet("background: transparent; border: none;")
        text_layout = QVBoxLayout(self.text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)
        text_layout.setAlignment(Qt.AlignVCenter)

        self.title_label = QLabel("JobPilot")
        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 15px;
                font-weight: 800;
                color: {COLORS.get('text', '#F0F6FC')};
                letter-spacing: 0.3px;
                background: transparent;
                border: none;
            }}
        """)
        self.sub_label = QLabel("JOB AUTOMATION")
        self.sub_label.setStyleSheet(f"""
            QLabel {{
                font-size: 9px;
                font-weight: 700;
                color: {COLORS.get('primary', '#FF5F15')};
                letter-spacing: 1.0px;
                background: transparent;
                border: none;
            }}
        """)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.sub_label)

        # Collapse / Expand button (< in expanded, > in collapsed)
        self.collapse_btn = CollapseButton()

        layout.addWidget(self.logo_badge, 0, Qt.AlignVCenter)
        layout.addWidget(self.text_widget, 1, Qt.AlignVCenter)
        layout.addWidget(self.collapse_btn, 0, Qt.AlignVCenter)

    def _on_logo_clicked(self, event):
        if event.button() == Qt.LeftButton:
            self.expand_requested.emit()

    def set_collapsed(self, collapsed: bool):
        self._is_collapsed = collapsed
        self.text_widget.setVisible(not collapsed)
        self.collapse_btn.set_collapsed(collapsed)
        if collapsed:
            self.layout().setContentsMargins(6, 0, 6, 0)
            self.layout().setSpacing(4)
            self.logo_badge.setToolTip("JobPilot — Click to expand")
        else:
            self.layout().setContentsMargins(8, 0, 8, 0)
            self.layout().setSpacing(6)
            self.logo_badge.setToolTip("")

    def _apply_badge_style(self):
        pix = ThemeManager.get_brand_pixmap(28, variant="app")
        if not pix.isNull():
            self.logo_badge.setPixmap(pix)
            self.logo_badge.setStyleSheet("""
                QLabel {
                    background: transparent;
                    border: none;
                    border-radius: 6px;
                }
            """)
        else:
            primary_color = COLORS.get('primary', '#FF5F15')
            self.logo_badge.setText("JP")
            self.logo_badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {primary_color};
                    color: white;
                    font-weight: 800;
                    font-size: 12px;
                    border-radius: 7px;
                }}
            """)

    def update_theme(self):
        self._apply_badge_style()
        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 15px;
                font-weight: 800;
                color: {COLORS.get('text', '#F0F6FC')};
                letter-spacing: 0.3px;
                background: transparent;
                border: none;
            }}
        """)
        self.sub_label.setStyleSheet(f"""
            QLabel {{
                font-size: 9px;
                font-weight: 700;
                color: {COLORS.get('primary', '#FF5F15')};
                letter-spacing: 1.0px;
                background: transparent;
                border: none;
            }}
        """)
        self.collapse_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: %(hover)s;
            }
        """ % {"hover": COLORS.get("surface_hover", "#262C36")})
        self.collapse_btn.update()


# ── Sidebar Footer ──────────────────────────────────────────────────────

class SidebarFooter(QWidget):
    """Compact status footer showing engine readiness."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_collapsed = False
        self._status_text = "Engine Ready"
        self._status_ok = True
        self.setFixedHeight(32)

    def set_collapsed(self, collapsed: bool):
        self._is_collapsed = collapsed
        self.update()

    def set_status(self, text: str, ok: bool = True):
        self._status_text = text
        self._status_ok = ok
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        border_color = QColor(COLORS.get("border", "#262C36"))
        text_muted = QColor(COLORS.get("text_dark", "#6E7681"))
        dot_color = QColor(COLORS.get("success", "#2EA043")) if self._status_ok else QColor(COLORS.get("danger", "#F85149"))

        # Top border line
        painter.setPen(QPen(border_color, 1.0))
        painter.drawLine(0, 0, w, 0)

        # Status dot
        dot_r = 3.5
        if self._is_collapsed:
            dot_x = w / 2.0
            dot_y = h / 2.0
            painter.setPen(Qt.NoPen)
            painter.setBrush(dot_color)
            painter.drawEllipse(QRectF(dot_x - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2))
        else:
            dot_x = 14.0
            dot_y = h / 2.0
            painter.setPen(Qt.NoPen)
            painter.setBrush(dot_color)
            painter.drawEllipse(QRectF(dot_x - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2))

            # Status text
            font = painter.font()
            font.setPixelSize(11)
            font.setWeight(QFont.Medium)
            painter.setFont(font)
            painter.setPen(text_muted)
            painter.drawText(QRectF(dot_x + dot_r + 8, 0, w - dot_x - 30, h),
                             Qt.AlignLeft | Qt.AlignVCenter, self._status_text)

        painter.end()


# ── Main Sidebar ────────────────────────────────────────────────────────

class Sidebar(QWidget):
    """Left navigation panel with data-driven sections, vector icons, and smooth collapse."""

    item_selected = Signal(str)      # emits route page_id
    filter_requested = Signal(str)   # emits filter_key for virtual nav items
    sidebar_toggled = Signal(bool)   # emits is_collapsed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        self.setMinimumWidth(EXPANDED_WIDTH)
        self.setMaximumWidth(EXPANDED_WIDTH)
        self.nav_items: Dict[str, SidebarNavItem] = {}
        self.section_headers: list[SidebarSectionHeader] = []
        self._active_id: Optional[str] = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Brand Header ──
        self.header = SidebarHeader(self)
        self.header.collapse_btn.clicked.connect(self.toggle_collapse)
        self.header.expand_requested.connect(self._on_logo_expand)

        # Brand separator
        self.brand_sep = QFrame()
        self.brand_sep.setFixedHeight(1)
        self.brand_sep.setStyleSheet(f"background-color: {COLORS.get('border', '#262C36')};")

        main_layout.addWidget(self.header)
        main_layout.addWidget(self.brand_sep)

        # ── Scrollable Navigation ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.nav_layout = QVBoxLayout(container)
        self.nav_layout.setContentsMargins(6, 4, 6, 4)
        self.nav_layout.setSpacing(2)

        for sec_idx, section in enumerate(SIDEBAR_SECTIONS):
            # Section spacing before (not first)
            if sec_idx > 0:
                spacer = QWidget()
                spacer.setFixedHeight(4)
                spacer.setStyleSheet("background: transparent;")
                self.nav_layout.addWidget(spacer)

            # Section header
            sec_header = SidebarSectionHeader(section.title)
            self.section_headers.append(sec_header)
            self.nav_layout.addWidget(sec_header)

            # Nav items in this section
            for entry in section.items:
                nav_item = SidebarNavItem(entry)
                nav_item.clicked.connect(self._on_item_clicked)
                self.nav_items[entry.id] = nav_item
                self.nav_layout.addWidget(nav_item)

        # Backwards compatibility: Map registered primary NAV_ITEMS
        self.buttons: Dict[str, SidebarNavItem] = {
            item.id: self.nav_items[item.id] for item in NAV_ITEMS if item.id in self.nav_items
        }

        self.nav_layout.addStretch(1)
        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

        # ── Footer ──
        self.footer = SidebarFooter()
        main_layout.addWidget(self.footer)

        # ── Sidebar base style ──
        self._apply_base_style()

    def _apply_base_style(self):
        self.setStyleSheet(f"""
            Sidebar {{
                background-color: {COLORS.get('surface', '#161B22')};
                border-right: 1px solid {COLORS.get('border', '#262C36')};
            }}
        """)

    # ── Public API ───────────────────────────────────────────────────

    def set_active_item(self, page_id: str):
        """Highlights the nav item matching page_id (route-based matching)."""
        matched_id = None
        for item_id, nav_item in self.nav_items.items():
            if nav_item.entry.route == page_id and nav_item.entry.filter_key is None:
                matched_id = item_id
                break

        if self._active_id and self._active_id in self.nav_items:
            active_entry = self.nav_items[self._active_id].entry
            if active_entry.route == page_id:
                matched_id = self._active_id

        if matched_id is None:
            matched_id = page_id  # fallback

        self._active_id = matched_id
        for item_id, nav_item in self.nav_items.items():
            nav_item.set_active(item_id == matched_id)

    def toggle_collapse(self) -> None:
        """Smoothly animates between expanded and collapsed widths."""
        start_w = self.width()
        end_w = COLLAPSED_WIDTH if not self.is_collapsed else EXPANDED_WIDTH
        self.is_collapsed = not self.is_collapsed

        # Update child states immediately
        self.header.set_collapsed(self.is_collapsed)
        self.footer.set_collapsed(self.is_collapsed)

        for nav_item in self.nav_items.values():
            nav_item.set_collapsed(self.is_collapsed)

        for sec_hdr in self.section_headers:
            sec_hdr.set_collapsed(self.is_collapsed)

        # Width animation
        self._anim_max = QPropertyAnimation(self, b"maximumWidth")
        self._anim_max.setDuration(ANIM_DURATION_MS)
        self._anim_max.setStartValue(start_w)
        self._anim_max.setEndValue(end_w)
        self._anim_max.setEasingCurve(QEasingCurve.InOutCubic)

        self._anim_min = QPropertyAnimation(self, b"minimumWidth")
        self._anim_min.setDuration(ANIM_DURATION_MS)
        self._anim_min.setStartValue(start_w)
        self._anim_min.setEndValue(end_w)
        self._anim_min.setEasingCurve(QEasingCurve.InOutCubic)

        self._anim_group = QParallelAnimationGroup(self)
        self._anim_group.addAnimation(self._anim_max)
        self._anim_group.addAnimation(self._anim_min)

        def _on_finish():
            self.sidebar_toggled.emit(self.is_collapsed)

        self._anim_group.finished.connect(_on_finish)
        self._anim_group.start()

    def update_theme(self) -> None:
        """Refreshes sidebar styles according to the current theme."""
        self._apply_base_style()
        self.brand_sep.setStyleSheet(f"background-color: {COLORS.get('border', '#262C36')};")
        self.header.update_theme()
        for sec_hdr in self.section_headers:
            sec_hdr.update()
        for nav_item in self.nav_items.values():
            nav_item.update()
        self.footer.update()

    def set_engine_status(self, text: str, ok: bool = True):
        """Updates the footer status indicator."""
        self.footer.set_status(text, ok)

    # ── Private ──────────────────────────────────────────────────────

    def _on_item_clicked(self, entry_id: str):
        """Handles navigation item clicks including virtual filter items."""
        if entry_id not in self.nav_items:
            return

        entry = self.nav_items[entry_id].entry
        self._active_id = entry_id

        # Update visual active state
        for item_id, nav_item in self.nav_items.items():
            nav_item.set_active(item_id == entry_id)

        # Emit navigation
        self.item_selected.emit(entry.route)

        # Emit filter if this is a virtual item
        if entry.filter_key:
            self.filter_requested.emit(entry.filter_key)
        elif entry.route == "jobs" and entry.filter_key is None:
            # "All Jobs" clears any filter
            self.filter_requested.emit("")

    def _on_logo_expand(self):
        """Expands sidebar when logo badge is clicked in collapsed mode."""
        if self.is_collapsed:
            self.toggle_collapse()
