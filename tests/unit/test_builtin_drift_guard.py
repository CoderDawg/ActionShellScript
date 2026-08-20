from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable

from core.runtime.builtins.builtin_registry import BUILTIN_FUNCTION_NAMES
from core.runtime.builtins.builtin_registry import format_builtin_function_name


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_PATH = REPO_ROOT / "core" / "runtime" / "script_runtime.py"
DOCS_PATH = REPO_ROOT / "docs" / "user" / "builtin_coverage_map.md"


def _format_names(names: Iterable[str]) -> str:
    formatted = [format_builtin_function_name(name) for name in sorted(names)]
    return ", ".join(formatted) if formatted else "<none>"


def _load_docs_builtin_names() -> set[str]:
    text = DOCS_PATH.read_text(encoding="utf-8")
    return {match.lower() for match in re.findall(r"^\| `([^`]+)` \|", text, flags=re.MULTILINE)}


def _load_runtime_builtin_names() -> set[str]:
    module = ast.parse(RUNTIME_PATH.read_text(encoding="utf-8"), filename=str(RUNTIME_PATH))
    builtin_names: set[str] = set()

    for node in module.body:
        if not isinstance(node, ast.ClassDef) or node.name != "ScriptRuntime":
            continue

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "_HOST_INTERACTION_BUILTIN_NAMES":
                        builtin_names.update(_string_set_from_ast(item.value))
            elif isinstance(item, ast.FunctionDef) and item.name == "_execute_builtin_call":
                builtin_names.update(_builtin_names_from_execute_builtin_call(item))

    return builtin_names


def _string_set_from_ast(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Set):
        return {
            element.value.lower()
            for element in node.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        }

    if isinstance(node, ast.Call):
        values: set[str] = set()
        for arg in node.args:
            values.update(_string_set_from_ast(arg))
        return values

    return set()


def _builtin_names_from_execute_builtin_call(function_node: ast.FunctionDef) -> set[str]:
    builtin_names: set[str] = set()
    for node in ast.walk(function_node):
        if not isinstance(node, ast.Compare):
            continue
        if not isinstance(node.left, ast.Name) or node.left.id != "normalized_name":
            continue
        if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
            continue
        if len(node.comparators) != 1:
            continue
        comparator = node.comparators[0]
        if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
            builtin_names.add(comparator.value.lower())
    return builtin_names


def _drift_message(
    *,
    registry_missing: set[str],
    docs_missing: set[str],
    docs_extra: set[str],
    runtime_extra: set[str],
) -> str:
    lines = [
        "Builtin drift detected across `core/runtime/builtins/builtin_registry.py`,",
        "`core/runtime/script_runtime.py`, and `docs/user/builtin_coverage_map.md`.",
    ]
    if registry_missing:
        lines.append(
            f"- Missing from runtime dispatch surface ({len(registry_missing)}): {_format_names(registry_missing)}"
        )
    if runtime_extra:
        lines.append(
            f"- Present in runtime dispatch surface but not registry ({len(runtime_extra)}): {_format_names(runtime_extra)}"
        )
    if docs_missing:
        lines.append(
            f"- Missing from coverage map ({len(docs_missing)}): {_format_names(docs_missing)}"
        )
    if docs_extra:
        lines.append(
            f"- Present in coverage map but not registry ({len(docs_extra)}): {_format_names(docs_extra)}"
        )
    return "\n".join(lines)


def test_builtin_registry_runtime_and_coverage_map_stay_in_sync() -> None:
    registry_names = set(BUILTIN_FUNCTION_NAMES)
    runtime_names = _load_runtime_builtin_names()
    docs_names = _load_docs_builtin_names()

    registry_missing = registry_names - runtime_names
    runtime_extra = runtime_names - registry_names
    docs_missing = registry_names - docs_names
    docs_extra = docs_names - registry_names

    assert not (registry_missing or runtime_extra or docs_missing or docs_extra), _drift_message(
        registry_missing=registry_missing,
        docs_missing=docs_missing,
        docs_extra=docs_extra,
        runtime_extra=runtime_extra,
    )
