"""ExamPanel - 考试模式视图组件。

P0-2: 从 ExamMode 拆出的纯视图层，负责考试进行中的 UI 渲染：
计时器条、题干、选项、操作栏、题号导航。编排逻辑（启动/交卷/计时循环/
历史保存/报告展示）保留在 ExamMode。

通过回调与 ExamMode 通信，避免反向依赖。
"""

import tkinter as tk
from tkinter import messagebox
from typing import Callable

from .theme import (
    theme,
    font_ui,
    font_ui_semibold,
    font_mono,
    create_primary_button,
    create_normal_button,
    create_card,
)
from .constants import MAX_OPTIONS
from .option_row import OptionRow
from .question_detail_card import get_question_type_style
from quiz_engine import QuizEngine
from .exam_session import ExamSession


class ExamPanel(tk.Frame):
    """考试视图组件（纯渲染 + 局部交互）。

    Args:
        parent: 父容器
        engine: 考试用 QuizEngine
        exam_session: 考试会话状态（已答/标记）
        on_prev: 上一题回调
        on_next: 下一题回调
        on_submit: 交卷回调
        on_mark: 标记当前题回调
        on_jump: 跳转到指定索引回调，签名为 (idx: int) -> None
        on_select_option: 选项被选择回调，签名为 (letter: str) -> None
    """

    def __init__(
        self,
        parent: tk.Misc,
        engine: QuizEngine,
        exam_session: ExamSession,
        on_prev: Callable[[], None],
        on_next: Callable[[], None],
        on_submit: Callable[[], None],
        on_mark: Callable[[], None],
        on_jump: Callable[[int], None],
        on_select_option: Callable[[str], None],
    ) -> None:
        super().__init__(parent, bg=theme.BG_PAGE)
        self.engine = engine
        self.exam_session = exam_session
        self._on_prev = on_prev
        self._on_next = on_next
        self._on_submit = on_submit
        self._on_mark = on_mark
        self._on_jump = on_jump
        self._on_select_option = on_select_option

        self.exam_option_cards: list[dict] = []
        self.nav_buttons: list[tk.Label] = []
        self.timer_label: tk.Label | None = None
        self.exam_progress_label: tk.Label | None = None
        # P1-6: 跟踪上一次的 current_index，支持增量更新题号导航按钮
        self._last_current_index: int = -1
        self.exam_type_label: tk.Label | None = None
        self.exam_question_text: tk.Text | None = None
        self.nav_canvas: tk.Canvas | None = None
        self.nav_frame: tk.Frame | None = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """构建考试视图 UI（P0-1: 拆分为 4 个子方法以控制单方法复杂度）。"""
        self._build_timer_bar()

        # 主体：左题区 + 右题号导航
        main_paned = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            bg=theme.BG_PAGE,
            sashrelief=tk.FLAT,
            sashwidth=4,
        )
        main_paned.pack(fill=tk.BOTH, expand=True)

        left_panel = tk.Frame(main_paned, bg=theme.BG_PAGE)
        main_paned.add(left_panel, minsize=600)

        self._build_question_area(left_panel)
        self._build_action_bar(left_panel)
        self._build_nav_panel(main_paned)

        # P2-UX: 窗口缩放时同步更新选项文本换行宽度
        self.bind("<Configure>", self._on_configure)

    def _build_timer_bar(self) -> None:
        """构建顶部计时器条（计时器标签 + 进度标签 + 题型标签）。"""
        timer_bar, timer_inner = create_card(self, inner_padx=24, inner_pady=12)
        timer_bar.pack(fill=tk.X, pady=(0, 12))

        timer_left = tk.Frame(timer_inner, bg=theme.BG_CARD)
        timer_left.pack(side=tk.LEFT)

        self.timer_label = tk.Label(
            timer_left, text="60:00", font=font_mono(20), fg=theme.RED, bg=theme.BG_CARD
        )
        self.timer_label.pack(side=tk.LEFT, padx=(0, 8))

        timer_hint = tk.Label(
            timer_left, text="剩余时间", font=font_ui(10), fg=theme.TEXT_MUTED, bg=theme.BG_CARD
        )
        timer_hint.pack(side=tk.LEFT)

        self.exam_progress_label = tk.Label(
            timer_inner,
            text="第 0 / 100 题",
            font=font_ui(11),
            fg=theme.TEXT_SECONDARY,
            bg=theme.BG_CARD,
        )
        self.exam_progress_label.pack(side=tk.RIGHT)

        self.exam_type_label = tk.Label(
            timer_inner, text="", font=font_ui_semibold(10), fg=theme.ACCENT, bg=theme.BG_CARD
        )
        self.exam_type_label.pack(side=tk.RIGHT, padx=(0, 16))

    def _build_question_area(self, left_panel: tk.Frame) -> None:
        """构建题干卡 + 选项卡。"""
        # 题干卡
        question_card, q_inner = create_card(left_panel, inner_pady=16)
        question_card.pack(fill=tk.X, pady=(0, 12))

        self.exam_question_text = tk.Text(
            q_inner,
            height=4,
            wrap=tk.WORD,
            font=font_ui(12),
            bg=theme.BG_CARD,
            fg=theme.TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=0,
            pady=0,
            selectbackground=theme.BG_SELECT,
            insertbackground=theme.TEXT_PRIMARY,
        )
        self.exam_question_text.pack(fill=tk.X)
        self.exam_question_text.config(state=tk.DISABLED)

        # 选项卡
        options_card, opt_inner = create_card(left_panel, inner_pady=14)
        options_card.pack(fill=tk.X, pady=(0, 12))

        for idx in range(MAX_OPTIONS):
            letter = chr(ord("A") + idx)
            row = OptionRow(
                opt_inner,
                letter=letter,
                on_click=lambda sel: self._on_select_option(sel),
                wraplength=550,
            )
            row.pack(fill=tk.X, pady=3)
            self.exam_option_cards.append(
                {
                    "row": row,
                    "letter": letter,
                }
            )

    def _build_action_bar(self, left_panel: tk.Frame) -> None:
        """构建操作栏（上一题/下一题 + 跳转 + 标记 + 交卷）。"""
        action_bar = tk.Frame(left_panel, bg=theme.BG_PAGE)
        action_bar.pack(fill=tk.X, pady=(0, 8))

        btn_left = tk.Frame(action_bar, bg=theme.BG_PAGE)
        btn_left.pack(side=tk.LEFT)

        prev_exam_btn = create_normal_button(
            btn_left,
            text="上一题 (←)",
            command=self._on_prev,
        )
        prev_exam_btn.pack(side=tk.LEFT, padx=(0, 4))

        next_exam_btn = create_normal_button(
            btn_left,
            text="下一题 (→)",
            command=self._on_next,
        )
        next_exam_btn.pack(side=tk.LEFT)

        # P2-UX: 考试模式支持按题号快速跳转
        jump_frame = tk.Frame(btn_left, bg=theme.BG_PAGE)
        jump_frame.pack(side=tk.LEFT, padx=(16, 0))

        tk.Label(
            jump_frame, text="跳转", font=font_ui(10), fg=theme.TEXT_MUTED, bg=theme.BG_PAGE
        ).pack(side=tk.LEFT, padx=(0, 4))

        self.jump_var = tk.StringVar()
        self.jump_entry = tk.Entry(
            jump_frame,
            textvariable=self.jump_var,
            width=5,
            font=font_ui(10),
            bg=theme.BG_CARD,
            fg=theme.TEXT_PRIMARY,
            insertbackground=theme.TEXT_PRIMARY,
            relief=tk.FLAT,
            bd=2,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
        )
        self.jump_entry.pack(side=tk.LEFT, padx=(0, 4))
        self.jump_entry.bind("<Return>", lambda event: self._on_jump_entry())

        jump_btn = create_normal_button(
            jump_frame,
            text="跳转",
            command=self._on_jump_entry,
            padx=10,
            pady=3,
        )
        jump_btn.pack(side=tk.LEFT)

        mark_btn = create_primary_button(
            action_bar,
            text="标记 (M)",
            command=self._on_mark,
            bg_color=theme.YELLOW,
            active_bg=theme.YELLOW_BORDER,
            padx=12,
            pady=5,
        )
        mark_btn.pack(side=tk.LEFT, padx=(8, 0))

        submit_exam_btn = create_primary_button(
            action_bar,
            text="交卷",
            command=self._on_submit,
            bg_color=theme.RED,
            active_bg="#dc2626",
            padx=20,
        )
        submit_exam_btn.pack(side=tk.RIGHT)

    def _build_nav_panel(self, main_paned: tk.PanedWindow) -> None:
        """构建右侧题号导航面板（可滚动按钮网格）。"""
        nav_panel = tk.Frame(
            main_paned, bg=theme.BG_CARD, highlightbackground=theme.BORDER, highlightthickness=1
        )
        main_paned.add(nav_panel, minsize=180)

        nav_inner = tk.Frame(nav_panel, bg=theme.BG_CARD)
        nav_inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        tk.Label(
            nav_inner,
            text="题号导航",
            font=font_ui_semibold(11),
            fg=theme.TEXT_PRIMARY,
            bg=theme.BG_CARD,
        ).pack(anchor=tk.W, pady=(0, 8))

        tk.Label(
            nav_inner,
            text="● 已答  ○ 未答  ★ 标记",
            font=font_ui(9),
            fg=theme.TEXT_MUTED,
            bg=theme.BG_CARD,
        ).pack(anchor=tk.W, pady=(0, 8))

        nav_scroll = tk.Scrollbar(nav_inner)
        nav_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.nav_canvas = tk.Canvas(
            nav_inner, bg=theme.BG_CARD, highlightthickness=0, yscrollcommand=nav_scroll.set
        )
        self.nav_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        nav_scroll.config(command=self.nav_canvas.yview)

        self.nav_frame = tk.Frame(self.nav_canvas, bg=theme.BG_CARD)
        self.nav_canvas.create_window((0, 0), window=self.nav_frame, anchor=tk.NW)

    def _on_configure(self, event: tk.Event) -> None:
        """窗口 resize 时同步更新选项文本换行宽度，避免内容被截断。"""
        new_wrap = max(200, event.width - 140)
        for item in self.exam_option_cards:
            item["row"].update_wraplength(new_wrap)

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def update_timer_display(self, time_remaining: int, total_seconds: int) -> None:
        """更新计时器标签与颜色。"""
        minutes = time_remaining // 60
        seconds = time_remaining % 60
        time_str = f"{minutes:02d}:{seconds:02d}"
        if self.timer_label is not None:
            self.timer_label.configure(text=time_str)
            if time_remaining <= 300:
                color = theme.RED if time_remaining % 2 == 0 else "#b91c1c"
                self.timer_label.configure(fg=color)

    def build_nav_buttons(self, total: int) -> None:
        """构建题号导航按钮。"""
        for btn in self.nav_buttons:
            btn.destroy()
        self.nav_buttons = []

        cols = 5
        for i in range(total):
            row = i // cols
            col = i % cols

            # P0-7: takefocus=True 让题号按钮可通过 Tab 获得键盘焦点
            btn = tk.Label(
                self.nav_frame,
                text=str(i + 1),
                font=font_ui(10),
                width=3,
                height=1,
                bg=theme.BG_INPUT,
                fg=theme.TEXT_SECONDARY,
                cursor="hand2",
                takefocus=True,
            )
            btn.grid(row=row, column=col, padx=2, pady=2)
            btn.bind("<Button-1>", lambda e, idx=i: self._on_jump(idx))  # type: ignore[misc]
            # P0-7: 键盘激活——Return / Space 跳转到对应题号
            btn.bind("<Return>", lambda e, idx=i: self._on_jump(idx))  # type: ignore[misc]
            btn.bind("<space>", lambda e, idx=i: self._on_jump(idx))  # type: ignore[misc]
            self.nav_buttons.append(btn)

        assert self.nav_frame is not None
        self.nav_frame.update_idletasks()
        if self.nav_canvas is not None:
            self.nav_canvas.config(scrollregion=self.nav_canvas.bbox(tk.ALL))

    def update_nav_buttons(self) -> None:
        """根据 engine 与 session 状态刷新题号导航（全量，用于初始化/reset）。"""
        current = self.engine.get_current_index()
        for i, btn in enumerate(self.nav_buttons):
            self._apply_nav_button_style(i, btn, current)
        # P1-6: 全量刷新后同步 _last_current_index
        self._last_current_index = current

    def _update_single_nav_button(self, idx: int) -> None:
        """增量更新单个题号按钮的样式（P1-6: 避免全量遍历）。"""
        if not (0 <= idx < len(self.nav_buttons)):
            return
        current = self.engine.get_current_index()
        self._apply_nav_button_style(idx, self.nav_buttons[idx], current)

    def _apply_nav_button_style(self, i: int, btn: tk.Label, current: int) -> None:
        """根据索引、当前位置和 session 状态应用按钮样式。"""
        if i == current:
            bg = theme.ACCENT
            fg = theme.SELECTED_TEXT
        elif self.exam_session.has_answer(i):
            bg = theme.GREEN_BG
            fg = theme.GREEN_TEXT
        else:
            bg = theme.BG_INPUT
            fg = theme.TEXT_SECONDARY

        if self.exam_session.is_marked(i):
            text = f"★{i + 1}"
        else:
            text = str(i + 1)

        btn.configure(text=text, bg=bg, fg=fg)

    def load_question(self) -> None:
        """加载当前题目到视图。"""
        question = self.engine.get_current_question()
        if not question or self.exam_question_text is None:
            return

        self.exam_question_text.config(state=tk.NORMAL)
        self.exam_question_text.delete(1.0, tk.END)
        self.exam_question_text.insert(
            tk.END, f"{self.engine.get_current_index() + 1}. {question.content}"
        )
        self.exam_question_text.config(state=tk.DISABLED)

        # 题型标签
        if self.exam_type_label is not None:
            type_text, type_fg = get_question_type_style(question.type)
            self.exam_type_label.configure(text=type_text, fg=type_fg)

        # 选项
        options_count = len(question.options)
        for i, item in enumerate(self.exam_option_cards):
            if i < options_count:
                item["row"].pack(fill=tk.X, pady=3)
                opt = question.options[i]
                item["row"].update_text(opt.text)
                item["row"].reset()
            else:
                item["row"].pack_forget()

        # 恢复已选状态
        answered_letters = self.exam_session.get_current_selected()
        for i, item in enumerate(self.exam_option_cards):
            letter = chr(ord("A") + i)
            if letter in answered_letters:
                item["row"].set_selected(True)

        # 进度
        progress = self.engine.get_progress()
        if self.exam_progress_label is not None:
            self.exam_progress_label.configure(
                text=f"第 {progress['current']} / {progress['total']} 题"
            )

        # P1-6: 切题时增量更新——只刷新旧 current 和新 current 两个按钮，
        # 避免 100~200 个按钮的全量 configure（每次 Tcl IPC）
        current = self.engine.get_current_index()
        if 0 <= self._last_current_index < len(self.nav_buttons) and self._last_current_index != current:
            self._update_single_nav_button(self._last_current_index)
        self._update_single_nav_button(current)
        self._last_current_index = current

    def sync_option_selection(self, selected: str) -> None:
        """根据已选字母串同步选项 UI（纯视图，不修改状态）。

        Args:
            selected: 已选字母排序串，如 "AC"
        """
        if self.engine is None:
            return
        current = self.engine.get_current_question()
        if not current:
            return

        options_count = len(current.options)
        for i, item in enumerate(self.exam_option_cards):
            if i >= options_count:
                continue
            letter_i = chr(ord("A") + i)
            is_selected = letter_i in selected
            item["row"].set_selected(is_selected)

        # P1-6: 选项选择只改变当前题的已答状态，只需更新当前按钮
        self._update_single_nav_button(self.engine.get_current_index())

    def _on_jump_entry(self) -> None:
        """从跳转输入框读取题号并跳转到对应题目（1-based）。"""
        if self.engine is None:
            return
        try:
            num = int(self.jump_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字！", parent=self)
            return

        total = self.engine.queue_length()
        if not 1 <= num <= total:
            messagebox.showerror("错误", f"请输入 1-{total} 之间的题号！", parent=self)
            return

        self._on_jump(num - 1)

    # ------------------------------------------------------------------
    # 键盘处理
    # ------------------------------------------------------------------

    def handle_key_press(self, event: tk.Event) -> str | None:
        """处理考试导航与标记键（选项选择由 ExamMode 经基类统一处理）。

        Returns:
            "break" 表示已处理，否则 None。
        """
        if not self.engine or not self.engine.get_current_question():
            return None

        keysym = event.keysym
        if keysym == "Left":
            self._on_prev()
            return "break"
        if keysym == "Right":
            self._on_next()
            return "break"

        key = event.char.upper() if event.char else ""
        if key == "M":
            self._on_mark()
            return "break"

        return None
