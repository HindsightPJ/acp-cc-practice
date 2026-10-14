"""双主题切换（ui.theme.set_theme_mode）与 AppState theme_mode 持久化。"""

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
    assert theme.BG_PAGE == "#eef1f6"
    assert theme.BTN_PRIMARY == "#1668dc"


def test_switch_to_dark_mutates_singleton():
    set_theme_mode("dark")
    assert current_theme_mode() == "dark"
    assert theme.BG_PAGE == "#0b0f16"
    assert theme.BTN_PRIMARY == "#4c8dff"
    assert theme.SELECTED_TEXT == "#0b1220"


def test_module_constants_sync_with_singleton():
    import ui.theme as theme_module

    set_theme_mode("dark")
    assert theme_module.BG_PAGE == "#0b0f16"
    set_theme_mode("light")
    assert theme_module.BG_PAGE == "#eef1f6"


def test_invalid_mode_falls_back_to_light():
    assert set_theme_mode("neon") == "light"
    assert current_theme_mode() == "light"


def test_switch_back_to_light_restores_tokens():
    set_theme_mode("dark")
    set_theme_mode("light")
    assert theme.BG_PAGE == "#eef1f6"
    assert theme.ACCENT == "#1668dc"


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
