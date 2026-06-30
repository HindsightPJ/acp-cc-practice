# 技术债清单

> 本文档记录 v1.0 发布时已知的代码质量问题与限制。
> 按风险等级和修复 ROI 排序，作为后续迭代的依据。
>
> 最后更新：2026-06-30 v1.0+（P0-P2 全部修复）

---

## P0 — 高风险（核心逻辑无测试覆盖）

### TD-01: `quiz_engine.py` 零单元测试

- **位置**：`quiz_engine.py` 全文件
- **问题**：核心业务逻辑（答题判定、统计、考试流程、错题索引反查）完全无测试覆盖
- **风险**：`submit_answer` 的多选排序比较、`record_exam_answer` 的跳跃答题、`get_wrong_answers` 依赖 `queue_index` 的索引反查都是易错逻辑，回归风险高
- **修复**：编写覆盖单选/多选、正确/错误、跳跃答题、统计累积的单元测试

### TD-02: `data_manager.parse_docx` 复杂正则未测试

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

### TD-05: `.env` 解析三套实现

- **位置**：`data_manager.py:212-225` / `author_tools/encrypt_questions.py:29-43` / `author_tools/generate_license.py:39-56`
- **问题**：三处各自用裸字符串解析 `.env`，行为可能不一致（引号、注释处理不同）
- **风险**：`data_manager._load_encryption_key` 不支持引号和行内注释，用户误写 `QUESTIONS_KEY="xxx"` 会保留引号导致解密失败
- **修复**：合并为公共函数 `load_env(path) -> dict`

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
- **注意**：破坏性更改——机器码算法变化，已签发的注册码需重新签发

### TD-08: `save_license` 非原子写入

- **位置**：`license/verifier.py:150-162`
- **问题**：直接 `open('w')` 写入，与 `data_manager.save_progress` 的原子写入模式（tmp + `os.replace`）不一致
- **风险**：断电可能导致 `license.dat` 损坏
- **修复**：复用 tmp + `os.replace` 模式

### TD-09: `generate_license.py` 写记录非原子 ✅ 已修复

- **位置**：`author_tools/generate_license.py` `record_issued`
- **问题**：写 `issued_licenses.json` 非原子，且 `record_issued` 失败未向上抛异常
- **修复**（已完成）：`record_issued` 改用 tmp + `os.replace` 原子写入模式（与 `data_manager.save_progress` 和 `verifier.save_license` 一致）；写入失败时清理 tmp 文件并上抛 `OSError`/`PermissionError`；新增 `test_record_issued_atomic_write_failure` 测试验证失败路径

### TD-10: `except Exception` 捕获过宽 ✅ 已修复

- **位置**：`data_manager.py` `load_or_parse_questions` + `load_full_questions`
- **问题**：使用 `except Exception` 捕获过宽，注释里有 `# pylint: disable=broad-exception-caught` 自我承认
- **修复**（已完成）：两处 `except Exception` 细化为 `(ValueError, OSError, json.JSONDecodeError, UnicodeDecodeError, InvalidToken)`——覆盖密钥格式错误 / 文件IO / 解密失败 / JSON损坏 / 编码错误；移除 `# pylint: disable=broad-exception-caught` 注释；延迟导入 `InvalidToken` 保持与原有 `Fernet` 延迟导入风格一致

---

## P3 — 代码质量

### TD-11: 函数过长 ✅ 已修复

| 函数 | 位置 | 行数 | 建议 |
|------|------|------|------|
| `PracticeMode._setup_mode_ui` | `ui/practice_mode.py:37-169` | ~130 | 拆分为 `_build_toolbar` / `_build_question_card` / `_build_options` / `_build_result_area` |
| `MainWindow._show_license_dialog` | `ui/main_window.py:266-348` | ~82 | 拆分为 UI 构建 / 机器码读取 / 验证逻辑 / 错误映射 |
| `DataManager.parse_docx` | `data_manager.py:48-117` | ~70 | 拆分为 `_detect_question` / `_detect_option` / `_detect_answer` / `_detect_explanation` |

### TD-12: God Object 倾向

- **位置**：`ui/main_window.py` `MainWindow` 类（450 行）
- **问题**：同时承担窗口构建、导航、授权状态、就绪度计算、license 对话框职责
- **修复**：拆分为 `MainWindow` + `LicenseDialog` + `MasteryRing`（已部分拆分）+ `Sidebar`

### TD-13: 类型注解不一致

- **位置**：`license/fingerprint.py:109` 用 PEP 604 `str | None`，其他文件用 `Optional[str]`
- **问题**：风格不统一；`ui/` 目录几乎无类型注解
- **修复**：统一为 `Optional[str]` 或在 `pyproject.toml` 声明 `python_requires=">=3.10"` 后统一用 PEP 604

### TD-14: 死参数 category ✅ 已修复

- **完成**：从 start_practice_mode 签名移除未使用的 category 参数；删除对应的死参数测试；98 项测试通过

- **位置**：`quiz_engine.py:15` `start_practice_mode(shuffle, category)` 的 `category` 参数从未在函数体内使用
- **修复**：删除参数或实现分类筛选功能

### TD-15: UI 与业务层耦合

- **位置**：`ui/practice_mode.py:345-348` 直接访问 `engine.stats` 字典字段
- **问题**：无显式接口契约，`QuizEngine` 内部结构变更会直接影响 UI
- **修复**：`QuizEngine` 提供TypedDict 或 dataclass 作为返回类型

---

## P4 — 测试基础设施

### TD-16: `requirements.txt` 未列开发依赖

- **问题**：`pytest` 未列为开发依赖，新贡献者不知如何跑测试
- **修复**：拆分 `requirements-dev.txt` 或使用 `pyproject.toml` extras

### TD-17: 无测试配置

- **问题**：无 `pytest.ini` / `pyproject.toml` 配置测试路径、标记
- **问题**：测试文件头部依赖 `sys.path.insert` 这种脆弱方式导入
- **修复**：添加 `pyproject.toml` 配置 pytest

### TD-18: 无覆盖率报告

- **问题**：无 `pytest-cov` 配置，无法量化测试覆盖
- **修复**：添加 `pytest-cov` + 配置最低覆盖率阈值

### TD-19: 无 UI 冒烟测试

- **问题**：无 `MainWindow` 能否实例化的 smoke test
- **修复**：添加 headless 冒烟测试（mock Tkinter）

### TD-20: 无 CI 配置

- **问题**：无 `.github/workflows/`，推送不触发测试
- **修复**：添加 GitHub Actions CI

---

## P5 — 构建与发布

### TD-21: 无 `version_info`

- **位置**：`acp-cc-practice.spec`
- **问题**：Windows 右键属性看不到版本号、公司、产品名
- **修复**：添加 `VSVersionInfo` 块

### TD-22: 无图标

- **位置**：`acp-cc-practice.spec`
- **问题**：`icon=` 参数缺失，EXE 用默认 PyInstaller 图标
- **修复**：制作 `.ico` 文件并引用

### TD-23: 无代码签名

- **问题**：未签名，Windows SmartScreen 会拦截未签名 EXE
- **修复**：购买代码签名证书或使用 sigstore

### TD-24: 依赖未锁定版本 ✅ 已修复

- **完成**：requirements.txt 改为上界约束（cryptography>=41.0.0,<50 等）；新增 requirements-dev.txt 含 pytest>=7.0.0,<10.0；99 项测试通过

- **位置**：`requirements.txt`
- **问题**：仅用 `>=`，`cryptography` 大版本升级可能导致 API 失效
- **修复**：改为 `cryptography>=41.0.0,<46` 或生成 `requirements.lock`

### TD-25: 无 `pyproject.toml`

- **问题**：项目无正式打包元数据（名称、版本、作者、Python 最低版本）
- **修复**：添加 `pyproject.toml`

---

## P6 — 文档

### TD-26: 无架构文档

- **问题**：无 ADR（Architecture Decision Records）记录设计决策
- **修复**：添加 `docs/architecture.md` 记录分层、授权协议、数据流

### TD-27: 无贡献指南

- **问题**：无 `CONTRIBUTING.md`
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
| TD-11 | P3 | ✅ 已修复 | 3 个长函数全部拆分（_setup_mode_ui + _show_license_dialog + parse_docx） |
| TD-12 | P3 | 待修复 | — |
| TD-13 | P3 | ✅ 已修复 | 统一为 Optional[str] |
| TD-14 | P3 | ✅ 已修复 | 移除 category 参数 |
| TD-15 | P3 | 待修复 | — |
| TD-16 | P4 | 待修复 | — |
| TD-17 | P4 | 待修复 | — |
| TD-18 | P4 | 待修复 | — |
| TD-19 | P4 | 待修复 | — |
| TD-20 | P4 | 待修复 | — |
| TD-21 | P5 | 待修复 | — |
| TD-22 | P5 | 待修复 | — |
| TD-23 | P5 | 待修复 | — |
| TD-24 | P5 | ✅ 已修复 | 上界约束 + requirements-dev.txt |
| TD-25 | P5 | ✅ 已修复 | 新增 pyproject.toml |
| TD-26 | P6 | 待修复 | — |
| TD-27 | P6 | 待修复 | — |
