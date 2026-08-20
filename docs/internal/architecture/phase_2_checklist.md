# Phase-2 Completion Checklist

Use this checklist to finish the phase-2 interpretation slice in ActionShellScript (ASS).

## Goal

Phase 2 is complete when the repo can derive a meaningful `InterpretedRecording` from a `RecordingSession` without mutating the recording truth, and when clicks, drags, and keyboard combinations are recognized by explicit interpretation rules.

## 1. Lock the phase-2 boundary

- Confirm `core/interpretation/recording_interpreter.py` only derives from `RecordingSession`.
- Confirm interpretation never mutates `session.events`.
- Confirm no shaping or playback policy is mixed into interpretation.
- Keep interpretation focused on meaning recognition only.

Done when:
- `RecordingSession` remains the only recording truth.
- `InterpretedRecording` is clearly derived and rebuildable.

## 2. Define the interpreted event vocabulary

- Decide the exact interpreted event types phase 2 supports.
- Write down the minimum event shapes for:
  - `mouse_click`
  - `mouse_click` with `clicks > 1` or a separate double-click type
  - `mouse_drag`
  - `key_hold`
  - `hotkey`
  - unchanged pass-through events
- Decide which common fields every interpreted event should carry.
- Decide how interpreted events preserve source timing and position data.

Done when:
- Later code does not have to guess what an interpreted event looks like.
- The event vocabulary is stable enough for phase 3 to consume.

## 3. Implement real click recognition

- Expand `core/interpretation/click_interpreter.py` beyond adjacent `mouse_down` + `mouse_up`.
- Use `click_max_move_distance_px`.
- Decide how mouse moves between press and release affect click recognition.
- Use the double-click config fields:
  - `double_click_max_interval_ms`
  - `double_click_max_distance_px`
  - `double_click_max_pause_ms`
  - `double_click_max_inter_click_move_distance_px`
- Decide whether multi-click is represented by one `mouse_click` event with `clicks` or by separate interpreted click event types.

Done when:
- Simple clicks are recognized reliably.
- Double-click behavior is intentional and config-driven.
- Most of `InterpretationConfig` click settings are actually used.

## 4. Implement real drag recognition

- Replace the pass-through stub in `core/interpretation/drag_interpreter.py`.
- Detect press-move-release drag sequences.
- Use:
  - `drag_min_distance_px`
  - `drag_min_duration_ms`
- Decide the output event shape for a drag.
- Decide whether the raw mouse events that formed the drag are replaced or preserved.

Done when:
- Drag behavior is recognized from raw mouse sequences.
- Small accidental movement during a click does not get mislabeled as a drag.

## 5. Implement real keyboard interpretation

- Replace the pass-through stubs in `core/interpretation/keyboard_interpreter.py`.
- Add key-hold recognition from `key_down` and `key_up`.
- Add hotkey recognition for modifier combinations.
- Decide how to treat overlapping and nested key sequences.
- Decide which raw key events survive unchanged.

Done when:
- Meaningful keyboard actions are recognized instead of only passing raw key events through.

## 6. Define replacement and pass-through rules

- Document exactly when raw events are replaced by interpreted events.
- Decide which event categories remain raw in phase 2.
- Define ordering guarantees across interpreted output.
- Decide whether interpreted events should carry provenance fields such as source indices or source event count.

Done when:
- The pipeline has explicit rules instead of accidental behavior.
- Future shaping code can rely on consistent output.

## 7. Strengthen `RecordingInterpreter`

- Review `core/interpretation/recording_interpreter.py` once the interpreters are real.
- Make sure the pass order is intentional:
  - clicks
  - drags
  - key holds
  - hotkeys
- Confirm the ordering does not create contradictions.
- Add comments only where the sequence would otherwise be unclear.

Done when:
- The pipeline order is deliberate and easy to reason about.

## 8. Add interpretation tests

- Create `tests/interpretation/`.
- Add tests for `core/interpretation/click_interpreter.py`:
  - simple click
  - click rejected by movement threshold
  - double-click recognition
  - mismatched button does not collapse
- Add tests for `core/interpretation/drag_interpreter.py`:
  - drag recognized above threshold
  - movement below threshold stays non-drag
- Add tests for `core/interpretation/keyboard_interpreter.py`:
  - key hold
  - hotkey
  - ordinary key sequence pass-through
- Add tests for `core/interpretation/recording_interpreter.py`:
  - full pipeline output
  - input session remains unchanged

Done when:
- The interpretation rules are covered and stable.
- Mutation of raw recording truth would be caught by tests.

## 9. Add at least one end-to-end interpretation path

- Add a small non-UI consumer of `application/interpretation_service.py`.
- This can be:
  - a tiny CLI command
  - or a test harness that records then interprets
- Confirm the resulting `InterpretedRecording` is usable and summarized correctly.

Done when:
- Phase 2 is proven as a real vertical slice, not just isolated modules.

## 10. Document the phase-2 scope

- Add a short doc or section under `docs/internal/architecture/`.
- State clearly:
  - phase 2 derives meaning from raw recording
  - it does not mutate `RecordingSession`
  - it does not do shaping
  - it does not do playback planning
- Link it from the architecture docs if helpful.

Done when:
- The repo explains the interpretation boundary clearly enough to prevent future drift.

## Recommended implementation order

1. Define the interpreted event vocabulary.
2. Implement click recognition.
3. Implement drag recognition.
4. Implement keyboard interpretation.
5. Tighten `RecordingInterpreter` pipeline behavior.
6. Add interpretation tests.
7. Add one end-to-end consumer path.
8. Add a short phase-2 doc note.

## Exit criteria for Phase 2

- `RecordingInterpreter` produces a meaningful `InterpretedRecording`.
- Clicks, drags, and keyboard combinations are actually recognized.
- `RecordingSession` remains unchanged after interpretation.
- Tests cover the interpretation rules.
- No shaping or playback behavior has leaked into phase 2.
