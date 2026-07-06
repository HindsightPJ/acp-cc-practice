# 贡献指南

感谢参与 `acp-cc-practice` 项目！本文档帮助你快速上手开发。

## 开发环境

### 依赖安装

```powershell
pip install -e ".[dev]"
```

包含运行依赖（`python-docx`、`cryptography`）+ 开发依赖（`pytest`、`pytest-cov`、`mypy`、`ruff`）。

### 运行测试

```powershell
# 非 GUI 全量测试（默认）
pytest

# 带覆盖率报告
pytest --cov --cov-report=term-missing

# GUI 测试（需要 display）
pytest -m gui

# 单个测试文件
pytest tests/unit/test_quiz_engine.py -v
```

当前非 GUI 测试数：251 项（总计 316 项，含 GUI 测试）。

## 项目结构

```
acp-cc-practice/
├── main.py                    # 入口
├── quiz_engine.py             # 答题引擎（业务层）
├── data_manager.py            # 题库加载/进度持久化
├── app_state.py               # 错题本、收藏、考试历史、进度持久化
├── env_utils.py               # .env 解析
├── pyproject.toml             # 项目元数据 + 依赖 + 工具配置
├── acp-cc-practice.spec       # PyInstaller 打包配置
├── license/                   # 授权层
│   ├── __init__.py
│   ├── fingerprint.py         # 机器指纹
│   ├── verifier.py            # 注册码验证
│   ├── crypto_utils.py        # PBKDF2 派生
│   └── public_key.py          # Ed25519 公钥
├── author_tools/              # 作者工具
│   ├── keygen.py              # 生成密钥对
│   ├── encrypt_questions.py   # 加密题库
│   └── generate_license.py    # 签发注册码
├── ui/                        # UI 层
│   ├── main_window.py         # 主窗口
│   ├── header.py              # 顶部标题栏
│   ├── sidebar.py             # 侧栏导航
│   ├── base_mode.py           # 模式基类
│   ├── base_dialog.py         # 对话框基类
│   ├── constants.py           # UI 层共享常量
│   ├── practice_mode.py       # 练习模式
│   ├── practice_panel.py      # 可复用练习视图
│   ├── practice_session.py    # 练习会话逻辑
│   ├── exam_mode.py           # 考试模式
│   ├── exam_panel.py          # 考试视图层
│   ├── exam_session.py        # 考试会话模型
│   ├── review_mode.py         # 背题模式
│   ├── wrong_book.py          # 错题本
│   ├── option_row.py          # 统一选项行
│   ├── question_detail_card.py # 题目详情卡片
│   ├── mode_toolbar.py        # 模式工具栏
│   ├── license_dialog.py      # 授权输入对话框
│   └── theme.py               # 设计 Token
├── tests/                     # 测试
│   ├── unit/                  # 单元测试
│   └── integration/           # 集成测试
├── data/                      # 题库数据
├── README.md                  # 安装与使用
├── TECH_DEBT.md               # 技术债追踪
└── docs/
    ├── architecture.md        # 架构与授权协议
    └── test_coverage_report.md # 覆盖率报告
```

## 代码风格

- Python 3.10+，类型注解统一使用 PEP 604：`str | None`
- 4 空格缩进
- 函数/方法添加 docstring（中文）
- 模块级函数优先于静态方法
- 延迟导入 `cryptography` 相关模块（保持与原有风格一致）
- UI 父容器类型统一为 `tk.Misc`

## 提交规范

```
<type>: <description>

- <detail 1>
- <detail 2>
```

类型：`feat`（新功能）/ `fix`（修复）/ `refactor`（重构）/ `test`（测试）/ `docs`（文档）/ `TD-XX`（技术债修复）

## 技术债

技术债记录在 [TECH_DEBT.md](TECH_DEBT.md)，按 P0-P6 分级。修复时：

1. 每次只做一项修改
2. 运行 `mypy --disallow-untyped-defs .`、`ruff check .`、`pytest` 验证无回归
3. 更新 `TECH_DEBT.md` 进度表
4. 提交时在 message 中标注 `TD-XX`

## CI

GitHub Actions 在 push/PR to main 时自动运行：

- `ruff check .`
- `mypy --disallow-untyped-defs .`
- `pytest tests/ -q --tb=short -o addopts="" -m "not gui"`

注意：
- CI 使用 Ubuntu runner，GUI 测试通过 `-m "not gui"` 跳过
- Windows-only 模块（如 `winreg`）的测试需加 `@pytest.mark.skipif(sys.platform != "win32")`

配置文件：[.github/workflows/ci.yml](.github/workflows/ci.yml)
