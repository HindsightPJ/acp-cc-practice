#!/usr/bin/env python3
"""check_deps_lock.py — 依赖精确锁定校验（RULE-VERLOCK 的机器化落地）

用法:
    python check_deps_lock.py [目录] [--json]
默认扫描当前目录下的 package.json / requirements*.txt / pyproject.toml。
发现 ^ ~ * latest 等范围版本时 exit 1（供 pre-commit / CI 拦截）。
"""
import argparse
import json
import re
import sys
from pathlib import Path

EXCLUDE_DIRS = {"node_modules", ".git", "miniprogram_npm", "dist", "build",
                "unpackage", ".venv", "venv", "__pycache__"}
RANGE_RE = re.compile(r"""["']?[\w@/.-]+["']?\s*:\s*["'](\^|~|\*|latest)""", re.IGNORECASE)
REQ_LINE_RE = re.compile(r"^[A-Za-z0-9[.\-_]+(?:\[[^\]]+\])?\s*(===|==|~=|>=|<=|>|<)?")
PYPROJECT_RANGE_RE = re.compile(r"""=\s*["']?\^|=\s*["']?~\d|["']\^|["']~\d""")


def iter_manifests(root: Path):
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.name == "package.json" or re.match(r"requirements.*\.txt$", path.name) or path.name == "pyproject.toml":
            yield path


def scan(root: Path) -> list:
    findings = []
    for path in iter_manifests(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            if path.name == "package.json":
                if stripped.startswith('"//'):  # 注释键跳过
                    continue
                for match in RANGE_RE.finditer(line):
                    findings.append({"file": str(path), "line": lineno,
                                     "rule": "npm-range-version", "match": match.group(0)[:60]})
            elif path.name.startswith("requirements"):
                if not stripped or stripped.startswith(("#", "-", ".")):
                    continue
                m = REQ_LINE_RE.match(stripped)
                if m and m.group(1) is None:
                    findings.append({"file": str(path), "line": lineno,
                                     "rule": "pip-unpinned", "match": stripped[:60]})
            elif path.name == "pyproject.toml":
                for match in PYPROJECT_RANGE_RE.finditer(line):
                    findings.append({"file": str(path), "line": lineno,
                                     "rule": "poetry-range-version", "match": match.group(0)[:60]})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    findings = scan(Path(args.root).resolve())
    if args.json:
        print(json.dumps({"findings": findings, "count": len(findings)}, ensure_ascii=False, indent=2))
    elif findings:
        print(f"[FAIL] 发现 {len(findings)} 处未精确锁定的依赖版本（RULE-VERLOCK）：")
        for f in findings[:20]:
            print(f"  {f['file']}:{f['line']}  [{f['rule']}]  {f['match']}")
        if len(findings) > 20:
            print(f"  ...（其余 {len(findings) - 20} 处略）")
    else:
        print("[OK] 所有依赖版本均精确锁定。")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
