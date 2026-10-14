"""双主题切换（ui.theme.set_theme_mode）与 AppState theme_mode 持久化（PySide6 版）。"""

import pytest

from app_state import AppState
from ui.theme import current_theme_mode, set_theme_mode, theme


@pytest.fixture(autouse=True)
def _restore_light_theme():
    """用例结束后恢复浅色，避免污染同进程后续 GUI 测试的取色。"""
    yield
    set_theme_mode("light")


def test_default_theme_is_light():
    assert current_theme_mode() == "light"
    assert theme.BG == "#f2f0eb"
    assert theme.ACCENT == "#002fa7"
    assert theme.ON_ACCENT == "#ffffff"


def test_switch_to_dark_mutates_singleton():
    set_theme_mode("dark")
    assert current_theme_mode() == "dark"
    assert theme.BG == "#141417"
    assert theme.ACCENT == "#5272ff"
    assert theme.PANEL == "#1a1a1f"


def test_theme_singleton_is_single_shared_instance():
    """模块导出的 theme 即全局单例，set_theme_mode 原地改字段（控件零缓存前提）。"""
    import ui.theme as theme_module
    from ui.theme import theme as singleton

    assert theme_module.theme is singleton
    set_theme_mode("dark")
    assert singleton.BG == "#141417"
    set_theme_mode("light")
    assert singleton.BG == "#f2f0eb"


def test_invalid_mode_falls_back_to_light():
    assert set_theme_mode("neon") == "light"
    assert current_theme_mode() == "light"


def test_switch_back_to_light_restores_tokens():
    set_theme_mode("dark")
    set_theme_mode("light")
    assert theme.BG == "#f2f0eb"
    assert theme.ACCENT == "#002fa7"
    assert theme.INK == "#111111"


def test_build_qss_contains_token_values():
    """build_qss 把当前主题 Token 展开进全局样式表（单一取色源）。"""
    from ui.theme import build_qss

    set_theme_mode("dark")
    qss = build_qss()
    assert theme.BG in qss
    assert theme.ACCENT in qss


def test_apply_qss_sets_application_stylesheet():
    """apply_qss 将样式表挂到 QApplication（控件零缓存颜色的前提）。"""
    from PySide6.QtWidgets import QApplication

    from ui.theme import apply_qss

    app = QApplication.instance() or QApplication([])
    apply_qss(app, "dark")
    assert app.styleSheet()
    apply_qss(app, "light")  # 恢复浅色，避免污染后续用例


class _FakeDataManager:
    def save_progress(self, progress: dict) -> None:
        self.saved = progress


def test_app_state_theme_mode_roundtrip():
    state = AppState(_FakeDataManager(), {"theme_mode": "dark"})
    assert state.get_theme_mode() == "dark"
    state.set_theme_mode("light")
    assert state.get_theme_mode() == "light"


def test_app_state_theme_mode_invalid_falls_back():
    assert AppState(_FakeDataManager(), {"theme_mode": "neon"}).get_theme_mode() == "light"
    assert AppState(_FakeDataManager(), {}).get_theme_mode() == "light"
