# Generate Script Guide

This guide shows how to use `ass-generate` to turn a saved raw recording session into phase-4 script text.

## What `ass-generate` Does

`ass-generate` runs the full recording-derived pipeline on a saved session file:

1. load raw session JSON
2. interpret it into higher-level meaning
3. shape that meaning into script-friendly actions
4. generate derived ASS script text

The generated script is useful for preview and export. It is not editable authority yet. In the current workflow, editable script authority starts later when generated text is explicitly converted into a `ScriptDocument`.

## Basic Usage

Generate a script preview from a saved session:

```powershell
ass-generate .\session.json
```

Generate from one of the sample fixtures:

```powershell
ass-generate .\samples\hotkey_copy.json
ass-generate .\samples\drag.json
```

Write the generated script to a file:

```powershell
ass-generate .\samples\drag.json --output .\generated.ass
```

## Common Options

Hide header comments:

```powershell
ass-generate .\session.json --no-header-comments
```

Hide source-summary comments but keep the main header:

```powershell
ass-generate .\session.json --no-source-summary
```

Drop standalone delay actions from generated output:

```powershell
ass-generate .\session.json --no-script-delays
```

Emit comments for unknown non-contract actions:

```powershell
ass-generate .\session.json --emit-unsupported-comments
```

Write CRLF line endings:

```powershell
ass-generate .\session.json --line-ending crlf --output .\generated.ass
```

## What The Output Looks Like

Depending on the shaped actions, generated script text may contain calls such as:

- `MouseClick("left", 100, 200, 1)`
- `Hotkey("ctrl", "c")`
- `SendText("hello")`
- `Sleep(250)`

Phase 4 also renders:

- `key_hold` as `KeyDown`, optional `Sleep`, then `KeyUp`
- `mouse_drag` as `MouseMove`, `MouseDown`, optional `Sleep`, `MouseMove`, `MouseUp`
- `hotkey` from shaped `keys`, or from shaped `modifiers` plus `trigger_key` when needed

## Keyboard Decision Tree

When you are deciding how recorded keyboard input should be represented, use this rule of thumb:

- Is the user entering literal text into a field?
  - Yes: shape it as `text`, then render it as `SendText(...)`
  - No: keep going
- Is the key a shortcut or modifier chord?
  - Examples: `Ctrl+C`, `Alt+Tab`, `Shift+Esc`
  - Yes: keep it as `hotkey`, or as explicit `KeyDown(...)` and `KeyUp(...)` when the exact press order matters
  - No: keep going
- Is the key a non-printable control key?
  - Examples: `Enter`, `Tab`, `Esc`, arrows, `Backspace`, `Delete`, `Home`, `End`
  - Yes: keep it as `KeyDown(...)` and `KeyUp(...)`
  - No: keep going
- Is the key a printable character being held as a real physical key press?
  - Examples: game controls, deliberate press-and-hold behavior, or timing-sensitive input
  - Yes: keep it as `KeyDown(...)` and `KeyUp(...)`
  - No: if it is ordinary typing, prefer `SendText(...)`

Short version:

- `SendText(...)` for typing words, sentences, punctuation, and other literal text
- `KeyDown(...)` / `KeyUp(...)` for physical key actions, shortcuts, and control keys

Capitalized text typed with `Shift`, like the `T` in a sentence start, should still be treated as literal text when you are using the text-oriented pipeline.

If a known shaped action reaches generation without the required contract fields, phase 4 emits a `# Unsupported shaped action: ...` comment instead of silently dropping that action.

## Typical Workflow

Record and save a session:

```powershell
ass-record --save-raw .\session.json
```

Generate script from that saved session:

```powershell
ass-generate .\session.json --output .\generated.ass
```

Preview shaping before generation when you want to inspect the intermediate action vocabulary:

```powershell
ass-shape .\session.json --show-actions
```

## Related Docs

- [Docs Index](../index.md)
