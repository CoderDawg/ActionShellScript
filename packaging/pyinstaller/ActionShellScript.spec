# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import os
import pkgutil
from pathlib import Path

import PySide6
from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_all, collect_submodules


# PyInstaller executes spec files without defining __file__, so fall back to the
# current working directory when the spec is evaluated in that mode.
if "__file__" in globals():
    repo_root = Path(__file__).resolve().parents[2]
else:
    repo_root = Path.cwd().resolve()
source_root = Path(os.environ.get("ASS_RELEASE_SOURCE_ROOT", str(repo_root))).resolve()


def bundle_trees(*entries: tuple[str, str]) -> list[tuple[str, str]]:
    return [(str(source), destination) for source, destination in entries]


def bundle_directory_tree(
    source: Path,
    prefix: str,
    *,
    exclude_directory_names: set[str] | frozenset[str] | None = None,
) -> list[tuple[str, str]]:
    return [
        (
            str(file_path),
            prefix
            if file_path.relative_to(source).parent == Path(".")
            else f"{prefix}/{file_path.relative_to(source).parent.as_posix()}",
        )
        for file_path in sorted(path for path in source.rglob("*") if path.is_file())
        if not exclude_directory_names
        or not any(part in exclude_directory_names for part in file_path.relative_to(source).parts[:-1])
    ]


def _collect_optional_pyside6_modules(*prefixes: str) -> list[str]:
    excluded_modules: list[str] = []
    for module_info in pkgutil.iter_modules(PySide6.__path__):
        if module_info.name.startswith(prefixes):
            excluded_modules.append(f"PySide6.{module_info.name}")
    return sorted(set(excluded_modules))


# The desktop and help apps are widget-based and only need the core Qt, GUI,
# widgets, WebEngine, SVG, and icon-loading pieces. PyInstaller's default Qt
# discovery pulls in a long tail of optional modules that we do not use.
_excluded_optional_pyside6_modules = _collect_optional_pyside6_modules(
    "Qt3D",
    "QtCharts",
    "QtConcurrent",
    "QtDataVisualization",
    "QtGraphs",
    "QtHelp",
    "QtLocation",
    "QtMultimedia",
    "QtNetworkAuth",
    "QtPdf",
    "QtPositioning",
    "QtQml",
    "QtQuick",
    "QtRemoteObjects",
    "QtScxml",
    "QtSensors",
    "QtSerialBus",
    "QtSerialPort",
    "QtSpatialAudio",
    "QtSvgWidgets",
    "QtTest",
    "QtTextToSpeech",
    "QtUiTools",
    "QtVirtualKeyboard",
    "QtWebEngineQuick",
    "QtWebView",
    "QtXml",
)


def build_bundle(
    *,
    name: str,
    script: str,
    console: bool,
    datas: list[tuple[str, str]] | list,
    binaries: list | None = None,
    hiddenimports: list[str] | None = None,
    runtime_hooks: list[str] | None = None,
    icon: str | None = None,
    excludes: list[str] | None = None,
):
    analysis = Analysis(
        [script],
        pathex=[str(repo_root)],
        binaries=binaries or [],
        datas=datas,
        hiddenimports=hiddenimports or [],
        hookspath=[],
        hooksconfig={},
        runtime_hooks=runtime_hooks or [],
        excludes=excludes or [],
        noarchive=False,
        optimize=0,
    )
    pyz = PYZ(analysis.pure)
    exe = EXE(
        pyz,
        analysis.scripts,
        exclude_binaries=True,
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=console,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        icon=icon,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        analysis.binaries,
        analysis.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name=name,
    )
    return analysis, pyz, exe, coll


qtawesome_datas, qtawesome_binaries, qtawesome_hiddenimports = collect_all("qtawesome")
dispatch_hiddenimports = sorted(set(collect_submodules("apps.cli")))
# qtpy imports packaging.version during desktop startup, so the bundled GUI needs
# the third-party packaging module available at runtime.
desktop_hiddenimports = sorted(set(qtawesome_hiddenimports) | {"packaging.version"})
desktop_binaries = list(qtawesome_binaries)
desktop_runtime_hooks = [
    str(repo_root / "packaging" / "pyinstaller" / "runtime_hooks" / "ass_shared_assets.py"),
    str(repo_root / "packaging" / "pyinstaller" / "runtime_hooks" / "ass_desktop_assets.py"),
]

desktop_datas = []
desktop_datas.extend(
    bundle_trees(
        (source_root / "ATTRIBUTION.txt", "."),
        (source_root / "LICENSE", "."),
        (source_root / "NOTICE", "."),
    )
)
desktop_datas.extend(qtawesome_datas)
desktop_datas.extend(
    bundle_directory_tree(
        source_root / "docs",
        "docs",
        exclude_directory_names={"internal"},
    )
)
desktop_datas.extend(bundle_directory_tree(source_root / "samples", "samples"))
desktop_datas.extend(bundle_directory_tree(source_root / "assets", "assets"))
desktop_datas.extend(
    bundle_directory_tree(source_root / "apps" / "desktop" / "assets", "apps/desktop/assets")
)
desktop_datas.extend(
    bundle_trees(
        (
            source_root / "apps" / "desktop" / "table_api" / "README.md",
            "apps/desktop/table_api/README.md",
        ),
    )
)

common_dispatch_datas = bundle_trees(
    (source_root / "LICENSE", "."),
    (source_root / "NOTICE", "."),
)

dispatch_targets = [
    ("ass-cli", source_root / "apps" / "cli" / "ass_cli.py"),
    ("ass-record", source_root / "apps" / "cli" / "main.py"),
]

single_command_targets = [
    ("ass-interpret", source_root / "apps" / "cli" / "interpret_command.py"),
    ("ass-record-interpret", source_root / "apps" / "cli" / "record_interpret_command.py"),
    ("ass-shape", source_root / "apps" / "cli" / "shape_command.py"),
    ("ass-generate", source_root / "apps" / "cli" / "generate_command.py"),
    ("ass-open-script", source_root / "apps" / "cli" / "document_command.py"),
    ("ass-play", source_root / "apps" / "cli" / "play_command.py"),
    ("ass-debug", source_root / "apps" / "cli" / "debug_command.py"),
    ("ass-filter-recording", source_root / "apps" / "cli" / "filter_recording_command.py"),
    (
        "ass-filter-interpretation",
        source_root / "apps" / "cli" / "filter_interpretation_command.py",
    ),
    ("ass-filter-shaping", source_root / "apps" / "cli" / "filter_shaping_command.py"),
    ("ass-filter-document", source_root / "apps" / "cli" / "filter_document_command.py"),
]

desktop_targets = [
    ("ass-gui", source_root / "apps" / "desktop" / "main.py"),
    ("ass-help", source_root / "apps" / "desktop" / "help_main.py"),
]

for name, script in dispatch_targets:
    build_bundle(
        name=name,
        script=str(script),
        console=True,
        datas=common_dispatch_datas,
        hiddenimports=dispatch_hiddenimports,
        excludes=_excluded_optional_pyside6_modules,
    )

for name, script in single_command_targets:
    build_bundle(
        name=name,
        script=str(script),
        console=True,
        datas=bundle_trees(
            (source_root / "LICENSE", "."),
            (source_root / "NOTICE", "."),
        ),
        excludes=_excluded_optional_pyside6_modules,
    )

for name, script in desktop_targets:
    build_bundle(
        name=name,
        script=str(script),
        console=False,
        datas=desktop_datas,
        binaries=desktop_binaries,
        hiddenimports=desktop_hiddenimports,
        runtime_hooks=desktop_runtime_hooks,
        icon=str(source_root / "apps" / "desktop" / "assets" / "retro_pixelated_teal_smiling_frog.ico"),
        excludes=_excluded_optional_pyside6_modules,
    )
