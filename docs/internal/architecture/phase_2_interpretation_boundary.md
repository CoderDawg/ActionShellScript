# Phase 2 Interpretation Boundary

Phase 2 derives meaning from raw `RecordingSession` events. It does not replace raw recording truth.

## Source Of Truth

- `RecordingSession` remains the only authoritative recording model.
- `InterpretedRecording` is a rebuildable derivative produced from `RecordingSession.events`.
- Interpretation code must treat `session.events` as read-only input.

## Interpreted Event Vocabulary

Phase 2 treats this interpreted event contract as stable for phase-3 consumers.

Every phase-2 output event carries these common fields:

- `type`
- `timestamp_ms`
- `end_timestamp_ms`
- `duration_ms`
- `source_start_index`
- `source_end_index`
- `source_event_count`

Phase 2 currently emits these event types:

- Raw pass-through events such as `mouse_move`, `mouse_down`, `mouse_up`, `mouse_wheel`, `key_down`, and `key_up` when no higher-level meaning is recognized. Pass-through events preserve their normalized raw fields and receive the common provenance/timing fields above.
- `mouse_click` with `button`, `clicks`, `x`, `y`, `press_x`, `press_y`, `release_x`, `release_y`, and `max_move_distance_px`.
- `mouse_drag` with `button`, `x`, `y`, `start_x`, `start_y`, `end_x`, `end_y`, and `distance_px`.
- `key_hold` with `key`.
- `hotkey` with `modifiers`, `trigger_key`, and `keys`.

The common provenance fields preserve the mapping back to raw source events. Mouse-derived events also preserve start and end positions directly on the interpreted event.

## Strictness Policy

Phase 2 intentionally prefers strict, rebuildable interpretation over best-effort guessing.

- Click candidates accept only `mouse_move` events between press and release. Wheel events, keyboard events, or other interleaved event types cause the candidate to remain raw.
- Double-click candidates accept only inter-click `mouse_move` events between the first click and second press. Any other interleaved event type prevents collapse into one multi-click event, but each qualifying single click can still collapse independently.
- Drag candidates accept only `mouse_move` events between press and release. Sparse movement is allowed, but non-mouse interleaving causes the span to remain raw.
- Key-hold candidates allow only modifier activity between the target `key_down` and matching `key_up`. Extra non-modifier key events keep the sequence raw.
- Hotkeys require ordered modifier presses and one derived non-modifier trigger `key_hold`. Once the trigger hold is complete, modifier releases may arrive in any order.
- Unmatched `mouse_down`, `mouse_up`, `key_down`, and `key_up` events remain raw pass-through events.
- Threshold comparisons are inclusive at the exact configured boundary. Values must exceed the configured threshold to be rejected.

## Replacement Rules

- Click recognition replaces raw `mouse_down`/`mouse_move`/`mouse_up` spans only when the span stays within the click movement thresholds.
- Double-click recognition replaces two qualifying click spans plus any qualifying inter-click mouse moves with one `mouse_click` event where `clicks == 2`.
- Drag recognition replaces raw `mouse_down`/`mouse_move`/`mouse_up` spans only when movement and duration satisfy drag thresholds.
- Key-hold recognition replaces non-modifier `key_down`/`key_up` spans when they are unambiguous.
- Hotkey recognition replaces modifier `key_down` events, one derived `key_hold` trigger, and the matching modifier `key_up` events when they form a complete modifier chord.
- Events that do not satisfy a replacement rule remain raw pass-through events.

## Ordering Guarantees

The interpretation pipeline runs in this order:

1. Click recognition
2. Drag recognition
3. Key-hold recognition
4. Hotkey recognition

This ordering keeps simple clicks from being reconsidered as drags, keeps drag-like mouse spans available until drag detection runs, and lets hotkeys build on already-recognized non-modifier key holds.

## Out Of Scope

Phase 2 does not:

- mutate `RecordingSession`
- perform shaping
- choose playback strategy
- plan playback timing beyond preserving source timing information
