"""
Unit tests for NoWheelEditFilter and Splash Screen Safety.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import (
    QApplication,
    QScrollArea,
    QWidget,
    QVBoxLayout,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QSlider,
    QSplashScreen,
)
from PySide6.QtCore import QPointF, QPoint, Qt
from PySide6.QtGui import QWheelEvent, QPixmap

from app.ui.wheel_filter import NoWheelEditFilter, install_no_wheel_edit_filter


class TestWheelFilterAndSplash(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(["test", "--offscreen"])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.filter = NoWheelEditFilter()
        self.scroll = QScrollArea()
        self.scroll.resize(400, 300)
        self.container = QWidget()
        self.container.resize(400, 1000)
        self.layout = QVBoxLayout(self.container)

        self.spin = QSpinBox()
        self.spin.setRange(0, 100)
        self.spin.setValue(10)

        self.double_spin = QDoubleSpinBox()
        self.double_spin.setRange(0.0, 100.0)
        self.double_spin.setValue(15.5)

        self.combo = QComboBox()
        self.combo.addItems(["Option A", "Option B", "Option C"])
        self.combo.setCurrentIndex(0)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)

        self.layout.addWidget(self.spin)
        self.layout.addWidget(self.double_spin)
        self.layout.addWidget(self.combo)
        self.layout.addWidget(self.slider)

        self.scroll.setWidget(self.container)
        self.scroll.show()

    def tearDown(self):
        self.scroll.close()

    def _create_wheel_event(self, delta_y: int = 120) -> QWheelEvent:
        return QWheelEvent(
            QPointF(10, 10),
            QPointF(10, 10),
            QPoint(0, 0),
            QPoint(0, delta_y),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )

    def test_spinbox_wheel_event_intercepted(self):
        initial_val = self.spin.value()
        ev = self._create_wheel_event(120)

        # Event filter should return True (event intercepted/forwarded)
        handled = self.filter.eventFilter(self.spin, ev)
        self.assertTrue(handled)
        self.assertEqual(self.spin.value(), initial_val)

    def test_doublespinbox_wheel_event_intercepted(self):
        initial_val = self.double_spin.value()
        ev = self._create_wheel_event(120)

        handled = self.filter.eventFilter(self.double_spin, ev)
        self.assertTrue(handled)
        self.assertEqual(self.double_spin.value(), initial_val)

    def test_combobox_wheel_event_intercepted_when_closed(self):
        initial_idx = self.combo.currentIndex()
        ev = self._create_wheel_event(120)

        handled = self.filter.eventFilter(self.combo, ev)
        self.assertTrue(handled)
        self.assertEqual(self.combo.currentIndex(), initial_idx)

    def test_slider_wheel_event_intercepted(self):
        initial_val = self.slider.value()
        ev = self._create_wheel_event(120)

        handled = self.filter.eventFilter(self.slider, ev)
        self.assertTrue(handled)
        self.assertEqual(self.slider.value(), initial_val)

    def test_combobox_wheel_event_allowed_when_popup_open(self):
        mock_view = MagicMock()
        mock_view.isVisible.return_value = True

        with patch.object(self.combo, "view", return_value=mock_view):
            ev = self._create_wheel_event(120)
            # Should return False to let Qt process scrolling inside the dropdown list
            handled = self.filter.eventFilter(self.combo, ev)
            self.assertFalse(handled)

    def test_global_install_helper(self):
        filt = install_no_wheel_edit_filter(self.app)
        self.assertIsNotNone(filt)
        self.assertIsInstance(filt, NoWheelEditFilter)

    def test_splash_screen_flags_no_stays_on_top(self):
        pix = QPixmap(100, 100)
        pix.fill(Qt.GlobalColor.black)
        splash = QSplashScreen(pix, Qt.WindowType.FramelessWindowHint)
        flags = splash.windowFlags()
        # Verify WindowStaysOnTopHint is NOT set
        self.assertFalse(bool(flags & Qt.WindowType.WindowStaysOnTopHint))
        splash.close()


if __name__ == "__main__":
    unittest.main()

