# Phase-3 Completion Checklist

Use this checklist to finish the phase-3 shaping slice in ActionShellScript (ASS).

## Goal

Phase 3 is complete when the repo can derive a meaningful `ShapedActionSequence` from an `InterpretedRecording` without mutating interpretation truth, and when shaping changes representation without redefining meaning.

## Current status

Phase 2 is now stable enough for phase-3 work to proceed.

What already exists:

- `core/shaping/shaping_config.py`
- `core/shaping/shaped_action_sequence.py`
- `core/shaping/shaping_pipeline.py`
- `core/shaping/mouse_shaper.py`
- `core/shaping/click_shaper.py`
- `core/shaping/keyboard_shaper.py`
- `core/shaping/delay_shaper.py`
- `application/shaping_service.py`
- `apps/cli/shape_command.py`

What is still missing:

- phase-4 consumers that depend only on the frozen shaped action contract

## 1. Define the shaped action vocabulary

- Decide the exact shaped action types phase 3 supports.
- Write down the minimum action shapes for:
  - click-like actions
  - drag-like actions
  - keyboard actions
  - delay actions
  - any preserved pass-through actions
- Decide which common fields every shaped action should carry.
- Decide whether provenance fields are preserved into shaped actions.

Done when:
- Later script generation code does not need to guess what a shaped action looks like.
- `ShapedActionSequence` has a stable contract instead of a generic list of dicts in practice.

Implemented contract:

- action types: `mouse_move`, `mouse_down`, `mouse_up`, `mouse_click`, `mouse_drag`, `mouse_wheel`, `key_down`, `key_up`, `key_hold`, `hotkey`, `text`, `delay`
- common fields preserved on every shaped action: `timestamp_ms`, `end_timestamp_ms`, `duration_ms`, `source_start_index`, `source_end_index`, `source_event_count`
- provenance is preserved through shaping, and collapsed actions carry combined timing and source spans
- simple clicks collapse to minimal click actions; text shaping can collapse printable `key_hold` runs into `text`

## 2. Lock the phase-3 boundary

- Confirm `core/shaping/shaping_pipeline.py` consumes `InterpretedRecording` and produces `ShapedActionSequence` only.
- Confirm shaping never mutates `interpreted.events`.
- Confirm shaping changes representation, not meaning.
- Confirm playback and script-generation policy do not leak backward into interpretation.

Done when:
- `InterpretedRecording` remains the interpretation truth.
- `ShapedActionSequence` is clearly derived and rebuildable.

## 3. Implement real click shaping or remove unused click-shaping policy

- Replace the pass-through behavior in `core/shaping/click_shaper.py`.
- Use `collapse_simple_click_sequences` intentionally.
- Use:
  - `click_collapse_distance_px`
  - `click_collapse_max_duration_ms`
- Decide which click patterns should be simplified in phase 3.
- Make sure shaping does not reinterpret clicks into something with different meaning.

Done when:
- Click-related shaping config fields actually affect output.
- Click shaping simplifies representation without changing what the user did.

## 4. Implement real keyboard shaping or remove unused keyboard-shaping policy

- Replace the pass-through behavior in `core/shaping/keyboard_shaper.py`.
- Decide whether `collapse_text_input` emits text-like actions, structured keyboard actions, or both depending on `keyboard_output_style`.
- Define explicit rules for when keyboard sequences collapse into simpler output.
- Keep keyboard shaping as representation cleanup, not keyboard meaning recognition.

Done when:
- Keyboard shaping config fields actually affect output.
- The shaped keyboard output is stable enough for script generation.

## 5. Finish mouse shaping

- Review `core/shaping/mouse_shaper.py`.
- Keep the existing `emit_mouse_moves` and `emit_only_click_positions` behavior only if it still fits the intended shaped action contract.
- Implement real use of `collapse_consecutive_mouse_moves`.
- Decide whether drag-sensitive move sequences must be preserved even when normal move emission is reduced.
- Make sure mouse shaping does not destroy actions needed by later phases.

Done when:
- Mouse shaping can simplify move-heavy sequences without accidentally losing needed path information.
- All mouse-related shaping config fields are either used intentionally or removed.

## 6. Verify delay shaping against the action contract

- Review `core/shaping/delay_shaper.py` against the final shaped action vocabulary.
- Confirm whether delay actions already exist before shaping or are expected to be inserted later.
- Confirm `emit_delays`, `min_delay_ms`, `max_delay_ms`, and `collapse_consecutive_delays` behave consistently with later script generation expectations.

Done when:
- Delay shaping is aligned with the rest of the phase-3 action model.
- Delay behavior is not an isolated rule set that later phases have to special-case.

## 7. Strengthen `ShapingPipeline`

- Review `core/shaping/shaping_pipeline.py` once the individual shapers are real.
- Confirm the pass order is intentional:
  - mouse shaping
  - click shaping
  - keyboard shaping
  - delay shaping
- Confirm the ordering does not create contradictions.
- Add comments only where the pass ordering would otherwise be unclear.

Done when:
- The shaping pass order is deliberate and easy to reason about.
- The pipeline is stable enough for phase 4 to build on.

## 8. Add shaping tests

- Create `tests/shaping/`.
- Add tests for `core/shaping/click_shaper.py`.
- Add tests for `core/shaping/keyboard_shaper.py`.
- Add tests for `core/shaping/mouse_shaper.py`.
- Add tests for `core/shaping/delay_shaper.py`.
- Add tests for `core/shaping/shaping_pipeline.py`.
- Verify in tests that:
  - source `InterpretedRecording` remains unchanged
  - config flags actually affect shaped output
  - shaping changes representation only
  - pass ordering is stable

Done when:
- Shaping rules are covered and reproducible.
- Regressions in representation cleanup would be caught by tests.

## 9. Add at least one end-to-end shaping path

- Add a small non-UI consumer of `application/shaping_service.py`.
- This can be:
  - a tiny CLI or harness
  - or a test-only pipeline that flows from interpretation into shaping
- Confirm the resulting `ShapedActionSequence` is usable and summarized correctly.

Done when:
- Phase 3 is proven as a real vertical slice, not just a set of isolated modules.

Implemented path:

- `ass-shape path\to\session.json`
- this flows from raw session JSON through interpretation and into `ShapedActionSequence`
- `--show-actions` prints the shaped output contract in a stable readable form

## 10. Document the phase-3 scope

- Add a short doc or section under `docs/internal/architecture/`.
- State clearly:
  - phase 3 consumes interpreted meaning
  - it does not mutate `InterpretedRecording`
  - it changes representation, not meaning
  - phase 4 script generation should consume shaped actions, not raw recording truth
- Link it from the architecture docs if helpful.

Done when:
- The repo explains the shaping boundary clearly enough to prevent future drift.

## Recommended implementation order

1. Define the shaped action vocabulary.
2. Lock the phase-3 boundary.
3. Implement click shaping or remove unused click-shaping config.
4. Implement keyboard shaping or remove unused keyboard-shaping config.
5. Finish mouse shaping.
6. Verify delay shaping against the final action contract.
7. Tighten `ShapingPipeline`.
8. Add shaping tests.
9. Add one end-to-end consumer path.
10. Add a short phase-3 boundary note.

## Exit criteria for Phase 3

- `ShapingPipeline` produces a meaningful `ShapedActionSequence`.
- Shaping changes representation without redefining meaning.
- `InterpretedRecording` remains unchanged after shaping.
- The shaping config fields actually control behavior.
- Tests cover the shaping rules.
- The shaped output is stable enough for phase-4 script generation.
