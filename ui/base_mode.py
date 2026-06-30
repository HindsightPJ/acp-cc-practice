import tkinter as tk
from tkinter import ttk, messagebox

from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from .theme import (
    BG_PAGE, BG_CARD, BG_INPUT, BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, font_ui, font_ui_semibold,
)


class BaseMode(ABC, ttk.Frame):
    """练习模式的抽象基类，包含公共功能和生命周期管理"""

    def __init__(self, parent, questions: List[Dict[str, Any]],
                 data_manager, progress: Dict[str, Any]):
        super().__init__(parent)
        self.questions = questions
        self.data_manager = data_manager
        self.progress = progress
        self._after_jobs: List[Any] = []  # 跟踪所有 after 回调

    def _add_after_job(self, job_id) -> None:
        """添加 after 作业并跟踪"""
        self._after_jobs.append(job_id)

    def _cancel_all_after_jobs(self) -> None:
        """取消所有待执行的 after 回调"""
        for job_id in self._after_jobs:
            try:
                self.after_cancel(job_id)
            except Exception:
                pass
        self._after_jobs.clear()

    def destroy(self) -> None:
        """窗口销毁时清理所有待执行的回调"""
        self._cancel_all_after_jobs()
        super().destroy()

    def _create_toolbar(self, parent) -> tuple:
        """创建公共工具栏，返回 (toolbar, progress_label, type_label)"""
        toolbar = tk.Frame(parent, bg=BG_PAGE)
        toolbar.pack(fill=tk.X, pady=(0, 12))

        toolbar_left = tk.Frame(toolbar, bg=BG_PAGE)
        toolbar_left.pack(side=tk.LEFT)

        progress_label = tk.Label(
            toolbar_left, text="第 0 题 / 共 0 题",
            font=font_ui(11), fg=TEXT_SECONDARY, bg=BG_PAGE)
        progress_label.pack(side=tk.LEFT, padx=(0, 16))

        type_label = tk.Label(
            toolbar_left, text="单选题",
            font=font_ui_semibold(10), fg=ACCENT, bg=BG_PAGE)
        type_label.pack(side=tk.LEFT)

        return toolbar, progress_label, type_label

    def _create_progress_bar(self, parent) -> tuple:
        """创建进度条，返回 (progress_bg, progress_bar_fill)"""
        progress_bg = tk.Frame(parent, bg=BORDER, height=3)
        progress_bg.pack(fill=tk.X, pady=(0, 16))
        progress_bg.pack_propagate(False)

        progress_bar_fill = tk.Frame(progress_bg, bg=ACCENT, width=0, height=3)
        progress_bar_fill.place(x=0, y=0, relheight=1.0)

        return progress_bg, progress_bar_fill

    def _update_progress_bar_width(self, progress_bar_fill, container_width: int, percentage: float) -> None:
        """更新进度条宽度"""
        if container_width > 0:
            bar_width = int(container_width * (percentage / 100))
            progress_bar_fill.configure(width=max(bar_width, 0))

    def _bind_keyboard(self) -> None:
        """绑定键盘事件"""
        self.focus_set()
        self.bind('<Key>', self._on_key_press)
        self.bind_all('<Button-1>', self._on_global_click)

    def _on_global_click(self, event) -> None:
        """全局点击处理，设置焦点。

        切 tab 时旧 mode 被 destroy，但 bind_all 注册的全局 callback 仍在
        Tcl 绑定表里，下次点击会调用已销毁 widget 的 focus_set 抛 TclError，
        静默忽略即可——旧 mode 已不活动，无需 focus。
        """
        try:
            self.focus_set()
        except tk.TclError:
            pass

    def _on_key_press(self, event):
        """键盘事件处理 - 子类可覆盖。

        导航键（Left/Right）的默认实现映射到 prev_question/next_question。
        子类如有特有按键，可在处理完后 `return super()._on_key_press(event)`
        复用本方法的导航逻辑，避免重复代码（TD-06 修复）。
        """
        key = event.char.upper() if event.char else ''
        keysym = event.keysym

        # 导航键默认处理
        if keysym == 'Left':
            self.prev_question()
            return 'break'
        if keysym == 'Right':
            self.next_question()
            return 'break'
        return None

    def next_question(self) -> Optional[Dict[str, Any]]:
        """下一题"""
        if self.engine and self.engine.has_next():
            self.engine.next_question()
            self.current_index = self.engine.current_index
            return self.engine.get_current_question()
        return None

    def prev_question(self) -> Optional[Dict[str, Any]]:
        """上一题"""
        if self.engine and self.engine.has_prev():
            self.engine.prev_question()
            self.current_index = self.engine.current_index
            return self.engine.get_current_question()
        return None

    # 抽象方法 - 子类必须实现
    @abstractmethod
    def _setup_mode_ui(self) -> None:
        """模式特有的UI初始化"""
        pass
