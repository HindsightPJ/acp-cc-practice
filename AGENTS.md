# AGENTS.md — ACP 云计算练习

阿里云 ACP 认证备考桌面应用（练习 / 考试 / 背题 / 错题本）。Python 3.10+ / PySide6 + QSS，
PyInstaller 单 exe 分发；题库为 Ed25519 离线授权 + 机器绑定加密，试用态仅加载固定的 20 题
明文试用库，完整题库密文在本地无法解密。

## 常用命令

```powershell
python main.py                                  # 开发运行
python -m pytest -m "gui or not gui" -q         # 全量测试（GUI 用例 offscreen 无头跑）
python -m ruff check .                          # lint
python -m ruff format --check .                 # 格式
python -m mypy --disallow-untyped-defs .        # 类型
pyinstaller acp-cc-practice.spec --noconfirm    # 打包
```

pre-commit 四钩子（ruff / ruff format / 硬编码密钥扫描 / 依赖精确锁定）提交时强制执行，不可绕过。

## 硬约束

- 版本单一来源：`pyproject.toml`；spec / README 不手写版本号
- 颜色 / 字体只允许存在于 `ui/theme.py`（`build_qss()` 全局样式表），控件代码禁止散写样式
- `quiz_engine.py` 保持纯逻辑（禁止 import PySide6），业务引擎可脱离 UI 测试
- 桌面 UI 锁定 PySide6 + QSS，禁 ttkbootstrap / tkinter 皮肤库；多主题由同一组语义 Token 生成
- 后台线程只 emit 信号，不碰控件；QTimer/线程在退出时 stop/wait 清理
- 敏感文件（.env、明文题库、author_tools/ 签发记录）永不入库，.gitignore 已覆盖，改规则前先想清楚

## 目录

- `main.py` — 入口：授权检查 → trial/full 题库加载 → 启动 UI
- `quiz_engine.py` / `app_state.py` / `data_manager.py` — 引擎 / 状态层 / 持久化（分层，UI 不碰原始 dict）
- `ui/` — 全部界面组件（theme.py 为唯一取色源）；`license/` — 授权校验（仓库内只含公钥）
- `tests/unit/` — pytest + pytest-qt；对话框在测试中必须 mock，真实模态框会阻塞
- `author_tools/` — 作者侧签发/加密工具，仅本地存在，不入库

## 当前状态（2026-10-15）

- 现役分支 `feature/pyside6-migration`（tkinter → PySide6 迁移完成，待合入 main）
- 361 用例 + mypy / ruff 门禁全绿；单 exe 约 32 MB
- 已知技术债见本地 `.ai_context/TECH_DEBT.md`（P0 两项已于 2026-10 复核关闭）
