"""tests/unit 共享 fixtures（PySide6 offscreen 版）。

P6 迁移：tkinter session 级 Tk 根实例 → Qt offscreen 平台。
- 环境变量必须在首个 QApplication 创建前设置，故置于模块顶层；
- QT_QPA_FONTDIR：offscreen 不扫系统字体，不指定会让文字渲染为空框；
- pytest-qt 提供 session 级 qapp 与 qtbot，此处不再自定义 QApplication fixture。
"""

import os

# 必须在任何 QApplication 实例化之前生效（conftest import 时点早于所有测试收集）
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PySide6.QtWidgets import QMessageBox


@pytest.fixture(autouse=True)
def _mute_message_boxes(monkeypatch):
    """静音 QMessageBox 全部静态弹窗：模态 exec 在 offscreen 无头进程下永久阻塞。

    默认 question 返回 No（保守：写操作类确认一律拒绝）；
    需要 Yes 或断言弹窗文案的用例在测试体内自行 monkeypatch 覆盖
    （fixture setup 先于测试体执行，后设置的 mock 生效）。
    """
    for name in ("information", "warning", "critical", "about"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
