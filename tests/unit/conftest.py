"""tests/unit 共享 fixtures。

P2-TEST: UI 测试共享同一个 session 级 Tk 根实例，避免多个模块各自创建/销毁
 tk.Tk() 导致 Tcl 解释器状态损坏（随机出现 tcl_findLibrary / tk.tcl 找不到）。
"""
import tkinter as tk

import pytest


@pytest.fixture(scope='session')
def root():
    """Session 级共享 Tk 实例，供所有 UI 单元测试复用。"""
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()
