"""
Miho-spot Desktop — Single-window backend GUI
Replaces the terminal. Frontend still runs in browser.
"""
import sys, os, json, random, threading
import urllib.request, webbrowser
from datetime import datetime
from pathlib import Path

# Path setup
if getattr(sys, 'frozen', False):
    # Frozen EXE: PyInstaller bundles all modules internally.
    # No sys.path manipulation needed — the bundled app package is self-contained.
    pass
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent / "miho-spot"
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QFrame, QPushButton, QCheckBox,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QSequentialAnimationGroup, QEasingCurve, QObject, pyqtSignal
from PyQt6.QtGui import QColor, QPalette, QPainter, QBrush, QRadialGradient
from PyQt6.QtWidgets import QGraphicsOpacityEffect

PORT = 8000

def find_free_port(start: int = 8000, max_attempts: int = 100) -> int:
    """Find the first available TCP port starting from 'start'."""
    import socket
    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}-{start+max_attempts}")

C1, C2, C3 = "#6366f1", "#a78bfa", "#22c55e"
CY, CR, CD, CT, CB = "#f59e0b", "#ef4444", "#94a3b8", "#e2e8f0", "#2a2a4a"
BG1, BG2 = "#0f0f23", "#1a1a2e"
FONT_MONO = "Cascadia Code, Consolas, Monaco, Courier New, monospace"

QUOTES = [
    '"这波属于是米哈游送钱给我抽卡，我不抽岂不是亏了？" —— 某氪金玩家',
    '"原神没有逼氪，只是你管不住手而已。" —— 米哈游法务部（虚构）',
    '"我已经卸载三次了，每次都是新版本前两天。" —— 某戒断失败玩家',
    '"米哈游：我们的游戏免费。玩家：我信了。"',
    '"当你发现一个bug，米哈游说这是feature。当玩家利用bug，米哈游说这是违规。" —— 贴吧老哥',
    '"你以为是你在玩游戏？其实是数值策划在玩你。" —— 深渊12层受害者',
    '"歪了莫娜 —— 每个原神玩家的一生之敌。"',
    '"社管是工作，米黑是生活。" —— 二游社区定律',
    '"我的圣遗物分比我高考分还高。"',
    '"我玩米哈游游戏不是因为它们好玩，是因为沉没成本。"',
    '"米哈游的保底机制：80抽保底，但你先歪。"',
    '"崩铁：一款副游做成主游，主游做成上班的游戏。"',
    '"绝区零的走格子，比我的上班路线还复杂。"',
    '"不要问角色强不强，问你的钱包厚不厚。"',
    '"米哈游：我们听取了玩家意见。玩家：哪个意见？"',
]


class Dot(QWidget):
    def __init__(self, color, sz=10):
        super().__init__()
        self.c = QColor(color)
        self.z = sz
        self.setFixedSize(sz + 6, sz + 6)
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(1.0)
        self.setGraphicsEffect(self._fx)
        a = QPropertyAnimation(self._fx, b"opacity")
        a.setDuration(1200); a.setStartValue(.35); a.setEndValue(1.)
        a.setEasingCurve(QEasingCurve.Type.InOutSine); a.setLoopCount(-1); a.start()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x, y, r = self.width() / 2, self.height() / 2, self.z / 2
        g = QRadialGradient(x, y, r + 2); g.setColorAt(0, self.c)
        c2 = QColor(self.c); c2.setAlphaF(.05); g.setColorAt(1, c2)
        p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(x - r), int(y - r), int(r * 2), int(r * 2))


class Card(QFrame):
    def __init__(self, p=None):
        super().__init__(p)
        self.setStyleSheet(f"Card{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(24,24,50,.9),stop:1 rgba(30,30,60,.75));border:1px solid {CB};border-radius:10px;}}")
        sh = QGraphicsDropShadowEffect(self); sh.setBlurRadius(14); sh.setColor(QColor(0, 0, 0, 60)); sh.setOffset(0, 2)
        self.setGraphicsEffect(sh)


class Stream(QObject):
    w = pyqtSignal(str, str)

    def __init__(self, lv="i"): super().__init__(); self.lv = lv

    def write(self, t):
        if t.strip(): self.w.emit(t.strip(), self.lv)

    def flush(self): pass

    def isatty(self): return False

    def fileno(self): raise OSError


class BackendGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.port = find_free_port(PORT)
        self._rdy = False
        self._st = datetime.now()
        self._ui()
        self._start_server()
        self._capture_logs()
        self._timers()

    def _ui(self):
        self.setWindowTitle("Miho-spot Backend")
        self.resize(1200, 700); self.setMinimumSize(900, 520)
        pa = QPalette(); pa.setColor(QPalette.ColorRole.Window, QColor(BG1)); pa.setColor(QPalette.ColorRole.WindowText, QColor(CT))
        pa.setColor(QPalette.ColorRole.Base, QColor(BG2)); pa.setColor(QPalette.ColorRole.Text, QColor(CT))
        pa.setColor(QPalette.ColorRole.Button, QColor(C1)); pa.setColor(QPalette.ColorRole.ButtonText, QColor("white"))
        self.setPalette(pa); self.setStyleSheet(f"QMainWindow{{background:{BG1};}}")
        cw = QWidget(); self.setCentralWidget(cw)
        root = QVBoxLayout(cw); root.setContentsMargins(14, 10, 14, 8); root.setSpacing(8)

        # Title
        tc = Card(); tl = QHBoxLayout(tc); tl.setContentsMargins(16, 10, 16, 8)
        t = QLabel("⚡ Miho-spot Backend · 米哈游舆情监测系统")
        t.setStyleSheet(f"font-size:18px;font-weight:800;color:{CT};"); tl.addWidget(t)
        tl.addStretch(); sub = QLabel("v1.2"); sub.setStyleSheet(f"color:{CD};font-size:11px;"); tl.addWidget(sub)
        root.addWidget(tc)

        # Status
        sc = Card(); sl = QHBoxLayout(sc); sl.setContentsMargins(14, 6, 14, 6); sl.setSpacing(10)
        lb = QLabel("🌐"); lb.setStyleSheet("font-size:12px;"); sl.addWidget(lb)
        self._ur = QLabel(f"localhost:{self.port}"); self._ur.setStyleSheet(f"color:{C1};font-size:12px;font-weight:700;"); sl.addWidget(self._ur)
        sl.addStretch()
        self._sd = Dot(CY, 10); sl.addWidget(self._sd)
        self._sl = QLabel("Starting..."); self._sl.setStyleSheet(f"color:{CY};font-size:11px;font-weight:700;"); sl.addWidget(self._sl)
        sl.addSpacing(10)
        self._wd = Dot(CY, 10); sl.addWidget(self._wd)
        wl = QLabel("Warn"); wl.setStyleSheet(f"color:{CY};font-size:10px;"); sl.addWidget(wl)
        sl.addSpacing(10)
        self._ed = Dot(CY, 10); sl.addWidget(self._ed)
        el = QLabel("Error"); el.setStyleSheet(f"color:{CY};font-size:10px;"); sl.addWidget(el)
        self._pl = QLabel(f":{self.port}"); self._pl.setStyleSheet(f"color:{CD};font-size:10px;margin-left:8px;"); sl.addWidget(self._pl)
        root.addWidget(sc)

        # Quote
        qc = Card(); ql = QVBoxLayout(qc); ql.setContentsMargins(12, 4, 12, 4)
        self._qt = QLabel(random.choice(QUOTES)); self._qt.setWordWrap(True); self._qt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qt.setStyleSheet(f"color:{C2};font-size:15px;font-style:italic;"); ql.addWidget(self._qt)
        root.addWidget(qc)

        # Toolbar
        tr = QHBoxLayout(); tr.setSpacing(8)
        db = QCheckBox("🐛 Debug")
        db.setStyleSheet(f"QCheckBox{{color:{CD};font-size:12px;font-weight:600;spacing:4px;}}QCheckBox::indicator{{width:16px;height:16px;border-radius:3px;border:2px solid {CB};background:{BG2};}}QCheckBox::indicator:checked{{background:{C1};border-color:{C1};}}")
        db.toggled.connect(lambda v: self._cn.setVisible(v)); tr.addWidget(db); tr.addStretch()
        op = QPushButton("🌐 打开前端")
        op.setStyleSheet(f"QPushButton{{background:transparent;color:{C2};border:1px solid {CB};border-radius:6px;padding:4px 14px;font-size:11px;font-weight:600;}}QPushButton:hover{{border-color:{C1};background:rgba(99,102,241,.1);}}")
        op.clicked.connect(lambda: webbrowser.open(f"http://localhost:{self.port}")); tr.addWidget(op)
        cl = QPushButton("Clear")
        cl.setStyleSheet(f"QPushButton{{background:transparent;color:{CD};border:1px solid {CB};border-radius:6px;padding:4px 12px;font-size:11px;}}QPushButton:hover{{border-color:{C1};color:{C2};}}")
        cl.clicked.connect(lambda: self._cn.clear()); tr.addWidget(cl)
        root.addLayout(tr)

        # Console (50% of window)
        self._cn = QTextEdit(); self._cn.setReadOnly(True); self._cn.setVisible(False)
        self._cn.setStyleSheet(f"QTextEdit{{background:#0a0a1a;color:{CT};border:1px solid {CB};border-radius:8px;font-family:{FONT_MONO};font-size:12px;padding:8px;}}QScrollBar:vertical{{background:{BG1};width:6px;border-radius:3px;}}QScrollBar::handle:vertical{{background:{CB};border-radius:3px;min-height:20px;}}")
        root.addWidget(self._cn, stretch=5)

        # Bottom
        bc = Card(); bl = QHBoxLayout(bc); bl.setContentsMargins(14, 5, 14, 5)
        self._up = QLabel("🕐 00:00:00"); self._up.setStyleSheet(f"color:{CD};font-size:10px;"); bl.addWidget(self._up)
        bl.addStretch()
        self._ca = QLabel("📊 --"); self._ca.setStyleSheet(f"color:{CD};font-size:10px;"); bl.addWidget(self._ca)
        bl.addSpacing(12)
        self._tm = QLabel(datetime.now().strftime("%Y-%m-%d %H:%M:%S")); self._tm.setStyleSheet(f"color:{CD};font-size:10px;"); bl.addWidget(self._tm)
        bl.addSpacing(8)
        self._ds = QLabel("🤖 DS: --"); self._ds.setStyleSheet(f"color:{CD};font-size:10px;"); bl.addWidget(self._ds)
        root.addWidget(bc)

    def _start_server(self):
        t = threading.Thread(target=self._run_server, daemon=True); t.start()
        self._poll = QTimer(self); self._poll.timeout.connect(self._check_ready); self._poll.start(2000)

    def _run_server(self):
        # When frozen, redirect ALL data to EXE-adjacent folder so it persists
        if getattr(sys, 'frozen', False):
            import app.models as _m
            base = Path(sys.executable).parent / "data"
            base.mkdir(parents=True, exist_ok=True)
            _m.DATA_DIR = str(base)
            _m.DB_PATH = os.path.join(str(base), "miho_spot.db")
            # Recreate engine and session bound to the correct DB
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            _m.engine = create_engine(f"sqlite:///{_m.DB_PATH}", echo=False)
            _m.SessionLocal = sessionmaker(bind=_m.engine)
            from app.api.routes import set_data_base_dir
            set_data_base_dir(str(base))

        import uvicorn
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from app.api.routes import router as ar
        from app.models import init_db, SessionLocal, AccountModel

        # Clear any source-level API key fallbacks (release policy)
        import app.crawlers as _cr
        _cr.TOPHUB_API_KEY = ""

        init_db()
        # Seed platform entries WITHOUT pre-filled API keys (release policy)
        db = SessionLocal()
        try:
            for p in ["zhihu", "douyin", "tieba", "tophub"]:
                if not db.query(AccountModel).filter(AccountModel.platform == p).first():
                    db.add(AccountModel(platform=p, username="", cookie="", is_valid=False))
            db.commit()
        finally:
            db.close()
        try:
            from app.sentiment import seed_default_keywords
            seed_default_keywords()
        except Exception as e:
            import traceback
            print(f"[Miho-spot] Keyword seed error: {e}\n{traceback.format_exc()}", file=sys.stderr)

        app = FastAPI(title="Miho-spot")
        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
        app.include_router(ar)

        # When frozen, serve the bundled frontend static build at root (/)
        if getattr(sys, 'frozen', False):
            from fastapi.staticfiles import StaticFiles
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                fe_dir = Path(meipass) / "frontend_dist"
            else:
                fe_dir = Path(__file__).resolve().parent / "frontend_dist"
            if fe_dir.exists() and (fe_dir / "index.html").exists():
                app.mount("/", StaticFiles(directory=str(fe_dir), html=True), name="frontend")
                print(f"[Miho-spot] Serving bundled frontend from {fe_dir}")

        uvicorn.run(app, host="0.0.0.0", port=self.port, log_level="warning")

    def _capture_logs(self):
        self._ls = Stream("i"); self._le = Stream("e")
        self._ls.w.connect(self._log); self._le.w.connect(self._log)
        sys.stdout = self._ls; sys.stderr = self._le

    def _log(self, tx, lv):
        try:
            c = {"i": CD, "e": CR, "w": CY}.get(lv, CD)
            t = {"i": "I", "e": "E", "w": "W"}[lv]
            ts = datetime.now().strftime("%H:%M:%S")
            self._cn.append(f'<span style="color:#444;">{ts}</span> <span style="color:{c};font-weight:700;">[{t}]</span> {tx}')
        except:
            pass

    def _check_ready(self):
        if not self._rdy:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/crawl/status", timeout=2)
                self._rdy = True; self._sd.c = QColor(C3)
                self._sl.setText("Running"); self._sl.setStyleSheet(f"color:{C3};font-size:11px;font-weight:700;")
            except:
                pass
        if self._rdy:
            self._poll.stop()

    def _timers(self):
        self._t = QTimer(self); self._t.timeout.connect(self._refresh); self._t.start(3000)
        self._c = QTimer(self); self._c.timeout.connect(lambda: self._tm.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))); self._c.start(1000)
        self._q = QTimer(self); self._q.timeout.connect(lambda: self._qt.setText(random.choice(QUOTES))); self._q.start(10000)

    def _refresh(self):
        if not self._rdy: return
        try:
            d = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/crawl/status", timeout=3).read())
            self._ca.setText(f"📊 h:{d.get('hotTotal',0)} s:{d.get('searchTotal',0)}")
        except:
            pass
        dt = datetime.now() - self._st; h, rm = divmod(int(dt.total_seconds()), 3600); m, s = divmod(rm, 60)
        self._up.setText(f"🕐 {h:02d}:{m:02d}:{s:02d}")
        try:
            ds = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/deepseek/status", timeout=2).read())
            if ds.get("isValid"): st = ("🤖 DS: Active", f"color:{C2};font-size:10px;font-weight:600;")
            elif ds.get("configured"): st = ("🤖 DS: Invalid", f"color:{CY};font-size:10px;")
            else: st = ("🤖 DS: Off", f"color:{CD};font-size:10px;")
        except:
            st = ("🤖 DS: --", f"color:{CD};font-size:10px;")
        self._ds.setText(st[0]); self._ds.setStyleSheet(st[1])


def main():
    a = QApplication(sys.argv); a.setApplicationName("Miho-spot Backend"); a.setStyle("Fusion")
    w = BackendGUI(); w.show(); sys.exit(a.exec())


if __name__ == "__main__":
    main()
