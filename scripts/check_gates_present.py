#!/usr/bin/env python3
"""项目侧门禁存在性 + 接入性校验器（machine_checks §5.4）。

存在它理由：`machine_checks` §九 把 check_secrets.py / check_deps_lock.py 记为门禁，
但"规则库里有"不等于"项目里有"，更不等于"项目里在跑"——PromptLib 审计 C5 正是
"门禁脚本一个不缺、可惜没人调用"的结果。本脚本只回答后两件事。

v2（2026-10-19，修复安全审计 H7）:
- 接入判定从"任意文本含脚本名"改为"非注释行含脚本名"——原纯子串匹配下，
  一行 TODO 注释提到脚本名即可让门禁自检变绿
- GATE_SCRIPTS 纳入本脚本自身；ruff/mypy/pytest/bandit 四个工具的 CI/钩子
  接入一并校验（bandit 曾只挂本地 pre-push、CI 不跑，本脚本自己也从未被跑）
- wiring 文件读取失败不再静默：记 WARN 并按"未证明接入"处理

用法：python scripts/check_gates_present.py <project_root>
退出码：0 = 全部存在且已接入；1 = 缺失或未接入；2 = 用法/参数错误
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

# Windows 控制台默认 GBK，中文提示在其它终端会变乱码（与 check_rules.py 同一处理）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

GATE_SCRIPTS = ("check_secrets.py", "check_deps_lock.py", "check_gates_present.py")
# 必须出现在 CI/钩子等 wiring 配置里的工具链（存在性不查项目目录——它们是环境工具）
TOOL_WIRING = ("ruff", "mypy", "pytest", "bandit")
# 能证明"脚本确实会被执行"的配置位置；命中任意一处即视为已接入
WIRING_FILES = (
    "package.json",
    ".pre-commit-config.yaml",
    ".pre-commit-config.yml",
    "lefthook.yml",
    "lefthook.yaml",
    "Makefile",
    "pyproject.toml",
    ".gitlab-ci.yml",
    "azure-pipelines.yml",
)
WIRING_DIRS = (".husky", ".github/workflows")
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "unpackage", "__pycache__", ".venv"}
_COMMENT_LINE_RE = re.compile(r"^\s*(#|//|<!--|\*|\"//)")


def _executable_lines(text: str) -> list[str]:
    """去掉纯注释行后的配置文本——接入证据必须来自可执行行（审计 H7：
    一行 TODO 注释提到脚本名就能让旧版自检变绿）。"""
    return [line for line in text.splitlines() if not _COMMENT_LINE_RE.match(line)]


def collect_wiring_lines(root: Path) -> tuple[list[str], list[str]]:
    """汇总所有可能引用门禁脚本的配置（按行）。返回 (可执行行列表, notes)。"""
    lines: list[str] = []
    notes: list[str] = []
    for rel in WIRING_FILES:
        candidate = root / rel
        if candidate.is_file():
            try:
                lines.extend(_executable_lines(candidate.read_text(encoding="utf-8", errors="ignore")))
            except OSError as err:
                notes.append(f"wiring 文件读取失败（按未证明接入处理）：{rel}: {err}")
    for rel in WIRING_DIRS:
        hook_dir = root / rel
        if not hook_dir.is_dir():
            continue
        for hook_file in hook_dir.rglob("*"):
            if hook_file.is_file() and not SKIP_DIRS & set(hook_file.parts):
                try:
                    lines.extend(_executable_lines(hook_file.read_text(encoding="utf-8", errors="ignore")))
                except OSError as err:
                    notes.append(f"wiring 文件读取失败（按未证明接入处理）：{hook_file}: {err}")
    return lines, notes


def npm_scripts_lines(root: Path) -> list[str]:
    """package.json 的 scripts 段单独取，避免注释/依赖名误判为接入。"""
    manifest = root / "package.json"
    if not manifest.is_file():
        return []
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8", errors="ignore"))
    except (json.JSONDecodeError, OSError) as parse_error:
        print(f"[GATES_WARN] package.json 解析失败，跳过该证据源：{parse_error}")
        return []
    scripts = raw.get("scripts") if isinstance(raw, dict) else None
    return list(scripts.values()) if isinstance(scripts, dict) else []


def locate(root: Path, script_name: str) -> Path | None:
    for rel in (f"scripts/{script_name}", script_name):
        candidate = root / rel
        if candidate.is_file():
            return candidate
    return None


def _sha(path: Path) -> str:
    raw = path.read_bytes().replace(bytes([13, 10]), bytes([10])).replace(bytes([13]), bytes([10]))
    return hashlib.sha256(raw).hexdigest()


def locate_baseline() -> dict | None:
    """库侧基线：任一已安装 global-rules skill 的 assets/project-manifest.json。

    注意：这是机器本地辅助判据（不同机器可有不同安装状态），fresh clone 上
    仅降级为项目内漂移校验，不影响主判定。
    """
    for rel in (".agents", ".qwenworkcn", ".trae-cn", ".workbuddy"):
        cand = Path.home() / rel / "skills" / "global-rules" / "assets" / "project-manifest.json"
        if cand.is_file():
            try:
                return json.loads(cand.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
    return None


def check_rule_copies(root: Path) -> tuple[list, list]:
    """规则副本新鲜度：项目内文档是静态快照，库更新了不会自己跟着动。

    返回 (failures, notes)。DRIFT/STALE 是红灯；缺基线只提示——否则老项目一升级检查器就全红。
    """
    manifest_path = root / ".ai_context" / "RULES_MANIFEST.json"
    if not manifest_path.is_file():
        return [], ["[RULES_MANIFEST_MISSING] 未记录规则副本基线，无法判断项目内文档是否过期"
                    "（跑一次 init_project.py 即生成）"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as err:
        return [f"[RULES_MANIFEST_UNREADABLE] {manifest_path}: {err}"], []

    baseline = locate_baseline()
    failures: list[str] = []
    for rec in manifest.get("files", []):
        rel, expected = rec.get("path", ""), rec.get("sha256", "")
        target = root / rel
        if not target.is_file():
            failures.append(f"[RULES_COPY_MISSING] 基线记录的文件在项目里不存在：{rel}")
            continue
        if expected and _sha(target) != expected:
            failures.append(f"[RULES_COPY_DRIFT] {rel} 与基线记录不一致"
                            f"（项目内被手改，或换过版本没重记基线）")
        if baseline:
            live = baseline.get("files", {}).get(rel, {}).get("sha256", "")
            recorded_up = rec.get("upstream_sha256", "")
            if live and recorded_up and live != recorded_up:
                failures.append(f"[RULES_COPY_STALE] {rel} 的库基线已更新"
                                f"（清单记于 {manifest.get('generated_at', '?')}）——"
                                f"项目里这份是旧快照，先 diff 差异再重跑 init_project.py --refresh")
    notes = [f"规则副本基线：{manifest.get('generated_at', '?')}，"
             f"覆盖 {len(manifest.get('files', []))} 个文件"
             + ("" if baseline else "；未找到库侧 project-manifest，仅校验项目内漂移")
             + ("；库侧基线为机器本地辅助判据" if baseline else "")]
    return failures, notes


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("用法：python scripts/check_gates_present.py <project_root>")
        return 2
    root = Path(argv[1])
    if not root.is_dir():
        print(f"[GATES_ERROR] 路径不存在或不是目录：{root}")
        return 2

    wiring_lines, wiring_notes = collect_wiring_lines(root)
    wiring_lines.extend(npm_scripts_lines(root))
    wiring_text = "\n".join(wiring_lines)

    missing: list[str] = []
    unwired: list[str] = []

    for script_name in GATE_SCRIPTS:
        if locate(root, script_name) is None:
            missing.append(script_name)
        elif not any(script_name in line for line in wiring_lines):
            unwired.append(script_name)

    unwired_tools = [tool for tool in TOOL_WIRING
                     if not re.search(rf"\b{re.escape(tool)}\b", wiring_text)]

    rule_failures, rule_notes = check_rule_copies(root)
    for note in rule_notes + wiring_notes:
        print(f"  [NOTE] {note}")

    if not missing and not unwired and not unwired_tools and not rule_failures:
        print("[GATES_OK] 门禁脚本已落到本项目且已被引用；工具链接入完整；规则副本与基线一致")
        return 0

    if missing:
        print(f"[GATES_MISSING] 项目缺失门禁脚本：{missing}")
        print("  §九 声称随库分发，但项目侧未复制；对应 [阻塞] 项实际无法执行。")
    if unwired:
        print(f"[GATES_NOT_WIRED] 以下脚本已存在但从未被任何可执行入口调用：{unwired}")
        print("  存在 ≠ 生效。重蹈审计 C5：脚本在目录里，门禁却从未跑过。")
    if unwired_tools:
        print(f"[GATES_TOOLS_NOT_WIRED] 以下质量工具未出现在 CI/钩子的可执行配置中：{unwired_tools}")
        print("  审计 H7：bandit 只挂本地 pre-push、CI 不跑时，绕过本地钩子即可绕过扫描。")
    for msg in rule_failures:
        print(f"  {msg}")
    print("  修复：① 随 AGENTS.md 复制到项目 scripts/；② 挂进 pre-commit / npm script / CI；"
          "③ 规则文档过期或漂移则先 diff 再更新副本，并重跑 init_project.py 刷新基线；④ 重跑本脚本。")
    print("  确因形态无法接入（纯离线无构建链）：交付说明标 [NO_LINT_GATE] 并手动补跑对应脚本。")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
