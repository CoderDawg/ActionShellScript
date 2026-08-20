from __future__ import annotations

import base64
import csv
import hashlib
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

import tomllib


PYPROJECT_PATH = Path(__file__).resolve().parent / "pyproject.toml"


@lru_cache(maxsize=1)
def _project_table() -> dict[str, object]:
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))["project"]


PROJECT_TABLE = _project_table()
PROJECT_NAME = str(PROJECT_TABLE["name"])
PROJECT_VERSION = str(PROJECT_TABLE["version"])
PROJECT_DESCRIPTION = str(PROJECT_TABLE["description"])
DIST_INFO = f"{PROJECT_NAME}-{PROJECT_VERSION}.dist-info"
WHEEL_TAG = "py3-none-any"
RUNTIME_DEPENDENCIES = tuple(str(dependency) for dependency in PROJECT_TABLE["dependencies"])
OPTIONAL_DEPENDENCIES = {
    extra_name: tuple(str(dependency) for dependency in dependencies)
    for extra_name, dependencies in PROJECT_TABLE["optional-dependencies"].items()
}
ENTRY_POINTS = (
    "ass-cli = apps.cli.ass_cli:main",
    "ass-record = apps.cli.main:main",
    "ass-gui = apps.desktop.main:main",
    "ass-help = apps.desktop.help_main:main",
    "ass-debug = apps.cli.debug_command:main",
    "ass-interpret = apps.cli.interpret_command:main",
    "ass-record-interpret = apps.cli.record_interpret_command:main",
    "ass-shape = apps.cli.shape_command:main",
    "ass-generate = apps.cli.generate_command:main",
    "ass-open-script = apps.cli.document_command:main",
    "ass-play = apps.cli.play_command:main",
    "ass-filter-recording = apps.cli.filter_recording_command:main",
    "ass-filter-interpretation = apps.cli.filter_interpretation_command:main",
    "ass-filter-shaping = apps.cli.filter_shaping_command:main",
    "ass-filter-document = apps.cli.filter_document_command:main",
)


def _metadata_text() -> str:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {PROJECT_NAME}",
        f"Version: {PROJECT_VERSION}",
        f"Summary: {PROJECT_DESCRIPTION}",
        "Requires-Python: >=3.11",
    ]
    lines.extend(f"Requires-Dist: {dependency}" for dependency in RUNTIME_DEPENDENCIES)
    for extra_name, dependencies in OPTIONAL_DEPENDENCIES.items():
        lines.append(f"Provides-Extra: {extra_name}")
        lines.extend(
            f'Requires-Dist: {dependency}; extra == "{extra_name}"'
            for dependency in dependencies
        )
    lines.append("")
    return "\n".join(lines)


def _wheel_text() -> str:
    return "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: actionshellscript-build-backend",
            "Root-Is-Purelib: true",
            f"Tag: {WHEEL_TAG}",
            "",
        ]
    )


def _entry_points_text() -> str:
    entry_point_lines = "\n".join(ENTRY_POINTS)
    return f"[console_scripts]\n{entry_point_lines}\n"


def _dist_info_dir(root: Path) -> Path:
    path = root / DIST_INFO
    path.mkdir(parents=True, exist_ok=True)
    return path


def _record_rows(root: Path) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for file_path in sorted(path for path in root.rglob("*") if path.is_file()):
        relative = file_path.relative_to(root).as_posix()
        if relative == f"{DIST_INFO}/RECORD":
            rows.append((relative, "", ""))
            continue

        data = file_path.read_bytes()
        digest = hashlib.sha256(data).digest()
        encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        rows.append((relative, f"sha256={encoded}", str(len(data))))
    return rows


def _write_record(root: Path) -> None:
    record_path = root / DIST_INFO / "RECORD"
    with record_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(_record_rows(root))


def _build_common_files(root: Path) -> None:
    dist_info = _dist_info_dir(root)
    (dist_info / "METADATA").write_text(_metadata_text(), encoding="utf-8")
    (dist_info / "WHEEL").write_text(_wheel_text(), encoding="utf-8")
    (dist_info / "entry_points.txt").write_text(_entry_points_text(), encoding="utf-8")


def _write_wheel_archive(staging_root: Path, wheel_directory: str, wheel_name: str) -> str:
    _write_record(staging_root)
    wheel_path = Path(wheel_directory) / wheel_name
    with ZipFile(wheel_path, "w", compression=ZIP_DEFLATED) as archive:
        for file_path in sorted(path for path in staging_root.rglob("*") if path.is_file()):
            archive.write(file_path, file_path.relative_to(staging_root).as_posix())
    return wheel_name


def _editable_pth_contents() -> str:
    return f"{Path(__file__).resolve().parent}\n"


def _wheel_filename(kind: str) -> str:
    return f"{PROJECT_NAME}-{PROJECT_VERSION}-{WHEEL_TAG}.whl"


def get_requires_for_build_wheel(config_settings=None) -> list[str]:
    return []


def get_requires_for_build_editable(config_settings=None) -> list[str]:
    return []


def prepare_metadata_for_build_wheel(metadata_directory: str, config_settings=None) -> str:
    dist_info = Path(metadata_directory) / DIST_INFO
    dist_info.mkdir(parents=True, exist_ok=True)
    (dist_info / "METADATA").write_text(_metadata_text(), encoding="utf-8")
    (dist_info / "WHEEL").write_text(_wheel_text(), encoding="utf-8")
    (dist_info / "entry_points.txt").write_text(_entry_points_text(), encoding="utf-8")
    return DIST_INFO


def prepare_metadata_for_build_editable(metadata_directory: str, config_settings=None) -> str:
    return prepare_metadata_for_build_wheel(metadata_directory, config_settings)


def build_wheel(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    with TemporaryDirectory() as temp_dir:
        staging_root = Path(temp_dir)
        _build_common_files(staging_root)
        (staging_root / f"{PROJECT_NAME}.pth").write_text(_editable_pth_contents(), encoding="utf-8")
        return _write_wheel_archive(staging_root, wheel_directory, _wheel_filename("wheel"))


def build_editable(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    with TemporaryDirectory() as temp_dir:
        staging_root = Path(temp_dir)
        _build_common_files(staging_root)
        (staging_root / f"{PROJECT_NAME}.pth").write_text(_editable_pth_contents(), encoding="utf-8")
        return _write_wheel_archive(staging_root, wheel_directory, _wheel_filename("editable"))
