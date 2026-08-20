from __future__ import annotations

import importlib.util
import tempfile
import sys
from pathlib import Path
from types import SimpleNamespace

from core.playback.playback_result import PlaybackResult


def _load_test_gui_module():
    script_path = Path(__file__).resolve().parents[2] / "tools" / "Test_GUI_V3.py"
    spec = importlib.util.spec_from_file_location("test_gui_v3", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load tools/Test_GUI_V3.py")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_diagnostic_config_resolves_override_path(tmp_path, monkeypatch) -> None:
    module = _load_test_gui_module()
    monkeypatch.chdir(tmp_path)

    config = module.build_diagnostic_config(
        SimpleNamespace(
            diagnostic_logging=False,
            diagnostic_stdout=False,
            diagnostic_log_path="logs/gui-diagnostics.log",
        )
    )

    assert config.enabled is False
    assert config.log_to_file is True
    assert config.log_path == (tmp_path / "logs" / "gui-diagnostics.log").resolve()


def test_announce_diagnostic_destination_prints_default_and_override_paths(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = _load_test_gui_module()
    monkeypatch.chdir(tmp_path)

    default_config = module.build_diagnostic_config(
        SimpleNamespace(
            diagnostic_logging=True,
            diagnostic_stdout=False,
            diagnostic_log_path=None,
        )
    )
    module.set_diagnostic_config(default_config)
    module._announce_diagnostic_destination()
    default_output = capsys.readouterr().out.splitlines()[0]

    assert default_output.startswith("Diagnostics log file   : ")
    default_path = Path(default_output.removeprefix("Diagnostics log file   : ").strip())
    assert default_path.parent == Path(tempfile.gettempdir())
    assert default_path.name.startswith("actionshellscript_diagnostics_Test_GUI_V3_")
    assert default_path.suffix == ".log"

    override_config = module.build_diagnostic_config(
        SimpleNamespace(
            diagnostic_logging=False,
            diagnostic_stdout=False,
            diagnostic_log_path="logs/gui-diagnostics.log",
        )
    )
    module.set_diagnostic_config(override_config)
    module._announce_diagnostic_destination()
    override_output = capsys.readouterr().out

    assert override_output == ""


def test_main_launches_detached_gui_after_announcing_diagnostics_path(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    module = _load_test_gui_module()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: SimpleNamespace(
            diagnostic_logging=True,
            diagnostic_stdout=False,
            diagnostic_log_path=None,
        ),
    )

    calls: list[tuple[list[str], dict[str, object]]] = []
    pythonw_path = str(tmp_path / "pythonw.exe")

    monkeypatch.setattr(module.shutil, "which", lambda name: pythonw_path if name in {"pythonw.exe", "pythonw"} else None)

    def fake_popen(command, **kwargs):
        calls.append((list(command), kwargs))

        class _Process:
            pass

        return _Process()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(module.sys, "argv", ["Test_GUI_V3.py", "--diagnostic-logging"])

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines()[0].startswith("Diagnostics log file   : ")
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[0] == pythonw_path
    assert Path(command[1]).name == "Test_GUI_V3.py"
    assert Path(command[1]).parent.name == "tools"
    assert command[2:] == ["--diagnostic-logging"]
    assert kwargs["env"][module._DETACHED_ENV_VAR] == "1"
    assert kwargs["stdin"] == module.subprocess.DEVNULL
    assert kwargs["stdout"] == module.subprocess.DEVNULL
    assert kwargs["stderr"] == module.subprocess.DEVNULL


def test_format_playback_status_lines_reuses_shared_failure_formatter() -> None:
    module = _load_test_gui_module()

    result = PlaybackResult(
        source_kind="script_document",
        source_id="script-1",
        executed_event_count=7,
        success=False,
        error_line=9,
        error_message="boom",
    )

    assert module.format_playback_status_lines(result) == [
        "Playback success       : False",
        "Executed event count   : 7",
        "Playback error line    : 9",
        "Playback error         : boom",
    ]
