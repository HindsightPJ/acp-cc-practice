#!/usr/bin/env python3
"""项目侧门禁存在性 + 接入性校验器（machine_checks §5.4）。

存在它理由：`machine_checks` §九 把 check_secrets.py / check_deps_lock.py 记为门禁，
但"规则库里有"不等于"项目里有"，更不等于"项目里在跑"——PromptLib 审计 C5 正是
"门禁脚本一个不缺、可惜没人调用"的结果。本脚本只回答后两件事。

用法：python scripts/check_gates_present.py <project_root>
退出码：0 = 全部存在且已接入；1 = 缺失或未接入；2 = 用法/参数错误
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

# Windows 控制台默认 GBK，中文提示在其它终端会变乱码（与 check_rules.py 同一处理）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

GATE_SCRIPTS = ("check_secrets.py", "check_deps_lock.py")
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


def collect_wiring_text(root: Path) -> str:
    """汇总所有可能引用门禁脚本的配置文本。只找可能的位置，避免全仓遍历。"""
    chunks: list[str] = []
    for rel in WIRING_FILES:
        candidate = root / rel
        if candidate.is_file():
            chunks.append(candidate.read_text(encoding="utf-8", errors="ignore"))
    for rel in WIRING_DIRS:
        hook_dir = root / rel
        if not hook_dir.is_dir():
            continue
        for hook_file in hook_dir.rglob("*"):
            if hook_file.is_file() and not SKIP_DIRS & set(hook_file.parts):
                chunks.append(hook_file.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


def npm_scripts_text(root: Path) -> str:
    """package.json 的 scripts 段单独取，避免注释/依赖名误判为接入。"""
    manifest = root / "package.json"
    if not manifest.is_file():
        return ""
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8", errors="ignore"))
    except (json.JSONDecodeError, OSError) as parse_error:
        print(f"[GATES_WARN] package.json 解析失败，跳过该证据源：{parse_error}")
        return ""
    scripts = raw.get("scripts") if isinstance(raw, dict) else None
    return " ".join(scripts.values()) if isinstance(scripts, dict) else ""


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
    """库侧基线：任一已安装 global-rules skill 的 assets/project-manifest.json。"""
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
             + ("" if baseline else "；未找到库侧 project-manifest，仅校验项目内漂移")]
    return failures, notes


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("用法：python scripts/check_gates_present.py <project_root>")
        return 2
    root = Path(argv[1])
    if not root.is_dir():
        print(f"[GATES_ERROR] 路径不存在或不是目录：{root}")
        return 2

    wiring = collect_wiring_text(root) + "\n" + npm_scripts_text(root)
    missing: list[str] = []
    unwired: list[str] = []

    for script_name in GATE_SCRIPTS:
        if locate(root, script_name) is None:
            missing.append(script_name)
        elif script_name not in wiring:
            unwired.append(script_name)

    rule_failures, rule_notes = check_rule_copies(root)
    for note in rule_notes:
        print(f"  [NOTE] {note}")

    if not missing and not unwired and not rule_failures:
        print("[GATES_OK] 门禁脚本已落到本项目且已被引用；规则副本与基线一致")
        return 0

    if missing:
        print(f"[GATES_MISSING] 项目缺失门禁脚本：{missing}")
        print("  §九 声称随库分发，但项目侧未复制；对应 [阻塞] 项实际无法执行。")
    if unwired:
        print(f"[GATES_NOT_WIRED] 以下脚本已存在但从不被任何入口调用：{unwired}")
        print("  存在 ≠ 生效。重蹈审计 C5：脚本在目录里，门禁却从未跑过。")
    for msg in rule_failures:
        print(f"  {msg}")
    print("  修复：① 随 AGENTS.md 复制到项目 scripts/；② 挂进 pre-commit / npm script / CI；"
          "③ 规则文档过期或漂移则先 diff 再更新副本，并重跑 init_project.py 刷新基线；④ 重跑本脚本。")
    print("  确因形态无法接入（纯离线无构建链）：交付说明标 [NO_LINT_GATE] 并手动补跑对应脚本。")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
