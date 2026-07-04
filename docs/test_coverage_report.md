# 测试覆盖率报告

**生成日期**: 2026-07-04  
**项目**: acp-cc-practice  
**Python 版本**: 3.10+  
**测试框架**: pytest 7.0+ with pytest-cov

> 本报告为快照。最新数据请运行 `pytest --cov --cov-report=term-missing`。

## 1. 覆盖率配置

`pyproject.toml` 中已配置 coverage source 与报告规则：

```toml
[tool.coverage.run]
source = ["quiz_engine", "data_manager", "env_utils", "license", "author_tools"]
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
show_missing = true
```

### 覆盖率目标

| 模块 | 目标覆盖率 | 说明 |
|------|-----------|------|
| quiz_engine | ≥90% | 核心业务逻辑 |
| data_manager | ≥85% | 数据持久化层 |
| env_utils | ≥95% | 配置解析工具 |
| license/* | ≥90% | 授权验证核心 |
| author_tools/* | ≥80% | 作者工具链 |
| **整体** | **≥85%** | **项目级目标** |

CI 已启用 `--cov-fail-under=70` 作为当前底线阈值，后续将逐步提升至 85%。

## 2. 测试文件清单

### 2.1 单元测试 (tests/unit/)

| 测试文件 | 被测模块 | 测试用例数 |
|---------|---------|-----------|
| test_quiz_engine.py | quiz_engine.py | 76 |
| test_data_manager.py | data_manager.py | 31 |
| test_app_state.py | app_state.py | 15 |
| test_exam_mode.py | ui/exam_mode.py | 15 |
| test_exam_panel.py | ui/exam_panel.py | 17 |
| test_exam_session.py | ui/exam_session.py | 15 |
| test_base_mode.py | ui/base_mode.py | 8 |
| test_practice_mode.py | ui/practice_mode.py | 2 |
| test_practice_session.py | ui/practice_session.py | 10 |
| test_review_mode.py | ui/review_mode.py | 7 |
| test_wrong_book.py | ui/wrong_book.py | 3 |
| test_verifier.py | license/verifier.py | 11 |
| test_fingerprint.py | license/fingerprint.py | 15 |
| test_encrypt_questions.py | author_tools/encrypt_questions.py | 9 |
| test_keygen.py | author_tools/keygen.py | 9 |
| test_generate_license.py | author_tools/generate_license.py | 10 |
| test_env_utils.py | env_utils.py | 7 |
| test_main.py | main.py | 11 |
| test_license_dialog.py | ui/license_dialog.py | 12 |
| test_main_window_ui.py | ui/* | 12 |
| test_ui_smoke.py | ui/* | 14 |

**单元测试总计**: 约 309 个测试用例

### 2.2 集成测试 (tests/integration/)

| 测试文件 | 测试场景 | 测试用例数 |
|---------|---------|-----------|
| test_full_flow.py | 端到端授权流程 | 2 |
| test_cross_machine.py | 跨机器使用 | 1 |
| test_key_stability.py | 密钥稳定性 | 1 |

**集成测试总计**: 4 个测试用例

### 2.3 测试总计

| 类别 | 用例数 | 执行时间（估算） |
|------|--------|----------------|
| 单元测试 | ~307 | ~5-7 秒 |
| 集成测试 | 4 | ~1-2 秒 |
| GUI 测试 | 61 | ~6-8 秒 |
| **非 GUI 总计** | **251** | **~7 秒** |

## 3. 模块级覆盖率汇总

| 模块 | 代码行数 | 覆盖率 | 状态 | 备注 |
|------|---------|--------|------|------|
| quiz_engine.py | ~112 | 98% | ✅ | 核心业务逻辑 |
| data_manager.py | ~202 | 88% | ✅ | 异常路径已补 |
| env_utils.py | ~25 | 100% | ✅ | 配置解析 |
| license/verifier.py | ~103 | 81% | ✅ | 授权验证 |
| license/fingerprint.py | ~56 | 79% | ⚠️ | PowerShell/CIM 分支待补 |
| license/crypto_utils.py | ~6 | 100% | ✅ | 派生工具 |
| license/public_key.py | ~1 | 100% | ✅ | 公钥常量 |
| author_tools/encrypt_questions.py | ~59 | 95% | ✅ | 题库加密 |
| author_tools/keygen.py | ~66 | 64% | ⚠️ | CLI 交互分支待补 |
| author_tools/generate_license.py | ~106 | 61% | ⚠️ | CLI 交互分支待补 |
| **TOTAL** | **747** | **83%** | ✅ | 达 CI 阈值 70% |

**整体覆盖率**: **83%**（CI 阈值 70%，项目目标 ≥85%）

## 4. 覆盖率盲区

### 高优先级

1. **author_tools CLI 分支**
   - `keygen.py` 的交互式密钥保存提示
   - `generate_license.py` 的 `record_issued` 与交互式输入
   - 这些分支需通过子进程或抽取为可测函数覆盖

2. **license/fingerprint.py 平台分支**
   - Windows PowerShell/CIM 失败降级路径
   - 非 Windows 平台读取注册表失败路径

3. **license/verifier.py 解密失败路径**
   - `InvalidToken` / `ValueError` 等解密异常分支
   - `license.dat` 文件损坏场景

### 中 / 低优先级

- UI 组件深度交互测试
- 性能 / 安全 / 兼容性测试

## 5. 改进建议

| 优先级 | 项 | 说明 |
|--------|-----|------|
| 中 | 补全 author_tools CLI 分支 | 将 `if __name__ == "__main__"` 逻辑抽取到可测函数 |
| 中 | 补全 license 异常路径 | mock 文件损坏、解密失败、指纹采集失败 |
| 低 | 提升 CI 阈值 | 当整体稳定 ≥85% 后将 `--cov-fail-under=70` 改为 85 |
| 低 | UI 端到端测试 | 需 xvfb / pytest-qt |
| 低 | 安全测试 | 注册码伪造、密文篡改 |

## 6. 结论

- **整体覆盖率**: 83%（未达 ≥85% 项目目标，已超过 CI 70% 底线）
- **核心模块**: `quiz_engine` 98%、env_utils 100%、data_manager 88%，覆盖扎实
- **测试用例数**: 非 GUI 251 个，总计 312 个
- **最大缺口**: `author_tools` CLI 分支、`license/fingerprint` 平台分支

## 附录：运行覆盖率报告

```bash
# 终端报告
pytest --cov --cov-report=term-missing

# HTML 报告
pytest --cov --cov-report=html

# GUI 测试
pytest -m gui
```

覆盖率排除规则：`pragma: no cover`、`def __repr__`、`raise NotImplementedError`、`if __name__ == "__main__":`、`pass`。
