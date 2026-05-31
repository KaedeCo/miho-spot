"""
Miho-spot Backend GUI Panel — PyQt6 Modern Dark Monitor
No business logic is modified. Pure display/status monitor.
"""

import sys
import os
import re
import random
import logging
import threading
import webbrowser
import urllib.request
import json
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QFrame, QPushButton, QCheckBox, QSpacerItem,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QObject
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QPainter, QBrush,
    QTextCursor, QRadialGradient
)

# --- Color Palette ---
BG_DARK   = "#0f0f23"
BG_CARD   = "#1a1a2e"
ACCENT    = "#6366f1"
ACCENT2   = "#a78bfa"
PURPLE    = "#8b5cf6"
GREEN     = "#22c55e"
YELLOW    = "#f59e0b"
RED       = "#ef4444"
TEXT      = "#e2e8f0"
TEXT_DIM  = "#94a3b8"
BORDER    = "#2a2a4a"
FONT_MONO = "Cascadia Code, Cascadia Mono, Consolas, Monaco, Courier New, monospace"

QUOTES = [
    '"这波属于是米哈游送钱给我抽卡，我不抽岂不是亏了？" —— 某氪金玩家',
    '"原神没有逼氪，只是你管不住手而已。" —— 米哈游法务部（虚构）',
    '"我已经卸载三次了，每次都是新版本前两天。" —— 某戒断失败玩家',
    '"米哈游：我们的游戏免费。玩家：我信了。"',
    '"当你发现一个bug，米哈游说这是feature——当玩家利用bug，米哈游说这是违规。" —— 贴吧老哥',
    '"你以为是你在玩游戏？其实是数值策划在玩你。" —— 深渊12层受害者',
    '"歪了莫娜 —— 每个原神玩家的一生之敌。"',
    '"这游戏哪都好，就是有点费钱。" —— 月卡党の谎言',
    '"别再问我为什么还在玩，我自己都不知道。" —— 退坑失败第108次',
    '"社管是工作，米黑是生活。" —— 二游社区定律',
    '"我的圣遗物分比我高考分还高。" —— 某原神玩家',
    '"米哈游：我们听取了玩家意见。玩家：哪个意见？"',
    '"不要问角色强不强，问你的钱包厚不厚。"',
    '"崩铁：一款副游做成主游，主游做成上班的游戏。"',
    '"我玩米哈游游戏不是因为它们好玩，是因为沉没成本。"',
]


class EmittingStream(QObject):
    text_written = pyqtSignal(str, str)

    def __init__(self, level="info"):
        super().__init__()
        self.level = level

    def write(self, text):
        if text and text.strip():
            self.text_written.emit(text.rstrip(), self.level)

    def flush(self):
        pass

    def isatty(self):
        return False

    def fileno(self):
        raise OSError


class StatusDot(QWidget):
    def __init__(self, color, size=10):
        super().__init__()
        self._color = QColor(color)
        self._size = size
        self.setFixedSize(size + 6, size + 6)
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(1.0)
        self.setGraphicsEffect(self._fx)
        self._anim = QPropertyAnimation(self._fx, b"opacity")
        self._anim.setDuration(1200)
        self._anim.setStartValue(0.35)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setLoopCount(-1)
        self._anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        r = self._size / 2
        grad = QRadialGradient(cx, cy, r + 2)
        grad.setColorAt(0, self._color)
        c2 = QColor(self._color)
        c2.setAlphaF(0.05)
        grad.setColorAt(1, c2)
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))


class QuoteLabel(QLabel):
    def __init__(self):
        super().__init__()
        self._quotes = QUOTES[:]
        random.shuffle(self._quotes)
        self._idx = 0
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"color: {ACCENT2}; font-size: 15px; font-style: italic; padding: 6px;")
        self.setText(self._quotes[0])
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.start(8000)

    def _rotate(self):
        self._idx = (self._idx + 1) % len(self._quotes)
        self.setText(self._quotes[self._idx])


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            Card {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 rgba(24,24,50,0.9), stop:1 rgba(30,30,60,0.75));
                border:1px solid {BORDER}; border-radius:10px; }}
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(14)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)


class MihoSpotMonitor(QMainWindow):
    def __init__(self, backend_port=8000):
        super().__init__()
        self.backend_port = backend_port
        self._init_ui()
        self._setup_log_capture()
        self._start_status_timers()

    def _init_ui(self):
        self.setWindowTitle("Miho-spot Monitor")
        self.resize(1200, 700)
        self.setMinimumSize(900, 520)

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(BG_DARK))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
        palette.setColor(QPalette.ColorRole.Base, QColor(BG_CARD))
        palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
        palette.setColor(QPalette.ColorRole.Button, QColor(ACCENT))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("white"))
        self.setPalette(palette)
        self.setStyleSheet(f"QMainWindow {{ background-color: {BG_DARK}; }}")

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 10, 14, 8)
        root.setSpacing(8)

        # ---- 1. Title Bar (compact) ----
        title_card = Card()
        tl = QHBoxLayout(title_card)
        tl.setContentsMargins(16, 10, 16, 8)
        self.title_lbl = QLabel("⚡ Miho-spot · 米哈游舆情监测系统")
        self.title_lbl.setStyleSheet(f"font-size:18px; font-weight:800; color:{TEXT};")
        tl.addWidget(self.title_lbl)
        tl.addStretch()
        sub = QLabel("Monitor v1.0")
        sub.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        tl.addWidget(sub)
        root.addWidget(title_card)

        # ---- 2. Status Row (compact) ----
        stat_card = Card()
        sl = QHBoxLayout(stat_card)
        sl.setContentsMargins(14, 6, 14, 6)
        sl.setSpacing(10)

        lbl = QLabel("🌐")
        lbl.setStyleSheet(f"font-size:12px;")
        sl.addWidget(lbl)
        self.url_lbl = QLabel("localhost:5173")
        self.url_lbl.setStyleSheet(f"color:{ACCENT}; font-size:12px; font-weight:700;")
        self.url_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        sl.addWidget(self.url_lbl)

        sl.addStretch()

        self.run_dot = StatusDot(GREEN, 10)
        sl.addWidget(self.run_dot)
        self.run_lbl = QLabel("Running")
        self.run_lbl.setStyleSheet(f"color:{GREEN}; font-size:11px; font-weight:700;")
        sl.addWidget(self.run_lbl)
        sl.addSpacing(10)

        self.warn_dot = StatusDot(YELLOW, 10)
        sl.addWidget(self.warn_dot)
        wl = QLabel("Warn")
        wl.setStyleSheet(f"color:{YELLOW}; font-size:10px;")
        sl.addWidget(wl)
        sl.addSpacing(10)

        self.err_dot = StatusDot(RED, 10)
        sl.addWidget(self.err_dot)
        el = QLabel("Error")
        el.setStyleSheet(f"color:{RED}; font-size:10px;")
        sl.addWidget(el)

        self.port_lbl = QLabel(f":{self.backend_port}")
        self.port_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px; margin-left:8px;")
        sl.addWidget(self.port_lbl)
        root.addWidget(stat_card)

        # ---- 3. Quote Bar (compact, bigger font) ----
        quote_card = Card()
        ql = QVBoxLayout(quote_card)
        ql.setContentsMargins(12, 4, 12, 4)
        self.quote_lbl = QuoteLabel()
        ql.addWidget(self.quote_lbl)
        root.addWidget(quote_card)

        # ---- 4. Toolbar row ----
        tool_row = QHBoxLayout()
        tool_row.setSpacing(8)

        self.dbg_chk = QCheckBox(" 🐛 Debug")
        self.dbg_chk.setStyleSheet(f"""
            QCheckBox {{ color:{TEXT_DIM}; font-size:12px; font-weight:600; spacing:4px; }}
            QCheckBox::indicator {{ width:16px; height:16px; border-radius:3px; border:2px solid {BORDER}; background:{BG_CARD}; }}
            QCheckBox::indicator:checked {{ background:{ACCENT}; border-color:{ACCENT}; }}
        """)
        self.dbg_chk.toggled.connect(lambda v: self.debug_console.setVisible(v))
        tool_row.addWidget(self.dbg_chk)

        tool_row.addStretch()

        open_btn = QPushButton("🌐 Start Browser")
        open_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{ACCENT2}; border:1px solid {BORDER};
                border-radius:6px; padding:4px 14px; font-size:11px; font-weight:600; }}
            QPushButton:hover {{ border-color:{ACCENT}; background:rgba(99,102,241,0.1); }}
        """)
        open_btn.clicked.connect(lambda: webbrowser.open("http://localhost:5173"))
        tool_row.addWidget(open_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{TEXT_DIM}; border:1px solid {BORDER};
                border-radius:6px; padding:4px 12px; font-size:11px; }}
            QPushButton:hover {{ border-color:{ACCENT}; color:{ACCENT2}; }}
        """)
        clear_btn.clicked.connect(lambda: self.debug_console.clear())
        tool_row.addWidget(clear_btn)
        root.addLayout(tool_row)

        # ---- 5. Debug Console (50% of window via stretch) ----
        self.debug_console = QTextEdit()
        self.debug_console.setReadOnly(True)
        self.debug_console.setVisible(False)
        self.debug_console.setStyleSheet(f"""
            QTextEdit {{ background:#0a0a1a; color:{TEXT}; border:1px solid {BORDER}; border-radius:8px;
                font-family:{FONT_MONO}; font-size:12px; padding:8px; }}
            QScrollBar:vertical {{ background:{BG_DARK}; width:6px; border-radius:3px; }}
            QScrollBar::handle:vertical {{ background:{BORDER}; border-radius:3px; min-height:20px; }}
        """)
        root.addWidget(self.debug_console, stretch=5)

        # ---- 6. Bottom Bar ----
        btm_card = Card()
        bl = QHBoxLayout(btm_card)
        bl.setContentsMargins(14, 5, 14, 5)

        self.uptime_lbl = QLabel("🕐 00:00:00")
        self.uptime_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        bl.addWidget(self.uptime_lbl)
        bl.addStretch()
        self.cache_lbl = QLabel("📊 --")
        self.cache_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        bl.addWidget(self.cache_lbl)
        bl.addSpacing(12)
        self.time_lbl = QLabel(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.time_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        bl.addWidget(self.time_lbl)
        bl.addSpacing(8)
        self.ds_lbl = QLabel("🤖 DS: --")
        self.ds_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        bl.addWidget(self.ds_lbl)
        root.addWidget(btm_card)

    def _setup_log_capture(self):
        self.out_stream = EmittingStream("info")
        self.err_stream = EmittingStream("error")
        self.out_stream.text_written.connect(self._append_log)
        self.err_stream.text_written.connect(self._append_log)
        sys.stdout = self.out_stream
        sys.stderr = self.err_stream
        logging.getLogger().addHandler(logging.StreamHandler(self.out_stream))

    def _append_log(self, text, level):
        try:
            cmap = {"info": TEXT_DIM, "error": RED, "warning": YELLOW}
            c = cmap.get(level, TEXT_DIM)
            tag = {"info": "I", "error": "E", "warning": "W"}[level]
            ts = datetime.now().strftime("%H:%M:%S")
            html = f'<span style="color:#444;">{ts}</span> <span style="color:{c};font-weight:700;">[{tag}]</span> {text}'
            self.debug_console.append(html)
        except Exception:
            pass

    def _start_status_timers(self):
        self._start_time = datetime.now()
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._refresh)
        self.status_timer.start(3000)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(lambda: self.time_lbl.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.clock_timer.start(1000)

    def _refresh(self):
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{self.backend_port}/api/crawl/status")
            data = json.loads(urllib.request.urlopen(req, timeout=3).read())
            hot, srch = data.get("hotTotal", 0), data.get("searchTotal", 0)
            self.cache_lbl.setText(f"📊 h:{hot} s:{srch}")
            self.run_dot._color = QColor(GREEN)
            self.run_lbl.setText("Running")
            self.run_lbl.setStyleSheet(f"color:{GREEN}; font-size:11px; font-weight:700;")
        except Exception:
            self.run_dot._color = QColor(RED)
            self.run_lbl.setText("Offline")
            self.run_lbl.setStyleSheet(f"color:{RED}; font-size:11px; font-weight:700;")

        delta = datetime.now() - self._start_time
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        self.uptime_lbl.setText(f"🕐 {h:02d}:{m:02d}:{s:02d}")

        try:
            req2 = urllib.request.Request(f"http://127.0.0.1:{self.backend_port}/api/deepseek/status")
            ds = json.loads(urllib.request.urlopen(req2, timeout=2).read())
            if ds.get("isValid"):
                self.ds_lbl.setText("🤖 DS: Active")
                self.ds_lbl.setStyleSheet(f"color:{ACCENT2}; font-size:10px; font-weight:600;")
            elif ds.get("configured"):
                self.ds_lbl.setText("🤖 DS: Invalid")
                self.ds_lbl.setStyleSheet(f"color:{YELLOW}; font-size:10px;")
            else:
                self.ds_lbl.setText("🤖 DS: Off")
                self.ds_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        except Exception:
            self.ds_lbl.setText("🤖 DS: --")
            self.ds_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")


def run_gui(host="0.0.0.0", port=8000):
    app = QApplication(sys.argv)
    app.setApplicationName("Miho-spot Monitor")
    app.setStyle("Fusion")
    window = MihoSpotMonitor(backend_port=port)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
