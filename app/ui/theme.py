"""
Centralized Theme Tokens & Stylesheet Management for JobPilot.
Modern ATS aesthetic with Refined Dark Canvas (#0F1117), Crisp Light Canvas (#F6F8FA),
and Vibrant Safety Orange Accents (#FF5F15).
"""

from pathlib import Path
from typing import Dict

_CHECK_ICON_PATH = (Path(__file__).parent / "assets" / "icons" / "check.svg").as_posix()
_CHEVRON_DOWN_PATH = (Path(__file__).parent / "assets" / "icons" / "chevron_down.svg").as_posix()
_CHEVRON_DOWN_HOVER_PATH = (Path(__file__).parent / "assets" / "icons" / "chevron_down_hover.svg").as_posix()

# 1. Refined Dark Canvas Palette (#0F1117)
DARK_COLORS: Dict[str, str] = {
    "background": "#0F1117",       # Refined dark canvas (pitch-clean obsidian neutral)
    "surface": "#161B22",          # Primary card & panel surface (clean charcoal)
    "surface_alt": "#1C2128",      # Elevated card / header / tab inactive background
    "surface_elevated": "#22272E", # Highlighted card / popover background
    "surface_hover": "#262C36",    # Hover state for lists and cards
    "surface_active": "#21262D",   # Active item highlight fill
    "border": "#262C36",           # Subtle non-intrusive card borders
    "border_light": "#333A46",     # Accent / hover borders
    "border_subtle": "#21262D",    # Extremely soft divider
    "primary": "#FF5F15",          # Vibrant Safety Orange accent
    "primary_hover": "#E04F0B",    # Rich deeper safety orange on hover
    "primary_subtle": "#FF5F1518", # Translucent safety orange tint
    "accent": "#FF7A3D",           # Soft warm safety orange highlight
    "text": "#F0F6FC",             # High-contrast crisp white-slate text
    "text_muted": "#8B949E",       # Balanced secondary slate-grey metadata
    "text_dark": "#6E7681",        # Hints, placeholders, disabled text
    "success": "#2EA043",          # Clean emerald green
    "success_subtle": "#2EA04318",
    "warning": "#D29922",          # Warm golden amber
    "warning_subtle": "#D2992218",
    "danger": "#F85149",           # Coral red
    "danger_subtle": "#F8514918",
    "info": "#388BFD",             # Sky royal blue
    "info_subtle": "#388BFD18",
    "purple": "#A371F7",           # Soft purple
    "purple_subtle": "#A371F718",
    "cyan": "#39C5CF",             # Bright cyan
    "cyan_subtle": "#39C5CF18",
}

# 2. Crisp Light Canvas Palette (#F6F8FA)
LIGHT_COLORS: Dict[str, str] = {
    "background": "#F6F8FA",       # Crisp light canvas background
    "surface": "#FFFFFF",          # Pure white card / panel surface
    "surface_alt": "#F0F2F5",      # Elevated / table header background
    "surface_elevated": "#EAEEF2", # Highlighted surface
    "surface_hover": "#EAEFF5",    # Hover state for lists and cards
    "surface_active": "#FF5F1518", # Active item safety orange tint
    "border": "#D0D7DE",           # Crisp light gray border
    "border_light": "#AFB8C1",     # Focused / accent border
    "border_subtle": "#0000000d",  # Soft divider
    "primary": "#FF5F15",          # Vibrant Safety Orange accent
    "primary_hover": "#E04F0B",    # Deeper orange on hover
    "primary_subtle": "#FF5F1518",
    "accent": "#FF7A3D",
    "text": "#1F2328",             # Crisp high-contrast dark text
    "text_muted": "#656D76",       # Secondary neutral slate
    "text_dark": "#8C959F",        # Disabled / placeholder
    "success": "#1A7F37",
    "success_subtle": "#1A7F3718",
    "warning": "#9A6700",
    "warning_subtle": "#9A670018",
    "danger": "#CF222E",
    "danger_subtle": "#CF222E18",
    "info": "#0969DA",
    "info_subtle": "#0969DA18",
    "purple": "#8250DF",
    "purple_subtle": "#8250DF18",
    "cyan": "#0598AB",
    "cyan_subtle": "#0598AB18",
}

# Active design tokens pointer (defaults to Refined Dark Canvas)
COLORS: Dict[str, str] = dict(DARK_COLORS)


class ThemeManager:
    """Manages application-wide styling, palette configuration, and theme switching."""

    current_mode: str = "dark"
    colors: Dict[str, str] = COLORS
    _listeners = []

    @classmethod
    def get_colors(cls) -> Dict[str, str]:
        """Returns the current active theme color token dictionary."""
        return COLORS

    @classmethod
    def get_instance(cls):
        """Returns the singleton ThemeManager class."""
        return cls

    @classmethod
    def add_listener(cls, callback) -> None:
        """Registers a callback to be invoked on theme changes."""
        if callback not in cls._listeners:
            cls._listeners.append(callback)

    @classmethod
    def notify_listeners(cls, mode: str) -> None:
        """Invokes all registered callbacks with the new mode name."""
        for cb in list(cls._listeners):
            try:
                cb(mode)
            except Exception:
                pass

    @staticmethod
    def get_stylesheet(tokens: Dict[str, str] = COLORS) -> str:
        """Generates comprehensive, balanced Qt stylesheet for the application."""
        return f"""
        /* Global Window & Base Typography */
        QMainWindow, QWidget {{
            background-color: {tokens["background"]};
            color: {tokens["text"]};
            font-family: "Ubuntu", "Liberation Sans", "DejaVu Sans", "Segoe UI", Inter, Roboto, Helvetica, Arial, sans-serif;
            font-size: 13px;
        }}

        /* Universal High-Contrast Tooltip Styling Across All Views */
        QToolTip {{
            background-color: #161B22;
            color: #FFFFFF;
            border: 1px solid #333A46;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 12px;
            font-weight: 500;
        }}

        /* Smooth Thin Pill Scrollbars */
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 6px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {tokens["border_light"]};
            min-height: 28px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {tokens["primary"]};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            border: none;
            background: transparent;
            height: 6px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: {tokens["border_light"]};
            min-width: 28px;
            border-radius: 3px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {tokens["primary"]};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* Push Buttons */
        QPushButton {{
            background-color: {tokens["surface"]};
            color: {tokens["text"]};
            border: 1px solid {tokens["border"]};
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {tokens["surface_hover"]};
            border-color: {tokens["border_light"]};
        }}
        QPushButton:pressed {{
            background-color: {tokens["surface_alt"]};
        }}
        QPushButton:disabled {{
            background-color: {tokens["surface"]};
            color: {tokens["text_dark"]};
            border-color: {tokens["border"]};
        }}

        /* LineEdits and Inputs */
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background-color: {tokens["surface"]};
            color: {tokens["text"]};
            border: 1px solid {tokens["border"]};
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 13px;
            selection-background-color: {tokens["primary"]};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {tokens["primary"]};
        }}
        QSpinBox, QDoubleSpinBox {{
            padding-right: 20px;
        }}

        /* ComboBox Dropdown */
        QComboBox {{
            padding-right: 28px;
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 24px;
            border: none;
            background: transparent;
        }}
        QComboBox::down-arrow {{
            image: url({_CHEVRON_DOWN_PATH});
            width: 10px;
            height: 6px;
        }}
        QComboBox::down-arrow:hover {{
            image: url({_CHEVRON_DOWN_HOVER_PATH});
        }}
        QComboBox QAbstractItemView {{
            background-color: {tokens["surface"]};
            color: {tokens["text"]};
            border: 1px solid {tokens["border"]};
            border-radius: 8px;
            selection-background-color: {tokens["primary"]};
            selection-color: #FFFFFF;
            padding: 4px;
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{
            min-height: 28px;
            padding: 4px 10px;
            border-radius: 4px;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: {tokens["surface_hover"]};
            color: {tokens["text"]};
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: {tokens["primary"]};
            color: #FFFFFF;
        }}

        /* Labels */
        QLabel {{
            background: transparent;
            color: {tokens["text"]};
        }}

        /* Modern CheckBoxes */
        QCheckBox {{
            color: {tokens["text"]};
            spacing: 8px;
            font-size: 13px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 1px solid {tokens["border_light"]};
            background: {tokens["surface"]};
        }}
        QCheckBox::indicator:hover {{
            border-color: {tokens["primary"]};
        }}
        QCheckBox::indicator:checked {{
            background-color: {tokens["primary"]};
            border-color: {tokens["primary"]};
            image: url({_CHECK_ICON_PATH});
        }}

        /* Dialogs */
        QDialog {{
            background-color: {tokens["surface"]};
            color: {tokens["text"]};
        }}

        /* Modern Progress Bars */
        QProgressBar {{
            background-color: {tokens["surface_alt"]};
            border: none;
            border-radius: 4px;
            text-align: center;
            color: {tokens["text"]};
        }}
        QProgressBar::chunk {{
            background-color: {tokens["primary"]};
            border-radius: 4px;
        }}

        /* Modern Card Frames & GroupBoxes */
        QGroupBox {{
            background-color: {tokens["surface"]};
            border: 1px solid {tokens["border"]};
            border-radius: 12px;
            margin-top: 20px;
            font-weight: 700;
            padding: 16px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 14px;
            color: {tokens["accent"]};
            padding: 0 6px;
        }}

        /* Default QFrame and QLabel must not have unwanted border boxes */
        QFrame {{
            border: none;
        }}
        QLabel {{
            background: transparent;
            border: none;
            color: {tokens["text"]};
        }}

        /* Modern Pill Tab Widgets */
        QTabWidget::pane {{
            border: 1px solid {tokens["border"]};
            background: {tokens["surface"]};
            border-radius: 10px;
            top: -1px;
        }}
        QTabBar::tab {{
            background: {tokens["surface_alt"]};
            color: {tokens["text_muted"]};
            padding: 8px 18px;
            border-radius: 8px;
            margin-right: 6px;
            font-weight: 600;
            font-size: 12px;
            border: 1px solid {tokens["border"]};
        }}
        QTabBar::tab:selected {{
            background: {tokens["primary"]};
            color: #ffffff;
            border: 1px solid {tokens["primary"]};
            font-weight: 700;
        }}
        QTabBar::tab:hover:!selected {{
            background: {tokens["surface_hover"]};
            color: {tokens["text"]};
        }}

        /* Modern ATS Table Styling */
        QTableWidget, QTableView {{
            background-color: {tokens["surface"]};
            alternate-background-color: {tokens["surface"]};
            border: 1px solid {tokens["border"]};
            border-radius: 10px;
            gridline-color: transparent;
            color: {tokens["text"]};
            selection-background-color: {tokens["surface_hover"]};
            selection-color: #FFFFFF;
        }}
        QTableWidget::item:hover, QTableView::item:hover {{
            background-color: {tokens["surface_hover"]};
            color: #FFFFFF;
        }}
        QTableWidget::item:selected, QTableView::item:selected {{
            background-color: {tokens["surface_hover"]};
            color: #FFFFFF;
        }}
        QTableWidget QWidget, QTableView QWidget {{
            background-color: transparent;
        }}
        QHeaderView::section {{
            background-color: {tokens["surface_alt"]};
            color: {tokens["text_muted"]};
            font-weight: 700;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border: none;
            border-bottom: 1px solid {tokens["border"]};
            padding: 10px 14px;
        }}
        QTableCornerButton::section {{
            background-color: {tokens["surface_alt"]};
            border: none;
        }}

        /* Status Bar */
        QStatusBar {{
            background-color: {tokens["surface"]};
            color: {tokens["text_muted"]};
            border-top: 1px solid {tokens["border"]};
            font-size: 12px;
            padding: 4px 12px;
        }}
        QStatusBar QLabel {{
            color: {tokens["text_muted"]};
        }}

        /* ================================================================= */
        /* ATS Application Components Cascade Rules                          */
        /* ================================================================= */

        /* Navigation Shell */
        Sidebar {{
            background-color: {tokens["surface"]};
            border-right: 1px solid {tokens["border"]};
        }}
        Sidebar QWidget#BrandFrame {{
            background-color: {tokens["surface"]};
        }}
        Sidebar QLabel {{
            background: transparent;
            border: none;
        }}
        SidebarBrand {{
            background: transparent;
        }}
        SidebarFooter {{
            background: transparent;
        }}
        CollapseButton {{
            background: transparent;
            border: none;
            border-radius: 6px;
        }}
        CollapseButton:hover {{
            background-color: {tokens["surface_hover"]};
        }}

        /* Top Header Bar */
        TopBar {{
            background-color: {tokens["surface"]};
            border-bottom: 1px solid {tokens["border"]};
        }}
        TopBar QLabel#TopBarTitle {{
            font-size: 16px;
            font-weight: 700;
            color: {tokens["text"]};
        }}
        TopBar QPushButton#TopBarSearch {{
            background-color: {tokens["surface_alt"]};
            color: {tokens["text_muted"]};
            border: 1px solid {tokens["border_light"]};
            border-radius: 18px;
            padding: 7px 16px;
            font-size: 12px;
            font-weight: 500;
            text-align: left;
            min-width: 320px;
        }}
        TopBar QPushButton#TopBarSearch:hover {{
            background-color: {tokens["surface_hover"]};
            color: {tokens["text"]};
            border-color: {tokens["primary"]};
        }}
        TopBar QFrame#UserPill {{
            background-color: {tokens["surface_alt"]};
            border: 1px solid {tokens["border_light"]};
            border-radius: 16px;
            padding: 4px 12px;
        }}
        TopBar QLabel#UserPillName {{
            font-size: 12px;
            font-weight: 600;
            color: {tokens["text"]};
        }}
        TopBar QPushButton#ThemeToggleBtn {{
            background-color: {tokens["surface_alt"]};
            color: {tokens["text"]};
            border: 1px solid {tokens["border_light"]};
            border-radius: 17px;
            font-size: 14px;
            padding: 0px;
        }}
        TopBar QPushButton#ThemeToggleBtn:hover {{
            background-color: {tokens["surface_hover"]};
            border-color: {tokens["primary"]};
        }}
        TopBar QLabel#PlatformLabel {{
            font-size: 11px;
            color: {tokens["text_muted"]};
            font-weight: 600;
        }}

        /* Page Header */
        PageHeader QLabel#PageHeaderTitle {{
            font-size: 22px;
            font-weight: 700;
            color: {tokens["text"]};
            background: transparent;
            border: none;
        }}
        PageHeader QLabel#PageHeaderSubtitle {{
            font-size: 13px;
            color: {tokens["text_muted"]};
            background: transparent;
            border: none;
        }}

        /* Welcome Banner */
        WelcomeBanner {{
            background-color: {tokens["surface"]};
            border: 1px solid {tokens["border"]};
            border-radius: 14px;
        }}
        WelcomeBanner QLabel#WelcomeGreeting {{
            color: {tokens["text"]};
            font-size: 18px;
            font-weight: 800;
            letter-spacing: -0.3px;
        }}
        WelcomeBanner QLabel#WelcomeStatus {{
            color: {tokens["text_muted"]};
            font-size: 12px;
            font-weight: 500;
        }}
        WelcomeBanner QPushButton#WelcomeSecondaryBtn {{
            background-color: {tokens["surface_alt"]};
            color: {tokens["text"]};
            border: 1px solid {tokens["border_light"]};
            border-radius: 8px;
            padding: 8px 14px;
            font-size: 12px;
            font-weight: 600;
        }}
        WelcomeBanner QPushButton#WelcomeSecondaryBtn:hover {{
            background-color: {tokens["surface_hover"]};
            border-color: {tokens["primary"]};
        }}
        WelcomeBanner QPushButton#WelcomePrimaryBtn {{
            background-color: {tokens["primary"]};
            color: #ffffff;
            border: none;
            border-radius: 8px;
            padding: 8px 18px;
            font-size: 12px;
            font-weight: 700;
        }}
        WelcomeBanner QPushButton#WelcomePrimaryBtn:hover {{
            background-color: {tokens["primary_hover"]};
        }}

        /* Modern Metric Cards */
        ModernMetricCard {{
            background-color: {tokens["surface"]};
            border: 1px solid {tokens["border"]};
            border-radius: 12px;
        }}
        ModernMetricCard:hover {{
            background-color: {tokens["surface_hover"]};
            border-color: {tokens["border_light"]};
        }}
        ModernMetricCard QLabel#MetricTitle {{
            color: {tokens["text_muted"]};
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        ModernMetricCard QLabel#MetricValue {{
            color: {tokens["text"]};
            font-size: 26px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }}

        /* Pipeline Funnel & Schedules */
        PipelineFunnelCard, UpcomingSchedulesCard {{
            background-color: {tokens["surface"]};
            border: 1px solid {tokens["border"]};
            border-radius: 12px;
        }}
        PipelineFunnelCard QLabel#FunnelTitle, UpcomingSchedulesCard QLabel#ScheduleCardTitle {{
            color: {tokens["text"]};
            font-size: 14px;
            font-weight: 700;
        }}
        PipelineFunnelCard QLabel#FunnelTotal, UpcomingSchedulesCard QLabel#ScheduleCount {{
            color: {tokens["text_muted"]};
            font-size: 11px;
            font-weight: 600;
            background-color: {tokens["surface_alt"]};
            padding: 3px 8px;
            border-radius: 6px;
        }}
        ScheduleItemWidget {{
            background-color: {tokens["surface_alt"]};
            border: 1px solid {tokens["border_light"]};
            border-radius: 8px;
        }}
        ScheduleItemWidget QLabel#ScheduleRole {{
            color: {tokens["text"]};
            font-size: 13px;
            font-weight: 600;
        }}
        ScheduleItemWidget QLabel#ScheduleTime {{
            color: {tokens["text_muted"]};
            font-size: 11px;
        }}

        /* Dashboard Frames & Dynamic Rows */
        DashboardView QFrame#DashboardFrame {{
            background-color: {tokens["surface"]};
            border: 1px solid {tokens["border"]};
            border-radius: 12px;
            padding: 14px;
        }}
        DashboardView QLabel#DashboardSectionTitle {{
            font-size: 14px;
            font-weight: 700;
            color: {tokens["text"]};
        }}
        DashboardView QWidget#DashboardRow {{
            background-color: {tokens["surface_alt"]};
            border: 1px solid {tokens["border_light"]};
            border-radius: 8px;
        }}
        DashboardView QLabel#DashboardRowTitle {{
            font-weight: 700;
            color: {tokens["text"]};
            font-size: 12px;
        }}
        DashboardView QLabel#DashboardRowSub {{
            color: {tokens["text_muted"]};
            font-size: 11px;
        }}
        PipelineFunnelCard QLabel#FunnelCount {{
            color: {tokens["text"]};
            font-size: 13px;
            font-weight: 700;
        }}

        DashboardView QLabel#DashboardRowBadge {{
            background-color: {tokens["surface_alt"]};
            color: {tokens["accent"]};
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 700;
        }}
        """

    @classmethod
    def apply_dark_theme(cls, app) -> None:
        """Applies refined dark canvas stylesheet to the QApplication."""
        cls.current_mode = "dark"
        COLORS.clear()
        COLORS.update(DARK_COLORS)
        try:
            from PySide6.QtGui import QPalette, QColor
            pal = app.palette()
            pal.setColor(QPalette.ToolTipBase, QColor("#161B22"))
            pal.setColor(QPalette.ToolTipText, QColor("#FFFFFF"))
            app.setPalette(pal)
        except Exception:
            pass
        app.setStyleSheet(cls.get_stylesheet(DARK_COLORS))
        cls.notify_listeners("dark")

    @classmethod
    def apply_light_theme(cls, app) -> None:
        """Applies crisp light canvas stylesheet to the QApplication."""
        cls.current_mode = "light"
        COLORS.clear()
        COLORS.update(LIGHT_COLORS)
        app.setStyleSheet(cls.get_stylesheet(LIGHT_COLORS))
        cls.notify_listeners("light")

    @classmethod
    def toggle_theme(cls, app) -> str:
        """Toggles between dark and light themes, returning the newly active mode name."""
        if cls.current_mode == "dark":
            cls.apply_light_theme(app)
            return "light"
        else:
            cls.apply_dark_theme(app)
            return "dark"

    @classmethod
    def get_brand_dir(cls) -> Path:
        """Returns directory containing brand icon assets."""
        return Path(__file__).parent / "assets" / "brand"

    @classmethod
    def get_app_icon(cls):
        """Returns a multi-resolution QIcon for desktop windows and dialogs."""
        from PySide6.QtGui import QIcon
        icon = QIcon()
        brand_dir = cls.get_brand_dir()
        for size in [16, 24, 32, 48, 64, 128, 256, 512]:
            path = brand_dir / f"jobpilot_{size}.png"
            if path.exists():
                icon.addFile(str(path))
        if icon.isNull():
            master = brand_dir / "jobpilot.png"
            if master.exists():
                icon.addFile(str(master))
        return icon

    @classmethod
    def get_tray_icon(cls, active: bool = False, variant: str = "app"):
        """Returns optimized QIcon for OS system tray."""
        from PySide6.QtGui import QIcon
        brand_dir = cls.get_brand_dir()
        if variant == "avatar":
            fn = "jobpilot_tray_avatar_active.png" if active else "jobpilot_tray_avatar.png"
        else:
            fn = "jobpilot_tray_active.png" if active else "jobpilot_tray.png"
        path = brand_dir / fn
        if path.exists():
            return QIcon(str(path))
        return cls.get_app_icon()

    @classmethod
    def get_brand_pixmap(cls, size: int = 32, variant: str = "app"):
        """Returns high-quality scaled brand QPixmap."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPixmap
        brand_dir = cls.get_brand_dir()
        if variant == "badge":
            fn = "jobpilot_badge.png"
        else:
            fn = f"jobpilot_{size}.png" if (brand_dir / f"jobpilot_{size}.png").exists() else "jobpilot.png"
        path = brand_dir / fn
        if not path.exists():
            path = brand_dir / "jobpilot.png"
        if path.exists():
            pix = QPixmap(str(path))
            return pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QPixmap()

