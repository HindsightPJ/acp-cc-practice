# 技术债清单

> 本文档记录 v1.0 发布时已知的代码质量问题与限制。
> 按风险等级和修复 ROI 排序，作为后续迭代的依据。
>
> 最后更新：2026-07-05（P0-P1 代码审查收尾：after job 内存泄漏、ExamPanel._build_ui 拆分、死代码清理、messagebox 一致性、UI 常量集中管理；CI 配置修复；测试数 316，覆盖率报告同步）

---

## P0 — 高风险（核心逻辑无测试覆盖）

### TD-01: `quiz_engine.py` 零单元测试 ✅ 已修复

- **完成**：新增 `tests/unit/test_quiz_engine.py`，59 个用例覆盖单选/多选、正确/错误、跳跃答题、错题索引反查、统计累积、考试流程；`quiz_engine.py` 覆盖率 98%

- **位置**：`quiz_engine.py` 全文件
- **问题**：核心业务逻辑（答题判定、统计、考试流程、错题索引反查）完全无测试覆盖
- **风险**：`submit_answer` 的多选排序比较、`record_exam_answer` 的跳跃答题、`get_wrong_answers` 依赖 `queue_index` 的索引反查都是易错逻辑，回归风险高
- **修复**：编写覆盖单选/多选、正确/错误、跳跃答题、统计累积的单元测试

### TD-02: `data_manager.parse_docx` 复杂正则未测试 ✅ 已修复

- **完成**：新增 13 个 `parse_docx` 测试，覆盖题干/选项/答案/解析各种格式；修复正则分支中的解析 bug；`data_manager.py` 覆盖率 88%

- **位置**：`data_manager.py:48-117`
- **问题**：70 行正则密集分支，单行条件判断超 300 字符（`data_manager.py:78`），完全未测试
- **风险**：题库格式微调可能导致解析失败，且难以定位
- **修复**：针对各种题干/选项/答案/解析格式编写解析测试

---

## P1 — 代码重复（DRY 违规）

### TD-03: `_derive_dk` 重复实现 ✅ 已修复

- **完成**：新增 `license/crypto_utils.py` 含 `derive_dk()` + `PBKDF2_ITERATIONS`；`verifier.py` / `generate_license.py` / `test_verifier.py` 改为导入共享模块；99 项测试全部通过

- **位置**：`license/verifier.py:48-56` ↔ `author_tools/generate_license.py:59-67`
- **问题**：PBKDF2HMAC 派生函数在客户端和作者侧完全重复实现，注释承认"必须严格一致"
- **风险**：两边漂移会导致验证静默失败
- **修复**：抽取到 `license/crypto_utils.py` 共享模块

### TD-04: `main.py` 错误退出模式重复 4 次 ✅ 已修复

- **完成**：抽取 `_show_fatal_error(title, message)` 辅助函数，替换 main() 中 4 处重复的 tk.Tk + messagebox + sys.exit(1) 模式；99 项测试通过

- **位置**：`main.py:68-74`、`77-80`、`83-86`、`104-107`
- **问题**：
  ```python
  root = tk.Tk()
  root.withdraw()
  messagebox.showerror("错误", ...)
  sys.exit(1)
  ```
- **修复**：抽取为 `_fatal_error(msg)` 辅助函数

### TD-05: `.env` 解析三套实现 ✅ 已修复

- **完成**：合并为公共函数 `load_env(path) -> dict` 并抽取到 `env_utils.py`；`data_manager.py`、`author_tools/encrypt_questions.py`、`author_tools/generate_license.py` 统一导入使用；支持引号包裹值与行内注释
- **位置**：`data_manager.py:212-225` / `author_tools/encrypt_questions.py:29-43` / `author_tools/generate_license.py:39-56`
- **问题**：三处各自用裸字符串解析 `.env`，行为可能不一致（引号、注释处理不同）
- **风险**：`data_manager._load_encryption_key` 不支持引号和行内注释，用户误写 `QUESTIONS_MASTER_KEY="xxx"` 会保留引号导致解密失败

### TD-06: 基类方法被完全覆盖未调 `super()` ✅ 已修复

- **位置**：`ui/practice_mode.py` ↔ `ui/base_mode.py` ↔ `ui/exam_mode.py` ↔ `ui/review_mode.py`
- **问题**：`_bind_keyboard` / `_on_global_click` / `_on_key_press` 在 3 个子类完全覆盖基类，未调用 `super()`，基类实现成为死代码
- **修复**（已完成）：
  - 删除 `PracticeMode` / `ExamMode` / `ReviewMode` 中与基类完全相同的 `_bind_keyboard` 和 `_on_global_click`（纯复制粘贴死代码）
  - `PracticeMode._on_key_press` 和 `ReviewMode._on_key_press` 末尾改用 `return super()._on_key_press(event)` 复用基类导航键逻辑
  - `ExamMode._on_key_press` 保留原样（Left → `exam_prev_question()` 与基类不同）
  - 净减少 38 行代码，118 项测试通过

---

## P2 — 安全与稳健性

### TD-07: 机器指纹维度偏弱 ✅ 已修复

- **位置**：`license/fingerprint.py`
- **问题**：`ComputerName` 用户可在系统设置中随意修改，是三个维度中最弱的；当前组合 `SHA-256(MachineGuid | VolumeSerial | ComputerName)` 中 ComputerName 占 1/3 权重过高
- **风险**：用户改计算机名会导致注册码失效（误伤合法用户）
- **修复**（已完成）：新增 `get_bios_serial()` 通过 `wmic bios get SerialNumber` 采集 BIOS 序列号作为第 4 维度；`compute_machine_code` 增加 `bios_serial` 参数；机器码变为 `SHA-256(guid|volume|name|bios)`；BIOS 获取失败时用空字符串（不阻断）；过滤 OEM 常见占位符；ComputerName 权重从 1/3 降到 1/4；新增 7 个 BIOS 相关测试
- **P1-3 更新**：`wmic` 在 Windows 11 22H2+ 已弃用，`get_bios_serial()` 已迁移到 PowerShell CIM（`Get-CimInstance Win32_BIOS`）；机器码算法不变，不影响已签发的注册码
- **注意**：破坏性更改——机器码算法变化，已签发的注册码需重新签发

### TD-08: `save_license` 非原子写入 ✅ 已修复

- **完成**：`LicenseVerifier.save_license` 改用 tmp + `os.replace` 原子写入模式，与 `data_manager.save_progress` 保持一致
- **位置**：`license/verifier.py:150-162`
- **问题**：直接 `open('w')` 写入，与 `data_manager.save_progress` 的原子写入模式（tmp + `os.replace`）不一致
- **风险**：断电可能导致 `license.dat` 损坏

### TD-09: `generate_license.py` 写记录非原子 ✅ 已修复

- **位置**：`author_tools/generate_license.py` `record_issued`
- **问题**：写 `issued_licenses.json` 非原子，且 `record_issued` 失败未向上抛异常
- **修复**（已完成）：`record_issued` 改用 tmp + `os.replace` 原子写入模式（与 `data_manager.save_progress` 和 `verifier.save_license` 一致）；写入失败时清理 tmp 文件并上抛 `OSError`/`PermissionError`；新增 `test_record_issued_atomic_write_failure` 测试验证失败路径

### TD-10: `except Exception` 捕获过宽 ✅ 已修复

- **位置**：`data_manager.py` `load_or_parse_questions` + `load_full_questions`
- **问题**：使用 `except Exception` 捕获过宽，注释里有 `# pylint: disable=broad-exception-caught` 自我承认
- **修复**（已完成）：两处 `except Exception` 细化为 `(ValueError, OSError, json.JSONDecodeError, UnicodeDecodeError, InvalidToken)`——覆盖密钥格式错误 / 文件IO / 解密失败 / JSON损坏 / 编码错误；移除 `# pylint: disable=broad-exception-caught` 注释；延迟导入 `InvalidToken` 保持与原有 `Fernet` 延迟导入风格一致

### TD-28: after job 跟踪集合无限增长 ✅ 已修复

- **位置**：`ui/base_mode.py`、派生模式（`exam_mode.py` / `review_mode.py`）
- **问题**：`_after_jobs` 用 `list[str]` 跟踪待执行 `after` 回调，旧 job 取消后未从列表移除；`ExamMode.update_timer` 每秒生成新 job，60 分钟考试会累积 3600 个无效引用，造成内存泄漏与悬挂回调
- **修复**（已完成）：
  - `_after_jobs: list[str]` → `set[str]`，自动去重
  - 新增 `_cancel_after_job(job_id)` 统一封装 `after_cancel` + `discard`，从 API 层面防止「取消后忘记移除」
  - `ExamMode.update_timer` 每次用 `_cancel_after_job` 清理旧 job 再注册新 job
  - 新增 4 个回归测试：remove-from-tracking / None-noop / idempotent / dedup

---

## P3 — 代码质量

### TD-11: 函数过长 ✅ 已修复

| 函数 | 位置 | 行数 | 建议 |
|------|------|------|------|
| `PracticeMode._setup_mode_ui` | `ui/practice_mode.py:37-169` | ~130 | 拆分为 `_build_toolbar` / `_build_question_card` / `_build_options` / `_build_result_area` |
| `MainWindow._show_license_dialog` | `ui/main_window.py:266-348` | ~82 | 拆分为 UI 构建 / 机器码读取 / 验证逻辑 / 错误映射 |
| `DataManager.parse_docx` | `data_manager.py:48-117` | ~70 | 拆分为 `_detect_question` / `_detect_option` / `_detect_answer` / `_detect_explanation` |
| `ExamPanel._build_ui` | `ui/exam_panel.py:83-282` | ~200 | 拆分为 `_build_timer_bar` / `_build_question_area` / `_build_action_bar` / `_build_nav_panel` |

- **完成（2026-07-05）**：`ExamPanel._build_ui` 拆分为 4 个子方法；17 个 `test_exam_panel.py` 用例全部通过；`mypy` / `ruff` / `pytest` 全绿

### TD-12: God Object 倾向 ⊝ 评估保留

- **位置**：`ui/main_window.py` `MainWindow` 类（344 行）
- **问题**：同时承担窗口构建、导航、授权状态、就绪度计算、license 对话框职责
- **修复**：拆分为 `MainWindow` + `LicenseDialog` + `MasteryRing`（已部分拆分）+ `Sidebar`
- **评估结论（2026-06-30）**：保留现状。理由：
  1. 无方法超过 70 行（最长 `_show_license_dialog` 68 行，纯逻辑已抽取到模块级函数）
  2. `LicenseDialog` 拆分收益低（68 行 UI 代码，强行抽类增加文件复杂度）
  3. `Sidebar` 与 MainWindow 耦合紧密（`_active_nav`/`_nav_refs` 状态共享），拆分需传递大量回调
  4. 无 UI 自动化测试覆盖，重构风险高于收益
  5. 待 TD-19（UI 冒烟测试）落地后再评估

### TD-13: 类型注解不一致 ✅ 已修复

- **位置**：`license/fingerprint.py:109` 用 PEP 604 `str | None`，其他文件用 `Optional[str]`
- **问题**：风格不统一；`ui/` 目录几乎无类型注解
- **修复（已完成）**：
  - `pyproject.toml` 已声明 `requires-python = ">=3.10"`，全项目统一使用 PEP 604 `str | None`
  - 为核心模块（`data_manager.py`、`main.py`、`ui/base_mode.py`、`ui/practice_panel.py`、`ui/main_window.py`、`ui/wrong_book.py`、`ui/practice_mode.py`、`ui/theme.py`、`ui/sidebar.py`、`ui/header.py` 等）补齐类型签名
  - 修复 `mypy --disallow-untyped-defs .` 全部类型错误
  - 验证：`mypy`、`ruff`、`pytest` 全部通过

### TD-14: 死参数 category ✅ 已修复

- **完成**：从 start_practice_mode 签名移除未使用的 category 参数；删除对应的死参数测试；98 项测试通过

- **位置**：`quiz_engine.py:15` `start_practice_mode(shuffle, category)` 的 `category` 参数从未在函数体内使用
- **修复**：删除参数或实现分类筛选功能

### TD-15: UI 与业务层耦合 ✅ 已修复

- **位置**：`ui/practice_mode.py:345-348` 直接访问 `engine.stats` 字典字段
- **问题**：无显式接口契约，`QuizEngine` 内部结构变更会直接影响 UI
- **完成**：`QuizEngine` 新增 5 个显式接口——`get_current_index` / `set_current_index` / `queue_length` / `get_question_at` / `set_questions_queue`；UI 18 处直接属性访问（base_mode 2 + exam_mode 8 + review_mode 8）全部迁移到接口调用；新增 12 个单元测试（含副本隔离契约）；156 项测试全部通过
- **修复**：`QuizEngine` 提供TypedDict 或 dataclass 作为返回类型
- **已完成（2026-06-30）**：`engine.stats` 已解耦
  - 新增 `QuizEngine.get_stats()` 返回副本，`practice_mode.py` 改用此方法
  - 新增 3 个测试（初始/累积/副本隔离），134 项测试通过
- **剩余耦合点**（待后续修复）：
  - `engine.current_index`：exam_mode.py(6处)、base_mode.py(2处) 直接读写
  - `engine.questions_queue`：exam_mode.py(2处)、review_mode.py(6处) 直接读写
  - `review_mode.py:33` 直接赋值 `engine.questions_queue = list(questions)`（最危险）
  - 建议新增 `get_current_index()`/`set_current_index()`/`get_questions_queue()`/`set_questions_queue()` 方法

### TD-29: write-only 死代码别名属性 ✅ 已修复

- **位置**：`ui/review_mode.py`（`review_question_text`、`review_option_rows`、`answer_label`、`review_explanation_text`）、`ui/practice_panel.py`（`question_text`、`result_label`、`explanation_text`）
- **问题**：从 `PracticePanel` / `QuestionDetailCard` 抽取可复用组件后，原模式类里留下大量只写不读的别名属性，误导维护者、增加混淆
- **修复**（已完成）：grep 确认无读取引用后删除 7 个别名属性；保留真正被使用的 `option_cards`；61 个 GUI 测试通过

### TD-30: UI messagebox 缺少 `parent=` ✅ 已修复

- **位置**：`ui/exam_mode.py`、`ui/review_mode.py`、`ui/practice_mode.py`、`ui/practice_panel.py`、`ui/wrong_book.py`
- **问题**：17 处 `messagebox.*` 调用未传 `parent=self`，导致弹窗可能不模态、焦点错乱、在 headless/多窗口场景下行为不可预期
- **修复**（已完成）：系统 grep 所有 35 处 messagebox 调用，为 17 处缺失 `parent=` 的调用补全；保留 `license_dialog.py:91` 例外（对话框尚未实例化，传 `parent=None` 合理）；mypy 类型检查辅助守卫

### TD-31: UI 魔法数字/字符串散落 ✅ 已修复

- **位置**：`ui/base_mode.py`、`ui/exam_panel.py`、`ui/practice_panel.py`、`ui/practice_session.py`、`ui/question_detail_card.py`、`ui/review_mode.py`、`ui/exam_mode.py`、`ui/exam_session.py`
- **问题**：`"ABCDEF"`、`"123456"`、`"single"`、`"multiple"`、`2000`、`1000`、`100`、`range(6)` 等魔法值硬编码在 8 个文件中，修改选项数量或题型标识时极易遗漏
- **修复**（已完成）：
  - 新增 `ui/constants.py` 集中管理：`MAX_OPTIONS`、`OPTION_KEYS`、`OPTION_NUMBERS`、`QUESTION_TYPE_SINGLE`、`QUESTION_TYPE_MULTIPLE`、`SAVE_DEBOUNCE_MS`、`AUTO_SHOW_ANSWER_DELAY_MS`、`TIMER_TICK_MS`
  - 8 个文件 12 处引用全部替换为常量
  - CI 已同步：Ubuntu runner 安装 Xvfb + 系统 Tk/X11 库，设置 `DISPLAY=:99`；pytest 使用 `-o addopts="" -m "not gui"` 避免 addopts 与命令行 marker 冲突

---

## P4 — 测试基础设施

### TD-16: `requirements.txt` 未列开发依赖 ✅ 已修复

- **问题**：`pytest` 未列为开发依赖，新贡献者不知如何跑测试
- **修复**：拆分 `requirements-dev.txt` 或使用 `pyproject.toml` extras

### TD-17: 无测试配置 ✅ 已修复

- **问题**：无 `pytest.ini` / `pyproject.toml` 配置测试路径、标记
- **问题**：测试文件头部依赖 `sys.path.insert` 这种脆弱方式导入
- **修复**：添加 `pyproject.toml` 配置 pytest

### TD-18: 无覆盖率报告 ✅ 已修复

- **问题**：无 `pytest-cov` 配置，无法量化测试覆盖
- **修复**：添加 `pytest-cov` + 配置最低覆盖率阈值
- **完成**：`pyproject.toml` 添加 [tool.coverage.*]；CI 启用 `--cov-fail-under=70`；核心模块覆盖率 83%（quiz_engine 98%、env_utils 100%、data_manager 88%）

### TD-19: 无 UI 冒烟测试 ⏳ 部分修复

- **问题**：无 `MainWindow` 能否实例化的 smoke test
- **修复**：添加 headless 冒烟测试（mock Tkinter）
- **已完成（2026-06-30）**：新增 `tests/unit/test_ui_smoke.py` 10 个测试
  - 覆盖所有 ui 子模块的 import（theme/base_mode/practice_mode/exam_mode/review_mode/wrong_book/option_row/main_window）
  - 验证类定义存在 + 继承关系正确（MainWindow→tk.Tk, MasteryRing→tk.Canvas）
  - 验证 TD-11 抽取的模块级函数可调用
- **剩余**：完整 MainWindow 实例化测试需要虚拟 display（xvfb），留待后续

### TD-20: 无 CI 配置 ✅ 已修复

- **问题**：无 `.github/workflows/`，推送不触发测试
- **修复**：添加 GitHub Actions CI

---

## P5 — 构建与发布

### TD-21: 无 `version_info` ✅ 已修复

- **位置**：`acp-cc-practice.spec`
- **问题**：Windows 右键属性看不到版本号、公司、产品名
- **完成**：`acp-cc-practice.spec` 顶部添加 `VSVersionInfo` 块（CompanyName=HindsightPJ, FileDescription=ACP 云计算练习软件, FileVersion=1.0.0, ProductName=ACP 云计算练习, ProductVersion=1.0.0, LegalCopyright=© 2026 HindsightPJ）；EXE() 调用添加 `version=version_info` 参数
- **修复**：添加 `VSVersionInfo` 块

### TD-22: 无图标 ✅ 已修复

- **完成**：
  - 从 `icons/original/icon-1024.png` 生成 `icons/icon.ico`（含 16/32/48/64/128/256 多尺寸）
  - `acp-cc-practice.spec` 的 `EXE()` 调用添加 `icon=os.path.join(SPECPATH, 'icons', 'icon.ico')`
  - `ui/main_window.py` 在开发模式（`python main.py`）下调用 `self.iconbitmap('icons/icon.ico')` 设置窗口标题栏图标；打包后由 EXE 图标控制

- **位置**：`acp-cc-practice.spec`
- **问题**：`icon=` 参数缺失，EXE 用默认 PyInstaller 图标
- **修复**：制作 `.ico` 文件并引用

### TD-23: 无代码签名 ✅ 已修复

- **完成**：
  - `pyproject.toml` 新增 `[project.optional-dependencies]` 的 `release = ["pyinstaller>=6.0,<7.0", "sigstore>=3.0,<4.0"]`
  - 新增 `.github/workflows/release.yml`：推送 `v*` tag 时触发
    - Windows runner 上 `pip install -e ".[release]"`
    - `pyinstaller acp-cc-practice.spec --noconfirm --clean` 构建 EXE
    - 使用 `sigstore/gh-action-sigstore-python@v3.0.0` 对 `dist/acp-cc-practice.exe` 进行 OIDC 无密钥签名，生成 `.sig` 和 `.crt`
    - 通过 `softprops/action-gh-release@v2` 创建 GitHub Release 并上传 EXE + `.sig` + `.crt`
  - 工作流所需权限：`contents: write` + `id-token: write`

- **问题**：未签名，Windows SmartScreen 会拦截未签名 EXE
- **修复**：使用 Sigstore 无密钥代码签名

### TD-24: 依赖未锁定版本 ✅ 已修复

- **完成**：requirements.txt 改为上界约束（cryptography>=41.0.0,<50 等）；新增 requirements-dev.txt 含 pytest>=7.0.0,<10.0；99 项测试通过

- **位置**：`requirements.txt`
- **问题**：仅用 `>=`，`cryptography` 大版本升级可能导致 API 失效
- **修复**：改为 `cryptography>=41.0.0,<46` 或生成 `requirements.lock`

### TD-25: 无 `pyproject.toml` ✅ 已修复

- **完成**：新增 `pyproject.toml`，含项目元数据、`[project]` 依赖、`[dev]` extras、pytest / coverage / mypy / ruff 工具配置
- **问题**：项目无正式打包元数据（名称、版本、作者、Python 最低版本）

---

## P6 — 文档

### TD-26: 无架构文档 ✅ 已修复

- **问题**：无 ADR（Architecture Decision Records）记录设计决策
- **完成**：新增 `docs/architecture.md`，含项目概述、分层结构图（UI/业务/数据/授权/作者工具）、授权协议（密钥体系表、机器指纹、注册码生成与验证流程、安全模型）、数据流（题库加载、进度持久化）、打包说明
- **修复**：添加 `docs/architecture.md` 记录分层、授权协议、数据流

### TD-27: 无贡献指南 ✅ 已修复

- **问题**：无 `CONTRIBUTING.md`
- **完成**：新增 `CONTRIBUTING.md`，含开发环境搭建（依赖安装、运行测试）、项目结构树、代码风格、提交规范、技术债修复流程、CI 说明
- **修复**：添加贡献指南

---

## 修复进度追踪

| ID | 优先级 | 状态 | 修复提交 |
|----|--------|------|----------|
| TD-01 | P0 | ✅ 已修复 | test_quiz_engine.py 59 用例 |
| TD-02 | P0 | ✅ 已修复 | 13 个 parse_docx 测试 + 正则 bug 修复 |
| TD-03 | P1 | ✅ 已修复 | 抽取到 license/crypto_utils.py |
| TD-04 | P1 | ✅ 已修复 | 抽取 _show_fatal_error 辅助函数 |
| TD-05 | P1 | ✅ 已修复 | 抽取到 env_utils.py |
| TD-06 | P1 | ✅ 已修复 | 删除 3 子类死代码 + super() 复用导航键 |
| TD-07 | P2 | ✅ 已修复 | 新增 BIOS 序列号第 4 维度（破坏性，需重签注册码） |
| TD-08 | P2 | ✅ 已修复 | tmp + os.replace 原子写入 |
| TD-09 | P2 | ✅ 已修复 | tmp + os.replace 原子写入 + 失败上抛异常 |
| TD-10 | P2 | ✅ 已修复 | 细化为 (ValueError, OSError, InvalidToken, JSONDecodeError, UnicodeDecodeError) |
| TD-11 | P3 | ✅ 已修复 | 4 个长函数拆分（_setup_mode_ui + _show_license_dialog + parse_docx + ExamPanel._build_ui） |
| TD-12 | P3 | ⊝ 评估保留 | 344 行但无方法超 70 行；无 UI 测试，风险>收益 |
| TD-13 | P3 | ✅ 已修复 | 统一为 PEP 604 `str | None`，补齐核心模块类型签名 |
| TD-14 | P3 | ✅ 已修复 | 移除 category 参数 |
| TD-15 | P3 | ✅ 已修复 | 新增 5 个接口（get_current_index/set_current_index/queue_length/get_question_at/set_questions_queue）+ UI 18 处迁移 + 12 个新测试 |
| TD-16 | P4 | ✅ 已修复 | requirements-dev.txt 补充 pytest-cov |
| TD-17 | P4 | ✅ 已修复 | pyproject.toml 添加 [tool.pytest.ini_options] |
| TD-18 | P4 | ✅ 已修复 | pyproject.toml 添加 [tool.coverage.*]，整体覆盖率 74% |
| TD-19 | P4 | ⏳ 部分修复 | 10 个 import 冒烟测试；完整实例化测试需 xvfb 待后续 |
| TD-20 | P4 | ✅ 已修复 | .github/workflows/ci.yml（Ubuntu + Python 3.10；ruff/mypy/pytest + Xvfb headless 支持） |
| TD-21 | P5 | ✅ 已修复 | spec 添加 VSVersionInfo（右键属性可见版本/公司/产品名） |
| TD-22 | P5 | ✅ 已修复 | 从 icon-1024.png 生成 icons/icon.ico，spec 引用 |
| TD-23 | P5 | ✅ 已修复 | release.yml + Sigstore OIDC 签名 |
| TD-24 | P5 | ✅ 已修复 | 上界约束 + requirements-dev.txt |
| TD-25 | P5 | ✅ 已修复 | 新增 pyproject.toml |
| TD-26 | P6 | ✅ 已修复 | 新增 docs/architecture.md |
| TD-27 | P6 | ✅ 已修复 | 新增 CONTRIBUTING.md |
| TD-28 | P2 | ✅ 已修复 | `_after_jobs` set + `_cancel_after_job` 统一取消语义 |
| TD-29 | P3 | ✅ 已修复 | 删除 write-only 别名属性 |
| TD-30 | P3 | ✅ 已修复 | 17 处 messagebox 补全 `parent=` |
| TD-31 | P3 | ✅ 已修复 | 新增 `ui/constants.py`，12 处魔法值替换 |
