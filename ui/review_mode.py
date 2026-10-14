import tkinter as tk
from tkinter import messagebox
from .theme import (
    theme,
    font_ui,
    font_ui_semibold,
    create_primary_button,
    create_normal_button,
    create_switch,
)

from quiz_engine import QuizEngine
from models import Question
from data_manager import DataManager
from app_state import AppState
from .base_mode import BaseMode
from .question_detail_card import QuestionDetailCard, get_question_type_style
from .mode_toolbar import ModeToolbar
from .constants import AUTO_SHOW_ANSWER_DELAY_MS


class ReviewMode(BaseMode):
    # P2-9: 覆盖基类的保存失败提示文案
    _save_failure_message = "收藏状态保存失败，请检查磁盘空间或文件权限。"

    def __init__(
        self,
        parent: tk.Misc,
        questions: list[Question],
        data_manager: DataManager | None,
        progress: AppState,
    ) -> None:
        super().__init__(parent, questions, data_manager, progress)
        self.showing_answer = False
        self.auto_show_answer = False
        # P0-5: 是否处于"只看收藏"筛选模式（影响队列来源 + 按钮文案）
        self.filtering_favorites: bool = False
        # P1-7: 题号→题目索引，收藏筛选时 O(M) 查找替代 O(N) 全量遍历
        self._question_by_number: dict[int, Question] = {q.number: q for q in questions}

        self.engine: QuizEngine = QuizEngine(questions)
        self.engine.set_questions_queue(questions)  # TD-15: 显式接口
        # P2-UX: 跟踪自动显示答案的 after 任务，快速切题时先取消旧任务
        # tkinter.after 返回字符串标识符，与 after_cancel 入参类型一致
        self._auto_show_job_id: str | None = None
        self._setup_mode_ui()
        self.load_question()
        self._bind_keyboard()

    def _setup_mode_ui(self) -> None:
        self.configure(style="TFrame")

        toolbar = ModeToolbar(self)

        self.progress_info = tk.Label(
            toolbar.left,
            text=f"第 1 题 / 共 {len(self.questions)} 题",
            font=font_ui(11),
            fg=theme.TEXT_SECONDARY,
            bg=theme.BG_PAGE,
        )
        self.progress_info.pack(side=tk.LEFT, padx=(0, 16))

        self.type_label = tk.Label(
            toolbar.left,
            text="单选题",
            font=font_ui_semibold(10),
            fg=theme.ACCENT,
            bg=theme.BG_PAGE,
        )
        self.type_label.pack(side=tk.LEFT, padx=(0, 12))

        # P0-5: "只看收藏"筛选按钮——点击切换是否仅显示收藏题列表
        self.filter_fav_btn = create_normal_button(
            toolbar.left,
            text="只看收藏",
            command=self.toggle_favorites_filter,
            padx=10,
            pady=3,
        )
        self.filter_fav_btn.pack(side=tk.LEFT)

        self.auto_var = tk.BooleanVar(value=False)
        create_switch(toolbar.right, self.auto_var, self._toggle_auto_show).pack(side=tk.LEFT)
        tk.Label(
            toolbar.right,
            text="自动显示答案",
            font=font_ui(11),
            fg=theme.TEXT_SECONDARY,
            bg=theme.BG_PAGE,
        ).pack(side=tk.LEFT, padx=(6, 16))

        jump_label = tk.Label(
            toolbar.right, text="跳转", font=font_ui(10), fg=theme.TEXT_MUTED, bg=theme.BG_PAGE
        )
        jump_label.pack(side=tk.LEFT, padx=(0, 4))

        self.jump_var = tk.StringVar()
        self.jump_entry = tk.Entry(
            toolbar.right,
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
        # P2-UX: 输入框支持回车跳转
        self.jump_entry.bind("<Return>", lambda event: self.jump_to_question())

        jump_btn = create_normal_button(
            toolbar.right,
            text="跳转",
            command=self.jump_to_question,
            padx=10,
            pady=3,
        )
        jump_btn.pack(side=tk.LEFT, padx=(0, 8))

        prev_btn = create_normal_button(
            toolbar.right,
            text="上一题 (←)",
            command=self.prev_question,
            padx=10,
            pady=3,
        )
        prev_btn.pack(side=tk.LEFT, padx=(0, 4))

        next_btn = create_normal_button(
            toolbar.right,
            text="下一题 (→)",
            command=self.next_question,
            padx=10,
            pady=3,
        )
        next_btn.pack(side=tk.LEFT)

        self.detail_card = QuestionDetailCard(
            self,
            on_option_click=None,
            option_wraplength=700,
            answer_placeholder="点击下方按钮显示答案",
            inner_padx=20,
            question_inner_pady=16,
            option_inner_pady=14,
            option_pady=2,
        )
        self.detail_card.pack(fill=tk.BOTH, expand=True)

        action_bar = tk.Frame(self, bg=theme.BG_PAGE)
        action_bar.pack(fill=tk.X, pady=(12, 0))

        self.toggle_answer_btn = create_primary_button(
            action_bar,
            text="显示答案 (Space)",
            command=self.toggle_answer,
            bg_color=theme.PURPLE,
            active_bg=theme.PURPLE_HOVER,
            width=16,
        )
        self.toggle_answer_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.favorite_btn = create_normal_button(
            action_bar,
            text="收藏",
            command=self.toggle_favorite,
        )
        self.favorite_btn.pack(side=tk.LEFT)

    def _on_key_press(self, event: tk.Event) -> str | None:
        if self._is_input_focused():
            return None

        keysym = event.keysym

        if keysym == "space":
            self.toggle_answer()
            return "break"

        # 导航键（Left/Right）交给基类处理（TD-06: 复用 super() 避免重复）
        return super()._on_key_press(event)

    def _toggle_auto_show(self) -> None:
        self.auto_show_answer = self.auto_var.get()
        if self.auto_show_answer and not self.showing_answer:
            self.toggle_answer()

    def load_question(self) -> None:
        # P2-UX: 快速切题时取消尚未执行的自动显示答案任务，避免作用到下一题
        # P0-5: 改用 _cancel_after_job 统一 cancel+remove，避免 _after_jobs 集合泄漏
        self._cancel_after_job(self._auto_show_job_id)
        self._auto_show_job_id = None

        question = self.engine.get_current_question()
        if question is None:
            return
        current_index = self.engine.get_current_index()

        # 题干 + 选项 + 答案/解析状态由 QuestionDetailCard 统一渲染
        self.detail_card.show_question(question)

        # 显示题目类型
        type_text, type_fg = get_question_type_style(question.type)
        self.type_label.configure(text=type_text, fg=type_fg)

        self.showing_answer = False
        self.toggle_answer_btn.configure(text="显示答案 (Space)")

        self.jump_var.set(str(current_index + 1))
        # P0-5: 进度信息显示当前队列长度（筛选收藏时队列变短，文案应随之变化）
        self.progress_info.configure(
            text=f"第 {current_index + 1} 题 / 共 {self.engine.queue_length()} 题"
        )

        self._sync_favorite_button()
        self._sync_filter_button()

        if self.auto_show_answer:
            self._auto_show_job_id = self.after(AUTO_SHOW_ANSWER_DELAY_MS, self.toggle_answer)
            self._add_after_job(self._auto_show_job_id)

    def toggle_answer(self) -> None:
        question = self.engine.get_current_question()
        if question is None:
            return

        if not self.showing_answer:
            self.showing_answer = True
            self.detail_card.reveal_correct_options(question)
            self.detail_card.set_answer_label(
                f"正确答案: {question.answer or '未知'}", fg=theme.GREEN
            )
            self.detail_card.set_explanation(question.explanation or "暂无解析")
            self.toggle_answer_btn.configure(text="隐藏答案 (Space)")
        else:
            self.showing_answer = False
            self.detail_card.clear_answer_state()
            self.detail_card.reset_options()
            self.toggle_answer_btn.configure(text="显示答案 (Space)")

    def next_question(self) -> None:
        if self.engine and self.engine.has_next():
            self.engine.next_question()
            self.load_question()

    def prev_question(self) -> None:
        if self.engine and self.engine.has_prev():
            self.engine.prev_question()
            self.load_question()

    def jump_to_question(self) -> None:
        try:
            num = int(self.jump_var.get())
            # P0-5: 边界基于当前队列长度（筛选模式下队列更短）
            total = self.engine.queue_length()
            if 1 <= num <= total:
                self.engine.set_current_index(num - 1)
                self.load_question()
            else:
                messagebox.showerror("错误", f"请输入 1-{total} 之间的题号！", parent=self)
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字！", parent=self)

    def toggle_favorite(self) -> None:
        question = self.engine.get_current_question()
        if question is None:
            return
        q_num = question.number
        # toggle_favorite 返回 True 表示当前已收藏，False 表示已取消收藏
        now_favorited = self.app_state.toggle_favorite(q_num)
        # P1-3: 延迟落盘，避免连续收藏触发多次磁盘写入（内存状态已即时更新）
        self._save_progress_delayed()
        self._sync_favorite_button()

        # P0-5: 筛选模式下，取消收藏的题目应从队列移除，保持"所见即所藏"
        if self.filtering_favorites and not now_favorited:
            self._refresh_favorites_queue()

    def _build_favorites_queue(self, fav_nums: list[int]) -> list[Question]:
        """将收藏题号列表转换为已排序的题目对象列表。

        过滤掉不在当前题库中的题号，使用 _question_by_number 索引实现 O(M) 查找。
        """
        return sorted(
            (self._question_by_number[n] for n in fav_nums if n in self._question_by_number),
            key=lambda q: q.number,
        )

    def _apply_favorites_queue(self, fav_questions: list[Question]) -> None:
        """应用收藏筛选队列：非空则进入筛选，空则退出筛选并恢复全量题库。"""
        if not fav_questions:
            self.filtering_favorites = False
            self.engine.set_questions_queue(self.questions)
        else:
            self.filtering_favorites = True
            self.engine.set_questions_queue(fav_questions)
        self.engine.set_current_index(0)
        self.load_question()

    def _refresh_favorites_queue(self) -> None:
        """筛选模式下根据当前收藏列表刷新队列。

        - 收藏为空：退出筛选模式，恢复全量题库
        - 仍有收藏：替换队列，索引归零并加载第一题
        """
        fav_questions = self._build_favorites_queue(self.app_state.get_favorites())
        self._apply_favorites_queue(fav_questions)

    def toggle_favorites_filter(self) -> None:
        """切换"只看收藏"筛选模式。"""
        if self.filtering_favorites:
            # 退出筛选：恢复全量题库
            self._apply_favorites_queue([])
            return

        # 进入筛选：检查收藏是否为空
        fav_nums = self.app_state.get_favorites()
        if not fav_nums:
            messagebox.showinfo(
                "提示",
                '暂无收藏题目。\n\n点击题目下方的"收藏"按钮可添加收藏。',
                parent=self,
            )
            return

        fav_questions = self._build_favorites_queue(fav_nums)
        if not fav_questions:
            # 收藏的题号在当前题库中不存在（如授权前的试用题库）
            messagebox.showinfo(
                "提示",
                "收藏的题目不在当前题库中。",
                parent=self,
            )
            return
        self._apply_favorites_queue(fav_questions)

    def _sync_filter_button(self) -> None:
        """根据筛选状态更新按钮文案与配色。"""
        if not hasattr(self, "filter_fav_btn"):
            return
        if self.filtering_favorites:
            self.filter_fav_btn.configure(text="显示全部", fg=theme.ACCENT, bg=theme.ACCENT_LIGHT)
        else:
            self.filter_fav_btn.configure(
                text="只看收藏", fg=theme.BTN_NORMAL_FG, bg=theme.BTN_NORMAL
            )

    def _sync_favorite_button(self) -> None:
        """根据当前题是否已收藏，更新按钮文字与配色作为静默反馈。"""
        if not self.engine:
            return
        question = self.engine.get_current_question()
        if question is None:
            return
        q_num = question.number
        is_fav = self.app_state.is_favorite(q_num)
        if is_fav:
            self.favorite_btn.configure(text="已收藏 ✓", fg=theme.ACCENT, bg=theme.ACCENT_LIGHT)
        else:
            self.favorite_btn.configure(text="收藏", fg=theme.BTN_NORMAL_FG, bg=theme.BTN_NORMAL)
