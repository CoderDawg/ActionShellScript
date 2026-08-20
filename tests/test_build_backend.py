from __future__ import annotations

from pathlib import Path
import tomllib

import build_backend


def _load_pyproject() -> dict[str, object]:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    return tomllib.loads(pyproject_path.read_text(encoding="utf-8"))


def test_project_version_and_description_match_the_phase_7_surface() -> None:
    pyproject = _load_pyproject()

    assert build_backend.PROJECT_VERSION == "0.2.0a2"
    assert pyproject["project"]["version"] == build_backend.PROJECT_VERSION
    assert build_backend.PROJECT_DESCRIPTION == (
        "ActionShellScript document, playback, debugger, help, and builtin tooling"
    )
    assert pyproject["project"]["description"] == build_backend.PROJECT_DESCRIPTION


def test_metadata_declares_the_phase_7_summary_and_dev_extra() -> None:
    metadata = build_backend._metadata_text()
    pyproject = _load_pyproject()

    assert f"Version: {build_backend.PROJECT_VERSION}" in metadata
    assert f"Summary: {build_backend.PROJECT_DESCRIPTION}" in metadata
    assert pyproject["project"]["description"] == build_backend.PROJECT_DESCRIPTION
    assert "Provides-Extra: dev" in metadata
    assert 'Requires-Dist: pytest>=8.0,<9.0; extra == "dev"' in metadata


def test_runtime_dependencies_match_pyproject_toml_exactly() -> None:
    pyproject = _load_pyproject()

    assert build_backend.RUNTIME_DEPENDENCIES == tuple(
        pyproject["project"]["dependencies"]
    )
    assert build_backend.OPTIONAL_DEPENDENCIES == {
        extra_name: tuple(dependencies)
        for extra_name, dependencies in pyproject["project"]["optional-dependencies"].items()
    }


def test_metadata_dependency_lines_match_pyproject_toml_exactly() -> None:
    pyproject = _load_pyproject()
    project_dependencies = pyproject["project"]["dependencies"]
    project_optional_dependencies = pyproject["project"]["optional-dependencies"]
    metadata = build_backend._metadata_text().splitlines()

    expected_lines = [f"Requires-Dist: {dependency}" for dependency in project_dependencies]
    expected_lines.extend(f"Provides-Extra: {extra_name}" for extra_name in project_optional_dependencies)
    for extra_name, dependencies in project_optional_dependencies.items():
        expected_lines.extend(
            f'Requires-Dist: {dependency}; extra == "{extra_name}"'
            for dependency in dependencies
        )

    actual_lines = [
        line
        for line in metadata
        if line.startswith(("Requires-Dist:", "Provides-Extra:"))
    ]

    assert actual_lines == expected_lines


def test_entry_points_match_the_current_console_scripts_exactly() -> None:
    entry_points = build_backend._entry_points_text()
    pyproject = _load_pyproject()
    project_scripts = pyproject["project"]["scripts"]

    expected_scripts = {
        "ass-cli": "apps.cli.ass_cli:main",
        "ass-record": "apps.cli.main:main",
        "ass-gui": "apps.desktop.main:main",
        "ass-help": "apps.desktop.help_main:main",
        "ass-debug": "apps.cli.debug_command:main",
        "ass-interpret": "apps.cli.interpret_command:main",
        "ass-record-interpret": "apps.cli.record_interpret_command:main",
        "ass-shape": "apps.cli.shape_command:main",
        "ass-generate": "apps.cli.generate_command:main",
        "ass-open-script": "apps.cli.document_command:main",
        "ass-play": "apps.cli.play_command:main",
        "ass-filter-recording": "apps.cli.filter_recording_command:main",
        "ass-filter-interpretation": "apps.cli.filter_interpretation_command:main",
        "ass-filter-shaping": "apps.cli.filter_shaping_command:main",
        "ass-filter-document": "apps.cli.filter_document_command:main",
    }

    assert "[console_scripts]" in entry_points
    assert set(project_scripts) == set(expected_scripts)
    assert project_scripts == expected_scripts
    assert entry_points.splitlines()[1:] == [
        f"{name} = {target}" for name, target in expected_scripts.items()
    ]


def test_requirements_txt_installs_the_local_checkout_editably() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    requirements_path = repo_root / "requirements.txt"
    assert requirements_path.read_text(encoding="utf-8").splitlines() == ["-e .[dev]"]

    for filename in (
        "requirements.in",
        "requirements_OLD.txt",
        "requrements.in",
        "requrements_OLD.txt",
    ):
        assert not (repo_root / filename).exists()
