# Phase 3 Shaping Boundary

Phase 3 reshapes interpreted meaning into a cleaner representation. It does not replace interpretation truth.

## Source Of Truth

- `InterpretedRecording` remains the authoritative interpretation model for this stage.
- `ShapedActionSequence` is a rebuildable derivative produced from `InterpretedRecording.events`.
- Shaping code must treat `interpreted.events` as read-only input.

## Current Repo State

The shaping slice already has its basic structure:

- `ShapingConfig`
- `ShapedActionSequence`
- `ShapingPipeline`
- `mouse_shaper.py`
- `click_shaper.py`
- `keyboard_shaper.py`
- `delay_shaper.py`
- `ShapingService`

What is real today:

- `click_shaper.py` simplifies eligible click events down to the frozen click contract.
- `keyboard_shaper.py` can keep structured keyboard actions or collapse printable key holds into `text`.
- `mouse_shaper.py` can drop mouse moves, keep only click-position-style output, or collapse move runs while preserving span metadata.
- `delay_shaper.py` drops, clamps, and collapses delay actions using the same common timing and provenance fields as the rest of the shaped contract.
- `tests/shaping/` covers each shaper, the pipeline, and an end-to-end CLI path.
- `apps/cli/shape_command.py` provides a non-UI interpretation-to-shaping slice.

## Role Of Shaping

Phase 3 is where representation choices belong.

Examples:

- reducing noisy mouse-move output
- collapsing adjacent delay actions
- choosing whether keyboard output stays structured or becomes more text-like
- simplifying click-heavy output for later script generation

These are representation decisions, not new interpretations of what the user did.

## Contract Expectations

Phase 3 should freeze a stable shaped action vocabulary before phase 4 depends on it.

The frozen phase-3 action vocabulary is:

- `mouse_move`
- `mouse_down`
- `mouse_up`
- `mouse_click`
- `mouse_drag`
- `mouse_wheel`
- `key_down`
- `key_up`
- `key_hold`
- `hotkey`
- `text`
- `delay`

Every shaped action preserves these common fields:

- `timestamp_ms`
- `end_timestamp_ms`
- `duration_ms`
- `source_start_index`
- `source_end_index`
- `source_event_count`

Provenance stays on shaped actions. Shaping may collapse multiple interpreted events into one action, but the resulting action still carries the combined timing span and combined source range.

Delay actions are explicit phase-3 output with:

- `type: "delay"`
- `duration_ms`
- the common timing and provenance fields

Keyboard output differs from phase 2 like this:

- `structured` output keeps `key_hold`, `hotkey`, `key_down`, and `key_up`
- `text` output collapses consecutive printable `key_hold` actions into `text`
- hotkeys and non-printable keys stay structured in both modes

Click output differs from phase 2 like this:

- simple clicks are reduced to `type`, `button`, `clicks`, `x`, `y`, and the common fields
- clicks outside the shaping thresholds keep their richer click-detail fields

## What Shaping Must Not Do

Phase 3 must not:

- mutate `InterpretedRecording`
- redefine interpretation meaning
- choose playback execution policy
- generate script text
- hide missing interpretation semantics behind shaping rules

If a change alters what the user did, it belongs in phase 2 interpretation, not in phase 3 shaping.

## Current Open Work

- Keep phase-4 consumers aligned with the frozen phase-3 contract.
- Extend script generation against `ShapedActionSequence` instead of interpreted-event assumptions.

## Downstream Contract

Phase 4 script generation should consume `ShapedActionSequence`, not raw recording truth and not ad hoc interpreted event assumptions.

That means phase 3 should leave the repo with:

- a stable shaped action vocabulary
- config fields that either drive real behavior or are removed
- predictable output that is safe for script generation to depend on
