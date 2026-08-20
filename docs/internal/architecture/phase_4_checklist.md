# Phase-4 Completion Checklist

Use this checklist to finish the phase-4 script generation slice in ActionShellScript (ASS).

## Goal

Phase 4 is complete when the repo can derive a meaningful `GeneratedScript` from a `ShapedActionSequence` without mutating shaping truth, and when generated script text is stable enough for downstream preview, export, and later conversion into a `ScriptDocument`.

## 1. Freeze the generated-script contract

- Decide the exact role of phase-4 output.
- State whether generated script text is intended to be executable immediately, previewable only, or both.
- Lock down the target script syntax for the current phase.
- Define how generated script should represent:
  - mouse clicks
  - mouse drags
  - mouse movement
  - wheel input
  - key holds
  - hotkeys
  - text
  - delays
- Define what happens when shaped actions are intentionally unsupported.

Done when:
- `GeneratedScript` has a stable contract instead of provisional renderer output.
- Later phases do not need to guess what phase-4 script text means.

## 2. Cover the full shaped-action vocabulary in the renderer

- Review `core/scripting/generation/action_to_script_renderer.py` against the shaped action contract.
- Ensure the renderer intentionally handles every shaped action type phase 4 claims to support.
- Add explicit rendering for currently missing or incomplete action types, especially:
  - `mouse_drag`
  - `hotkey`
  - `key_hold`
- If any shaped action types are intentionally unsupported in phase 4, make that an explicit contract decision instead of silent omission.

Done when:
- The generation renderer covers the full shaped-action vocabulary you intend phase 4 to support.
- Missing action handling is intentional and visible.

## 3. Lock the phase-4 boundary

- Confirm `core/scripting/generation/script_generation_pipeline.py` consumes `ShapedActionSequence` and produces `GeneratedScript` only.
- Confirm generation never mutates `shaped.actions`.
- Confirm generation does not silently become editable script authority.
- Keep `GeneratedScript` explicitly derived and disposable.

Done when:
- `ShapedActionSequence` remains the authoritative shaping output.
- `GeneratedScript` is clearly rebuildable and non-authoritative.

## 4. Tighten header and metadata behavior

- Review `core/scripting/generation/header_comment_renderer.py`.
- Confirm `include_header_comments` and `include_source_summary` behave intentionally.
- Decide whether the current header text is the actual desired script header or temporary wording.
- Decide whether unsupported actions should emit metadata comments, hard failures, or be disallowed before generation.

Done when:
- Header output and metadata behavior are stable enough to be tested and documented.

## 5. Verify line-ending and output normalization behavior

- Review `core/scripting/generation/script_generation_pipeline.py` output assembly.
- Confirm line ending behavior is intentional.
- Confirm trailing newline behavior is intentional.
- Confirm empty output behavior is intentional.
- Confirm config such as `indent`, `line_ending`, `emit_delays`, and `emit_metadata_comments` either drives real behavior or is removed or deferred.

Done when:
- Script text output is stable across runs and platform expectations are clear.
- Config fields are either meaningful or intentionally absent.

## 6. Add generation tests

- Create `tests/generation/`.
- Add tests for `core/scripting/generation/action_to_script_renderer.py`.
- Add tests for `core/scripting/generation/header_comment_renderer.py`.
- Add tests for `core/scripting/generation/script_generation_pipeline.py`.
- Add tests for `application/script_generation_service.py`.
- Verify in tests that:
  - source `ShapedActionSequence` remains unchanged
  - header flags affect output
  - delay-emission flags affect output
  - unsupported actions are handled intentionally
  - line endings and trailing newline behavior are stable

Done when:
- Generation rules are covered and reproducible.
- Regressions in script rendering would be caught by tests.

## 7. Add at least one end-to-end generation path

- Add a small non-UI consumer of `application/script_generation_service.py`.
- This can be:
  - a dedicated CLI command such as `ass-generate`
  - or a test-only pipeline that flows from interpretation into shaping into generation
- Confirm the resulting `GeneratedScript` is usable and summarized correctly.

Done when:
- Phase 4 is proven as a real vertical slice, not just generation modules on disk.

## 8. Document the phase-4 scope

- Add a short doc or section under `docs/internal/architecture/`.
- State clearly:
  - phase 4 consumes `ShapedActionSequence`
  - it does not mutate shaping truth
  - generated script is derived output, not editable authority
  - phase 5 is where authority converts into `ScriptDocument`
- Link it from the architecture docs if helpful.

Done when:
- The repo explains the script-generation boundary clearly enough to prevent future drift.

## 9. Update stale project messaging

- Review project metadata and docs that still describe ASS as phase-1 only.
- Update wording so the repo accurately reflects the implemented slices.
- Make sure phase-4 entry points and docs are discoverable.

Done when:
- The repo no longer presents itself as only a phase-1 recording CLI once phase 4 is actually in place.

## Recommended implementation order

1. Freeze the generated-script contract.
2. Cover the full shaped-action vocabulary in the renderer.
3. Lock the phase-4 boundary.
4. Tighten header and metadata behavior.
5. Verify line-ending and output normalization behavior.
6. Add generation tests.
7. Add one end-to-end consumer path.
8. Add a short phase-4 boundary note.
9. Update stale project messaging.

## Exit criteria for Phase 4

- `ScriptGenerationPipeline` produces a meaningful `GeneratedScript`.
- The renderer covers the full shaped-action vocabulary phase 4 intends to support.
- `GeneratedScript` remains clearly derived and non-authoritative.
- Generation tests exist and pass.
- At least one end-to-end generation path exists.
- The docs explain the phase-4 boundary and usage.
