from __future__ import annotations

from pathlib import Path

from core.runtime.script_runtime import ScriptRuntime


def test_enum_examples_demo_sample_compiles_and_matches_runtime_output() -> None:
    runtime = ScriptRuntime()

    script = Path("samples/enum_examples_demo.ass").read_text(encoding="utf-8")
    context = runtime.compile(script)

    assert context.console_output == [
        "hidden: hidden\n",
        "visible: visible\n",
        "maximized: maximized\n",
        "direct_name: visible\n",
    ]
