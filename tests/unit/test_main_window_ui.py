"""完整 UI 实例化冒烟测试（TD-19）。

在 headless 环境（无 display）下自动跳过；Windows/有 display 环境可运行。
gui 标记的测试默认被 pytest 跳过，需单独运行：pytest -m gui
"""
import pytest


def _tk_display_available():
    """检测当前环境是否可以实例化 tkinter.Tk。"""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.destroy()
        return True
    except tk.TclError:
        return False


HAS_DISPLAY = _tk_display_available()
pytestmark = [
    pytest.mark.skipif(not HAS_DISPLAY, reason="No GUI display available"),
    pytest.mark.gui,
]


SAMPLE_QUESTIONS = [
    {
        'number': 1,
        'type': 'single',
        'content': '测试题目',
        'options': [
            {'letter': 'A', 'text': '选项A'},
            {'letter': 'B', 'text': '选项B'},
        ],
        'answer': 'A',
        'explanation': '解析',
    }
]


class FakeDataManager:
    """最小化的 DataManager 替代品，仅用于 UI 实例化测试。"""

    data_dir = '/tmp/acp-test-data'

    def load_progress(self):
        return {
            'practice_stats': {'correct': 0, 'total': 0},
            'wrong_questions': [],
        }

    def save_progress(self, progress):
        pass


@pytest.fixture(scope='module')
def root():
    """模块级共享 Tk 实例，供非 MainWindow 的 UI 组件测试复用。"""
    import tkinter as tk
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def clean_root(root):
    """每次测试前清理 root 下的子组件，避免状态泄漏。"""
    import tkinter as tk
    for child in list(root.winfo_children()):
        child.destroy()
    # 清理可能遗留的全局绑定（子组件测试里不会绑，但防御性保留）
    try:
        root.unbind_all('<Button-1>')
    except tk.TclError:
        pass
    root.update_idletasks()
    yield root
    for child in list(root.winfo_children()):
        child.destroy()
    root.update_idletasks()


@pytest.fixture
def fake_data_manager():
    return FakeDataManager()


def test_main_window_can_instantiate(fake_data_manager):
    """MainWindow 可完整实例化并包含 Sidebar。"""
    import tkinter as tk
    from ui.main_window import MainWindow

    app = MainWindow(
        SAMPLE_QUESTIONS,
        fake_data_manager,
        license_status=None,
        meta={'total': len(SAMPLE_QUESTIONS)},
    )
    assert isinstance(app, tk.Tk)
    assert app.title() == "ACP 云计算练习"
    assert app.sidebar is not None
    app.destroy()


def test_main_window_mode_switching(fake_data_manager):
    """MainWindow 可在四种模式之间切换而不抛出异常。"""
    from ui.main_window import MainWindow

    app = MainWindow(
        SAMPLE_QUESTIONS,
        fake_data_manager,
        license_status=None,
        meta={'total': len(SAMPLE_QUESTIONS)},
    )

    app.show_exam_mode()
    assert app.mode_title.cget('text') == '考试'
    assert app._active_nav == 'exam'

    app.show_review_mode()
    assert app.mode_title.cget('text') == '背题'
    assert app._active_nav == 'review'

    app.show_wrong_book()
    assert app.mode_title.cget('text') == '错题本'
    assert app._active_nav == 'wrong'

    app.show_practice_mode()
    assert app.mode_title.cget('text') == '练习'
    assert app._active_nav == 'practice'

    app.destroy()


def test_sidebar_can_instantiate(clean_root):
    """Sidebar 可独立实例化并设置活动导航项。"""
    from ui.sidebar import Sidebar

    calls = []
    nav_defs = [
        ('practice', '练习', lambda: calls.append('practice')),
        ('exam', '考试', lambda: calls.append('exam')),
    ]
    sidebar = Sidebar(clean_root, nav_defs, on_nav_clicked=lambda t: calls.append(t))
    sidebar.pack()

    assert sidebar.winfo_exists()
    sidebar.set_active_nav('exam')
    assert sidebar._active_nav == 'exam'

    sidebar.destroy()


def test_license_dialog_can_instantiate(clean_root):
    """LicenseDialog 可实例化（不实际显示对话框）。"""
    from ui.license_dialog import LicenseDialog

    dialog = LicenseDialog(clean_root, '/tmp/test-license-dir')
    assert dialog.parent is clean_root
    assert dialog.license_dir == '/tmp/test-license-dir'
    assert dialog.verify_and_save is not None


def test_header_can_instantiate_and_update(clean_root):
    """Header 组件可独立实例化并更新标题与统计。"""
    from ui.header import Header

    header = Header(clean_root, total_count=100, trial_count=20, mode_title='考试')
    header.pack()

    assert header.winfo_exists()
    assert header.mode_title.cget('text') == '考试'
    assert '题库共 100 题' in header.license_status_label.cget('text')

    header.set_mode_title('练习')
    assert header.mode_title.cget('text') == '练习'

    header.update_stats(practiced=10, accuracy=80.0, wrong_count=2)
    stats_text = header.stats_label.cget('text')
    assert '已练 10 题' in stats_text
    assert '正确率 80%' in stats_text
    assert '错题 2' in stats_text

    header.destroy()


def test_header_activate_click_callback(clean_root):
    """Header 的「输入注册码」按钮点击触发外部回调。"""
    from ui.header import Header

    calls = []
    header = Header(clean_root, total_count=100, trial_count=20,
                    on_activate_click=lambda: calls.append('activate'))
    header.pack()

    assert header.activate_btn is not None
    header.activate_btn.invoke()
    assert calls == ['activate']

    header.destroy()


def test_mastery_ring_boundary_values(clean_root):
    """MasteryRing 对越界/异常值做安全截断。"""
    from ui.mastery_ring import MasteryRing

    ring = MasteryRing(clean_root)
    ring.pack()

    ring.set_mastery(0.0)
    assert ring._mastery == 0.0

    ring.set_mastery(1.0)
    assert ring._mastery == 1.0

    ring.set_mastery(1.5)
    assert ring._mastery == 1.0

    ring.set_mastery(-0.5)
    assert ring._mastery == 0.0

    ring.set_mastery(float('nan'))
    assert ring._mastery == 0.0

    ring.set_mastery(float('inf'))
    assert ring._mastery == 0.0

    ring.set_mastery(None)
    assert ring._mastery == 0.0

    ring.set_mastery('invalid')
    assert ring._mastery == 0.0

    ring.destroy()


def test_sidebar_nav_click_triggers_callback(clean_root):
    """Sidebar 导航点击触发 command 与 on_nav_clicked 回调。"""
    from ui.sidebar import Sidebar

    commands = []
    clicks = []
    nav_defs = [
        ('practice', '练习', lambda: commands.append('practice_cmd')),
        ('exam', '考试', lambda: commands.append('exam_cmd')),
    ]
    sidebar = Sidebar(
        clean_root, nav_defs,
        on_nav_clicked=lambda t: clicks.append(t))
    sidebar.pack()

    # 直接调用内部处理函数模拟点击
    sidebar._handle_nav_click('exam')
    assert commands == ['exam_cmd']
    assert clicks == ['exam']
    assert sidebar._active_nav == 'exam'

    sidebar.destroy()


def test_sidebar_same_tab_click_does_not_rebuild(clean_root):
    """P2-24: 重复点击当前 tab 不应再次触发 command 和 on_nav_clicked。"""
    from ui.sidebar import Sidebar

    commands = []
    clicks = []
    nav_defs = [
        ('practice', '练习', lambda: commands.append('practice_cmd')),
        ('exam', '考试', lambda: commands.append('exam_cmd')),
    ]
    sidebar = Sidebar(
        clean_root, nav_defs,
        on_nav_clicked=lambda t: clicks.append(t))
    sidebar.pack()

    # 首次切到 exam
    sidebar._handle_nav_click('exam')
    assert commands == ['exam_cmd']
    assert clicks == ['exam']

    # 重复点击 exam：不应再触发回调或重建 mode
    sidebar._handle_nav_click('exam')
    assert commands == ['exam_cmd']
    assert clicks == ['exam']
    assert sidebar._active_nav == 'exam'

    sidebar.destroy()


def test_license_dialog_verify_callback(clean_root, monkeypatch):
    """LicenseDialog 验证按钮调用自定义回调并正确关闭对话框。"""
    import time
    from ui.license_dialog import LicenseDialog

    calls = []

    def fake_verify(code, license_dir, machine_code=None):
        calls.append((code, license_dir, machine_code))
        return (True, 'OK', True)

    # P2-6: mock messagebox 避免 _on_verify_done 弹窗阻塞测试
    monkeypatch.setattr('tkinter.messagebox.showinfo', lambda *a, **k: None)

    dialog = LicenseDialog(clean_root, '/tmp/test-license-dir',
                           verify_and_save=fake_verify)
    # P0-2: 模拟 show() 缓存 machine_code，_on_verify 会传入此值
    dialog._machine_code = 'test-machine-code'
    # 修复：原测试调用不存在的 _build_dialog，实际方法名是 _build_content
    dialog._create_dialog()
    dialog._build_content('machine-code')
    dialog._license_entry.insert('1.0', 'test-code')
    dialog._on_verify()

    # P2-6: 验证改为异步，轮询处理 after 回调直到 dialog 关闭（最多 2s）
    deadline = time.time() + 2.0
    while time.time() < deadline:
        clean_root.update()
        if dialog.dialog is None:
            break
        time.sleep(0.01)

    assert calls == [('test-code', '/tmp/test-license-dir', 'test-machine-code')]
    # 验证成功后对话框应已关闭
    assert dialog.dialog is None
