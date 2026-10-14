"""主窗口：F 方案「时刻表」框架（标题栏 / 站牌头 / board-nav / 模式页 / modeline）。

结构（自上而下，间距 0 的垂直网格，desktop_python.md §6 QSS 单一取色源）：
- TitleBar（44px Frameless 站牌条，见 titlebar.py）
- QFrame#head 站牌头：brand + 副题 + 时钟（QTimer 30s 刷新，随控件销毁）
- QFrame#boardNav：4 个导航行（黑底反白激活态，子标签经 navActive 属性驱动，
  原因见 theme.py QSS 注释——祖先伪类不可靠）
- QStackedWidget 模式页：practice/exam/review/wrong，各页自带网格体与动作条
- QLabel#modeline 底部状态行

快捷键（WindowShortcut）：A–D 选项、Return/Enter 提交、← → 翻题，经 _route
鸭子类型转发到当前页的 on_letter/on_submit/on_prev/on_next；Ctrl+T 切主题。

线程红线（desktop_python.md §二）：后台任务只经信号触 UI，本类不直接跑后台。
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from PySide6.QtCore import QDate, Qt, QTime, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
)

from .theme import (
    THEME_DARK,
    THEME_LIGHT,
    apply_qss,
    current_theme_mode,
    repolish,
    set_theme_mode,
)
from .titlebar import TitleBar, setup_frameless

from app_state import AppState
from data_manager import DataManager
from license import LicenseStatus
from models import Question
from .exam_mode import ExamMode
from .practice_mode import PracticeMode
from .review_mode import ReviewMode
from .wrong_book import WrongBookPage

logger = logging.getLogger(__name__)

# 导航定义：(key, 编号, 名称, 标题栏 tag)
NAV_DEFS: tuple[tuple[str, str, str, str], ...] = (
    ("practice", "01", "练习模式", "PRACTICE"),
    ("exam", "02", "考试模式", "EXAM"),
    ("review", "03", "背题模式", "REVIEW"),
    ("wrong", "04", "错题本", "WRONGBOOK"),
)

_BRAND = "ACP·云算题库"
_SUB = "阿里云专业认证\n每日练习"


class MainWindow(QMainWindow):
    """时刻表框架主窗口。模式页经 show_mode 切换，业务页在 P4 起接入。"""

    def __init__(
        self,
        questions: list[Question],
        data_manager: DataManager,
        license_status: LicenseStatus | None = None,
        meta: dict[str, Any] | None = None,
        license_dir: str | None = None,
    ) -> None:
        super().__init__()
        setup_frameless(self)  # 必须在 show() 之前
        self.setWindowTitle("ACP 云计算练习")
        self.resize(1200, 760)
        self.setMinimumSize(980, 640)
        self._set_app_icon()

        self.questions: list[Question] = questions
        self.data_manager = data_manager
        # TD-30：AppState 封装进度，UI 不直接操作原始 dict
        self.app_state = AppState(data_manager, data_manager.load_progress())
        self.license_status = license_status
        self.meta = meta or {}
        # license.dat 持久化目录：打包后必须写到 exe 同级 data/（非 _MEIPASS）
        self.license_dir = license_dir or data_manager.data_dir

        # 主题：控件创建前定模式，QSS 应用到整个应用（控件零缓存颜色）
        set_theme_mode(self.app_state.get_theme_mode())
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_qss(app)

        self._nav_buttons: dict[str, tuple[QPushButton, QLabel, QLabel, QLabel]] = {}
        self._mode_keys: list[str] = [d[0] for d in NAV_DEFS]

        self._build_ui()
        self._install_shortcuts()

        # 页面状态变化 → 刷新 board-nav 计数与 modeline（信号驱动，免轮询）
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            if hasattr(page, "state_changed"):
                page.state_changed.connect(self._refresh_current_state)

        # 时钟：父控件为 self，窗口销毁随 QObject 树释放（L1 资源红线）
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(30_000)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start()
        self._update_clock()

        self.show_mode("practice")

    # -------------------------------------------------------------- 装配
    def _set_app_icon(self) -> None:
        """开发模式读项目根 icons/；PyInstaller 打包后读 _MEIPASS 临时目录。"""
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(__file__)))
        icon_path = os.path.join(base, "icons", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def _build_ui(self) -> None:
        root = QFrame()
        root.setObjectName("windowRoot")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(1, 1, 1, 1)  # 让 windowRoot 的 1px 分界线可见
        v.setSpacing(0)

        self.titlebar = TitleBar(tag=NAV_DEFS[0][3])
        v.addWidget(self.titlebar)

        v.addWidget(self._build_head())
        v.addWidget(self._build_nav())

        self.stack = QStackedWidget()
        v.addWidget(self.stack, 1)
        # 模式页顺序必须与 NAV_DEFS 严格一致（idClicked 按索引路由）
        self.stack.addWidget(PracticeMode(self.questions, self.app_state))
        self.stack.addWidget(ExamMode(self.questions, self.app_state))
        self.stack.addWidget(ReviewMode(self.questions, self.app_state))
        self.stack.addWidget(WrongBookPage(self.questions, self.app_state))

        self.modeline = QLabel()
        self.modeline.setObjectName("modeline")
        v.addWidget(self.modeline)

    def _build_head(self) -> QFrame:
        head = QFrame()
        head.setObjectName("head")
        h = QHBoxLayout(head)
        h.setContentsMargins(34, 20, 34, 14)
        h.setSpacing(22)

        brand = QLabel(_BRAND)
        brand.setObjectName("brand")
        h.addWidget(brand)

        sub = QLabel(_SUB)
        sub.setObjectName("subTitle")
        h.addWidget(sub)
        h.addStretch(1)

        clock_box = QVBoxLayout()
        clock_box.setSpacing(4)
        self._clock_time = QLabel()
        self._clock_time.setObjectName("clockTime")
        self._clock_date = QLabel()
        self._clock_date.setObjectName("clockDate")
        clock_box.addWidget(self._clock_time, 0, Qt.AlignmentFlag.AlignRight)
        clock_box.addWidget(self._clock_date, 0, Qt.AlignmentFlag.AlignRight)
        h.addLayout(clock_box)
        return head

    def _build_nav(self) -> QFrame:
        nav = QFrame()
        nav.setObjectName("boardNav")
        h = QHBoxLayout(nav)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        for index, (key, no, name, _tag) in enumerate(NAV_DEFS):
            btn = QPushButton()
            btn.setProperty("navRow", True)
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            inner = QHBoxLayout(btn)
            inner.setContentsMargins(0, 0, 0, 0)
            inner.setSpacing(10)
            lbl_no = QLabel(no)
            lbl_no.setProperty("navNo", True)
            lbl_nm = QLabel(name)
            lbl_nm.setProperty("navNm", True)
            lbl_cnt = QLabel("—")
            lbl_cnt.setProperty("navCnt", True)
            inner.addWidget(lbl_no)
            inner.addWidget(lbl_nm)
            inner.addStretch(1)
            inner.addWidget(lbl_cnt)
            btn.setMinimumHeight(44)

            self._nav_group.addButton(btn, index)
            self._nav_buttons[key] = (btn, lbl_no, lbl_nm, lbl_cnt)
            h.addWidget(btn, 1)

        self._nav_group.idClicked.connect(self._on_nav_clicked)
        return nav

    # -------------------------------------------------------------- 导航
    def _on_nav_clicked(self, index: int) -> None:
        if 0 <= index < len(self._mode_keys):
            self.show_mode(self._mode_keys[index])

    def _refresh_current_state(self) -> None:
        """模式页 state_changed 槽：刷新当前页的导航计数与 modeline。"""
        key = self._mode_keys[self.stack.currentIndex()]
        self._refresh_nav_counts()
        self._update_modeline(key)

    def show_mode(self, key: str) -> None:
        """切换模式页：切前 flush 旧页防抖进度 + 导航反白 + tag + modeline。"""
        if key not in self._nav_buttons:
            logger.warning("未知模式 %r，忽略", key)
            return
        index = self._mode_keys.index(key)
        if self.stack.currentIndex() != index:
            old_page = self.stack.currentWidget()
            flush = getattr(old_page, "flush_pending_save", None)
            if callable(flush):
                flush()
        self.stack.setCurrentIndex(index)
        for k, (btn, lbl_no, lbl_nm, lbl_cnt) in self._nav_buttons.items():
            active = k == key
            btn.setChecked(active)
            for lbl in (lbl_no, lbl_nm, lbl_cnt):
                lbl.setProperty("navActive", active)
                repolish(lbl)
        tag = NAV_DEFS[index][3]
        self.titlebar.set_tag(tag)
        self._refresh_nav_counts()
        self._update_modeline(key)

    def _refresh_nav_counts(self) -> None:
        """刷新各行右侧计数：页面可提供 nav_count()，缺省 '—'；错题行实时。"""
        for index, (key, _no, _nm, _tag) in enumerate(NAV_DEFS):
            if key == "wrong":
                text = str(self.app_state.wrong_count())
            else:
                page = self.stack.widget(index)
                provider = getattr(page, "nav_count", None)
                text = provider() if callable(provider) else "—"
            _btn, _no_lbl, _nm_lbl, lbl_cnt = self._nav_buttons[key]
            lbl_cnt.setText(text)

    def _update_modeline(self, key: str) -> None:
        page = self.stack.widget(self._mode_keys.index(key))
        provider = getattr(page, "modeline_text", None)
        if callable(provider):
            self.modeline.setText(provider())
            return
        total = self.meta.get("total", len(self.questions))
        lic = "已授权" if self.license_status == LicenseStatus.AUTHORIZED else "试用模式"
        self.modeline.setText(
            f"MODEL {key.upper()} · 题库 {total} · 错题 {self.app_state.wrong_count()} · {lic}"
        )

    # -------------------------------------------------------------- 时钟
    def _update_clock(self) -> None:
        self._clock_time.setText(QTime.currentTime().toString("hh:mm"))
        # 日期占位符属 QDate（QTime.toString 不解析 yyyy 等日期 token）
        self._clock_date.setText(f"SESSION · {QDate.currentDate().toString('yyyy.MM.dd')}")

    # -------------------------------------------------------------- 快捷键
    def _install_shortcuts(self) -> None:
        routes: tuple[tuple[str, str, tuple[Any, ...]], ...] = (
            ("A", "on_letter", ("A",)),
            ("B", "on_letter", ("B",)),
            ("C", "on_letter", ("C",)),
            ("D", "on_letter", ("D",)),
            ("Return", "on_submit", ()),
            ("Enter", "on_submit", ()),
            ("Left", "on_prev", ()),
            ("Right", "on_next", ()),
        )
        for seq, method, args in routes:
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(
                lambda m=method, a=args: self._route(m, *a)  # type: ignore[misc] - 闭包捕获实参
            )
        theme_sc = QShortcut(QKeySequence("Ctrl+T"), self)
        theme_sc.setContext(Qt.ShortcutContext.WindowShortcut)
        theme_sc.activated.connect(self.toggle_theme)

    def _route(self, method: str, *args: Any) -> None:
        """把快捷键转发给当前模式页（页面未实现则忽略）。"""
        page = self.stack.currentWidget()
        handler = getattr(page, method, None)
        if callable(handler):
            handler(*args)

    # -------------------------------------------------------------- 主题
    def toggle_theme(self) -> None:
        """浅色/深色切换：换 Token + 重应用 QSS + 持久化（fail-safe 落盘）。"""
        new_mode = THEME_DARK if current_theme_mode() == THEME_LIGHT else THEME_LIGHT
        set_theme_mode(new_mode)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_qss(app, new_mode)
        self.app_state.set_theme_mode(new_mode)
        if not self.app_state.save_safe():
            logger.warning("主题模式持久化失败（下次启动回退上次保存值）")

    # -------------------------------------------------------------- 退出
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        # 先 flush 当前页未落盘的防抖进度（快照同步进 app_state），再兜底落盘
        page = self.stack.currentWidget()
        flush = getattr(page, "flush_pending_save", None)
        if callable(flush):
            flush()
        if not self.app_state.save_safe():
            logger.error("退出时保存进度失败")
        super().closeEvent(event)
