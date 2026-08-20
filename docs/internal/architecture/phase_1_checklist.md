# Phase-1 Completion Checklist

Use this checklist to finish the phase-1 recording CLI slice in ActionShellScript (ASS).

## Goal

Phase 1 is complete when the repo can start a recording session, capture raw global input, stop cleanly, and return a `RecordingSession` without requiring interpretation, shaping, playback, or editor workflows.

## 1. Package the repo so Phase 1 is runnable

- Add `pyproject.toml`.
- Declare the Python version target.
- Add `pynput` as a dependency.
- Add a console entry point for the recording CLI.
- Decide whether ASS is installed as a package or run as a source tree, and make imports consistent with that choice.

Done when:
- `python -m pip install -r requirements.txt` works from the repo root and installs the local checkout in editable mode with the `dev` extra. The equivalent direct command is `python -m pip install -e .[dev]`.
- The CLI can be launched from an installed entry point or a clean module invocation.

## 2. Make the CLI execution path clean and stable

- Verify `apps/cli/main.py` is the intended entry module.
- Verify `apps/cli/record_command.py` is the only phase-1 command surface.
- Remove any temporary `sys.path` hacks if packaging makes them unnecessary.
- Confirm absolute imports and package layout are consistent.

Done when:
- The recording command starts from the repo root without import errors.
- The same command path works after editable install.

## 3. Verify the recording slice end to end

- Run the CLI against the real `infrastructure/input/pynput_backend.py`.
- Confirm `start -> capture -> Ctrl+C -> stop -> summary` works.
- Confirm mouse move, mouse button, wheel, and keyboard events are captured as raw events.
- Confirm session state changes are correct in `core/recording/session_recorder.py`.
- Confirm relative timestamps are sane.

Done when:
- A short manual recording completes without crashing.
- The returned `RecordingSession` contains raw events and correct start/stop metadata.

## 4. Add minimal unit tests for the recording domain

- Add tests for `core/recording/recording_session.py`:
  - start
  - stop
  - append event only while recording
  - duration calculation
- Add tests for `core/recording/session_recorder.py`:
  - start success
  - start rollback on capture failure
  - stop success
  - reset behavior
  - filtering by config flags
- Add tests for `core/recording/recorder_config.py`:
  - valid defaults
  - threshold validation
- Add a fake backend test double for `core/recording/input_capture.py`.

Done when:
- Phase-1 tests run without needing real OS input hooks.
- The recorder lifecycle is covered by focused tests.

## 5. Keep raw-event authority clean

- Review `core/recording/event_normalizer.py`.
- Decide one of:
  - remove it from phase-1 usage entirely
  - rename or narrow it to a raw-event validator only
  - leave it present but unused until later phases
- Confirm `core/recording/session_recorder.py` stores raw events only.

Done when:
- There is no normalization, interpretation, or shaping in the authoritative phase-1 recording path.

## 6. Tighten config and backend alignment

- Verify `core/recording/recorder_config.py` matches what `infrastructure/input/pynput_backend.py` actually reads.
- Verify event names emitted by the backend match what `core/recording/session_recorder.py` accepts:
  - `mouse_move`
  - `mouse_down`
  - `mouse_up`
  - `mouse_wheel`
  - `key_down`
  - `key_up`
- Decide whether filtering belongs in backend, recorder, or both, and keep it intentional.

Done when:
- Backend, config, and recorder use one consistent event vocabulary and one consistent set of capture flags.

## 7. Clean repo and package hygiene

- Add missing `__init__.py` files only where needed for your packaging choice.
- Fix small naming drift like the docstring header in `infrastructure/debug_logger.py`.
- Make sure there is one clear tests location and naming convention.
- Remove placeholder or misleading files if they create confusion for phase 1.

Done when:
- The repo layout reads like an intentional fresh repo, not a half-migrated prototype.

## 8. Write a tiny phase-1 usage note

- Add a short section to the docs explaining how to run the recording CLI.
- Include install and run steps.
- Include the current phase-1 scope:
  - raw recording only
  - no interpretation
  - no playback
  - no editor authority

Done when:
- Someone opening the repo can run phase 1 without reading the whole architecture doc.

## 9. Define the explicit phase-1 exit criteria

- Recording starts from the CLI.
- Raw global input is captured.
- `RecordingSession` is the only recording truth.
- `SessionRecorder.stop()` returns a completed session.
- No interpretation, shaping, or generation is required for the recorder to function.
- Tests cover the lifecycle and config gating.
- The repo is installable and runnable.

## Recommended implementation order

1. Add `pyproject.toml`.
2. Verify the CLI import and run path.
3. Run one manual recording end to end.
4. Add fake-backend tests.
5. Remove or quarantine `event_normalizer.py` from the phase-1 path.
6. Clean small repo hygiene issues.
7. Add a short run doc.
