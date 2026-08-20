# Builtin Reconciliation Plan

This document reconciles the old `Macro_Recorder` builtin surface with the current `ActionShellScript` runtime.

Its purpose is not to dismiss or discard the earlier builtin work.

Its purpose is to do three things at once:

- protect prior work
- clarify present ASS support
- plan future recovery intentionally

## Why This Document Exists

The old `Macro_Recorder` project accumulated a substantial builtin surface over time. That work represents real runtime behavior, host-integration decisions, validation rules, and testable scripting capability.

ASS currently carries only part of that capability forward.

At the moment there are three related but different builtin truths in ASS:

- the broad name list in [core/runtime/builtins/builtin_registry.py](../../../core/runtime/builtins/builtin_registry.py)
- the actively recovered dispatcher in [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py)
- the status notes in [docs/user/builtin_coverage_map.md](../../user/builtin_coverage_map.md)

This document is here to align those truths without treating the old builtin work as wasted.

## Guiding Principle

The old builtins should be treated as:

- existing prior capability
- partially migrated runtime surface
- preserved recovery candidates where that makes sense

They should not be treated automatically as:

- mistakes
- clutter to erase
- functionality ASS should never support again

At the same time, ASS should not overstate what its runtime actually supports today.

## Current Situation

The broad old builtin name surface still survives in ASS primarily through:

- [core/runtime/builtins/builtin_registry.py](../../../core/runtime/builtins/builtin_registry.py)

But the active runtime dispatcher in:

- [core/runtime/script_runtime.py](../../../core/runtime/script_runtime.py)

now supports the playback, host-interaction, file/path, binary/encoding, and utility builtins that were recovered during the migration slices.

The older fuller implementation still exists in the legacy project at:

- `packages/app_core/runtime/builtin_macro_calls.py`

That older file should be understood as a preserved capability source, not as something ASS has to pretend is already live.

## What This Plan Is Trying To Protect

The old builtin work still matters in at least four ways:

### 1. Behavioral design

The old project already answered many questions about:

- argument validation
- host service boundaries
- file/path semantics
- binary conversion behavior
- keyboard and mouse convenience helpers

Those decisions still have value even when the code is not yet migrated into ASS.

### 2. Migration leverage

When ASS wants one of those capabilities back, it often does not need to invent it from scratch.

It can recover:

- runtime behavior
- validation rules
- error messages
- tests

from the old implementation selectively.

### 3. Scope discipline

A preserved legacy capability list helps ASS make conscious choices about:

- what belongs in the current contract
- what is deferred
- what is intentionally out of scope

### 4. Future scripting growth

If ASS expands beyond playback-first automation into richer host or utility scripting, much of that earlier builtin work becomes directly relevant again.

## What Needs Clarification

ASS needs to separate these categories more clearly.

### Implemented In ASS Now

These builtins are part of the active ASS runtime contract because they are actually dispatched today.

#### Action and playback builtins

- `Sleep`
- `MouseMove`
- `MouseDown`
- `MouseUp`
- `MouseClick`
- `MouseWheel`
- `KeyDown`
- `KeyUp`
- `Hotkey`
- `SendText`
- `GetMouseMoveSpeed`
- `SetMouseMoveSpeed`

#### Host-interaction builtins

- `KeyToggle`
- `MsgBox`
- `PixelGetColor`
- `PixelSearch`

#### File and path builtins

- `ReadFile`
- `WriteFile`
- `AppendFile`
- `FileExists`
- `DeleteFile`
- `CreateDir`
- `DirExists`
- `PathExists`
- `PathCombine`
- `PathNormalize`
- `IsPathValid`
- `FileName`
- `DirectoryName`
- `ExtensionName`

#### Binary and encoding builtins

- `ReadBytes`
- `WriteBytes`
- `AppendBytes`
- `BinaryLength`
- `Hex`
- `FromHex`
- `Base64`
- `FromBase64`
- `Binary`
- `BinaryMid`
- `BinaryToString`

#### Output and diagnostic builtins

- `Write`
- `WriteLn`
- `DiagWrite`
- `DiagWriteLn`

#### Small utility and conversion builtins

- `String`
- `Abs`
- `Asc`
- `AscW`
- `Chr`
- `ChrW`
- `BitAnd`
- `BitNot`
- `BitNotUnsigned`
- `BitRotate`
- `BitShift`
- `BitOr`
- `BitXor`

These are the builtins ASS should present as currently supported.

### Recovered In ASS Now

These older builtins fit ASS well and are now part of the recovered runtime surface:

- `KeyPress`
- `SendKeys`
- `MouseClickDrag`
- `MouseDrag`
- `GetMouseMoveSpeed`
- `SetMouseMoveSpeed`
- `KeyToggle`
- `MsgBox`
- `PixelGetColor`
- `PixelSearch`
- `ReadFile`
- `WriteFile`
- `AppendFile`
- `FileExists`
- `DeleteFile`
- `CreateDir`
- `DirExists`
- `PathExists`
- `PathCombine`
- `PathNormalize`
- `IsPathValid`
- `FileName`
- `DirectoryName`
- `ExtensionName`
- `ReadBytes`
- `WriteBytes`
- `AppendBytes`
- `BinaryLength`
- `Hex`
- `FromHex`
- `Base64`
- `FromBase64`
- `Binary`
- `BinaryMid`
- `BinaryToString`
- `BitNotUnsigned`
- `BitRotate`

These are no longer “future candidates”; they are currently implemented runtime behavior.

## What Should Change In ASS Now

The main goal is not to erase the old builtins.

The main goal is to make ASS honest about which of them are:

- active now
- likely next
- preserved but deferred

## Recommended Terminology

Use these terms in docs and planning:

### Supported Now

Meaning:

- builtins that are actively implemented in the ASS runtime
- in practice, this now includes the playback, host, file/path, binary, and utility slices recovered from `Macro_Recorder`

### Planned Next

Meaning:

- optional follow-on work such as helper extraction, refactors, or additional scripting surface beyond the current migration map

### Deferred From Macro_Recorder

Meaning:

- legacy source material preserved for reference
- not currently required for the active ASS runtime contract

This wording is much better than language that sounds like the old work is being abandoned.

## Recommended Near-Term Runtime Contract

### Keep active now

Keep the recovered runtime surface as the present ASS contract:

- playback builtins
- output and diagnostics
- host-interaction helpers
- file/path helpers
- binary/encoding helpers
- the remaining small utility and bitwise helpers recovered in the final slice

## Registry Guidance

The builtin registry and runtime dispatcher are now aligned for the recovered migration surface.

Any future names added to the registry should be accompanied by explicit runtime support, tests, and documentation updates so the recovered contract stays honest.

## Documentation Guidance

[docs/user/builtin_coverage_map.md](../../user/builtin_coverage_map.md) should evolve from “mismatch report” into a stable support map.

Recommended sections:

- `Supported Now`
- `Planned Next`
- `Deferred From Macro_Recorder`

That document should help users understand:

- what works today
- what future helper or scope expansion work is under consideration
- what remains preserved only as reference material

## Runtime Error Guidance

[core/runtime/runtime_errors.py](../../../core/runtime/runtime_errors.py) now serves as the validation surface for the recovered runtime behavior.

Keep extending it in step with any future builtin additions so the runtime errors stay descriptive and aligned with the dispatcher.

## Test Guidance

ASS should add a guardrail so the registry, dispatcher, and docs do not drift apart again.

Recommended addition:

- a coverage-oriented test that compares the builtin registry against the runtime dispatcher surface

This should protect the recovered contract and make future expansion deliberate.

## Recommended Reconciliation Order

### 1. Clarify categories

Explicitly classify builtins as:

- supported now
- planned next
- deferred from `Macro_Recorder`

### 2. Update the user-facing builtin map

Rewrite [docs/user/builtin_coverage_map.md](../../user/builtin_coverage_map.md) using those categories.

### 3. Decide registry strictness

Keep the registry aligned with the runtime for anything that is intended to be active.

### 4. Add or refine tests for future expansion

Protect the recovered builtin contract so registry/runtime drift does not quietly return.

### 5. Document any future scope expansion intentionally

If ASS expands beyond the current surface, document the new slice explicitly rather than folding it into the existing recovered contract.

## Practical Recommendation

For ASS now, the most balanced path is:

- keep the current supported runtime surface honest
- preserve respect for the older builtin work
- keep future expansion intentional and documented
- avoid blurring recovered behavior with unrelated helper-extraction work

## Exit Criteria

This reconciliation is in a good place when:

- ASS clearly describes the recovered runtime surface
- the builtin registry and dispatcher stay aligned
- the user docs reflect the current implementation state
- any future expansion has an explicit, documented plan
- tests protect the builtin contract from drifting again

## Short Version

The older builtin work should be treated as valuable preserved capability, not as clutter.

ASS still needs to be truthful about what is live today.

The right path is:

- protect prior work
- clarify present support
- keep the recovered surface documented
- expand intentionally when there is a new scope decision
