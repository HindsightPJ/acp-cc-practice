# ACP 云计算练习软件 — 修复与优化总结报告

> 生成日期：2026-06-30  
> 范围：本次会话期间对 `acp-cc-practice` 项目的代码复核、技术债修复、重构与测试优化  
> 状态：未提交，等待最终审查

---

## 一、摘要

本次工作围绕三大目标展开：

1. **复核核心业务逻辑**：确认 `quiz_engine.py` 与 `wrong_book.py` 的逻辑正确性。
2. **处理 TD-12（MainWindow God Object）**：进一步拆分 `MainWindow`，新增 `Header` 组件，使主窗口职责更清晰。
3. **处理 TD-19（无 UI 冒烟测试）**：补充 UI 组件冒烟测试，并通过「共享 Tk 实例 + pytest marker 隔离」策略将全量测试耗时从不可接受降至 8 秒级别。

全量 176 项测试通过，无回归。

---

## 二、代码逻辑复核

### 2.1 `quiz_engine.py`

| 检查项 | 结论 |
|---|---|
| 多选答案排序比较 | ✅ 正确，`selected_sorted` 与 `answer_sorted` 均排序后比较，顺序无关 |
| `record_exam_answer` 跳跃答题 | ✅ 正确，不推进 `current_index`，仅记录指定题号结果 |
| `get_wrong_answers` 索引反查 | ✅ 正确，通过 `queue_index` 反查原始队列，避免错位 |
| TD-15 显式接口 | ✅ 完整：`get_current_index/set_current_index/queue_length/get_question_at/set_questions_queue/get_stats/get_exam_elapsed_seconds` |
| 注意事项 | `submit_answer` 与 `record_exam_answer` 各自累加 `stats['total']`，当前 UI 模式隔离，不会混用 |

### 2.2 `ui/wrong_book.py`

| 检查项 | 结论 |
|---|---|
| QuizEngine 接口使用 | ✅ 全部通过显式接口访问，无直接属性访问 |
| 子窗口生命周期 | ✅ `destroy()` 主动关闭错题练习子窗口，避免幽灵窗口与状态分裂 |
| 错题状态持久化 | ✅ 标记已掌握 / 清空错题均调用 `save_progress`，树和计数同步刷新 |
| 模态行为 | ✅ 错题练习使用 `grab_set` 模态窗口 |

---

## 三、重构模块

### 3.1 TD-12：MainWindow God Object 重构

**新增文件**：

- `ui/header.py` — 顶部 Header 组件，封装模式标题、授权状态、全局统计、「输入注册码」按钮。

**修改文件**：

- `ui/main_window.py`
  - 引入 `Header` 组件，移除内嵌的 `_build_header` 方法。
  - 模式切换方法改为调用 `self.header.set_mode_title(...)`。
  - 统计更新改为调用 `self.header.update_stats(...)`。
  - 清理未使用的 theme 导入。
  - `MainWindow` 行数从 ~344 行降至 ~160 行。

**职责划分**：

| 组件 | 职责 |
|---|---|
| `MainWindow` | 窗口生命周期、模式切换路由、状态聚合 |
| `Sidebar` | 品牌、导航、就绪度环、错题指示器 |
| `MasteryRing` | 就绪度可视化 |
| `LicenseDialog` | 注册码输入与验证交互 |
| `Header`（新增） | 模式标题、授权状态、全局统计、激活按钮 |

---

## 四、测试优化

### 4.1 TD-19：UI 冒烟测试补充

**新增/修改文件**：

- `tests/unit/test_main_window_ui.py`
  - 新增 5 个测试，文件内共 9 个测试：
    - `Header` 独立实例化及标题/统计更新
    - `Header` 激活按钮回调
    - `MasteryRing` 边界值与异常值截断
    - `Sidebar` 导航点击触发双回调
    - `LicenseDialog` 验证回调与关闭行为
  - 原有 `MainWindow` 实例化、四种模式切换、`Sidebar` / `LicenseDialog` 独立实例化测试保留。

### 4.2 性能优化策略

**问题**：早期 `test_main_window_ui.py` 9 个测试各自创建/销毁 `tk.Tk()`，Windows 环境下耗时约 252 秒。

**方案**：

1. **共享实例**：使用 `scope='module'` 的 `root` fixture 创建一个 `tk.Tk()`，供 `Sidebar` / `Header` / `MasteryRing` / `LicenseDialog` 等子组件测试复用。
2. **状态隔离**：`clean_root` fixture 每次测试前后销毁子组件、解绑全局事件、调用 `update_idletasks()`。
3. **标记隔离**：所有 UI 测试加 `@pytest.mark.gui`，`pyproject.toml` 默认 `-m 'not gui'` 跳过 GUI 测试。
4. **保留独立窗口**：`MainWindow` 继承 `tk.Tk`，无法挂载到共享 root，保留独立创建/销毁。

**配置变更**：

- `pyproject.toml`：新增 `markers` 定义，修改 `addopts` 默认跳过 gui 测试。

---

## 五、性能提升数据

| 场景 | 优化前 | 优化后 | 提升 |
|---|---|---|---|
| 仅 UI 冒烟测试（9 个） | ~252 秒 | 6.61 秒 | **~38 倍** |
| 非 UI 全量测试（167 个） | 15.42 秒 | 9.97 秒 | 日常更快 |
| 完整全量测试（176 个） | 超时/极慢 | **8.15 秒** | 可接受 |

> 注：优化前完整全量测试因 UI 测试过慢而无法在合理时间内完成；优化后全部 176 项测试 8.15 秒通过。

---

## 六、文件变更清单

### 新增文件

- `ui/header.py`
- `ui/sidebar.py`（本次会话前已拆分，本次持续使用）
- `ui/mastery_ring.py`（本次会话前已拆分，本次持续使用）
- `ui/license_dialog.py`（本次会话前已拆分，本次持续使用）
- `tests/unit/test_main_window_ui.py`

### 修改文件

- `ui/main_window.py` — 接入 Header，简化职责
- `pyproject.toml` — pytest markers 与默认 addopts
- `TECH_DEBT.md` — 更新 TD-12、TD-19 状态，新增 pytest 性能优化最佳实践附录

### 复核文件（无代码改动）

- `quiz_engine.py`
- `ui/wrong_book.py`

---

## 七、验证结果

```text
$ pytest -q
167 passed, 9 deselected in 10.04s

$ pytest -m gui -q
9 passed in 6.61s

$ pytest -q -m ''
176 passed in 8.15s
```

---

## 八、待处理项

| ID | 说明 | 状态 |
|---|---|---|
| TD-22 | EXE 图标 | 待用户准备 `.ico` 文件 |
| TD-23 | 代码签名 | 按用户要求暂缓 |

---

## 九、结论

本次修复和优化完成了 TD-12 与 TD-19，核心业务逻辑经过复核无异常，UI 测试性能问题得到根本性解决。项目当前处于干净、可测试、可继续交付的状态，等待用户最终确认后提交。
