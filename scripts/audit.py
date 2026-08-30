#!/usr/bin/env python3
"""Report repository incompleteness that can otherwise hide behind passing tests.

The audit is intentionally static and read-only.  It checks wiring and documentation,
then reports corpus health without attempting to seed, repair, or generate any data.
"""

from __future__ import annotations

import ast
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
CODE_DIRS = ("agent", "pipeline", "mcp")
DOC_PATHS = ("README.md", "CLAUDE.md", "PLAN.md", "NEXT_INPUTS.md")
MARKER_RE = re.compile(r"\b(?:TODO|FIXME|XXX|HACK)\b|NotImplementedError")
PATH_RE = re.compile(
    r"(?<![\w.-])(?P<path>(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.(?:md|py|json|npy|npz|txt|toml|mmd|docx))(?![\w.-])"
)


@dataclass(frozen=True)
class Finding:
    category: str
    detail: str


def python_files(root: Path = ROOT) -> list[Path]:
    return sorted(
        path
        for directory in CODE_DIRS
        for path in (root / directory).rglob("*.py")
        if "__pycache__" not in path.parts
    )


def all_python_files(root: Path = ROOT) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if not {".git", ".venv", "__pycache__"}.intersection(path.parts)
    )


def module_name(path: Path, root: Path = ROOT) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def imported_modules(path: Path, tree: ast.AST, root: Path = ROOT) -> set[str]:
    """Return import targets, including children imported from a package."""

    current = module_name(path, root)
    package = current.rsplit(".", 1)[0] if "." in current else ""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parent = package.split(".") if package else []
                anchor = parent[: max(0, len(parent) - node.level + 1)]
                base = ".".join([*anchor, base]).strip(".")
            if base:
                found.add(base)
            for alias in node.names:
                if alias.name != "*" and base:
                    found.add(f"{base}.{alias.name}")
    return found


def orphan_modules(root: Path = ROOT) -> list[Finding]:
    files = python_files(root)
    modules = {module_name(path, root): path for path in files}
    imported: set[str] = set()
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in all_python_files(root))
    for path in all_python_files(root):
        imported.update(imported_modules(path, parse(path), root))
    findings: list[Finding] = []
    for name, path in modules.items():
        if path.name == "__init__.py":
            continue
        dynamically_loaded = str(path.relative_to(root)) in source_text
        if name not in imported and not dynamically_loaded:
            findings.append(Finding("orphan modules", str(path.relative_to(root))))
    return findings


def mcp_tool_names(server_path: Path) -> set[str]:
    tree = parse(server_path)
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "mcp"
                and decorator.func.attr == "tool"
            ):
                names.add(node.name)
    return names


def unwired_mcp_tools(root: Path = ROOT) -> list[Finding]:
    agent_source = "\n".join(
        path.read_text(encoding="utf-8") for path in (root / "agent").rglob("*.py")
    )
    return [
        Finding("unwired MCP tools", name)
        for name in sorted(mcp_tool_names(root / "mcp" / "server.py"))
        if not re.search(rf"\b{re.escape(name)}\b", agent_source)
    ]


def config_constants(path: Path) -> set[str]:
    tree = parse(path)
    return {
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets if isinstance(node, ast.Assign) else [node.target]
        )
        if isinstance(target, ast.Name) and target.id.isupper()
    }


def dead_config(root: Path = ROOT) -> list[Finding]:
    constants = config_constants(root / "agent" / "config.py")
    used: set[str] = set()
    for path in all_python_files(root):
        if path == root / "agent" / "config.py":
            continue
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Name) and node.id in constants:
                used.add(node.id)
            if isinstance(node, ast.Attribute) and node.attr in constants:
                used.add(node.attr)
    architecture = (root / "docs" / "architecture.md")
    documented = architecture.read_text(encoding="utf-8") if architecture.is_file() else ""
    return [
        Finding("dead config", name)
        for name in sorted(constants - used)
        if f"audit-accept: agent/config.py:{name}" not in documented
    ]


def role_skills(path: Path) -> set[str]:
    tree = parse(path)
    for node in tree.body:
        target = (
            node.target
            if isinstance(node, ast.AnnAssign)
            else node.targets[0]
            if isinstance(node, ast.Assign) and len(node.targets) == 1
            else None
        )
        value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
        if not isinstance(target, ast.Name):
            continue
        if target.id != "ROLE_SKILLS" or not isinstance(value, ast.Dict):
            continue
        return {
            value.value
            for item in value.values
            if isinstance(item, (ast.Tuple, ast.List))
            for value in item.elts
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
        }
    return set()


def orphan_skills(root: Path = ROOT) -> list[Finding]:
    declared = role_skills(root / "agent" / "skills.py")
    discovered = {
        path.parent.name for path in (root / ".claude" / "skills").glob("*/SKILL.md")
    }
    return [Finding("orphan skills", name) for name in sorted(discovered - declared)]


def untested_modules(root: Path = ROOT) -> list[Finding]:
    tests = "\n".join(
        path.read_text(encoding="utf-8") for path in (root / "tests").rglob("*.py")
    )
    findings: list[Finding] = []
    for path in python_files(root):
        if path.name == "__init__.py":
            continue
        dotted = module_name(path, root)
        if dotted not in tests and not re.search(rf"\b{re.escape(path.stem)}\b", tests):
            findings.append(Finding("untested modules", str(path.relative_to(root))))
    return findings


def markers(root: Path = ROOT) -> list[Finding]:
    excluded = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
    findings: list[Finding] = []
    for path in root.rglob("*"):
        if not path.is_file() or excluded.intersection(path.parts):
            continue
        if path.suffix.lower() not in {".md", ".py", ".toml", ".json", ".mmd"}:
            continue
        if path.relative_to(root) in {Path("scripts/audit.py"), Path("tests/test_audit.py")}:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if MARKER_RE.search(line):
                findings.append(Finding("debt markers", f"{path.relative_to(root)}:{number}"))
    return findings


def state_fields(path: Path) -> set[str]:
    tree = parse(path)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "DraftState":
            return {
                item.target.id
                for item in node.body
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
            }
    return set()


def unread_state_fields(root: Path = ROOT) -> list[Finding]:
    fields = state_fields(root / "agent" / "state.py")
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in all_python_files(root)
        if path != root / "agent" / "state.py"
    )
    return [
        Finding("unread state fields", name)
        for name in sorted(fields)
        if not re.search(rf"[\"']{re.escape(name)}[\"']", source)
    ]


def documentation_paths(root: Path = ROOT) -> Iterable[Path]:
    yield from (root / name for name in DOC_PATHS if (root / name).is_file())
    yield from sorted((root / "docs").rglob("*.md"))


def broken_doc_references(root: Path = ROOT) -> list[Finding]:
    project_roots = {
        "agent",
        "corpus",
        "docs",
        "drafts",
        "evals",
        "intel",
        "mcp",
        "ops",
        "pipeline",
        "private",
        "scripts",
        "tests",
    }
    findings: list[Finding] = []
    seen: set[tuple[Path, str]] = set()
    for doc in documentation_paths(root):
        in_fence = False
        for line in doc.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in PATH_RE.finditer(line):
                value = match.group("path").rstrip(".,;:)")
                first = value.split("/", 1)[0]
                if (
                    value.startswith(("http://", "https://"))
                    or first not in project_roots
                    or "YYYY" in value
                    or (doc.name == "PLAN.md" and value.startswith("intel/reports/"))
                ):
                    continue
                candidate = root / value
                private_template = root / "corpus" / "identity" / Path(value).name
                if value.startswith("private/") and private_template.is_file():
                    continue
                key = (doc, value)
                if key not in seen and not candidate.exists():
                    seen.add(key)
                    findings.append(
                        Finding("broken doc references", f"{doc.relative_to(root)} → {value}")
                    )
    return findings


def missing_plan_outputs(root: Path = ROOT) -> list[Finding]:
    """Check the explicit generated reports promised by the historical plan."""

    plan = (root / "PLAN.md").read_text(encoding="utf-8")
    outputs = {match.group("path") for match in PATH_RE.finditer(plan)}
    declared = {
        value
        for value in outputs
        if value.startswith(("intel/reports/", "ops/metrics/"))
    }
    return [
        Finding("missing PLAN outputs", value)
        for value in sorted(declared)
        if not (root / value).exists()
    ]


def data_health(root: Path = ROOT) -> list[str]:
    sys.path.insert(0, str(root))
    from pipeline import claims, common, voice

    posts = common.load_all_posts()
    clusters = Counter(
        int(post["template_id"])
        for post in posts
        if isinstance(post.get("template_id"), int)
    )
    xfactor_count = sum(isinstance(post.get("x_factor"), (int, float)) for post in posts)
    author_count = len(
        {str(post.get("author_handle") or "") for post in posts if post.get("author_handle")}
    )
    fingerprint = voice.load_fingerprint()
    return [
        "data health",
        f"  posts: {len(posts)}",
        f"  distinct authors: {author_count}",
        f"  x-factor coverage: {xfactor_count}/{len(posts)}",
        "  template-cluster size distribution: "
        + (
            ", ".join(
                f"size {size}: {count}"
                for size, count in sorted(Counter(clusters.values()).items())
            )
            or "none"
        ),
        f"  singleton templates: {sum(size == 1 for size in clusters.values())}",
        f"  allowlist size: {len(claims.load_allowlist())}",
        "  voice fingerprint: "
        f"{int(fingerprint.get('sample_count') or 0)} samples, "
        f"{int(fingerprint.get('word_count') or 0)} words",
    ]


def ungated_artifacts(root: Path = ROOT) -> list[Finding]:
    queue = root / "drafts" / "queue"
    required = (
        "claims_checked: true",
        "voice_check: pass",
        "confidential_terms_check: pass",
        "created_at:",
        "## Review notes",
    )
    findings: list[Finding] = []
    for path in sorted(queue.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if not all(value in text for value in required):
            findings.append(Finding("ungated queue artifacts", str(path.relative_to(root))))
    return findings


def collect(root: Path = ROOT) -> tuple[list[Finding], list[str]]:
    checks = (
        orphan_modules,
        unwired_mcp_tools,
        dead_config,
        orphan_skills,
        untested_modules,
        markers,
        unread_state_fields,
        broken_doc_references,
        missing_plan_outputs,
        ungated_artifacts,
    )
    findings = [finding for check in checks for finding in check(root)]
    return findings, data_health(root)


def main() -> int:
    findings, health = collect()
    grouped: dict[str, list[str]] = defaultdict(list)
    for finding in findings:
        grouped[finding.category].append(finding.detail)
    print("Repository audit")
    print("=" * 16)
    if grouped:
        for category, details in grouped.items():
            print(f"{category} ({len(details)}):")
            for detail in details:
                print(f"  - {detail}")
    else:
        print("No incompleteness found.")
    print()
    print("\n".join(health))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
