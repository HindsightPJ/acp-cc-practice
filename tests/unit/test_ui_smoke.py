"""UI 模块冒烟测试（TD-19）。

验证所有 UI 模块可导入，捕获语法错误、import 链断裂、循环依赖等问题。
完整的 MainWindow 实例化测试需要虚拟 display（xvfb），留待后续。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_ui_package_importable():
    """TD-19: ui 包可导入。"""
    import ui  # pylint: disable=unused-import
    assert ui is not None


def test_ui_theme_module_importable():
    """TD-19: ui.theme 模块可导入（含颜色常量 + 字体工厂）。"""
    from ui import theme  # pylint: disable=unused-import
    assert hasattr(theme, 'BG_PAGE')
    assert hasattr(theme, 'font_ui')


def test_ui_base_mode_importable():
    """TD-19: ui.base_mode 模块可导入。"""
    from ui import base_mode  # pylint: disable=unused-import
    assert hasattr(base_mode, 'BaseMode')


def test_ui_practice_mode_importable():
    """TD-19: ui.practice_mode 模块可导入。"""
    from ui import practice_mode  # pylint: disable=unused-import
    assert hasattr(practice_mode, 'PracticeMode')


def test_ui_exam_mode_importable():
    """TD-19: ui.exam_mode 模块可导入。"""
    from ui import exam_mode  # pylint: disable=unused-import
    assert hasattr(exam_mode, 'ExamMode')


def test_ui_review_mode_importable():
    """TD-19: ui.review_mode 模块可导入。"""
    from ui import review_mode  # pylint: disable=unused-import
    assert hasattr(review_mode, 'ReviewMode')


def test_ui_wrong_book_importable():
    """TD-19: ui.wrong_book 模块可导入。"""
    from ui import wrong_book  # pylint: disable=unused-import
    assert hasattr(wrong_book, 'WrongBook')


def test_ui_option_row_importable():
    """TD-19: ui.option_row 模块可导入。"""
    from ui import option_row  # pylint: disable=unused-import


def test_ui_main_window_importable():
    """TD-19: ui.main_window 模块可导入（含 MainWindow + MasteryRing + 模块级函数）。"""
    from ui import main_window  # pylint: disable=unused-import
    assert hasattr(main_window, 'MainWindow')
    assert hasattr(main_window, 'MasteryRing')
    # TD-11 抽取的模块级函数
    assert callable(main_window._get_license_error_message)
    assert callable(main_window._verify_and_save_license)


def test_main_window_class_hierarchy():
    """TD-19: MainWindow 继承 tk.Tk，MasteryRing 继承 tk.Canvas。"""
    import tkinter as tk
    from ui.main_window import MainWindow, MasteryRing
    assert issubclass(MainWindow, tk.Tk)
    assert issubclass(MasteryRing, tk.Canvas)
