from __future__ import annotations

from pathlib import Path

from core.runtime.script_runtime import ScriptRuntime


def test_string_helpers_demo_sample_compiles_and_matches_runtime_output() -> None:
    runtime = ScriptRuntime()

    script = Path("samples/string_helpers_demo.ass").read_text(encoding="utf-8")
    context = runtime.compile(script)

    assert context.console_output == [
        "compare_equal: 0\n",
        "compare_sensitive: -1\n",
        "search_rightmost: 17\n",
        "search_bounded: 5\n",
        "regex_escape: a\\.b\n",
        "regex_is_match: 1\n",
        "regex_in_str: 9\n",
        "regex_match_full: Ada Lovelace\n",
        "regex_match_first: Ada\n",
        "regex_match_last: Lovelace\n",
        "regex_replace: a[1]b[2]c[3]\n",
        "regex_replace_extended: 3\n",
        "replace_all: 1 two 1 two\n",
        "replace_from_start: abXYZf\n",
        "@Extended: 1\n",
        "@Error: 0\n",
        "lower: mixed case\n",
        "upper: MIXED CASE\n",
        "length: 17\n",
        "left: Action\n",
        "right: Script\n",
        "mid: Shell\n",
        "trim_left: ShellScript\n",
        "trim_right: ActionShell\n",
        "reverse: tpircSllehSnoitcA\n",
        "joined: Ada, Lovelace\n",
    ]
