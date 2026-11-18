"""
Global Wheel Event Filter for JobPilot UI.

Prevents accidental editing of form inputs (QComboBox, QSpinBox, QDoubleSpinBox,
QSlider, QDateTimeEdit) when scrolling views or dialogs with the mouse wheel.
When a user scrolls over these input controls, the wheel event is redirected to the
nearest ancestor QScrollArea so the page scrolls smoothly without altering field values.
"""

from typing import Optional
from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QAbstractSpinBox,
    QSlider,
    QDateTimeEdit,
    QScrollArea,
)


class NoWheelEditFilter(QObject):
    """Event filter intercepting wheel events on input widgets to prevent accidental value changes."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel:
            if isinstance(watched, (QComboBox, QAbstractSpinBox, QSlider, QDateTimeEdit)):
                # If QComboBox dropdown list is currently visible, allow scrolling within the list
                if isinstance(watched, QComboBox):
                    try:
                        view = watched.view()
                        if view and view.isVisible():
                            return False
                    except Exception:
                        pass

                # Prevent value modification: forward wheel event to ancestor QScrollArea if present
                parent = watched.parentWidget()
                while parent is not None:
                    if isinstance(parent, QScrollArea):
                        parent.viewport().event(event)
                        return True
                    parent = parent.parentWidget()

                # If not inside a scroll area, suppress wheel editing to prevent accidental changes
                return True

        return super().eventFilter(watched, event)


_global_wheel_filter: Optional[NoWheelEditFilter] = None


def install_no_wheel_edit_filter(app: Optional[QApplication] = None) -> Optional[NoWheelEditFilter]:
    """Installs the NoWheelEditFilter globally on the QApplication instance."""
    global _global_wheel_filter
    target_app = app or QApplication.instance()
    if target_app and _global_wheel_filter is None:
        _global_wheel_filter = NoWheelEditFilter(parent=target_app)
        target_app.installEventFilter(_global_wheel_filter)
    return _global_wheel_filter

