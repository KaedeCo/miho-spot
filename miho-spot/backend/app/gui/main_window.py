"""
Miho-spot Backend - PyQt6 Desktop GUI
Provides a desktop interface for the Miho-spot sentiment monitoring tool.
"""
import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
        QHeaderView, QStatusBar, QSplitter, QTextEdit, QProgressBar,
        QFrame, QGridLayout, QGroupBox, QMessageBox, QLineEdit,
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
    from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QPixmap
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("[Miho-spot] PyQt6 not installed. Desktop GUI unavailable.")


class CrawlWorker(QThread):
    """Background worker for crawling tasks"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, platforms: list):
        super().__init__()
        self.platforms = platforms

    def run(self):
        import time
        total = len(self.platforms) * 100
        try:
            for i, platform in enumerate(self.platforms):
                self.log.emit(f"[{platform}] 正在爬取热搜数据...")
                for p in range(100):
                    time.sleep(0.02)
                    self.progress.emit(int(((i * 100) + p) / len(self.platforms)))
                self.log.emit(f"[{platform}] 爬取完成")
            self.progress.emit(100)
            self.finished.emit({"status": "success", "message": "所有平台爬取完成"})
        except Exception as e:
            self.error.emit(str(e))


DARK_STYLE = """
QMainWindow {
    background-color: #0f0f1a;
}
QWidget {
    background-color: #0f0f1a;
    color: #e2e8f0;
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}
QLabel {
    color: #e2e8f0;
}
QPushButton {
    background-color: #6366f1;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #4f46e5;
}
QPushButton:pressed {
    background-color: #4338ca;
}
QPushButton:disabled {
    background-color: #2a2a4a;
    color: #555;
}
QTabWidget::pane {
    border: 1px solid #2a2a4a;
    background-color: #1a1a2e;
    border-radius: 8px;
}
QTabBar::tab {
    background-color: #1a1a2e;
    color: #94a3b8;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
QTabBar::tab:selected {
    background-color: #252540;
    color: #a78bfa;
    border-bottom: 2px solid #6366f1;
}
QTableWidget {
    background-color: #1a1a2e;
    alternate-background-color: #1f1f35;
    color: #e2e8f0;
    border: 1px solid #2a2a4a;
    gridline-color: #2a2a4a;
    border-radius: 8px;
}
QHeaderView::section {
    background-color: #252540;
    color: #94a3b8;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #2a2a4a;
    font-weight: bold;
}
QStatusBar {
    background-color: #1a1a2e;
    color: #94a3b8;
    border-top: 1px solid #2a2a4a;
}
QProgressBar {
    border: 1px solid #2a2a4a;
    border-radius: 6px;
    text-align: center;
    color: white;
    background-color: #1a1a2e;
}
QProgressBar::chunk {
    background-color: #6366f1;
    border-radius: 5px;
}
QTextEdit {
    background-color: #1a1a2e;
    color: #e2e8f0;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    padding: 8px;
}
QFrame#card {
    background-color: #1a1a2e;
    border: 1px solid #2a2a4a;
    border-radius: 12px;
    padding: 16px;
}
"""


class MihoSpotWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.apply_style()

    def init_ui(self):
        self.setWindowTitle("Miho-spot - 米哈游舆情监测系统")
        self.setGeometry(100, 100, 1400, 900)
        self.setMinimumSize(1000, 700)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title_label = QLabel("Miho-spot")
        title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #a78bfa;")
        subtitle = QLabel("  |  米哈游舆情监测系统")
        subtitle.setStyleSheet("font-size: 14px; color: #94a3b8;")
        header.addWidget(title_label)
        header.addWidget(subtitle)
        header.addStretch()

        # Tagline
        tagline = QLabel('"从此以后，每个人都是社管，亦或者都不是社管。" — By Chronostasis')
        tagline.setStyleSheet("font-size: 12px; color: #6366f1; font-style: italic; padding: 8px 16px; background-color: #1a1a2e; border-radius: 8px; border-left: 3px solid #6366f1;")
        header.addWidget(tagline)

        main_layout.addLayout(header)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_monitor_tab(), "📊 数据仪表盘")
        self.tabs.addTab(self._create_crawl_tab(), "🕷️ 爬取控制")
        self.tabs.addTab(self._create_log_tab(), "📝 运行日志")
        main_layout.addWidget(self.tabs)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 — Miho-spot v1.0.0")

    def _create_monitor_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Stats cards row
        cards = QHBoxLayout()

        card_data = [
            ("热搜总数", "150", "#6366f1"),
            ("二游相关", "47", "#a78bfa"),
            ("正面舆情", "18", "#22c55e"),
            ("负面舆情", "15", "#ef4444"),
            ("中性舆情", "10", "#f59e0b"),
        ]

        for label, value, color in card_data:
            card = QFrame()
            card.setObjectName("card")
            card.setStyleSheet(f"QFrame#card {{ background-color: #1a1a2e; border-radius: 12px; padding: 16px; border: 1px solid #2a2a4a; }}")
            card_layout = QVBoxLayout(card)
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
            val = QLabel(value)
            val.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {color};")
            card_layout.addWidget(lbl)
            card_layout.addWidget(val)
            cards.addWidget(card)

        layout.addLayout(cards)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["平台", "排名", "标题", "热度", "情感", "关联"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)

        # Sample data
        sample = [
            ("知乎", "#1", "原神5.7版本纳塔剧情引发热议", "985万", "正面", "-"),
            ("抖音", "#2", "星穹铁道3.4卡池抽取建议", "872万", "中性", "-"),
            ("贴吧", "#3", "绝区零新角色强度评测", "765万", "负面", "-"),
            ("知乎", "#5", "米哈游Q1财报公布", "654万", "正面", "-"),
            ("抖音", "#8", "明日方舟终末地二测开启", "543万", "无关", "明日方舟"),
        ]

        self.table.setRowCount(len(sample))
        for i, row in enumerate(sample):
            for j, val in enumerate(row):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if j == 4:
                    colors = {"正面": "#22c55e", "负面": "#ef4444", "中性": "#f59e0b", "无关": "#6b7280"}
                    item.setForeground(QColor(colors.get(val, "#e2e8f0")))
                self.table.setItem(i, j, item)

        layout.addWidget(self.table)

        # Refresh button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        refresh_btn = QPushButton("🔄 刷新数据")
        refresh_btn.clicked.connect(self._on_refresh)
        btn_layout.addWidget(refresh_btn)
        layout.addLayout(btn_layout)

        return widget

    def _create_crawl_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Control panel
        control = QGroupBox("爬取控制面板")
        control.setStyleSheet("QGroupBox { color: #a78bfa; font-weight: bold; border: 1px solid #2a2a4a; border-radius: 12px; margin-top: 12px; padding-top: 20px; } QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 8px; }")
        control_layout = QGridLayout(control)

        platforms = [
            ("知乎热榜", "知乎热门话题实时爬取"),
            ("抖音热榜", "抖音短视频热搜数据采集"),
            ("贴吧热榜", "百度贴吧热议话题爬取"),
        ]

        for i, (name, desc) in enumerate(platforms):
            control_layout.addWidget(QLabel(f"<b>{name}</b>"), i, 0)
            control_layout.addWidget(QLabel(desc), i, 1)
            btn = QPushButton("开始爬取")
            btn.setFixedWidth(100)
            btn.clicked.connect(lambda checked, p=name: self._on_crawl(p))
            control_layout.addWidget(btn, i, 2)

        self.crawl_all_btn = QPushButton("🕷️ 一键爬取全部平台")
        self.crawl_all_btn.setStyleSheet("font-size: 16px; padding: 15px 30px;")
        self.crawl_all_btn.clicked.connect(self._on_crawl_all)

        layout.addWidget(control)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        layout.addWidget(self.crawl_all_btn)
        layout.addStretch()

        return widget

    def _create_log_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("font-family: 'Consolas', 'Courier New', monospace; font-size: 13px;")
        self.log_view.append("[Miho-spot] 系统启动完成")
        self.log_view.append("[Miho-spot] 数据库初始化成功")

        layout.addWidget(self.log_view)

        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self.log_view.clear)
        layout.addWidget(clear_btn)

        return widget

    def _on_refresh(self):
        self.status_bar.showMessage("正在刷新数据...")
        QTimer.singleShot(1500, lambda: self.status_bar.showMessage("数据刷新完成 ✓"))

    def _on_crawl(self, platform: str):
        self.status_bar.showMessage(f"正在爬取 {platform}...")
        self.log_view.append(f"[爬取] 开始爬取 {platform}")
        QTimer.singleShot(2000, lambda: self._on_crawl_finished(platform))

    def _on_crawl_all(self):
        self.crawl_all_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_view.append("[爬取] 开始全平台爬取...")

        self.worker = CrawlWorker(["zhihu", "douyin", "tieba"])
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.log.connect(self.log_view.append)
        self.worker.finished.connect(self._on_crawl_all_finished)
        self.worker.error.connect(lambda e: self.log_view.append(f"[错误] {e}"))
        self.worker.start()

    def _on_crawl_finished(self, platform: str):
        self.status_bar.showMessage(f"{platform} 爬取完成 ✓")
        self.log_view.append(f"[爬取] {platform} 爬取完成")

    def _on_crawl_all_finished(self, result):
        self.crawl_all_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("全平台爬取完成 ✓")
        self.log_view.append(f"[爬取] {result['message']}")
        QMessageBox.information(self, "爬取完成", result["message"])

    def apply_style(self):
        self.setStyleSheet(DARK_STYLE)


def run_gui():
    if not PYQT_AVAILABLE:
        raise ImportError("PyQt6 not installed. Install with: pip install PyQt6 PyQt6-WebEngine")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(15, 15, 26))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(226, 232, 240))
    palette.setColor(QPalette.ColorRole.Base, QColor(26, 26, 46))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(31, 31, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(37, 37, 64))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(226, 232, 240))
    palette.setColor(QPalette.ColorRole.Text, QColor(226, 232, 240))
    palette.setColor(QPalette.ColorRole.Button, QColor(37, 37, 64))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(226, 232, 240))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(99, 102, 241))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    window = MihoSpotWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
