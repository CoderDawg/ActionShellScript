from __future__ import annotations

import time
from pathlib import Path

import pytest

from core.runtime.script_runtime import ScriptRuntime


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "samples"


def _sample_path(name: str) -> Path:
    return SAMPLES_DIR / name


def _patch_working_dir(monkeypatch: pytest.MonkeyPatch, workdir: Path) -> None:
    monkeypatch.setattr("core.runtime.execution_context.os.getcwd", lambda: str(workdir))
    monkeypatch.setattr("core.runtime.script_runtime.os.getcwd", lambda: str(workdir))


def _patch_date_time_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    parsed_epoch = 1779848005
    next_day_epoch = 1779934405
    date_serial_epoch = 1779753600

    def fake_localtime(epoch_seconds: float | None = None) -> time.struct_time:
        if epoch_seconds in (None, parsed_epoch):
            return time.struct_time((2026, 5, 26, 15, 4, 5, 2, 146, 0))
        if epoch_seconds == next_day_epoch:
            return time.struct_time((2026, 5, 27, 15, 4, 5, 3, 147, 0))
        if epoch_seconds == date_serial_epoch:
            return time.struct_time((2026, 5, 26, 0, 0, 0, 2, 146, 0))
        raise AssertionError(f"unexpected localtime epoch: {epoch_seconds!r}")

    def fake_gmtime(epoch_seconds: float | None = None) -> time.struct_time:
        return time.struct_time((2026, 5, 26, 22, 13, 25, 2, 146, 0))

    def fake_mktime(time_tuple) -> float:
        values = tuple(time_tuple)[:6]
        if values == (2026, 5, 26, 15, 4, 5):
            return float(parsed_epoch)
        if values == (2026, 5, 27, 15, 4, 5):
            return float(next_day_epoch)
        if values == (2026, 5, 26, 0, 0, 0):
            return float(date_serial_epoch)
        raise AssertionError(f"unexpected mktime tuple: {values!r}")

    monkeypatch.setattr("core.runtime.script_runtime.time.time", lambda: 1779848005.25)
    monkeypatch.setattr("core.runtime.script_runtime.time.localtime", fake_localtime)
    monkeypatch.setattr("core.runtime.script_runtime.time.gmtime", fake_gmtime)
    monkeypatch.setattr("core.runtime.script_runtime.time.mktime", fake_mktime)


def test_date_time_demo_sample_compiles_and_matches_runtime_output() -> None:
    runtime = ScriptRuntime()
    sample_path = _sample_path("date_time_demo.ass")

    with pytest.MonkeyPatch.context() as monkeypatch:
        _patch_date_time_helpers(monkeypatch)
        monkeypatch.setattr(runtime, "_utc_offset", lambda args, _context: -420)
        context = runtime.compile(sample_path.read_text(encoding="utf-8"), source_path=sample_path)

    assert context.console_output == [
        "1779848005\n",
        "2026-05-26 15:04:05\n",
        "2026-05-26 22:13:25\n",
        "2026-05-26 15:04:05\n",
        "2026-05-27 15:04:05\n",
        "2026-05-26 15:04:05 +0200\n",
        "2026-05-26 15:04:05 +0000\n",
        "-420\n",
        "2026-05-26 00:00:00\n",
        "54245\n",
        "31\n",
        "True\n",
        "False\n",
        "1\n",
    ]


def test_read_file_demo_sample_compiles_and_matches_runtime_output() -> None:
    runtime = ScriptRuntime()
    sample_path = _sample_path("read_file_demo.ass")

    context = runtime.compile(sample_path.read_text(encoding="utf-8"), source_path=sample_path)

    assert context.console_output == [
        "Hello from ReadFile\n",
        "This fixture sits beside the demo\n",
        "Each line is printed by the script\n",
    ]


def test_path_helpers_demo_sample_compiles_and_matches_runtime_output() -> None:
    runtime = ScriptRuntime()
    sample_path = _sample_path("path_helpers_demo.ass")

    context = runtime.compile(sample_path.read_text(encoding="utf-8"), source_path=sample_path)

    assert context.console_output == [
        "file_0: read_file_demo.ass\n",
        "file_1: read_file_demo.txt\n",
        "directory_0: samples\n",
    ]


def test_remove_dir_demo_sample_compiles_and_matches_runtime_output(tmp_path: Path) -> None:
    runtime = ScriptRuntime()
    sample_path = _sample_path("remove_dir_demo.ass")

    with pytest.MonkeyPatch.context() as monkeypatch:
        _patch_working_dir(monkeypatch, tmp_path)
        context = runtime.compile(sample_path.read_text(encoding="utf-8"), source_path=sample_path)

    assert context.console_output == [
        "before: True\n",
        "after: False\n",
    ]


def test_copy_helpers_demo_sample_compiles_and_matches_runtime_output(tmp_path: Path) -> None:
    runtime = ScriptRuntime()
    sample_path = _sample_path("copy_helpers_demo.ass")

    with pytest.MonkeyPatch.context() as monkeypatch:
        _patch_working_dir(monkeypatch, tmp_path)
        context = runtime.compile(sample_path.read_text(encoding="utf-8"), source_path=sample_path)

    assert context.console_output == [
        "file_exists: True\n",
        "dir_exists: True\n",
        "copied_text: hello\n",
    ]


def test_move_helpers_demo_sample_compiles_and_matches_runtime_output(tmp_path: Path) -> None:
    runtime = ScriptRuntime()
    sample_path = _sample_path("move_helpers_demo.ass")

    with pytest.MonkeyPatch.context() as monkeypatch:
        _patch_working_dir(monkeypatch, tmp_path)
        context = runtime.compile(sample_path.read_text(encoding="utf-8"), source_path=sample_path)

    assert context.console_output == [
        "file_exists_after_move: True\n",
        "dir_exists_after_move: True\n",
        "moved_text: hello\n",
    ]


def test_metadata_helpers_demo_sample_compiles_and_matches_runtime_output(tmp_path: Path) -> None:
    runtime = ScriptRuntime()
    sample_path = _sample_path("metadata_helpers_demo.ass")

    with pytest.MonkeyPatch.context() as monkeypatch:
        _patch_working_dir(monkeypatch, tmp_path)
        context = runtime.compile(sample_path.read_text(encoding="utf-8"), source_path=sample_path)

    assert context.console_output == [
        "size: 11\n",
        "dir_size: 11\n",
        "file_name: payload.txt\n",
        "is_dir: False\n",
        "time_is_float: 1\n",
        "sha256: b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9\n",
        "md5: 5eb63bbbe01eeed093cb22bb8f5acdc3\n",
        "crc32: 0d4a1185\n",
        "adler32: 1a0b045d\n",
    ]


def test_traversal_helpers_demo_sample_compiles_and_matches_runtime_output(tmp_path: Path) -> None:
    runtime = ScriptRuntime()
    sample_path = _sample_path("traversal_helpers_demo.ass")

    with pytest.MonkeyPatch.context() as monkeypatch:
        _patch_working_dir(monkeypatch, tmp_path)
        context = runtime.compile(sample_path.read_text(encoding="utf-8"), source_path=sample_path)

    assert context.console_output == [
        "dir_0: nested\n",
        "dir_1: deep\n",
        "files_0: alpha.txt\n",
        "files_1: beta.txt\n",
    ]


def test_file_compare_demo_sample_compiles_and_matches_runtime_output(tmp_path: Path) -> None:
    runtime = ScriptRuntime()
    sample_path = _sample_path("file_compare_demo.ass")

    with pytest.MonkeyPatch.context() as monkeypatch:
        _patch_working_dir(monkeypatch, tmp_path)
        context = runtime.compile(sample_path.read_text(encoding="utf-8"), source_path=sample_path)

    assert context.console_output == [
        "same: 0\n",
        "less: -1\n",
        "greater: 1\n",
    ]
