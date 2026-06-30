# 贡献指南

感谢参与 acp-cc-practice 项目！本文档帮助你快速上手开发。

## 开发环境

### 依赖安装

```powershell
pip install -r requirements-dev.txt
```

包含运行依赖（python-docx, cryptography）+ 开发依赖（pytest, pytest-cov）。

### 运行测试

```powershell
# 全量测试
python -m pytest tests/ --tb=short -q

# 带覆盖率报告
python -m pytest tests/ --cov --cov-report=term-missing -q

# 单个测试文件
python -m pytest tests/unit/test_quiz_engine.py -v
```

当前测试数：144 项，覆盖率 74%。

## 项目结构

```
acp-cc-practice/
├── main.py                    # 入口
├── quiz_engine.py             # 答题引擎（业务层）
├── data_manager.py            # 题库加载/进度持久化
├── env_utils.py               # .env 解析
├── ui/                        # UI 层
│   ├── main_window.py         # 主窗口
│   ├── practice_mode.py       # 练习模式
│   ├── exam_mode.py           # 考试模式
│   ├── review_mode.py         # 背题模式
│   ├── wrong_book.py          # 错题本
│   ├── base_mode.py           # 模式基类
│   ├── option_row.py          # 选项组件
│   └── theme.py               # 颜色/字体常量
├── license/                   # 授权层
│   ├── fingerprint.py         # 机器指纹
│   ├── verifier.py            # 注册码验证
│   ├── crypto_utils.py        # PBKDF2 派生
│   └── public_key.py          # Ed25519 公钥
├── author_tools/              # 作者工具
│   ├── keygen.py              # 生成密钥对
│   ├── encrypt_questions.py   # 加密题库
│   └── generate_license.py    # 签发注册码
├── tests/                     # 测试
│   ├── unit/                  # 单元测试
│   └── integration/           # 集成测试
├── data/                      # 题库数据
├── pyproject.toml             # 项目元数据 + pytest 配置
├── requirements.txt           # 运行依赖
├── requirements-dev.txt       # 开发依赖
├── acp-cc-practice.spec       # PyInstaller 打包配置
└── TECH_DEBT.md               # 技术债追踪
```

## 代码风格

- Python 3.10+，使用 `Optional[str]` 风格类型注解
- 4 空格缩进
- 函数/方法添加 docstring（中文）
- 模块级函数优先于静态方法
- 延迟导入 `cryptography` 相关模块（保持与原有风格一致）

## 提交规范

```
<type>: <description>

- <detail 1>
- <detail 2>
```

类型：`feat`（新功能）/ `fix`（修复）/ `refactor`（重构）/ `test`（测试）/ `docs`（文档）/ `TD-XX`（技术债修复）

## 技术债

技术债记录在 `TECH_DEBT.md`，按 P0-P6 分级。修复时：
1. 每次只做一项修改
2. 运行全部测试验证无回归
3. 更新 TECH_DEBT.md 进度表
4. 提交时在 message 中标注 TD-XX

## CI

GitHub Actions 在 push/PR to main 时自动运行测试（Python 3.10/3.11/3.12）。
配置文件：`.github/workflows/ci.yml`
