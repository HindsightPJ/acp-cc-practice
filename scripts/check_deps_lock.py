#!/usr/bin/env python3
"""check_deps_lock.py — 依赖精确锁定校验（RULE-VERLOCK 的机器化落地）

用法:
    python check_deps_lock.py [目录] [--json]
默认扫描当前目录下的 package.json / requirements*.txt / requirements*.lock /
pyproject.toml。发现范围版本时 exit 1（供 pre-commit / CI 拦截）。

规则（2026-10-19 v2，修复安全审计 H6）:
- requirements*.lock（pip-compile 产物，真正的锁定文件）按 == 严格校验，
  此前只匹配 *.txt、lock 文件完全不校验
- requirements*.txt 只放行 ==/===；~=/>=/<= 等"存在操作符即合规"的旧判据
  废除（与脚本自称的"精确锁定"对齐）
- package.json 范围检测补 >=/<=/</>（原 RANGE_RE 只认 ^ ~ * latest）
- pyproject.toml 的 PEP 508 兼容区间（>=x,<y）是声明层合法形态，精确锁定
  以 requirements.lock 为准；poetry 风格（^ ~）仍然拦截
- 目录遍历 os.walk(followlinks=False)；manifest 读取失败记入 notes，
  不再静默 continue（失败模式偏向漏报对锁门禁是最差取向）
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

EXCLUDE_DIRS = {"node_modules", ".git", "miniprogram_npm", "dist", "build",
                "unpackage", ".venv", "venv", "__pycache__"}
# npm：^ ~ * latest 以及 >=/<=/</> 开头的范围；前缀精确形态（file:/link:/workspace:/
# npm:/git+/http）另列白名单
RANGE_RE = re.compile(r"""["']?[\w@/.-]+["']?\s*:\s*["'](\^|~|\*|latest|>=?|<=?|<{1,2})""", re.IGNORECASE)
NPM_EXACT_PREFIX_RE = re.compile(r"^(file:|link:|workspace:|npm:|git\+|git://|git@|https?://|github:)", re.IGNORECASE)
REQ_LINE_RE = re.compile(r"^([A-Za-z0-9][.\-\w]*)(?:\[[^\]]+\])?\s*(===|==|~=|>=|<=|>|<)?\s*(.*)$")
PYPROJECT_RANGE_RE = re.compile(r"""=\s*["']?\^|=\s*["']?~\d|["']\^|["']~\d""")
LOCK_LINE_RE = re.compile(r"^([A-Za-z0-9][.\-\w]*)(?:\[[^\]]+\])?==(\S+)")
ALLOWED_PIP_OPS = {"==", "==="}


def iter_manifests(root: Path):
    """os.walk(followlinks=False)：不跟随 junction/symlink（审计 H5/H6 共性）。"""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            if (name == "package.json" or name == "pyproject.toml"
                    or re.match(r"requirements.*\.(txt|lock)$", name)):
                yield Path(dirpath) / name


def scan(root: Path) -> tuple[list, list]:
    findings: list[dict] = []
    notes: list[str] = []
    for path in iter_manifests(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as err:
            notes.append(f"{path}: 读取失败 {err}")
            continue
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            if path.name == "package.json":
                if stripped.startswith('"//'):  # 注释键跳过
                    continue
                for match in RANGE_RE.finditer(line):
                    findings.append({"file": str(path), "line": lineno,
                                     "rule": "npm-range-version", "match": match.group(0)[:60]})
                # 非数字开头且不在白名单前缀的版本值 = 非精确锁定（审计 H6：>= 绕过）
                for value_match in re.finditer(r"""["']([\w@/.-]+)["']\s*:\s*["']([^"']+)["']""", line):
                    value = value_match.group(2)
                    if value and not value[0].isdigit() and not NPM_EXACT_PREFIX_RE.match(value):
                        findings.append({"file": str(path), "line": lineno,
                                         "rule": "npm-unpinned",
                                         "match": f"{value_match.group(1)}: {value}"[:60]})
            elif re.match(r"requirements.*\.lock$", path.name):
                # 锁文件：除注释/空行/-- 选项外，每行必须是 name==version 精确形态
                if not stripped or stripped.startswith(("#", "-")):
                    continue
                if not LOCK_LINE_RE.match(stripped):
                    findings.append({"file": str(path), "line": lineno,
                                     "rule": "lock-not-pinned", "match": stripped[:60]})
            elif path.name.startswith("requirements"):
                if not stripped or stripped.startswith(("#", "-", ".")):
                    continue
                m = REQ_LINE_RE.match(stripped)
                if not m:
                    continue
                op = m.group(2)
                if op is None:
                    findings.append({"file": str(path), "line": lineno,
                                     "rule": "pip-unpinned", "match": stripped[:60]})
                elif op not in ALLOWED_PIP_OPS:
                    # 审计 H6：旧判据"存在任何操作符即合规"放行了 >= 区间
                    findings.append({"file": str(path), "line": lineno,
                                     "rule": "pip-range-version", "match": stripped[:60]})
            elif path.name == "pyproject.toml":
                for match in PYPROJECT_RANGE_RE.finditer(line):
                    findings.append({"file": str(path), "line": lineno,
                                     "rule": "poetry-range-version", "match": match.group(0)[:60]})
    return findings, notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    findings, notes = scan(Path(args.root).resolve())
    if args.json:
        print(json.dumps({"findings": findings, "count": len(findings), "notes": notes},
                         ensure_ascii=False, indent=2))
    elif findings:
        print(f"[FAIL] 发现 {len(findings)} 处未精确锁定的依赖版本（RULE-VERLOCK）：")
        for f in findings[:20]:
            print(f"  {f['file']}:{f['line']}  [{f['rule']}]  {f['match']}")
        if len(findings) > 20:
            print(f"  ...（其余 {len(findings) - 20} 处略）")
    else:
        print("[OK] 所有依赖版本均精确锁定。")
    for note in notes[:10]:
        print(f"  [NOTE] {note}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
