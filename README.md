# ACP 云计算练习

v1.0

一个用于备考阿里云 ACP（Alibaba Cloud Professional）云计算认证的桌面练习工具。基于 Python + Tkinter，零外部依赖（除 `python-docx` 用于解析题库、`cryptography` 用于题库加密与授权机制），开箱即用。

## 免责声明

本项目仅供个人学习与备考练习使用。

- 仓库包含一份**加密题库** `data/questions.enc`（Fernet 对称加密，AES-128-CBC + HMAC-SHA256），**不含明文题库，也不含主密钥 K**
- 主密钥 K 永不离开作者机器，客户端只能通过作者签发的**注册码**解出 K（Ed25519 签名 + AES-256-GCM 绑定机器码）
- 仓库同时提供 20 题明文试用 `data/questions_trial.json`，无需授权即可体验
- 题库源文件（`.docx` / `.doc`）受版权保护，不分发、不入库
- 所有题目版权归原版权方所有，使用者需自行获取合法题库授权
- 如版权方认为本项目存在侵权，请联系仓库所有者删除

## 功能

- **练习模式**：逐题作答，提交后即时显示对错与解析，支持单选/多选、键盘快捷键、错题自动入库
- **考试模式**：模拟真实考试，可选题量与时长，倒计时、答题卡导航、交卷后生成成绩报告
- **背题模式**：直接显示题干与解析，按空格键切换答案显隐，支持收藏题目
- **错题本**：自动收集练习中的错题，空状态友好提示，可查看详情、专项练习、清空
- **就绪度环**：侧栏底部把「练习覆盖率 × 正确率」合成为单一弧线，一眼可见离考试还差多远

## 设计取向

UI 走「Quiet Academy」极简教育风，并融合 Glassmorphism 视觉暗示：

- **冷白页面 + macOS 深灰侧栏**：纯白主背景 + `#1c1c1e` 深灰侧栏，长时间刷题不刺眼，强对比聚焦内容
- **教育蓝单一强调色**：`#2563eb`（blue-600）替代常见 Tailwind 默认蓝，传达「知识 / 专注 / 学术」气质，刻意减少颜色种类
- **Inter 字体优先 + 真实检测**：优先使用 Inter（Google 免费字体，粗细分明），系统未安装时 fallback 到 Segoe UI Variable / Microsoft YaHei UI，通过 `font.families()` 真实查询避免指定字体被静默替换
- **Canvas 真圆字母块**：选项左侧字母圆块用 `tk.Canvas.create_oval` 绘制真圆（非方块），暗示 Glassmorphism 的柔和质感
- **统一 OptionRow 组件**：练习 / 考试 / 背题 / 错题四种模式共用同一选项行，状态机 `idle → hover → selected → correct/wrong/revealed` 集中管理
- **就绪度环**：避免堆砌「已练 / 正确率 / 连击 / 勋章」四个数字，把用户真正关心的「能不能过」做成单一弧线
- **空状态视图**：错题本为空时显示引导文案，而非空白列表

## 项目结构

```
acp-cc-practice/
├── main.py                  # 入口：检查授权 → 加载 trial/full → 启动 UI
├── quiz_engine.py           # 题库引擎：题目队列、作答、统计、报告
├── data_manager.py          # 题库加载（trial/full 两段式）+ 进度持久化
├── requirements.txt         # 依赖（python-docx + cryptography）
├── acp-cc-practice.spec     # PyInstaller 打包配置（console=False，无 cmd 窗口）
├── .env.example             # .env 模板（作者密钥，本地保留）
├── .gitignore
├── license/                 # 客户端授权模块
│   ├── __init__.py          # LicenseStatus / LicenseError 枚举
│   ├── fingerprint.py       # 采集三维度指纹 → SHA-256 机器码
│   ├── public_key.py        # 内置 Ed25519 公钥（可公开）
│   └── verifier.py          # 验签 + PBKDF2 派生 + AES-GCM 解 K + license.dat 持久化
├── author_tools/            # 作者侧工具（入库但不含密钥，密钥在 .env）
│   ├── keygen.py            # 一次性生成 K + Ed25519 密钥对
│   ├── encrypt_questions.py # 加密全库 + 切 trial 20 题 + 生成 meta
│   └── generate_license.py  # 输入机器码 → 签发注册码
├── data/                    # 数据目录
│   ├── questions.enc        # 全库 Fernet 密文（868 题，入库）
│   ├── questions_trial.json # 试用题库（前 20 题明文，入库）
│   └── questions_meta.json  # 元数据（入库）
├── tests/                   # 测试套件（40 个测试）
│   ├── unit/                # 单元测试
│   └── integration/         # 集成测试
└── ui/
    ├── __init__.py
    ├── main_window.py       # 主窗口：侧栏 + 就绪度环 + 模式切换 + 授权状态栏
    ├── theme.py             # 设计 Token：色板 / 字体检测 / 按钮
    ├── option_row.py        # 统一选项行组件（Canvas 真圆字母块）
    ├── base_mode.py         # 模式基类
    ├── practice_mode.py     # 练习模式
    ├── exam_mode.py         # 考试模式（datetime 防计时漂移）
    ├── review_mode.py       # 背题模式（收藏按钮状态同步）
    └── wrong_book.py        # 错题本（空状态视图）
```

## 快速开始

### 环境要求

- Python 3.10+（授权模块用了 `str | None` 原生语法）
- Windows 桌面环境（授权机制依赖三维度机器指纹；macOS/Linux 降级试用 20 题）
- 依赖：`pip install -r requirements.txt`

### 两种使用方式

#### 方式 A：试用 + 授权模式（默认，推荐）

仓库默认提供 20 题明文试用，其余 848 题加密。完整使用需作者授权：

1. **试用**：直接运行，UI 顶部显示「题库共 868 题 · 试用版」
2. **申请授权**：
   - 启动程序，点「输入注册码」按钮
   - 复制弹窗显示的「机器码」（64 字符 hex）
   - 把机器码发给作者
3. **输入注册码**：作者回发注册码后，粘贴进弹窗，点「验证」
4. **重启程序**：自动加载完整 868 题

**授权机制**：
- 注册码绑定到申请时的机器（基于三维度指纹：MachineGuid + C盘卷序列号 + 计算机名）
- 重装系统 / 换硬盘会导致指纹变化，需重新申请
- 注册码不可跨机器使用
- 题库更新时无需重新申请（K 不变）

#### 方式 B：使用自己的密钥重新加密题库（高级）

如果你有合法的题库授权，并希望使用自己的密钥：

1. 运行 `python author_tools/keygen.py` 生成 K + Ed25519 密钥对 → 写入 `.env`
2. 把生成的公钥复制到 `license/public_key.py`
3. 准备明文 `questions.json`，运行 `python author_tools/encrypt_questions.py` 生成加密题库
4. 启动 `python main.py`，用 `python author_tools/generate_license.py` 为自己签发注册码

### 安装与运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动
python main.py
```

### 打包为 exe（作者侧）

```bash
python -m PyInstaller acp-cc-practice.spec --clean --noconfirm
# 产物在 dist/acp-cc-practice.exe（无 cmd 窗口）
```

## 数据文件

| 文件 | 位置 | 入库 | 说明 |
|------|------|------|------|
| `questions.enc` | `data/` | ✓ 入库 | 全库 Fernet 密文（868 题），需 K 解密，K 由注册码解出 |
| `questions_trial.json` | `data/` | ✓ 入库 | 试用题库（前 20 题明文），无需授权即可加载 |
| `questions_meta.json` | `data/` | ✓ 入库 | 元数据（total / trial_count / version），UI 显示总量用 |
| `progress.json` | `data/` | ✗ 排除 | 学习进度（错题本、练习统计、考试历史、收藏），**首次使用时自动生成**，原子写入，损坏自动备份 |
| `license.dat` | `data/` | ✗ 排除 | 用户本地注册码（机器绑定），首次授权后生成 |
| `app.log` | `data/` | ✗ 排除 | 运行日志（WARNING 级别，排错用） |
| `.env` | 项目根 | ✗ 排除 | 作者密钥（`QUESTIONS_MASTER_KEY` + `ED25519_*`），**本地保留，绝不入库** |
| `issued_licenses.json` | `author_tools/` | ✗ 排除 | 作者侧签发记录（含机器码与备注） |

**加载顺序**：
1. 检查 `license.dat` → 验证注册码 → 解出 K → 用 K 解密 `questions.enc`（868 题）
2. 无授权或验证失败 → 加载 `questions_trial.json`（20 题试用）

**进度持久化**：`progress.json` 在每次练习结束时自动保存到用户数据目录（打包后为 exe 同级 `data/`），重启程序不会丢失。

## 快捷键

| 按键 | 练习模式 | 考试模式 | 背题模式 |
|------|----------|----------|----------|
| `A` ~ `F` | 选择选项 | 选择选项 | — |
| `Enter` | 提交答案 | 提交答案 | — |
| `→` / `Space` | 下一题 | 下一题 | 下一题 / 显示答案 |
| `←` | 上一题 | 上一题 | 上一题 |
| `Esc` | — | — | 退出 |

## 已知限制

- **授权仅支持 Windows**：机器指纹基于三维度（MachineGuid + C盘卷序列号 + 计算机名），非 Windows 平台降级试用（20 题）
- **反编译防护仅基础**：PyInstaller 单文件打包不加密字节码，但主密钥 K 不在客户端，patch 验证函数无用——`questions.enc` 解密需要真 K
- **离线授权无过期机制**：注册码永久有效（K 不变时），作者可轮换 K 让所有已签发注册码失效
- **重装系统/换硬盘会失效**：指纹含卷序列号和 MachineGuid，硬件变更需重新申请注册码
- **题库加密单向**：`questions.enc` 的主密钥 K 在作者 `.env`，若 `.env` 丢失则无法解密
- **Tkinter 视觉限制**：不支持 `backdrop-filter blur`（Glassmorphism 核心），仅用 Canvas 真圆 + 柔和边框暗示玻璃感
- **字体依赖系统安装**：Inter 字体需用户自行从 Google Fonts 下载安装，未安装时 fallback 到系统默认字体
- 暂不支持题库分类筛选、多用户、暗色模式

## 发布清单（v1.0）

以下文件应包含在 GitHub 仓库中：

```
acp-cc-practice/
├── .gitignore
├── .env.example
├── README.md
├── acp-cc-practice.spec          # 打包配置（console=False）
├── main.py
├── data_manager.py
├── quiz_engine.py
├── requirements.txt
├── license/
│   ├── __init__.py
│   ├── fingerprint.py            # 三维度指纹
│   ├── public_key.py
│   └── verifier.py
├── author_tools/
│   ├── keygen.py
│   ├── encrypt_questions.py
│   └── generate_license.py
├── data/
│   ├── questions.enc             # 加密全库
│   ├── questions_trial.json      # 20 题试用
│   └── questions_meta.json       # 元数据
├── tests/
│   ├── unit/                     # 单元测试
│   └── integration/              # 集成测试
└── ui/
    ├── __init__.py
    ├── main_window.py
    ├── theme.py
    ├── option_row.py
    ├── base_mode.py
    ├── practice_mode.py
    ├── exam_mode.py
    ├── review_mode.py
    └── wrong_book.py
```

**不入库的文件**：`.env`、`data/progress.json`、`data/license.dat`、`data/app.log`、`data/questions.json`、`author_tools/issued_licenses.json`、`build/`、`dist/`、`__pycache__/`、`.pytest_cache/`

## License

仅供个人学习交流使用。
