import math
import tkinter as tk
from tkinter import ttk

from .theme import (
    BG_PAGE, BG_CARD, BG_INPUT, BG_HOVER, BG_SELECT,
    BORDER, BORDER_LIGHT,
    INK, INK_SOFT, INK_TEXT, INK_TEXT_MUTED, INK_DIVIDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_PLACEHOLDER,
    ACCENT, ACCENT_HOVER, ACCENT_LIGHT, ACCENT_BORDER,
    GREEN, GREEN_BG, GREEN_BORDER, GREEN_TEXT,
    RED, RED_BG, RED_BORDER, RED_TEXT,
    YELLOW, YELLOW_BG, YELLOW_BORDER, YELLOW_TEXT,
    PURPLE, PURPLE_BG, PURPLE_BORDER, PURPLE_TEXT,
    SELECTED_BG, SELECTED_TEXT,
    CORRECT_BG, CORRECT_TEXT, CORRECT_HINT_BG, CORRECT_HINT_TEXT,
    WRONG_BG, WRONG_TEXT,
    BTN_PRIMARY, BTN_PRIMARY_HOVER, BTN_PRIMARY_ACTIVE,
    BTN_NORMAL, BTN_NORMAL_FG, BTN_NORMAL_HOVER, BTN_NORMAL_ACTIVE,
    BTN_DISABLED, BTN_DISABLED_FG,
    TAB_ACTIVE_FG, TAB_ACTIVE_BORDER, TAB_INACTIVE_FG,
    font_ui, font_ui_semibold, font_mono, font_display,
)
from .practice_mode import PracticeMode
from .exam_mode import ExamMode
from .review_mode import ReviewMode
from .wrong_book import WrongBook
from license import LicenseStatus, LicenseError
from license.verifier import verify, LicenseVerifier


SIDEBAR_WIDTH = 200
RING_SIZE = 88
RING_THICKNESS = 6


class MasteryRing(tk.Canvas):
    """就绪度环：把「练习覆盖率 × 正确率」合成为单一指标。

    这是页面的 signature 元素——把用户真正关心的「我离考试还差多远」
    做成一眼可见的弧线，避免堆砌「已练 / 正确率 / 连击」四个数字。
    """

    def __init__(self, parent, size=RING_SIZE, thickness=RING_THICKNESS):
        super().__init__(parent, width=size, height=size,
                         bg=INK, highlightthickness=0, bd=0)
        self._size = size
        self._thickness = thickness
        self._mastery = 0.0  # 0.0 ~ 1.0
        self._draw()

    def set_mastery(self, mastery: float) -> None:
        """mastery: 0.0 ~ 1.0。负值或 NaN 视作 0。"""
        try:
            m = float(mastery)
        except (TypeError, ValueError):
            m = 0.0
        if math.isnan(m) or math.isinf(m):
            m = 0.0
        self._mastery = max(0.0, min(1.0, m))
        self._draw()

    def _draw(self) -> None:
        self.delete('all')
        size = self._size
        thickness = self._thickness
        pad = thickness  # 留出描边空间
        bbox = (pad, pad, size - pad, size - pad)

        # 背景环
        self.create_arc(bbox, outline=INK_DIVIDER, width=thickness,
                        style='arc', start=90, extent=360)

        # 进度弧（从 12 点钟方向顺时针）
        extent = -360 * self._mastery  # Tkinter arc extent 负值=顺时针
        if self._mastery > 0:
            self.create_arc(bbox, outline=ACCENT, width=thickness,
                            style='arc', start=90, extent=extent)

        # 中心百分比
        pct = int(round(self._mastery * 100))
        self.create_text(size // 2, size // 2 - 6,
                         text=f"{pct}%",
                         fill=INK_TEXT, font=font_display(18, True))
        self.create_text(size // 2, size // 2 + 14,
                         text="就绪度",
                         fill=INK_TEXT_MUTED, font=font_ui(9))


_LICENSE_ERROR_MESSAGES = {
    None: "授权失败，请检查注册码。",
    'invalid_signature': "注册码无效，请联系作者。",
    'wrong_machine': "注册码不属于本机，请确认机器码后重新申请。",
    'corrupt_questions': "题库密文损坏，请联系作者。",
    'corrupt_license': "注册码文件损坏。",
}


def _get_license_error_message(err) -> str:
    """根据 LicenseError 枚举返回用户可读消息（TD-11: 从 _show_license_dialog 抽取）。"""
    err_key = err.value if err else None
    return _LICENSE_ERROR_MESSAGES.get(err_key, "授权失败。")


def _verify_and_save_license(code: str, license_dir: str):
    """验证注册码并持久化（TD-11: 从 _show_license_dialog 抽取）。

    Args:
        code: 用户输入的注册码
        license_dir: license.dat 保存目录

    Returns:
        (success, message, should_close_dialog)
    """
    status, k, err = verify(code)
    if status == LicenseStatus.AUTHORIZED and k:
        verifier = LicenseVerifier(data_dir=license_dir)
        if verifier.save_license(code):
            return (True, "授权成功！请重启程序加载完整题库。", True)
        return (False, "注册码验证成功，但保存到本地失败。\n请检查程序目录写入权限。", False)
    return (False, _get_license_error_message(err), False)


class MainWindow(tk.Tk):
    def __init__(self, questions, data_manager, license_status=None, meta=None,
                 license_dir=None):
        super().__init__()

        self.title("ACP 云计算练习")
        self.geometry("1200x760")
        self.minsize(1000, 640)

        self.questions = questions
        self.data_manager = data_manager
        self.progress = data_manager.load_progress()
        self.license_status = license_status
        self.meta = meta or {}
        # license.dat 持久化目录：打包后必须写到 exe 同级 data/（非 _MEIPASS 临时目录）
        # 若未传入，fallback 到 data_manager.data_dir（开发模式可用）
        self.license_dir = license_dir or data_manager.data_dir

        self.current_frame = None
        self._active_nav = 'practice'
        self._nav_refs = {}

        self.configure_ui()
        self.create_widgets()
        self.show_practice_mode()
        self._refresh_mastery()

    def configure_ui(self):
        self.configure(bg=BG_PAGE)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=BG_PAGE)
        style.configure('TSeparator', background=BORDER)

    # -------------------------------------------------------------- 布局
    def create_widgets(self):
        # 整体：左侧栏 + 右内容区
        body = tk.Frame(self, bg=BG_PAGE)
        body.pack(fill=tk.BOTH, expand=True)

        sidebar = tk.Frame(body, bg=INK, width=SIDEBAR_WIDTH)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        content_wrapper = tk.Frame(body, bg=BG_PAGE)
        content_wrapper.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 顶部细 header（模式名 + 全局统计）
        header = tk.Frame(content_wrapper, bg=BG_CARD, height=56)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        self._build_header(header)

        self.content_area = tk.Frame(content_wrapper, bg=BG_PAGE)
        self.content_area.pack(fill=tk.BOTH, expand=True, padx=24, pady=16)

    def _build_sidebar(self, parent):
        # 品牌
        brand = tk.Frame(parent, bg=INK)
        brand.pack(fill=tk.X, padx=20, pady=(20, 16))

        tk.Label(brand, text="ACP",
                 font=font_display(20, True),
                 fg=ACCENT, bg=INK).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(brand, text="云计算练习",
                 font=font_ui(11),
                 fg=INK_TEXT_MUTED, bg=INK).pack(side=tk.LEFT, pady=(4, 0))

        # 分隔
        tk.Frame(parent, bg=INK_DIVIDER, height=1).pack(fill=tk.X, padx=20)

        # 导航
        nav_container = tk.Frame(parent, bg=INK)
        nav_container.pack(fill=tk.X, padx=12, pady=(12, 0))

        nav_defs = [
            ('practice', '练习', self.show_practice_mode),
            ('exam', '考试', self.show_exam_mode),
            ('review', '背题', self.show_review_mode),
            ('wrong', '错题本', self.show_wrong_book),
        ]

        for tab_id, tab_text, command in nav_defs:
            self._build_nav_item(nav_container, tab_id, tab_text, command)

        # 弹性空间，把就绪度环推到底部
        spacer = tk.Frame(parent, bg=INK)
        spacer.pack(fill=tk.BOTH, expand=True)

        # 就绪度环（signature）
        ring_wrap = tk.Frame(parent, bg=INK)
        ring_wrap.pack(pady=(0, 8))

        self.mastery_ring = MasteryRing(ring_wrap)
        self.mastery_ring.pack()

        tk.Label(parent, text="练习覆盖 × 正确率",
                 font=font_ui(9),
                 fg=INK_TEXT_MUTED, bg=INK).pack(pady=(0, 4))

        # 错题数小指示
        self.wrong_indicator = tk.Label(
            parent, text="",
            font=font_ui(10),
            fg=INK_TEXT_MUTED, bg=INK)
        self.wrong_indicator.pack(pady=(0, 20))

    def _build_nav_item(self, parent, tab_id, tab_text, command):
        item = tk.Frame(parent, bg=INK, cursor='hand2')
        item.pack(fill=tk.X, pady=2)

        indicator = tk.Frame(item, bg=INK, width=3)
        indicator.pack(side=tk.LEFT, fill=tk.Y)

        label = tk.Label(item, text=tab_text,
                         font=font_ui(12),
                         fg=INK_TEXT_MUTED, bg=INK,
                         cursor='hand2', anchor='w',
                         padx=14, pady=10)
        label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._nav_refs[tab_id] = {
            'frame': item,
            'label': label,
            'indicator': indicator,
            'command': command,
        }

        for w in [item, label]:
            w.bind('<Button-1>', lambda e, t=tab_id: self._on_nav_click(t))
            w.bind('<Enter>', lambda e, t=tab_id: self._on_nav_hover(t))
            w.bind('<Leave>', lambda e, t=tab_id: self._on_nav_leave(t))

    def _build_header(self, parent):
        inner = tk.Frame(parent, bg=BG_CARD)
        inner.pack(fill=tk.BOTH, expand=True, padx=24)

        self.mode_title = tk.Label(
            inner, text="练习",
            font=font_display(16, True),
            fg=TEXT_PRIMARY, bg=BG_CARD)
        self.mode_title.pack(side=tk.LEFT, pady=12)

        # 授权状态 + 题库总量显示
        total = self.meta.get('total', len(self.questions))
        if self.license_status == LicenseStatus.AUTHORIZED:
            status_text = f"题库共 {total} 题 · 已授权"
        else:
            status_text = f"题库共 {total} 题 · 试用版（前 {len(self.questions)} 题）"
        self.license_status_label = tk.Label(
            inner, text=status_text,
            font=font_ui(10),
            fg=TEXT_MUTED, bg=BG_CARD)
        self.license_status_label.pack(side=tk.LEFT, padx=12, pady=12)

        self._stats_label = tk.Label(
            inner, text="",
            font=font_ui(10),
            fg=TEXT_MUTED, bg=BG_CARD)
        self._stats_label.pack(side=tk.RIGHT, pady=12)

        # 「输入注册码」按钮（仅试用模式显示）
        if self.license_status != LicenseStatus.AUTHORIZED:
            self.activate_btn = tk.Button(
                inner, text="输入注册码",
                command=self._show_license_dialog,
                font=font_ui(10),
                bg=ACCENT, fg='white',
                relief='flat',
                padx=12, pady=4,
                cursor='hand2',
                activebackground=ACCENT_HOVER,
                activeforeground='white')
            self.activate_btn.pack(side=tk.RIGHT, padx=8, pady=12)

    def _show_license_dialog(self):
        """弹出注册码输入对话框（TD-11: 已拆分纯逻辑到模块级函数）。"""
        from license.fingerprint import get_machine_code_or_none
        from tkinter import messagebox

        machine_code = get_machine_code_or_none()
        if machine_code is None:
            messagebox.showerror("错误", "无法读取本机机器码，授权仅支持 Windows。")
            return

        dialog = tk.Toplevel(self)
        dialog.title("输入注册码")
        dialog.geometry("500x420")
        dialog.transient(self)
        dialog.grab_set()

        # 机器码显示
        tk.Label(dialog, text="本机机器码：",
                 font=font_ui_semibold(11),
                 fg=TEXT_PRIMARY, bg=BG_PAGE).pack(anchor='w', padx=15, pady=(15, 5))
        code_entry = tk.Text(dialog, height=3, wrap='char',
                             font=font_mono(9),
                             bg=BG_INPUT, fg=TEXT_PRIMARY,
                             relief='flat', bd=0,
                             highlightbackground=BORDER, highlightthickness=1)
        code_entry.insert('1.0', machine_code)
        code_entry.config(state='disabled')
        code_entry.pack(fill='x', padx=15, pady=(0, 10))

        tk.Label(dialog, text="把此机器码发给作者，收到注册码后粘贴到下方：",
                 font=font_ui(9),
                 fg=TEXT_MUTED, bg=BG_PAGE).pack(anchor='w', padx=15)

        # 注册码输入框
        license_entry = tk.Text(dialog, height=8, wrap='char',
                                font=font_mono(9),
                                bg=BG_INPUT, fg=TEXT_PRIMARY,
                                relief='flat', bd=0,
                                highlightbackground=BORDER, highlightthickness=1)
        license_entry.pack(fill='both', expand=True, padx=15, pady=10)

        def on_verify():
            code = license_entry.get('1.0', 'end').strip()
            if not code:
                messagebox.showwarning("提示", "请输入注册码", parent=dialog)
                return
            # TD-11: 验证 + 保存逻辑抽取到模块级 _verify_and_save_license
            success, message, should_close = _verify_and_save_license(
                code, self.license_dir)
            if success:
                messagebox.showinfo("成功", message, parent=dialog)
            else:
                messagebox.showerror("失败", message, parent=dialog)
            if should_close:
                dialog.destroy()

        btn_frame = tk.Frame(dialog, bg=BG_PAGE)
        btn_frame.pack(fill='x', padx=15, pady=(0, 15))
        tk.Button(btn_frame, text="验证", command=on_verify,
                  bg=ACCENT, fg='white', relief='flat', padx=20,
                  cursor='hand2',
                  activebackground=ACCENT_HOVER, activeforeground='white').pack(side='right')
        tk.Button(btn_frame, text="取消", command=dialog.destroy,
                  relief='flat', padx=20,
                  bg=BTN_NORMAL, fg=BTN_NORMAL_FG,
                  cursor='hand2').pack(side='right', padx=5)

    # -------------------------------------------------------------- 交互
    def _on_nav_click(self, tab_id):
        ref = self._nav_refs.get(tab_id)
        if ref:
            ref['command']()
            self._update_nav_highlight()
            self._update_stats_display()

    def _on_nav_hover(self, tab_id):
        if tab_id == self._active_nav:
            return
        ref = self._nav_refs.get(tab_id)
        if ref:
            ref['label'].configure(fg=INK_TEXT)

    def _on_nav_leave(self, tab_id):
        if tab_id == self._active_nav:
            return
        ref = self._nav_refs.get(tab_id)
        if ref:
            ref['label'].configure(fg=INK_TEXT_MUTED)

    def _update_nav_highlight(self):
        for tab_id, ref in self._nav_refs.items():
            if tab_id == self._active_nav:
                ref['label'].configure(fg=ACCENT, font=font_ui_semibold(12))
                ref['indicator'].configure(bg=ACCENT)
            else:
                ref['label'].configure(fg=INK_TEXT_MUTED, font=font_ui(12))
                ref['indicator'].configure(bg=INK)

    def _update_stats_display(self):
        practice_stats = self.progress.get('practice_stats', {})
        correct = practice_stats.get('correct', 0)
        total_practiced = practice_stats.get('total', 0)
        accuracy = (correct / total_practiced * 100) if total_practiced > 0 else 0
        wrong_count = len(self.progress.get('wrong_questions', []))
        self._stats_label.configure(
            text=f"已练 {total_practiced} 题  ·  正确率 {accuracy:.0f}%  ·  错题 {wrong_count}")

    def _refresh_mastery(self):
        """就绪度 = 练习覆盖率 × 正确率。

        覆盖率 = 已练习题数 / 题库总数；
        正确率 = 练习正确数 / 练习总数。
        两个值都在 [0, 1]，乘积也在 [0, 1]。
        """
        total_pool = len(self.questions) if self.questions else 0
        practice_stats = self.progress.get('practice_stats', {})
        total_practiced = practice_stats.get('total', 0)
        correct = practice_stats.get('correct', 0)

        coverage = (total_practiced / total_pool) if total_pool > 0 else 0
        accuracy = (correct / total_practiced) if total_practiced > 0 else 0
        # 覆盖率超过 1.0 时（重复刷题）按 100% 计
        coverage = min(coverage, 1.0)
        mastery = coverage * accuracy

        self.mastery_ring.set_mastery(mastery)

        wrong_count = len(self.progress.get('wrong_questions', []))
        self.wrong_indicator.configure(
            text=f"错题本 {wrong_count} 题" if wrong_count else "错题本为空",
            fg=RED if wrong_count > 0 else INK_TEXT_MUTED)

        self._update_stats_display()

    # -------------------------------------------------------------- 模式切换
    def clear_content(self):
        if self.current_frame:
            self.current_frame.destroy()
            self.current_frame = None

    def _switch_to(self, mode_title, factory):
        self.clear_content()
        self._active_nav = mode_title
        self._update_nav_highlight()
        self.current_frame = factory()
        self.current_frame.pack(fill=tk.BOTH, expand=True)
        # 切 tab 后刷新就绪度环（进度可能因上次练习更新）
        self._refresh_mastery()

    def show_practice_mode(self):
        self.mode_title.configure(text="练习")
        self._switch_to('practice', lambda: PracticeMode(
            self.content_area, self.questions, self.data_manager, self.progress))

    def show_exam_mode(self):
        self.mode_title.configure(text="考试")
        self._switch_to('exam', lambda: ExamMode(
            self.content_area, self.questions, self.data_manager, self.progress))

    def show_review_mode(self):
        self.mode_title.configure(text="背题")
        self._switch_to('review', lambda: ReviewMode(
            self.content_area, self.questions, self.data_manager, self.progress))

    def show_wrong_book(self):
        self.mode_title.configure(text="错题本")
        self._switch_to('wrong', lambda: WrongBook(
            self.content_area, self.questions, self.data_manager, self.progress))
