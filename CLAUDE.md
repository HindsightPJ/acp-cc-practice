# ACP 云计算练习 — Agent 规则手册

> 本文档是 AI 在该项目中的首条上下文。只放「下次写代码时没看到就会犯错」的规则，历史叙事进 git log。

## 1. 项目身份

- **名称**：ACP 云计算练习（`acp-cc-practice`）
- **形态**：Python + Tkinter 桌面题库练习应用
- **受众**：备考阿里云 ACP 云计算认证的个人用户
- **分发**：源码 + GitHub Release 单文件 EXE
- **授权**：机器绑定注册码，保护加密题库版权

## 2. 关键约定

### 2.1 技术栈与版本

- Python 3.10+
- 类型注解统一使用 PEP 604：`str | None`（禁止回到 `Optional[str]`）
- Tkinter 构建 UI，不使用外部 UI 框架
- 依赖单一来源：`pyproject.toml`；不使用 `requirements.txt` / `requirements-dev.txt`

### 2.2 代码风格

- 4 空格缩进
- 函数/方法写 docstring（中文）
- 模块级函数优先于静态方法
- 延迟导入 `cryptography` 相关模块（保持与原有风格一致）
- UI 父容器类型统一为 `tk.Misc`

### 2.3 测试纪律

- 每次修改一项 → 运行 `pytest` 验证无回归
- 强制质量门：
  ```powershell
  mypy --disallow-untyped-defs .
  ruff check .
  pytest
  ```
- GUI 测试标记 `@pytest.mark.gui`，CI 默认跳过
- 非 GUI 测试应在 10 秒内完成

### 2.4 数据与授权红线

- **`.env`**、**`issued_licenses.json`**、**`progress.json`**、**`license.dat`**、**`app.log`** 禁止入库
- `data/questions.enc` 等 3 个文件虽在 `.gitignore` 中，但被显式放行，可入库
- 注册码与机器绑定；BIOS 序列号是机器码第 4 维度
- 主密钥 K 永不离开作者机器

## 3. 架构速查

```
main.py
├── license/verifier.py      # 注册码验证 + 题库解密
├── data_manager.py          # 题库加载 + 进度持久化
├── quiz_engine.py           # 答题/统计/考试流程
├── app_state.py             # 错题本、收藏、考试历史、进度持久化
└── ui/
    ├── main_window.py       # 主窗口 + 模式路由
    ├── header.py            # 顶部标题栏
    ├── sidebar.py           # 侧栏导航 + 就绪度环 + 错题指示器
    ├── base_mode.py         # 模式基类（键盘分发模板方法）
    ├── practice_mode.py     # 练习模式
    ├── practice_panel.py    # 可复用练习视图
    ├── practice_session.py  # 练习会话逻辑
    ├── exam_mode.py         # 考试模式控制器
    ├── exam_panel.py        # 考试视图层
    ├── exam_session.py      # 考试会话模型
    ├── review_mode.py       # 背题模式
    ├── wrong_book.py        # 错题本
    ├── option_row.py        # 统一选项行组件
    ├── question_detail_card.py # 题目详情卡片
    ├── mode_toolbar.py      # 模式工具栏
    ├── license_dialog.py    # 授权输入对话框
    ├── base_dialog.py       # 对话框基类（模态/居中/关闭）
    └── theme.py             # 设计 Token
```

## 4. 深入文档指针

| 主题 | 文件 |
|---|---|
| 架构、授权协议、数据流 | [docs/architecture.md](docs/architecture.md) |
| 测试覆盖率与改进建议 | [docs/test_coverage_report.md](docs/test_coverage_report.md) |
| 技术债清单 | [TECH_DEBT.md](TECH_DEBT.md) |
| 开发环境、提交规范 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 安装与使用 | [README.md](README.md) |

## 5. 常见命令

```powershell
# 开发安装
pip install -e ".[dev]"

# 启动
python main.py

# 质量门
mypy --disallow-untyped-defs .
ruff check .
pytest

# 打包
pyinstaller acp-cc-practice.spec

# 发布（推送 v* tag 后由 GitHub Actions 自动构建并签名上传）
git tag -a v1.0.1 -m "release v1.0.1"
git push origin v1.0.1
```

## 6. 修改前必查

- [ ] 是否与现有 UI 组件（`PracticePanel`、`QuestionDetailCard`、`OptionRow`、`ModeToolbar`）重复？
- [ ] 是否新增未类型注解的函数/方法？
- [ ] 是否直接访问 `QuizEngine` 内部属性？（应走显式接口）
- [ ] 进度/错题保存是否使用 `AppState.save_safe()` 并提示失败？
- [ ] UI 层新增的魔法数字/字符串是否已加入 [`ui/constants.py`](ui/constants.py)？
- [ ] 取消 `after` 回调是否使用 `_cancel_after_job(job_id)`（统一 cancel + remove，禁止手动 `after_cancel` 后忘记 `discard`）？
- [ ] 新增 `messagebox.*` 调用是否传了 `parent=self`？
- [ ] 是否更新了 `TECH_DEBT.md` 对应条目？
