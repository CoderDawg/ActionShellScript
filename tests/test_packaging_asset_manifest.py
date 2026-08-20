from __future__ import annotations

import ast
import sys
import types
from pathlib import Path

from packaging.asset_manifest import load_asset_manifest


def _load_pyinstaller_spec_namespace() -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[1]
    spec_path = repo_root / "packaging" / "pyinstaller" / "ActionShellScript.spec"
    source = spec_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(spec_path))

    namespace: dict[str, object] = {}

    collect_optional_pyside6_modules = next(
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name == "_collect_optional_pyside6_modules"
    )
    excluded_optional_pyside6_modules = next(
        node
        for node in module_ast.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_excluded_optional_pyside6_modules"
            for target in node.targets
        )
    )

    fake_pkgutil = types.ModuleType("pkgutil")
    fake_pkgutil.iter_modules = lambda _path: [types.SimpleNamespace(name="QtPrintSupport")]

    fake_pyside6 = types.ModuleType("PySide6")
    fake_pyside6.__path__ = ["<fake-pyside6-path>"]

    original_pkgutil = sys.modules.get("pkgutil")
    original_pyside6 = sys.modules.get("PySide6")
    sys.modules["pkgutil"] = fake_pkgutil
    sys.modules["PySide6"] = fake_pyside6
    try:
        helper_module = ast.Module(
            body=[
                ast.Import(names=[ast.alias(name="pkgutil")]),
                ast.Import(names=[ast.alias(name="PySide6")]),
                collect_optional_pyside6_modules,
                excluded_optional_pyside6_modules,
            ],
            type_ignores=[],
        )
        ast.fix_missing_locations(helper_module)
        exec(compile(helper_module, filename=str(spec_path), mode="exec"), namespace)
    finally:
        if original_pkgutil is None:
            sys.modules.pop("pkgutil", None)
        else:
            sys.modules["pkgutil"] = original_pkgutil
        if original_pyside6 is None:
            sys.modules.pop("PySide6", None)
        else:
            sys.modules["PySide6"] = original_pyside6

    return namespace


def test_packaging_asset_manifest_lists_existing_files() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = repo_root / "packaging" / "asset_manifest.json"
    manifest = load_asset_manifest(manifest_path)

    runtime_assets = manifest.runtime_assets
    assert manifest.installer_setup_icon in runtime_assets

    for relative_path in runtime_assets:
        assert (repo_root / relative_path).exists()


def test_packaging_release_files_do_not_duplicate_runtime_asset_literals() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    build_release_text = (repo_root / "packaging" / "scripts" / "build_release.ps1").read_text(encoding="utf-8")

    for asset_literal in (
        "apps\\desktop\\assets\\combo_box_arrow.svg",
        "apps\\desktop\\assets\\retro_pixelated_teal_smiling_frog.ico",
        "apps\\desktop\\assets\\retro_pixelated_teal_smiling_frog.png",
        "assets\\icons\\msc_debug-breakpoint.png",
    ):
        assert asset_literal not in build_release_text


def test_packaging_installer_cli_shortcut_keeps_console_open() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    installer_text = (repo_root / "packaging" / "installer" / "ActionShellScript.iss").read_text(encoding="utf-8")
    spec_text = (repo_root / "packaging" / "pyinstaller" / "ActionShellScript.spec").read_text(
        encoding="utf-8"
    )
    launcher_text = (
        repo_root
        / "packaging"
        / "pyinstaller"
        / "launchers"
        / "ass-cli-help.cmd"
    ).read_text(encoding="utf-8")

    assert 'Name: "{group}\\ActionShellScript CLI"' in installer_text
    assert 'Filename: "{cmd}"' in installer_text
    assert '/k ""{app}\\ass-cli\\ass-cli.exe"" --help' in installer_text
    assert 'IconFilename: "{app}\\ass-cli\\ass-cli.exe"' in installer_text
    assert 'ass-cli-help.cmd' not in spec_text
    assert 'common_dispatch_datas if name == "ass-cli" else' not in spec_text
    assert '"%~dp0ass-cli.exe" --help' in launcher_text
    assert "pause" in launcher_text


def test_packaging_pyinstaller_spec_keeps_qt_print_support() -> None:
    namespace = _load_pyinstaller_spec_namespace()

    collect_optional_pyside6_modules = namespace["_collect_optional_pyside6_modules"]
    excluded_optional_pyside6_modules = namespace["_excluded_optional_pyside6_modules"]

    assert "PySide6.QtPrintSupport" in collect_optional_pyside6_modules("QtPrintSupport")
    assert "PySide6.QtPrintSupport" in excluded_optional_pyside6_modules
