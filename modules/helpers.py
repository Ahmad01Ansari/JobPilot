'''
Helper Functions
'''



# Imports

import os
import sys
import json
import pathlib

from time import sleep
from random import randint
from datetime import datetime, timedelta
from pprint import pprint

from config.settings import logs_folder_path


def _show_qt_alert(text: str, title: str = "JobPilot Alert", button: str = "OK", poll_condition=None) -> None:
    """Renders a modern PySide6 dark-themed alert dialog."""
    from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
    from PySide6.QtCore import Qt, QTimer

    app = QApplication.instance() or QApplication([])

    dlg = QDialog()
    dlg.setWindowTitle(str(title))
    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
    dlg.setFixedWidth(480)
    dlg.setStyleSheet("""
        QDialog {
            background-color: #0d1117;
            border: 1px solid #30363d;
            border-radius: 12px;
        }
        QLabel {
            color: #f0f6fc;
            font-family: 'Segoe UI', Ubuntu, Cantarell, sans-serif;
        }
        QPushButton {
            background-color: #ff5f15;
            color: #ffffff;
            font-size: 13px;
            font-weight: 700;
            border-radius: 6px;
            padding: 9px 22px;
            border: none;
        }
        QPushButton:hover {
            background-color: #e04f0f;
        }
    """)

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(14)

    hdr = QLabel(f"<b>{title}</b>")
    hdr.setStyleSheet("font-size: 15px; font-weight: 700; color: #ff5f15;")
    layout.addWidget(hdr)

    msg_lbl = QLabel(str(text or ""))
    msg_lbl.setStyleSheet("font-size: 13px; color: #c9d1d9; line-height: 1.4;")
    msg_lbl.setWordWrap(True)
    layout.addWidget(msg_lbl)

    btn_layout = QHBoxLayout()
    btn_layout.addStretch()
    btn = QPushButton(str(button))
    btn.clicked.connect(dlg.accept)
    btn_layout.addWidget(btn)
    layout.addLayout(btn_layout)

    if poll_condition:
        timer = QTimer(dlg)
        def _check_poll():
            try:
                if poll_condition():
                    timer.stop()
                    dlg.accept()
            except Exception:
                pass
        timer.timeout.connect(_check_poll)
        timer.start(1000)

    dlg.exec()


_helpers_dispatcher = None

def _get_helpers_dispatcher():
    global _helpers_dispatcher
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QObject, Signal, Slot, Qt

    app = QApplication.instance()
    if not app:
        return None
    if _helpers_dispatcher is None:
        class _QtHelpersDispatcher(QObject):
            request_confirm = Signal(object)
            request_goal = Signal(object)

            def __init__(self):
                super().__init__()
                self.confirm_result = None
                self.goal_result = None
                self.request_confirm.connect(self._handle_confirm, Qt.BlockingQueuedConnection)
                self.request_goal.connect(self._handle_goal, Qt.BlockingQueuedConnection)

            @Slot(object)
            def _handle_confirm(self, params):
                self.confirm_result = _create_and_exec_qt_confirm(**params)

            @Slot(object)
            def _handle_goal(self, params):
                self.goal_result = _create_and_exec_qt_goal(**params)

        _helpers_dispatcher = _QtHelpersDispatcher()
        _helpers_dispatcher.moveToThread(app.thread())
    return _helpers_dispatcher


def _create_and_exec_qt_confirm(
    text: str = "",
    title: str = "JobPilot Confirmation",
    buttons: list = None,
    poll_condition=None,
    timeout_seconds: int = None,
) -> str:
    """Renders a modern PySide6 dark-themed confirmation dialog."""
    from PySide6.QtWidgets import (
        QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
    )
    from PySide6.QtCore import Qt, QTimer

    btns = list(buttons or ["OK", "Cancel"])
    default_res = btns[-1] if btns else "OK"

    dlg = QDialog()
    dlg.setWindowTitle(str(title))
    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
    dlg.setFixedWidth(600)
    dlg.setStyleSheet("""
        QDialog {
            background-color: #0d1117;
            border: 1px solid #30363d;
            border-radius: 12px;
        }
        QLabel {
            color: #f0f6fc;
            font-family: 'Segoe UI', Ubuntu, Cantarell, sans-serif;
        }
        QPushButton#btn_primary {
            background-color: #238636;
            color: #ffffff;
            font-size: 13px;
            font-weight: 700;
            border-radius: 6px;
            padding: 10px 22px;
            border: 1px solid rgba(240, 246, 252, 0.1);
        }
        QPushButton#btn_primary:hover {
            background-color: #2ea043;
        }
        QPushButton#btn_secondary {
            background-color: #21262d;
            color: #f0f6fc;
            font-size: 13px;
            font-weight: 600;
            border-radius: 6px;
            padding: 10px 20px;
            border: 1px solid #30363d;
        }
        QPushButton#btn_secondary:hover {
            background-color: #30363d;
        }
        QPushButton#btn_danger {
            background-color: #21262d;
            color: #f85149;
            font-size: 13px;
            font-weight: 600;
            border-radius: 6px;
            padding: 10px 20px;
            border: 1px solid #30363d;
        }
        QPushButton#btn_danger:hover {
            background-color: #b62324;
            color: #ffffff;
            border-color: #b62324;
        }
    """)

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(14)

    header = QLabel(f"<b>{title}</b>")
    header.setStyleSheet("font-size: 16px; font-weight: 700; color: #ff5f15;")
    layout.addWidget(header)

    msg_str = str(text or "")
    if "Option 1" in msg_str or "2FA" in title or "Two-Factor" in msg_str:
        desc = QLabel("LinkedIn requires security verification to sign in:")
        desc.setStyleSheet("font-size: 13px; color: #8b949e;")
        layout.addWidget(desc)

        card = QFrame()
        card.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px;")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(8)

        step1 = QLabel("<b style='color: #58a6ff;'>Step 1:</b> Open your LinkedIn mobile app and tap <b>'Yes'</b>.")
        step1.setStyleSheet("font-size: 13px; color: #c9d1d9;")
        step1.setWordWrap(True)

        step2 = QLabel("<b style='color: #58a6ff;'>Step 2:</b> Or enter the SMS / authenticator code directly in Chrome.")
        step2.setStyleSheet("font-size: 13px; color: #c9d1d9;")
        step2.setWordWrap(True)

        card_layout.addWidget(step1)
        card_layout.addWidget(step2)
        layout.addWidget(card)

        info_lbl = QLabel("After approving on your phone or in Chrome, click <b>'I Have Authenticated'</b> below to begin applying.")
        info_lbl.setStyleSheet("font-size: 12.5px; color: #8b949e;")
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)
    else:
        msg_lbl = QLabel(msg_str)
        msg_lbl.setStyleSheet("font-size: 13px; color: #c9d1d9; line-height: 1.4;")
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

    status_card = None
    status_lbl = None
    remaining = [timeout_seconds] if (timeout_seconds and timeout_seconds > 0) else [None]
    if poll_condition or remaining[0] is not None:
        status_card = QFrame()
        status_card.setStyleSheet("background-color: rgba(255, 119, 51, 0.12); border: 1px solid rgba(255, 119, 51, 0.35); border-radius: 6px; padding: 10px;")
        s_layout = QHBoxLayout(status_card)
        s_layout.setContentsMargins(12, 8, 12, 8)
        timer_text = f"⏱ Active waiting... ({remaining[0]}s remaining)" if remaining[0] else "⏱ Active waiting..."
        status_lbl = QLabel(timer_text)
        status_lbl.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #ff7733;")
        status_lbl.setWordWrap(True)
        s_layout.addWidget(status_lbl)
        layout.addWidget(status_card)

    result = [default_res]

    btn_layout = QHBoxLayout()
    btn_layout.setSpacing(12)
    btn_layout.addStretch()

    btn_primary = None
    for b_text in btns:
        btn = QPushButton(b_text)
        b_lower = b_text.lower()
        if "authenticated" in b_lower or any(w in b_lower for w in ["submit", "approve", "continue", "look", "yes", "ok", "confirm"]):
            btn.setObjectName("btn_primary")
            btn_primary = btn
        elif any(w in b_lower for w in ["discard", "cancel", "no", "stop"]):
            btn.setObjectName("btn_danger")
        else:
            btn.setObjectName("btn_secondary")

        def _make_handler(val):
            return lambda: _on_click(val)

        def _on_click(val):
            result[0] = val
            dlg.accept()

        btn.clicked.connect(_make_handler(b_text))
        btn_layout.addWidget(btn)

    layout.addLayout(btn_layout)

    # Polling & countdown logic
    if poll_condition or remaining[0] is not None:
        auth_detected = [False]
        timer = QTimer(dlg)

        def _on_timer_tick():
            # Check if user has authenticated in browser/mobile
            if poll_condition and not auth_detected[0]:
                try:
                    if poll_condition():
                        auth_detected[0] = True
                        if status_card and status_lbl:
                            status_card.setStyleSheet("background-color: rgba(63, 185, 80, 0.15); border: 1px solid rgba(63, 185, 80, 0.4); border-radius: 6px; padding: 10px;")
                            status_lbl.setText("✓ Authentication detected in browser! Click 'I Have Authenticated' below to proceed.")
                            status_lbl.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #3fb950;")
                        if btn_primary:
                            btn_primary.setFocus()
                except Exception:
                    pass

            if remaining[0] is not None:
                remaining[0] -= 1
                if not auth_detected[0] and status_lbl:
                    status_lbl.setText(f"⏱ Active waiting... ({remaining[0]}s remaining)")
                if remaining[0] <= 0:
                    result[0] = "timed_out"
                    timer.stop()
                    dlg.reject()
                    return

        timer.timeout.connect(_on_timer_tick)
        timer.start(1000)

    dlg.exec()
    return result[0]


def _create_and_exec_qt_goal(platform_name: str, current_count: int, current_goal: int) -> tuple[bool, int]:
    """Renders a modern PySide6 dark-themed daily goal reached dialog."""
    from PySide6.QtWidgets import (
        QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox, QFrame
    )
    from PySide6.QtCore import Qt

    dlg = QDialog()
    dlg.setWindowTitle(f"Daily Goal Reached — {platform_name}")
    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
    dlg.setFixedWidth(560)
    dlg.setStyleSheet("""
        QDialog {
            background-color: #0d1117;
            border: 1px solid #30363d;
            border-radius: 12px;
        }
        QLabel {
            color: #f0f6fc;
            font-family: 'Segoe UI', Ubuntu, Cantarell, sans-serif;
        }
        QPushButton#btn_continue {
            background-color: #ff5f15;
            color: #ffffff;
            font-size: 13px;
            font-weight: 700;
            border-radius: 6px;
            padding: 10px 22px;
            border: none;
        }
        QPushButton#btn_continue:hover {
            background-color: #e04f0f;
        }
        QPushButton#btn_stop {
            background-color: #21262d;
            color: #f0f6fc;
            font-size: 13px;
            font-weight: 600;
            border-radius: 6px;
            padding: 10px 20px;
            border: 1px solid #30363d;
        }
        QPushButton#btn_stop:hover {
            background-color: #30363d;
        }
        QSpinBox {
            background-color: #161b22;
            color: #ffffff;
            font-size: 14px;
            font-weight: 700;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 4px 8px;
            min-height: 32px;
        }
        QSpinBox:focus {
            border-color: #ff5f15;
        }
    """)

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(26, 22, 26, 22)
    layout.setSpacing(14)

    header = QLabel(f"Daily Application Goal Reached — {platform_name}")
    header.setStyleSheet("font-size: 16px; font-weight: 700; color: #ff5f15;")
    layout.addWidget(header)

    desc = QLabel(f"You have submitted <b>{current_count}</b> job application(s) today, reaching your configured daily goal of <b>{current_goal}</b>.")
    desc.setStyleSheet("font-size: 13px; color: #c9d1d9;")
    desc.setWordWrap(True)
    layout.addWidget(desc)

    advisory = QFrame()
    advisory.setStyleSheet("background-color: rgba(210, 153, 34, 0.08); border-left: 3px solid #d29922; border-radius: 4px; padding: 10px;")
    adv_layout = QVBoxLayout(advisory)
    adv_layout.setContentsMargins(14, 10, 14, 10)
    adv_layout.setSpacing(4)
    adv_title = QLabel("Account Safety Advisory")
    adv_title.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #e3b341;")
    adv_body = QLabel(f"Applying to more than 50 jobs per day can trigger automated rate limits or account restrictions on {platform_name}.")
    adv_body.setStyleSheet("font-size: 12px; color: #c9d1d9; line-height: 1.4;")
    adv_body.setWordWrap(True)
    adv_layout.addWidget(adv_title)
    adv_layout.addWidget(adv_body)
    layout.addWidget(advisory)

    prompt = QLabel("Do you want to continue applying to more jobs? If yes, specify how many additional jobs to apply for:")
    prompt.setStyleSheet("font-size: 12.5px; color: #8b949e;")
    prompt.setWordWrap(True)
    layout.addWidget(prompt)

    input_row = QHBoxLayout()
    input_row.setSpacing(12)
    lbl_input = QLabel("Additional jobs to apply:")
    lbl_input.setStyleSheet("font-size: 13px; font-weight: 600; color: #f0f6fc;")
    spn = QSpinBox()
    spn.setRange(1, 200)
    spn.setValue(10)
    spn.setSingleStep(5)
    spn.setFixedWidth(100)
    input_row.addWidget(lbl_input)
    input_row.addWidget(spn)
    input_row.addStretch()
    layout.addLayout(input_row)

    layout.addSpacing(6)

    result = [False, 0]

    btn_layout = QHBoxLayout()
    btn_layout.setSpacing(12)
    btn_stop = QPushButton("Stop Automation (Recommended)")
    btn_stop.setObjectName("btn_stop")
    def _on_stop():
        result[0] = False
        result[1] = 0
        dlg.reject()
    btn_stop.clicked.connect(_on_stop)

    btn_continue = QPushButton("Continue Applying")
    btn_continue.setObjectName("btn_continue")
    def _on_continue():
        result[0] = True
        result[1] = spn.value()
        dlg.accept()
    btn_continue.clicked.connect(_on_continue)

    btn_layout.addWidget(btn_stop)
    btn_layout.addStretch()
    btn_layout.addWidget(btn_continue)
    layout.addLayout(btn_layout)

    dlg.exec()
    return result[0], result[1]


def _show_qt_confirm(
    text: str = "",
    title: str = "JobPilot Confirmation",
    buttons: list = None,
    poll_condition=None,
    timeout_seconds: int = None,
) -> str:
    """Renders a modern PySide6 dark-themed confirmation dialog safely on the main GUI thread."""
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QThread

        app = QApplication.instance()
        if not app:
            return None

        # If already on the Qt main thread, execute directly
        if QThread.currentThread() == app.thread():
            return _create_and_exec_qt_confirm(text, title, buttons, poll_condition, timeout_seconds)

        # If on a secondary worker thread, dispatch to Qt main thread
        dispatcher = _get_helpers_dispatcher()
        if dispatcher:
            dispatcher.request_confirm.emit({
                "text": text,
                "title": title,
                "buttons": buttons,
                "poll_condition": poll_condition,
                "timeout_seconds": timeout_seconds,
            })
            return dispatcher.confirm_result
        return None
    except Exception as e:
        print_lg(f"[show_qt_confirm dispatch notice] {e}")
        return None


def _show_qt_goal_dialog(platform_name: str, current_count: int, current_goal: int) -> tuple[bool, int]:
    """Renders a modern PySide6 daily goal reached dialog safely on the main GUI thread."""
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QThread

        app = QApplication.instance()
        if not app:
            return False, 0

        # If already on the Qt main thread, execute directly
        if QThread.currentThread() == app.thread():
            return _create_and_exec_qt_goal(platform_name, current_count, current_goal)

        # If on a secondary worker thread, dispatch to Qt main thread
        dispatcher = _get_helpers_dispatcher()
        if dispatcher:
            dispatcher.request_goal.emit({
                "platform_name": platform_name,
                "current_count": current_count,
                "current_goal": current_goal,
            })
            return dispatcher.goal_result or (False, 0)
        return False, 0
    except Exception as e:
        print_lg(f"[show_qt_goal_dialog dispatch notice] {e}")
        return False, 0


def show_modern_alert(
    text: str = "",
    title: str = "JobPilot Alert",
    button: str = "OK",
    poll_condition=None,
) -> None:
    """
    Renders an error or notification dialog styled with JobPilot's Refined Dark Palette.
    Replaces legacy/default OS alert popups across the bot.
    """
    import sys
    import os

    msg = str(text or "")
    print(f"[{title}] {msg}")

    # Headless / unit test guard
    if "unittest" in sys.modules or os.environ.get("TESTING") == "1":
        return

    if sys.platform != "win32" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return

    # 1. Try modern PySide6 dialog first
    try:
        _show_qt_alert(text=msg, title=title, button=button, poll_condition=poll_condition)
        return
    except Exception as qt_err:
        pass

    # 2. Resilient Tkinter fallback
    try:
        import tkinter as tk
        import tkinter.font as tkfont

        root = tk.Tk()
        root.title(str(title))
        root.configure(bg="#0F1117")
        root.minsize(480, 200)
        root.resizable(False, False)

        try:
            root.tk.call('tk', 'scaling', 1.33)
        except Exception:
            pass

        try:
            root.attributes("-topmost", True)
        except Exception:
            pass

        families = set(tkfont.families(root))
        sys_font = "sans-serif"
        for candidate in ["texgyreheros", "nimbus sans l", "latin modern sans", "helvetica", "avantgarde"]:
            if candidate in families:
                sys_font = candidate
                break

        header = tk.Frame(root, bg="#161B22", padx=20, pady=12, highlightbackground="#262C36", highlightthickness=1)
        header.pack(fill="x")

        hdr_lbl = tk.Label(
            header,
            text=str(title),
            font=(sys_font, 11, "bold"),
            fg="#FF5F15",
            bg="#161B22",
            anchor="w",
        )
        hdr_lbl.pack(fill="x")

        body = tk.Frame(root, bg="#0F1117", padx=20, pady=16)
        body.pack(fill="both", expand=True)

        msg_lbl = tk.Label(
            body,
            text=msg,
            font=(sys_font, 10),
            fg="#F0F6FC",
            bg="#0F1117",
            wraplength=440,
            justify="left",
            anchor="w",
        )
        msg_lbl.pack(fill="both", expand=True)

        btn_bar = tk.Frame(root, bg="#161B22", padx=20, pady=12, highlightbackground="#262C36", highlightthickness=1)
        btn_bar.pack(fill="x", side="bottom")

        def _close(event=None):
            try:
                root.destroy()
            except Exception:
                pass

        def _bind_keys():
            try:
                root.bind("<Return>", _close)
                root.bind("<Escape>", _close)
            except Exception:
                pass
        root.after(1000, _bind_keys)

        btn = tk.Button(
            btn_bar,
            text=str(button),
            command=_close,
            bg="#FF5F15",
            fg="#FFFFFF",
            activebackground="#E04F0F",
            activeforeground="#FFFFFF",
            font=(sys_font, 10, "bold"),
            padx=20,
            pady=6,
            cursor="hand2",
            relief="flat",
            bd=0,
        )
        btn.pack(side="right")

        if poll_condition:
            def _poll_check():
                try:
                    if poll_condition():
                        _close()
                        return
                except Exception:
                    pass
                try:
                    root.after(1000, _poll_check)
                except Exception:
                    pass
            root.after(1000, _poll_check)

        root.update_idletasks()
        w = max(root.winfo_width(), 480)
        h = max(root.winfo_height(), 200)
        x = (root.winfo_screenwidth() // 2) - (w // 2)
        y = (root.winfo_screenheight() // 2) - (h // 2)
        root.geometry(f"{w}x{h}+{x}+{y}")

        root.lift()
        root.after_idle(root.attributes, "-topmost", True)
        root.after(100, root.lift)
        root.after(200, root.focus_force)
        body.focus_set()
        root.mainloop()
    except Exception as e:
        print(f"[show_modern_alert fallback] {e}")


alert = show_modern_alert


def show_modern_confirm(
    text: str = "",
    title: str = "JobPilot Confirmation",
    buttons: list = None,
    poll_condition=None,
    timeout_seconds: int = None,
) -> str:
    """
    Renders an interactive confirmation dialog styled with JobPilot's Refined Dark Palette.
    Replaces legacy pyautogui.confirm calls.
    Returns the string text of the button clicked by the user, or 'timed_out' if timeout_seconds expires.
    """
    import sys
    import os

    btns = list(buttons or ["OK", "Cancel"])
    default_res = btns[-1] if btns else "OK"

    msg = str(text or "")
    print_lg(f"[{title}] {msg}")

    # Headless / unit test guard
    if os.environ.get("TESTING") == "1":
        return btns[0] if btns else "OK"

    if sys.platform != "win32" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return btns[0] if btns else "OK"

    # 1. Try modern PySide6 dialog first
    try:
        return _show_qt_confirm(
            text=msg,
            title=title,
            buttons=btns,
            poll_condition=poll_condition,
            timeout_seconds=timeout_seconds,
        )
    except Exception as qt_err:
        pass

    # 2. Resilient Tkinter fallback
    result = [default_res]

    try:
        import tkinter as tk
        import tkinter.font as tkfont

        root = tk.Tk()
        root.title(str(title))
        root.configure(bg="#0F1117")
        root.minsize(560, 260)
        root.resizable(False, False)

        try:
            root.tk.call('tk', 'scaling', 1.33)
        except Exception:
            pass

        try:
            root.attributes("-topmost", True)
        except Exception:
            pass

        families = set(tkfont.families(root))
        sys_font = "sans-serif"
        for candidate in ["texgyreheros", "nimbus sans l", "latin modern sans", "helvetica", "avantgarde"]:
            if candidate in families:
                sys_font = candidate
                break

        # Header Frame (Top)
        header = tk.Frame(root, bg="#161B22", padx=20, pady=12, highlightbackground="#262C36", highlightthickness=1)
        header.pack(fill="x", side="top")

        hdr_lbl = tk.Label(
            header,
            text=str(title),
            font=(sys_font, 11, "bold"),
            fg="#FF5F15",
            bg="#161B22",
            anchor="w",
        )
        hdr_lbl.pack(fill="x")

        # Action Bar (Bottom)
        btn_bar = tk.Frame(root, bg="#161B22", padx=20, pady=12, highlightbackground="#262C36", highlightthickness=1)
        btn_bar.pack(fill="x", side="bottom")

        def _make_handler(btn_text):
            def _handler(event=None):
                result[0] = btn_text
                try:
                    root.destroy()
                except Exception:
                    pass
            return _handler

        root.protocol("WM_DELETE_WINDOW", _make_handler(default_res))

        # Add buttons right-to-left
        primary_btn_widget = None
        for i, b_text in enumerate(reversed(btns)):
            b_lower = b_text.lower()
            if "authenticated" in b_lower or any(w in b_lower for w in ["submit", "approve", "continue", "look", "yes", "ok", "confirm"]):
                bg_col = "#238636"
                act_col = "#2EA043"
            elif any(w in b_lower for w in ["discard", "cancel", "no", "stop"]):
                bg_col = "#21262D"
                act_col = "#B62324"
            else:
                bg_col = "#21262D"
                act_col = "#30363D"

            btn = tk.Button(
                btn_bar,
                text=b_text,
                command=_make_handler(b_text),
                bg=bg_col,
                fg="#FFFFFF",
                activebackground=act_col,
                activeforeground="#FFFFFF",
                font=(sys_font, 10, "bold"),
                padx=16,
                pady=7,
                cursor="hand2",
                relief="flat",
                bd=0,
            )
            btn.pack(side="right", padx=(6, 0))
            if "authenticated" in b_lower or i == 0:
                primary_btn_widget = btn

        def _bind_keys():
            try:
                root.bind("<Escape>", _make_handler(default_res))
            except Exception:
                pass
        root.after(1000, _bind_keys)

        # Message Body
        body = tk.Frame(root, bg="#0F1117", padx=24, pady=16)
        body.pack(fill="both", expand=True)

        clean_text = msg.replace("📱 ", "[Step 1] ").replace("🔑 ", "[Step 2] ")
        msg_lbl = tk.Label(
            body,
            text=clean_text,
            font=(sys_font, 10),
            fg="#F0F6FC",
            bg="#0F1117",
            wraplength=510,
            justify="left",
            anchor="w",
        )
        msg_lbl.pack(fill="both", expand=True)

        timer_remaining = [timeout_seconds] if (timeout_seconds and timeout_seconds > 0) else [None]
        timer_lbl = None
        if timer_remaining[0] is not None:
            timer_lbl = tk.Label(
                body,
                text=f"• Active waiting... ({timer_remaining[0]}s remaining)",
                font=(sys_font, 10, "bold"),
                fg="#FF5F15",
                bg="#0F1117",
                anchor="w",
            )
            timer_lbl.pack(fill="x", pady=(10, 0))

        if poll_condition or (timer_remaining[0] is not None):
            auth_detected = [False]
            def _poll_check():
                if poll_condition and not auth_detected[0]:
                    try:
                        if poll_condition():
                            auth_detected[0] = True
                            if timer_lbl:
                                timer_lbl.config(
                                    text="✓ Authentication detected in browser! Click 'I Have Authenticated' below to proceed.",
                                    fg="#3FB950",
                                )
                            if primary_btn_widget:
                                primary_btn_widget.focus_set()
                    except Exception:
                        pass

                if timer_remaining[0] is not None:
                    timer_remaining[0] -= 1
                    if not auth_detected[0] and timer_lbl:
                        try:
                            timer_lbl.config(text=f"• Active waiting... ({timer_remaining[0]}s remaining)")
                        except Exception:
                            pass
                    if timer_remaining[0] <= 0:
                        result[0] = "timed_out"
                        try:
                            root.destroy()
                        except Exception:
                            pass
                        return

                try:
                    root.after(1000, _poll_check)
                except Exception:
                    pass
            root.after(1000, _poll_check)

        root.update_idletasks()
        w = max(root.winfo_width(), 560)
        h = max(root.winfo_height(), 260)
        x = max(0, (root.winfo_screenwidth() // 2) - (w // 2))
        y = max(0, (root.winfo_screenheight() // 2) - (h // 2))
        root.geometry(f"{w}x{h}+{x}+{y}")

        root.lift()
        root.after_idle(root.attributes, "-topmost", True)
        root.after(100, root.lift)
        root.after(200, root.focus_force)

        body.focus_set()
        root.mainloop()
        return result[0]
    except Exception as e:
        print_lg(f"[show_modern_confirm fallback] {e}")
        return result[0]


confirm = show_modern_confirm


def show_modern_goal_dialog(
    platform_name: str,
    current_count: int,
    current_goal: int,
) -> tuple[bool, int]:
    """
    Renders a modern dark-themed dialog when the daily application goal is reached.
    Advises the user about account restriction safety limits (LinkedIn/Naukri >50 apps/day),
    and asks whether to cleanly stop automation or continue with an additional number of jobs.

    Returns:
        tuple[bool, int]: (should_continue, additional_count)
    """
    import sys
    import os

    print_lg(
        f"\n[Daily Goal Alert] Reached daily goal of {current_goal} applications on {platform_name} "
        f"(Total applied today: {current_count}). Prompting user for continuation decision."
    )

    # Headless / unit test guard: safely stop in non-interactive environments
    if os.environ.get("TESTING") == "1":
        return False, 0

    if sys.platform != "win32" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return False, 0

    # 1. Try modern PySide6 dialog first
    try:
        return _show_qt_goal_dialog(platform_name=platform_name, current_count=current_count, current_goal=current_goal)
    except Exception as qt_err:
        pass

    # 2. Resilient Tkinter fallback
    result = [False, 0]

    try:
        import tkinter as tk
        import tkinter.font as tkfont

        root = tk.Tk()
        root.title(f"Daily Goal Reached — {platform_name}")
        root.configure(bg="#0F1117")
        root.minsize(560, 310)
        root.resizable(False, False)

        try:
            root.tk.call('tk', 'scaling', 1.33)
        except Exception:
            pass

        families = set(tkfont.families(root))
        sys_font = "sans-serif"
        for candidate in ["texgyreheros", "nimbus sans l", "latin modern sans", "helvetica", "avantgarde"]:
            if candidate in families:
                sys_font = candidate
                break

        # Header Title Bar
        header = tk.Frame(root, bg="#161B22", padx=20, pady=12, highlightbackground="#262C36", highlightthickness=1)
        header.pack(fill="x")

        hdr_lbl = tk.Label(
            header,
            text=f"Daily Application Goal Reached — {platform_name}",
            font=(sys_font, 11, "bold"),
            fg="#FF5F15",
            bg="#161B22",
            anchor="w",
        )
        hdr_lbl.pack(fill="x")

        # Action Bar (Buttons)
        btn_bar = tk.Frame(root, bg="#161B22", padx=20, pady=12, highlightbackground="#262C36", highlightthickness=1)
        btn_bar.pack(fill="x", side="bottom")

        def _on_stop(event=None):
            result[0] = False
            result[1] = 0
            print_lg(f"[Daily Goal Dialog] User decided to STOP automation at {current_count} applications.")
            try:
                root.destroy()
            except Exception:
                pass

        def _on_continue(event=None):
            try:
                val = int(spin_var.get().strip())
                if val <= 0:
                    val = 10
            except Exception:
                val = 10
            result[0] = True
            result[1] = val
            print_lg(f"[Daily Goal Dialog] User decided to CONTINUE with +{val} additional applications.")
            try:
                root.destroy()
            except Exception:
                pass

        root.protocol("WM_DELETE_WINDOW", _on_stop)

        btn_stop = tk.Button(
            btn_bar,
            text="Stop Automation (Recommended)",
            command=_on_stop,
            bg="#21262D",
            fg="#F0F6FC",
            activebackground="#30363D",
            activeforeground="#FFFFFF",
            font=(sys_font, 9, "bold"),
            padx=16,
            pady=7,
            cursor="hand2",
            relief="flat",
            bd=0,
        )
        btn_stop.pack(side="left")

        btn_continue = tk.Button(
            btn_bar,
            text="Continue Applying",
            command=_on_continue,
            bg="#FF5F15",
            fg="#FFFFFF",
            activebackground="#E04F0F",
            activeforeground="#FFFFFF",
            font=(sys_font, 9, "bold"),
            padx=18,
            pady=7,
            cursor="hand2",
            relief="flat",
            bd=0,
        )
        btn_continue.pack(side="right")

        # Body Message Frame
        body = tk.Frame(root, bg="#0F1117", padx=20, pady=14)
        body.pack(fill="both", expand=True)

        msg_text = (
            f"You have submitted {current_count} job application(s) today, reaching your configured daily goal of {current_goal}.\n\n"
            f"[Account Safety Advisory]\n"
            f"Applying more than 50 jobs per day can trigger automated rate limits or account restrictions on {platform_name}.\n\n"
            f"Do you want to continue applying to more jobs? If yes, specify how many additional jobs to apply for:"
        )

        msg_lbl = tk.Label(
            body,
            text=msg_text,
            font=(sys_font, 9),
            fg="#F0F6FC",
            bg="#0F1117",
            wraplength=520,
            justify="left",
            anchor="w",
        )
        msg_lbl.pack(fill="x", pady=(0, 10))

        # Additional applications input row
        input_row = tk.Frame(body, bg="#0F1117")
        input_row.pack(fill="x", pady=4)

        input_lbl = tk.Label(
            input_row,
            text="Additional jobs to apply:",
            font=(sys_font, 10, "bold"),
            fg="#8B949E",
            bg="#0F1117",
        )
        input_lbl.pack(side="left", padx=(0, 10))

        spin_var = tk.StringVar(value="10")
        spinbox = tk.Spinbox(
            input_row,
            from_=1,
            to=200,
            increment=5,
            textvariable=spin_var,
            width=8,
            font=(sys_font, 10, "bold"),
            bg="#161B22",
            fg="#FFFFFF",
            insertbackground="#FFFFFF",
            highlightbackground="#30363D",
            highlightthickness=1,
            relief="flat",
        )
        spinbox.pack(side="left")

        def _bind_keys():
            try:
                spinbox.bind("<Return>", _on_continue)
                root.bind("<Escape>", _on_stop)
            except Exception:
                pass
        root.after(1000, _bind_keys)

        root.update_idletasks()
        w = max(root.winfo_width(), 560)
        h = max(root.winfo_height(), 310)
        x = max(0, (root.winfo_screenwidth() // 2) - (w // 2))
        y = max(0, (root.winfo_screenheight() // 2) - (h // 2))
        root.geometry(f"{w}x{h}+{x}+{y}")

        root.lift()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        root.after_idle(root.attributes, "-topmost", True)
        root.after(100, root.lift)
        root.after(200, root.focus_force)

        spinbox.focus_set()
        spinbox.selection_range(0, "end")

        root.mainloop()
        return result[0], result[1]
    except Exception as e:
        print_lg(f"[show_modern_goal_dialog fallback] {e}")
        return False, 0


# Ensure monkey-patching so legacy pyautogui calls use modern dialogs everywhere
try:
    import pyautogui
    pyautogui.alert = show_modern_alert
    pyautogui.confirm = show_modern_confirm
except Exception:
    pass



#### Common functions ####

#< Directories related
def make_directories(paths: list[str]) -> None:
    '''
    Function to create missing directories
    '''
    for path in paths:
        path = os.path.expanduser(path) # Expands ~ to user's home directory
        path = path.replace("//","/")
        
        # If path looks like a file path, get the directory part
        if '.' in os.path.basename(path):
            path = os.path.dirname(path)

        if not path: # Handle cases where path is empty after dirname
            continue

        try:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True) # exist_ok=True avoids race condition
        except Exception as e:
            print(f'Error while creating directory "{path}": ', e)


def get_default_temp_profile() -> str:
    '''Returns a writable Chrome profile folder for JobPilot browser sessions.'''
    home = pathlib.Path.home()
    if sys.platform.startswith('win'):
        local_app_data = os.environ.get('LOCALAPPDATA')
        base = pathlib.Path(local_app_data) if local_app_data else home / 'AppData' / 'Local'
        new_path = base / 'JobPilotChromeProfile'
        legacy_path = base / 'ApplyAndPrayChromeProfile'
        return str(legacy_path if legacy_path.exists() and not new_path.exists() else new_path)
    elif sys.platform.startswith('linux'):
        new_path = home / '.jobpilot-chrome-profile'
        legacy_path = home / '.apply-and-pray-chrome-profile'
        return str(legacy_path if legacy_path.exists() and not new_path.exists() else new_path)
    new_path = home / 'Library' / 'Application Support' / 'Google' / 'Chrome' / 'JobPilotChromeProfile'
    legacy_path = home / 'Library' / 'Application Support' / 'Google' / 'Chrome' / 'ApplyAndPrayChromeProfile'
    return str(legacy_path if legacy_path.exists() and not new_path.exists() else new_path)

def find_default_profile_directory() -> str | None:
    '''
    Dynamically finds the default Google Chrome 'User Data' directory path
    across Windows, macOS, and Linux, regardless of OS version.

    Returns the absolute path as a string, or None if the path is not found.
    '''
    
    home = pathlib.Path.home()
    
    # Windows
    if sys.platform.startswith('win'):
        paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
            os.path.expandvars(r"%USERPROFILE%\AppData\Local\Google\Chrome\User Data"),
            os.path.expandvars(r"%USERPROFILE%\Local Settings\Application Data\Google\Chrome\User Data")
        ]
    # Linux
    elif sys.platform.startswith('linux'):
        paths = [
            str(home / ".config" / "google-chrome"),
            str(home / ".var" / "app" / "com.google.Chrome" / "data" / ".config" / "google-chrome"),
        ]
    # MacOS ## For some reason, opening with profile in MacOS is not creating a session for undetected-chromedriver!
    # elif sys.platform == 'darwin':
    #     paths = [
    #         str(home / "Library" / "Application Support" / "Google" / "Chrome")
    #     ]
    else:
        return None

    # Check each potential path and return the first one that exists
    for path_str in paths:
        if os.path.exists(path_str):
            return path_str
            
    return None
#>


#< Logging related
def critical_error_log(possible_reason: str, stack_trace: Exception) -> None:
    '''
    Function to log and print critical errors along with datetime stamp
    '''
    print_lg(possible_reason, stack_trace, datetime.now(), from_critical=True)


def get_log_path() -> str:
    '''
    Function to resolve canonical logs path using AppPaths.
    '''
    try:
        from app.services.os.app_paths import AppPaths
        logs_dir = AppPaths.get_logs_dir()
        logs_dir.mkdir(parents=True, exist_ok=True)
        return str((logs_dir / "log.txt").resolve())
    except Exception:
        try:
            path = logs_folder_path + "/log.txt"
            p = pathlib.Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            return str(p.resolve())
        except Exception:
            return "log.txt"


__logs_file_path = get_log_path()
_log_listeners: list = []


def add_log_listener(callback) -> None:
    """Registers a callback to receive log messages in real-time."""
    if callback not in _log_listeners:
        _log_listeners.append(callback)


def remove_log_listener(callback) -> None:
    """Unregisters a previously added log listener callback."""
    if callback in _log_listeners:
        _log_listeners.remove(callback)


def print_lg(*msgs: str | dict, end: str = "\n", pretty: bool = False, flush: bool = False, from_critical: bool = False) -> None:
    '''
    Function to log and print. **Note that, `end` and `flush` parameters are ignored if `pretty = True`**
    '''
    global __logs_file_path
    try:
        log_path = __logs_file_path if __logs_file_path else get_log_path()
        for message in msgs:
            msg_str = str(message)
            try:
                from app.services.sanitizer_service import LogSanitizer
                msg_str = LogSanitizer.sanitize_text(msg_str)
            except Exception:
                pass
            pprint(msg_str) if pretty else print(msg_str, end=end, flush=flush)
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, 'a+', encoding="utf-8") as file:
                    file.write(msg_str + end)
            except Exception as file_err:
                print(f"[Log Error] Could not write to {log_path}: {file_err}", file=sys.stderr)
            for listener in list(_log_listeners):
                try:
                    listener(msg_str)
                except Exception:
                    pass
    except Exception as e:
        print(f"[Logger Warning] Exception in print_lg: {e}", file=sys.stderr)
#>


def buffer(speed: int=0) -> None:
    '''
    Function to wait within a period of selected random range.
    * Will not wait if input `speed <= 0`
    * Will wait within a random range of 
      - `0.6 to 1.0 secs` if `1 <= speed < 2`
      - `1.0 to 1.8 secs` if `2 <= speed < 3`
      - `1.8 to speed secs` if `3 <= speed`
    '''
    if speed<=0:
        return
    elif speed <= 1 and speed < 2:
        return sleep(randint(6,10)*0.1)
    elif speed <= 2 and speed < 3:
        return sleep(randint(10,18)*0.1)
    else:
        return sleep(randint(18,round(speed)*10)*0.1)
    

def manual_login_retry(is_logged_in: callable, limit: int = 3) -> None:
    '''
    Function to ask and validate manual login with modern dark UI
    '''
    count = 0
    while not is_logged_in():
        print_lg("Seems like you're not logged in! Waiting for login...")
        button = "Confirm Login"
        message = f'After you successfully Log In in Chrome, click "{button}" below.\n(Or login will be detected automatically once redirected).'
        if count >= limit:
            button = "Skip Confirmation"
            message = f'If you are already logged in, click "{button}".'
        count += 1
        res = show_modern_confirm(message, "Login Required", [button], poll_condition=is_logged_in)
        if res == "auto_completed" or is_logged_in():
            print_lg("Login detected successfully!")
            return
        for _ in range(5):
            if is_logged_in():
                print_lg("Login detected successfully!")
                return
            sleep(1)
        if count > limit:
            return



def calculate_date_posted(time_string: str) -> datetime | None | ValueError:
    '''
    Function to calculate date posted from string.
    Returns datetime object | None if unable to calculate | ValueError if time_string is invalid
    Valid time string examples:
    * 10 seconds ago
    * 15 minutes ago
    * 2 hours ago
    * 1 hour ago
    * 1 day ago
    * 10 days ago
    * 1 week ago
    * 1 month ago
    * 1 year ago
    '''
    import re
    time_string = time_string.strip()
    now = datetime.now()

    match = re.search(r'(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago', time_string, re.IGNORECASE)

    if match:
        try:
            value = int(match.group(1))
            unit = match.group(2).lower()

            if 'second' in unit:
                return now - timedelta(seconds=value)
            elif 'minute' in unit:
                return now - timedelta(minutes=value)
            elif 'hour' in unit:
                return now - timedelta(hours=value)
            elif 'day' in unit:
                return now - timedelta(days=value)
            elif 'week' in unit:
                return now - timedelta(weeks=value)
            elif 'month' in unit:
                return now - timedelta(days=value * 30)  # Approximation
            elif 'year' in unit:
                return now - timedelta(days=value * 365)  # Approximation
        except (ValueError, IndexError):
            # Fallback for cases where parsing fails
            pass
    
    # If regex doesn't match, or parsing failed, return None.
    # This will skip jobs where the date can't be determined, preventing crashes.
    return None


def convert_to_lakhs(value: str) -> str:
    '''
    Converts str value to lakhs, no validations are done except for length and stripping.
    Examples:
    * "100000" -> "1.00"
    * "101,000" -> "10.1," Notice ',' is not removed 
    * "50" -> "0.00"
    * "5000" -> "0.05" 
    '''
    value = value.strip()
    l = len(value)
    if l > 0:
        if l > 5:
            value = value[:l-5] + "." + value[l-5:l-3]
        else:
            value = "0." + "0"*(5-l) + value[:2]
    return value


def convert_to_json(data) -> dict:
    '''
    Function to convert data to JSON, if unsuccessful, returns `{"error": "Unable to parse the response as JSON", "data": data}`
    '''
    try:
        result_json = json.loads(data)
        return result_json
    except json.JSONDecodeError:
        return {"error": "Unable to parse the response as JSON", "data": data}


def truncate_for_csv(data, max_length: int = 131000, suffix: str = "...[TRUNCATED]") -> str:
    '''
    Function to truncate data for CSV writing to avoid field size limit errors.
    * Takes in `data` of any type and converts to string
    * Takes in `max_length` of type `int` - maximum allowed length (default: 131000, leaving room for suffix)
    * Takes in `suffix` of type `str` - text to append when truncated
    * Returns truncated string if data exceeds max_length
    '''
    try:
        # Convert data to string
        str_data = str(data) if data is not None else ""
        
        # If within limit, return as-is
        if len(str_data) <= max_length:
            return str_data
        
        # Truncate and add suffix
        truncated = str_data[:max_length - len(suffix)] + suffix
        return truncated
    except Exception as e:
        return f"[ERROR CONVERTING DATA: {e}]"