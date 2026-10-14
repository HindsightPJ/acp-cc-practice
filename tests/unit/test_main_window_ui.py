"""MainWindow PySide6 版冒烟与框架行为测试。

覆盖：完整实例化（titlebar/head/board-nav/stack/modeline）、四模式切换、
导航反白与计数、授权按钮双态、快捷键鸭子路由、closeEvent flush。
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QMainWindow

from models import Option, Question
from ui.main_window import NAV_DEFS, MainWindow

pytestmark = pytest.mark.gui


SAMPLE_QUESTIONS = [
    Question(
        number=1,
        type="single",
        content="测试题目",
        options=[Option("A", "选项A"), Option("B", "选项B")],
        answer="A",
        explanation="解析",
    ),
    Question(
        number=2,
        type="single",
        content="测试题目二",
        options=[Option("A", "选项A"), Option("B", "选项B")],
        answer="B",
        explanation="解析二",
    ),
]


class FakeDataManager:
    """最小 DataManager 替代（MainWindow 只读 load_progress/data_dir）。"""

    def __init__(self, tmp_path: Path):
        self.data_dir = str(tmp_path)
        self.save_progress = MagicMock()  # 落盘调用断言用

    def load_progress(self):
        return {"practice_stats": {"correct": 0, "wrong": 0, "total": 0}, "wrong_questions": []}


@pytest.fixture
def window(qtbot, tmp_path):
    w = MainWindow(SAMPLE_QUESTIONS, FakeDataManager(tmp_path), license_status=None)
    qtbot.addWidget(w)
    return w


# ---------- 实例化 ----------


def test_main_window_can_instantiate(window):
    """MainWindow 可完整实例化：窗口标题、QMainWindow 基类、四页入栈。"""
    assert isinstance(window, QMainWindow)
    assert window.windowTitle() == "ACP 云计算练习"
    assert window.stack.count() == len(NAV_DEFS)
    assert window.titlebar is not None
    assert window.modeline.text()


def test_license_btn_trial_state(window):
    """试用模式：授权按钮可点、文案引导输入注册码。"""
    assert window.license_btn.isEnabled()
    assert window.license_btn.text() == "输入注册码"


def test_license_btn_authorized_disabled(qtbot, tmp_path):
    """已授权：按钮禁用。"""
    from license import LicenseStatus

    w = MainWindow(
        SAMPLE_QUESTIONS, FakeDataManager(tmp_path), license_status=LicenseStatus.AUTHORIZED
    )
    qtbot.addWidget(w)

    assert not w.license_btn.isEnabled()
    assert w.license_btn.text() == "已授权"


# ---------- 模式切换 ----------


def test_show_mode_switches_all_pages(window):
    """四模式切换：nav 反白、titlebar tag、modeline 联动。"""
    for key, _no, _name, tag in NAV_DEFS:
        window.show_mode(key)
        assert window.stack.currentIndex() == [d[0] for d in NAV_DEFS].index(key)
        assert window.titlebar._tag.text() == tag
        btn = window._nav_buttons[key][0]
        assert btn.isChecked() is True
        assert window.modeline.text()


def test_show_mode_unknown_key_is_noop(window):
    """未知模式 key 忽略且不崩溃。"""
    window.show_mode("nonexistent")

    assert window.stack.currentIndex() == 0


def test_nav_click_switches_mode(window):
    """点击 board-nav 行切换模式（idClicked 路由）。"""
    window._nav_buttons["exam"][0].click()

    assert window.stack.currentIndex() == 1


def test_show_mode_flushes_previous_page(window):
    """切页时旧页防抖进度被 flush（flush_pending_save 鸭子探测）。"""
    practice = window.stack.widget(0)
    practice.app_state = MagicMock()
    practice.app_state.save_safe.return_value = True
    practice._pending_save = True

    window.show_mode("exam")

    practice.app_state.save_safe.assert_called_once()
    assert practice._pending_save is False


# ---------- 导航计数 ----------


def test_nav_counts_refresh(window):
    """错题行计数来自 app_state；练习行显示位置计数。"""
    window.app_state.add_wrong_question(1)
    window._refresh_nav_counts()

    assert window._nav_buttons["wrong"][3].text() == "1"
    assert window._nav_buttons["practice"][3].text() == "1/2"


def test_state_changed_refreshes_modeline(window):
    """模式页 state_changed → 主窗口刷新（信号接线）。"""
    window.show_mode("review")
    before = window.modeline.text()

    page = window.stack.currentWidget()
    page.on_next()  # 触发 state_changed

    assert window.modeline.text() != before


# ---------- 快捷键路由 ----------


def test_route_forwards_to_current_page(window):
    """_route 鸭子转发：方法存在则调用，不存在则忽略。"""
    page = window.stack.currentWidget()
    called = []
    page.on_submit = lambda: called.append("submit")

    window._route("on_submit")
    assert called == ["submit"]

    window._route("nonexistent_method")  # 不抛异常


def test_review_page_has_no_letter_semantics(window):
    """背题页未实现 on_letter → A-D 转发被忽略。"""
    window.show_mode("review")

    window._route("on_letter", "A")  # 不抛异常


# ---------- 退出 ----------


def test_close_event_flushes_pending_save(qtbot, tmp_path):
    """closeEvent 先 flush 当前页防抖进度再兜底落盘。"""
    w = MainWindow(SAMPLE_QUESTIONS, FakeDataManager(tmp_path), license_status=None)
    qtbot.addWidget(w)
    page = w.stack.currentWidget()
    page.app_state.save_safe = MagicMock(return_value=True)
    page._pending_save = True

    w.close()

    page.app_state.save_safe.assert_called()
    assert page._pending_save is False


# ---------- 主题切换 ----------


def test_toggle_theme_switches_and_persists(window):
    """Ctrl+T 切主题：Token 模式翻转 + 持久化落盘。"""
    from ui.theme import current_theme_mode

    before = current_theme_mode()

    window.toggle_theme()

    assert current_theme_mode() != before
    assert window.app_state._data_manager.save_progress.called

    window.toggle_theme()  # 切回，避免污染其他用例
