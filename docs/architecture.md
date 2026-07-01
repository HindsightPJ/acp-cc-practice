# 架构文档

> 本文档记录 acp-cc-practice 的分层结构、授权协议、数据流与安全模型。

## 1. 项目概述

ACP 云计算练习软件——基于 Tkinter 的桌面题库练习应用，支持练习/考试/背题三种模式。
通过机器绑定注册码机制保护题库版权，作者侧加密题库，用户侧解密使用。

## 2. 分层结构

```
┌─────────────────────────────────────────┐
│  UI 层（ui/）                           │
│  main_window.py · practice_mode.py     │
│  exam_mode.py · review_mode.py         │
│  wrong_book.py · base_mode.py          │
├─────────────────────────────────────────┤
│  业务层                                 │
│  quiz_engine.py（答题/统计/考试流程）   │
├─────────────────────────────────────────┤
│  数据层                                 │
│  data_manager.py（题库加载/进度持久化） │
│  env_utils.py（.env 解析）              │
├─────────────────────────────────────────┤
│  授权层（license/）                     │
│  fingerprint.py（机器指纹）             │
│  verifier.py（注册码验证 + 题库解密）   │
│  crypto_utils.py（PBKDF2 派生）         │
├─────────────────────────────────────────┤
│  作者工具（author_tools/）              │
│  keygen.py（生成密钥对）                │
│  encrypt_questions.py（加密题库）       │
│  generate_license.py（签发注册码）      │
└─────────────────────────────────────────┘
```

## 3. 授权协议

### 3.1 密钥体系

| 密钥 | 用途 | 存储位置 |
|------|------|----------|
| K（主密钥） | AES-GCM 加密题库 | 作者 .env（不离开作者机器） |
| Ed25519 私钥 | 签名注册码 | 作者 .env |
| Ed25519 公钥 | 验证注册码签名 | 打包进 EXE（verifier.py） |
| DK（派生密钥） | 解密注册码中的 K | 运行时从机器码 + salt 派生 |

### 3.2 机器指纹

机器码 = SHA-256(MachineGuid | VolumeSerial | ComputerName | BiosSerial).hex()

四维度组合，降低单一维度变化导致误伤的概率。
BIOS 序列号获取失败时降级为空字符串，不阻断机器码生成。

### 3.3 注册码生成与验证

**作者侧**（generate_license.py）：
1. 输入用户机器码
2. 生成随机 salt(16) + nonce(12)
3. DK = PBKDF2(machine_code, salt, 600000)
4. encrypted_K = nonce + AES-GCM(nonce, K, DK, aad=salt)
5. signature = Ed25519.sign(salt + encrypted_K)
6. 注册码 = base64(signature(64) + salt(16) + encrypted_K(72)) = 152 字节

**用户侧**（verifier.py）：
1. base64 解码注册码
2. Ed25519 验签（公钥内置）
3. 用本机机器码 + salt 派生 DK
4. AES-GCM 解密得到 K
5. 持久化注册码到 license.dat
6. 用 K 解密 questions.enc 加载全库

### 3.4 安全模型

- 主密钥 K 永远不离开作者机器
- 注册码与机器绑定，换机无法使用
- 反编译 EXE 只能获取公钥，无法获取 K
- 每台机器的 DK 不同，即使注册码泄露也无法在其他机器使用

## 4. 数据流

### 4.1 题库加载

```
docx 原始题库
  → author_tools/encrypt_questions.py
  → data/questions.enc（Fernet 加密）
  → data/questions_trial.json（前 20 题明文）
  → data/questions_meta.json（元数据）

用户侧加载：
  优先读 questions.enc（需 K 解密）
  → fallback questions.json（明文缓存）
  → fallback docx 解析
```

### 4.2 进度持久化

```
progress.json（用户数据目录）
  - wrong_questions: 错题列表
  - practice_stats: 练习统计
  - exam_history: 考试历史
  - favorites: 收藏

写入策略：原子写入（tmp + os.replace）
损坏恢复：自动备份为 .corrupt-{timestamp}
```

## 5. 打包

PyInstaller 打包为单文件 EXE：
- `data/` 目录打包进 EXE（只读）
- `license.dat` / `progress.json` / `app.log` 写到 exe 同级 `data/`（可写）
- `console=False`，使用 logging 替代 print
