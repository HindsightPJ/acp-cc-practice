#!/usr/bin/env python3
"""check_secrets.py — 硬编码密钥扫描（audit_checklist §6.1#8 的机器化落地）

用法:
    python check_secrets.py [目录] [--json]
默认扫描当前目录。命中疑似硬编码密钥时 exit 1（供 pre-commit / CI 拦截）。
规则: 只认"赋值给字面量"的形态，占位符（xxx/your/TODO/{{}}/<>) 不算命中。
"""
import argparse
import json
import re
import sys
from pathlib import Path

# 排除目录与文件（依赖/构建产物/锁文件误报率极高，一律跳过）
EXCLUDE_DIRS = {"node_modules", ".git", "miniprogram_npm", "dist", "build",
                "unpackage", ".venv", "venv", "__pycache__", ".workbuddy"}
EXCLUDE_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "check_secrets.py"}
TEXT_EXTS = {".js", ".ts", ".vue", ".py", ".json", ".yaml", ".yml", ".env",
             ".wxml", ".wxss", ".md", ".html", ".css", ".sh", ".toml", ".ini"}

# 赋值形态: key = "value" 或 key: "value" 或 key='value'
# （2026-09-27 修正：原 VERBOSE 模式下 alternation 内混入两个裸引号字面量，产生多余分支）
SECRET_KEY_RE = re.compile(
    r"""(?:api[_-]?key|apikey|secret(?:[_-]?key)?|access[_-]?key|
    auth[_-]?token|token|passwd|password|pwd|appsecret|
    private[_-]?key)['"\s]*[:=]['"\s]*([^\s'"]{8,})""",
    re.IGNORECASE | re.VERBOSE)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")

PLACEHOLDER_RE = re.compile(
    r"^(xxx+|yoursecret|your[_-]?.*|changeme|example|test|dummy|"
    r"\{\{.*\}\}|<.*>|\$\{.*\}|process\.env\..*|import\.meta\.env\..*)$", re.IGNORECASE)


def is_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER_RE.match(value.strip()))


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.name in EXCLUDE_FILES:
            continue
        if path.suffix.lower() not in TEXT_EXTS:
            continue
        yield path


def scan(root: Path) -> list:
    findings = []
    for path in iter_text_files(root):
        try:
            for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                stripped = line.strip()
                # 注释行不扫（文档示例/规则文件本身常含 key 字样）
                if stripped.startswith(("//", "#", "*", "<!--")):
                    continue
                for match in SECRET_KEY_RE.finditer(line):
                    if not is_placeholder(match.group(1)):
                        findings.append({"file": str(path), "line": lineno,
                                         "rule": "secret-assignment", "match": match.group(0)[:60]})
                for match in PRIVATE_KEY_RE.finditer(line):
                    findings.append({"file": str(path), "line": lineno,
                                     "rule": "private-key-block", "match": "-----BEGIN ... PRIVATE KEY-----"})
        except OSError:
            continue
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", help="扫描根目录（默认当前目录）")
    parser.add_argument("--json", action="store_true", help="JSON 输出（供 CI 消费）")
    args = parser.parse_args()

    findings = scan(Path(args.root).resolve())
    if args.json:
        print(json.dumps({"findings": findings, "count": len(findings)}, ensure_ascii=False, indent=2))
    elif findings:
        print(f"[FAIL] 发现 {len(findings)} 处疑似硬编码密钥：")
        for f in findings[:20]:
            print(f"  {f['file']}:{f['line']}  [{f['rule']}]  {f['match']}")
        if len(findings) > 20:
            print(f"  ...（其余 {len(findings) - 20} 处略）")
    else:
        print("[OK] 未发现硬编码密钥。")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
