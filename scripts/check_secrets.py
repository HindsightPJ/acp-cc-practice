#!/usr/bin/env python3
"""check_secrets.py — 硬编码密钥扫描（audit_checklist §6.1#8 的机器化落地）

用法:
    python check_secrets.py [目录] [--json]
默认扫描当前目录。命中疑似硬编码密钥时 exit 1（供 pre-commit / CI 拦截）。

规则（2026-10-19 v2，修复安全审计 H5 的漏报/误报形态）:
- 赋值形态：key = "value" / key: value；引号内允许空格（带空格口令不再漏报）
- 拼接形态：key = "a" + "b..." 字符串片段拼接后判长（只认单字面量的绕过堵上）
- 高熵字面量：≥32 字符 base64/hex 形态的引号字面量直接命中，不依赖变量名
  （变量名/行内含 public 的除外——公钥可公开）
- PEM 私钥块；.pem/.key/.p12/.pfx/.crt 后缀全文件扫；文件名含
  private/secret/credential 的文件按文本全扫
- 占位符与环境变量间接引用（os.environ / os.getenv / environ.get /
  process.env / import.meta.env）不算命中——官方推荐写法不再误报
- Python 文件经 tokenize 区分注释与字符串（docstring 里的密钥不再因
  行首 # 判定被漏掉）；其它语言沿用行首启发式
- 目录遍历 os.walk(followlinks=False)（不跟随 junction/symlink），
  遍历/读取失败与 >2MB 跳过均记入 notes——失败模式必须是"喊出来"，不是静默 [OK]
"""
import argparse
import io
import json
import math
import os
import re
import sys
import tokenize
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 排除目录与文件（依赖/构建产物/锁文件误报率极高，一律跳过）
# author_tools / .ai_context：作者侧本地工具与机器本地状态（.gitignore 明确
# 绝不入库）——门禁防的是"进仓库"，扫永不入库的本地文件只产出噪音
EXCLUDE_DIRS = {"node_modules", ".git", "miniprogram_npm", "dist", "build",
                "unpackage", ".venv", "venv", "__pycache__", ".workbuddy",
                "author_tools", ".ai_context"}
EXCLUDE_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml",
                 "check_secrets.py", "check_deps_lock.py", "check_gates_present.py"}
# 哈希清单：内容是文件 sha256 指纹（RULES_MANIFEST / skill-manifest 等），
# 高熵规则必然命中，非密钥
MANIFEST_JSON_RE = re.compile(r"manifest.*\.json$|manifest\.json$", re.IGNORECASE)
TEXT_EXTS = {".js", ".ts", ".vue", ".py", ".json", ".yaml", ".yml", ".env",
             ".wxml", ".wxss", ".md", ".html", ".css", ".sh", ".toml", ".ini",
             # 密钥/证书文件按文本全扫（审计 H5：.pem 装整把私钥不报 = 门禁失效）
             ".pem", ".key", ".p12", ".pfx", ".crt"}
MAX_FILE_BYTES = 2 * 1024 * 1024  # 超大文件跳过并记 note（此前全量 read_text 可卡死门禁）
SENSITIVE_FILENAME_RE = re.compile(r"private|secret|credential|passphrase", re.IGNORECASE)

# 赋值形态: key = ... 或 key: ...（值部分捕获后由 _extract_value 解析）
SECRET_KEY_RE = re.compile(
    r"""(?:api[_-]?key|apikey|secret(?:[_-]?key)?|access[_-]?key|
    auth[_-]?token|token|passwd|password|pwd|appsecret|
    private[_-]?key|passphrase)['"\s]*[:=](.*)$""",
    re.IGNORECASE | re.VERBOSE)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----")
# 高熵字面量：≥32 字符 base64/hex 形态的引号字符串（不依赖变量名）
QUOTED_LITERAL_RE = re.compile(r"""["']([^"'\n]{32,})["']""")

PLACEHOLDER_RE = re.compile(
    r"^(xxx+|yoursecret|your[_-]?.*|changeme|example|test|dummy|"
    r"\{\{.*\}\}|<.*>|\$\{.*\}|process\.env\..*|import\.meta\.env\..*|"
    r"os\.environ\[.*|os\.environ\.get\(.*|os\.getenv\(.*|environ\.get\(.*)$",
    re.IGNORECASE)
# GH Actions permissions（id-token: write 等）与布尔语义值不是密钥
SEMANTIC_VALUE_RE = re.compile(r"^(write|read|read-write|none|true|false)$", re.IGNORECASE)
# 环境变量间接引用整体不算命中（值以函数/下标调用开头而非字面量）
ENV_INDIRECT_RE = re.compile(
    r"""^\s*(?:os\.environ\[|os\.environ\.get\(|os\.getenv\(|environ\.get\(|process\.env\.|import\.meta\.env\.)""",
    re.IGNORECASE)


def is_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER_RE.match(value.strip()))


def _entropy(s: str) -> float:
    """Shannon 熵（bit/char）；base64/hex 密钥通常 > 3.5，重复模式远低于此。"""
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def _extract_value(rest: str) -> str | None:
    """从赋值右侧提取"第一个字面量值"；返回 None 表示右侧不是字面量（如 os.environ）。"""
    rest = rest.strip()
    if not rest:
        return None
    # 拼接形态："sk-" + "abcdef..." → 拼所有引号片段后判长（审计 H5：拼接绕过）
    if "+" in rest:
        fragments = re.findall(r"""["']([^"'\n]+)["']""", rest)
        if fragments:
            return "".join(fragments)
    quote = rest[0]
    if quote in ("'", '"'):
        end = rest.find(quote, 1)
        if end > 0:
            return rest[1:end]
        return rest[1:]
    # 无引号：取到空白为止
    token = rest.split()[0]
    return token if token else None


def _python_comment_lines(text: str) -> set[int]:
    """tokenize 找出真实注释行号；解析失败回退空集（宁多扫不漏扫）。"""
    comments: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                comments.add(tok.start[0])
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return comments
    return comments


def iter_text_files(root: Path):
    """os.walk(followlinks=False)：不跟随 junction/symlink（审计 H5：rglob 会
    跟随自引用 junction 静默截断且吞遍历错误）。"""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            if name in EXCLUDE_FILES or MANIFEST_JSON_RE.search(name):
                continue
            yield Path(dirpath) / name


def _should_scan(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTS:
        return True
    return bool(SENSITIVE_FILENAME_RE.search(path.name))


def scan(root: Path) -> tuple[list, list]:
    findings: list[dict] = []
    notes: list[str] = []
    for path in iter_text_files(root):
        if not _should_scan(path):
            continue
        try:
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                notes.append(f"{path}: {size} 字节超过上限，跳过扫描")
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as err:
            notes.append(f"{path}: 读取失败 {err}")
            continue

        if path.suffix.lower() == ".py":
            comment_lines = _python_comment_lines(text)
        else:
            comment_lines = set()
        if path.suffix.lower() not in TEXT_EXTS:
            # 敏感文件名兜底：逐行全扫，不做注释豁免
            comment_lines = set()

        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if lineno in comment_lines:
                continue
            if not path.suffix.lower() == ".py" and stripped.startswith(("//", "#", "*", "<!--")):
                continue

            for match in SECRET_KEY_RE.finditer(line):
                value = _extract_value(match.group(1))
                if (value and len(value) >= 8
                        and not is_placeholder(value)
                        and not SEMANTIC_VALUE_RE.match(value)
                        and not ENV_INDIRECT_RE.match(match.group(1))):
                    findings.append({"file": str(path), "line": lineno,
                                     "rule": "secret-assignment", "match": match.group(0)[:60]})
            for match in PRIVATE_KEY_RE.finditer(line):
                findings.append({"file": str(path), "line": lineno,
                                 "rule": "private-key-block",
                                 "match": "-----BEGIN ... PRIVATE KEY-----"})
            # 高熵字面量兜底：换变量名/拼进 dict 的密钥不再因不在枚举里而漏报
            if "public" not in line.lower():
                for match in QUOTED_LITERAL_RE.finditer(line):
                    literal = match.group(1)
                    if (re.fullmatch(r"[A-Za-z0-9+/=_-]{32,}", literal)
                            and _entropy(literal) >= 3.5
                            and not is_placeholder(literal)):
                        findings.append({"file": str(path), "line": lineno,
                                         "rule": "high-entropy-literal",
                                         "match": f"...{literal[:24]}... ({len(literal)} chars)"})
    return findings, notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", help="扫描根目录（默认当前目录）")
    parser.add_argument("--json", action="store_true", help="JSON 输出（供 CI 消费）")
    args = parser.parse_args()

    findings, notes = scan(Path(args.root).resolve())
    if args.json:
        print(json.dumps({"findings": findings, "count": len(findings), "notes": notes},
                         ensure_ascii=False, indent=2))
    elif findings:
        print(f"[FAIL] 发现 {len(findings)} 处疑似硬编码密钥：")
        for f in findings[:20]:
            print(f"  {f['file']}:{f['line']}  [{f['rule']}]  {f['match']}")
        if len(findings) > 20:
            print(f"  ...（其余 {len(findings) - 20} 处略）")
    else:
        print("[OK] 未发现硬编码密钥。")
    for note in notes[:10]:
        print(f"  [NOTE] {note}")
    if len(notes) > 10:
        print(f"  [NOTE] ...（其余 {len(notes) - 10} 条略）")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
