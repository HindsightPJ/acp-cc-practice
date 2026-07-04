import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Callable

from .theme import theme

from .practice_mode import PracticeMode
from .exam_mode import ExamMode
from .review_mode import ReviewMode
from .wrong_book import WrongBook
from .sidebar import Sidebar
from .license_dialog import LicenseDialog
from .header import Header
from app_state import AppState
from data_manager import DataManager
from license import LicenseStatus
from models import Question


class MainWindow(tk.Tk):
    def __init__(
        self,
        questions: list[Question],
        data_manager: DataManager,
        license_status: LicenseStatus | None = None,
        meta: dict[str, Any] | None = None,
        license_dir: str | None = None,
    ) -> None:
        super().__init__()

        self.title("ACP 云计算练习")
        self.geometry("1200x760")
        self.minsize(1000, 640)

        self.questions: list[Question] = questions
        self.data_manager = data_manager
        # TD-30: 用 AppState 封装进度，UI 不再直接操作原始 dict
        self.app_state = AppState(data_manager, data_manager.load_progress())
        self.license_status = license_status
        self.meta = meta or {}
        # license.dat 持久化目录：打包后必须写到 exe 同级 data/（非 _MEIPASS 临时目录）
        # 若未传入，fallback 到 data_manager.data_dir（开发模式可用）
        self.license_dir = license_dir or data_manager.data_dir

        self.current_frame: tk.Widget | None = None
        self._active_nav = "practice"
        self.sidebar: Sidebar | None = None

        self.configure_ui()
        self.create_widgets()
        self.show_practice_mode()
        self._refresh_mastery()

    def configure_ui(self) -> None:
        self.configure(bg=theme.BG_PAGE)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=theme.BG_PAGE)
        style.configure("TSeparator", background=theme.BORDER)

    # -------------------------------------------------------------- 布局
    def create_widgets(self) -> None:
        # 整体：左侧栏 + 右内容区
        body = tk.Frame(self, bg=theme.BG_PAGE)
        body.pack(fill=tk.BOTH, expand=True)

        nav_defs: list[tuple[str, str, Callable[[], None] | None]] = [
            ("practice", "练习", self.show_practice_mode),
            ("exam", "考试", self.show_exam_mode),
            ("review", "背题", self.show_review_mode),
            ("wrong", "错题本", self.show_wrong_book),
        ]
        self.sidebar = Sidebar(
            body,
            nav_defs,
            on_nav_clicked=self._on_nav_clicked,
        )
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

        content_wrapper = tk.Frame(body, bg=theme.BG_PAGE)
        content_wrapper.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 顶部细 header（模式名 + 全局统计）
        total = self.meta.get("total", len(self.questions))
        self.header = Header(
            content_wrapper,
            license_status=self.license_status,
            total_count=total,
            trial_count=len(self.questions),
            on_activate_click=self._show_license_dialog,
            mode_title="练习",
        )
        self.header.pack(fill=tk.X, side=tk.TOP)
        # 保持对内部标签的引用，兼容现有测试与外部访问
        self.mode_title = self.header.mode_title
        self.license_status_label = self.header.license_status_label
        self._stats_label = self.header.stats_label

        self.content_area = tk.Frame(content_wrapper, bg=theme.BG_PAGE)
        self.content_area.pack(fill=tk.BOTH, expand=True, padx=24, pady=16)

    def _show_license_dialog(self) -> None:
        """弹出注册码输入对话框（逻辑已拆分到 LicenseDialog）。"""
        dialog = LicenseDialog(self, self.license_dir)
        dialog.show()

    # -------------------------------------------------------------- 交互
    def _on_nav_clicked(self, tab_id: str) -> None:
        """Sidebar 导航点击后的外部回调：同步主窗口状态。"""
        self._active_nav = tab_id
        self._update_stats_display()

    def _update_nav_highlight(self) -> None:
        if self.sidebar is None:
            return
        self.sidebar.set_active_nav(self._active_nav)

    def _update_stats_display(self, wrong_count: int | None = None) -> None:
        practice_stats = self.app_state.get_practice_stats()
        correct = practice_stats.get("correct", 0)
        total_practiced = practice_stats.get("total", 0)
        accuracy = (correct / total_practiced * 100) if total_practiced > 0 else 0
        # P1-2: 调用方已计算 wrong_count 时直接复用，避免重复读取
        if wrong_count is None:
            wrong_count = self.app_state.wrong_count()
        self.header.update_stats(total_practiced, accuracy, wrong_count)

    def _refresh_mastery(self) -> None:
        """就绪度 = 练习覆盖率 × 正确率。

        覆盖率 = 已练习题数 / 题库总数；
        正确率 = 练习正确数 / 练习总数。
        两个值都在 [0, 1]，乘积也在 [0, 1]。
        """
        total_pool = len(self.questions) if self.questions else 0
        practice_stats = self.app_state.get_practice_stats()
        total_practiced = practice_stats.get("total", 0)
        correct = practice_stats.get("correct", 0)

        coverage = (total_practiced / total_pool) if total_pool > 0 else 0
        accuracy = (correct / total_practiced) if total_practiced > 0 else 0
        # 覆盖率超过 1.0 时（重复刷题）按 100% 计
        coverage = min(coverage, 1.0)
        mastery = coverage * accuracy

        wrong_count = self.app_state.wrong_count()
        if self.sidebar is not None:
            self.sidebar.set_mastery(mastery)
            self.sidebar.set_wrong_indicator(
                text=f"错题本 {wrong_count} 题" if wrong_count else "错题本为空",
                fg=theme.RED if wrong_count > 0 else theme.INK_TEXT_MUTED,
            )

        # P1-2: 传入已计算的 wrong_count，避免 _update_stats_display 重复读取
        self._update_stats_display(wrong_count)

    # -------------------------------------------------------------- 模式切换
    def clear_content(self) -> None:
        if self.current_frame:
            self.current_frame.destroy()
            self.current_frame = None

    def _is_exam_in_progress(self) -> bool:
        """检查当前是否在考试中（用于切 tab 前确认，避免丢失考试状态）。"""
        if not isinstance(self.current_frame, ExamMode):
            return False
        # P0-3: timer_running 为 True 表示考试进行中（开始按钮已禁用、计时器在跑）
        return bool(self.current_frame.timer_running)

    def _switch_to(self, mode_title: str, factory: Callable[[], tk.Widget]) -> None:
        # P0-3: 考试进行中切 tab 会丢失 answers/marked/时间，先确认
        if self._is_exam_in_progress():
            if not messagebox.askyesno(
                "确认切换",
                "考试正在进行中，切换模式将放弃本次考试。\n\n确定要切换吗？",
                parent=self,
            ):
                # 用户取消：恢复 sidebar 高亮到当前 tab（_handle_nav_click 已切到新 tab）
                if self.sidebar is not None:
                    self.sidebar.set_active_nav(self._active_nav)
                return
        self.clear_content()
        self._active_nav = mode_title
        self._update_nav_highlight()
        new_frame = factory()
        self.current_frame = new_frame
        new_frame.pack(fill=tk.BOTH, expand=True)
        # 切 tab 后刷新就绪度环（进度可能因上次练习更新）
        self._refresh_mastery()

    def show_practice_mode(self) -> None:
        self.header.set_mode_title("练习")
        self._switch_to(
            "practice",
            lambda: PracticeMode(
                self.content_area, self.questions, self.data_manager, self.app_state
            ),
        )

    def show_exam_mode(self) -> None:
        self.header.set_mode_title("考试")
        self._switch_to(
            "exam",
            lambda: ExamMode(self.content_area, self.questions, self.data_manager, self.app_state),
        )

    def show_review_mode(self) -> None:
        self.header.set_mode_title("背题")
        self._switch_to(
            "review",
            lambda: ReviewMode(
                self.content_area, self.questions, self.data_manager, self.app_state
            ),
        )

    def show_wrong_book(self) -> None:
        self.header.set_mode_title("错题本")
        self._switch_to(
            "wrong",
            lambda: WrongBook(self.content_area, self.questions, self.data_manager, self.app_state),
        )
