"""UI 模块冒烟测试（TD-19，PySide6 版）。

验证所有 UI 模块可导入（语法错误 / import 链断裂 / 循环依赖），
以及关键类的 Qt 基类归属。
"""


# ---------- 包与模块导入 ----------


def test_ui_package_importable():
    import ui  # pylint: disable=unused-import

    assert ui is not None


def test_ui_theme_importable():
    from ui import theme

    assert hasattr(theme.theme, "BG")
    assert hasattr(theme.theme, "ACCENT")
    assert callable(theme.build_qss)
    assert callable(theme.apply_qss)


def test_ui_base_mode_importable():
    from ui import base_mode

    assert hasattr(base_mode, "BaseModePage")
    assert hasattr(base_mode, "SAVE_DEBOUNCE_MS")


def test_ui_mode_pages_importable():
    from ui import exam_mode, practice_mode, review_mode, wrong_book

    assert hasattr(practice_mode, "PracticeMode")
    assert hasattr(exam_mode, "ExamMode")
    assert hasattr(review_mode, "ReviewMode")
    assert hasattr(wrong_book, "WrongBookPage")


def test_ui_panels_and_components_importable():
    from ui import (
        answer_sheet,
        exam_panel,
        option_row,
        practice_panel,
        question_detail_card,
    )

    assert hasattr(practice_panel, "PracticePanel")
    assert hasattr(exam_panel, "ExamPanel")
    assert hasattr(answer_sheet, "AnswerSheet")
    assert hasattr(answer_sheet, "StatColumn")
    assert hasattr(option_row, "OptionRow")
    assert hasattr(question_detail_card, "QuestionDetailCard")
    assert hasattr(question_detail_card, "type_label")


def test_ui_dialogs_and_titlebar_importable():
    from ui import base_dialog, exam_report_dialog, license_dialog, titlebar

    assert hasattr(base_dialog, "BaseDialog")
    assert hasattr(exam_report_dialog, "ExamReportDialog")
    assert hasattr(license_dialog, "LicenseDialog")
    assert hasattr(titlebar, "TitleBar")
    assert hasattr(titlebar, "setup_frameless")


def test_ui_main_window_importable():
    from ui import main_window

    assert hasattr(main_window, "MainWindow")
    assert hasattr(main_window, "NAV_DEFS")


# ---------- 类层次 ----------


def test_main_window_class_hierarchy():
    from PySide6.QtWidgets import QMainWindow

    from ui.main_window import MainWindow

    assert issubclass(MainWindow, QMainWindow)


def test_base_mode_page_class_hierarchy():
    from PySide6.QtWidgets import QFrame

    from ui.base_mode import BaseModePage

    assert issubclass(BaseModePage, QFrame)


def test_dialogs_class_hierarchy():
    from PySide6.QtWidgets import QDialog

    from ui.base_dialog import BaseDialog
    from ui.exam_report_dialog import ExamReportDialog
    from ui.license_dialog import LicenseDialog

    assert issubclass(BaseDialog, QDialog)
    assert issubclass(ExamReportDialog, BaseDialog)
    assert issubclass(LicenseDialog, BaseDialog)


def test_theme_token_sets_have_identical_fields():
    """浅/深两套 Token 字段名必须一致（theme.py 导入时自校验的静态复核）。"""
    from ui.theme import _DARK_TOKENS, _LIGHT_TOKENS

    assert set(_LIGHT_TOKENS) == set(_DARK_TOKENS)
