from __future__ import annotations

from application.script_generation_service import ScriptGenerationService
from core.scripting.generation.script_generation_config import ScriptGenerationConfig
from core.shaping.shaped_action_sequence import ShapedActionSequence


def test_script_generation_service_generates_and_summarizes_script() -> None:
    shaped = ShapedActionSequence(
        source_session_id="session-10",
        source_interpreted_event_count=2,
        actions=[
            {"type": "mouse_move", "x": 10, "y": 20},
            {"type": "text", "text": "ok"},
        ],
    )
    service = ScriptGenerationService(
        config=ScriptGenerationConfig(include_header_comments=False)
    )

    generated = service.generate_script(shaped)
    summary = service.summarize(generated)

    assert generated.text == 'MouseMove(10, 20)\nSendText("ok")\n'
    assert summary.source_session_id == "session-10"
    assert summary.source_action_count == 2
    assert summary.line_count == 2
