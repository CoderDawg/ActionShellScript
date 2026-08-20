# Pixel Inspector User Guide

`Pixel Inspector` is the desktop tool for reading the pointer position, live pixel color, and nearby window metadata under the cursor.

Open it from `Tools > Pixel Inspector...` in the desktop app. The built-in `Documentation` action now opens this guide directly.

## What It Shows

The window is organized around three live readouts:

- pointer location, screen index, and screen name
- sampled pixel color, shown in the currently selected numeric base
- window handle and title beneath the pointer, when available

The magnifier preview gives you a zoomed view of the current pointer location, and the output pane shows the current snapshot in a copy-friendly text format.

## Main Controls

- `Capture` pauses or resumes live sampling.
- `Copy` copies the current snapshot text to the clipboard.
- `Pointer Coordinates` shows a live tooltip at the cursor with `X` and `Y`.
- `Coordinate Capture` listens for desktop mouse clicks and records them as `MouseClick(...)` notes in the output pane.
- `Refresh Output` clears any click notes and redraws the current output snapshot.
- `Stay on top` keeps the inspector above other windows.
- `Restore Defaults` returns the tool to its default zoom, base, and window behavior.
- `Documentation` opens this guide.
- `About` shows the short product summary for the tool.

## Toolbar

The toolbar mirrors the main inspection controls for quick access:

- `Copy` copies the current snapshot text to the clipboard.
- `Capture` toggles live sampling on and off.
- `Pointer Coordinates` toggles the cursor tooltip and uses the same red/green state cues as the menu item.
- `Coordinate Capture` toggles click logging and uses the same red/green state cues as the menu item.
- `Refresh Output` clears the click history and redraws the snapshot text.
- `Zoom In` and `Zoom Out` adjust the magnifier scale.
- `Close` exits the Pixel Inspector.
- `Documentation` opens this guide.

## Numeric Base

The color and coordinate readouts can be shown in:

- hexadecimal
- decimal
- octal

Use the `Options` menu to switch bases when you want a different representation for debugging or reporting.

The `Options` menu also includes:

- `Display Base` for choosing hexadecimal, decimal, or octal output
- `Capture` / `Disable Capture` for live sampling
- `Enable Pointer Coordinates` / `Disable Pointer Coordinates` for the cursor tooltip
- `Enable Coordinate Capture` / `Disable Coordinate Capture` for desktop mouse click logging
- `Auto-follow Coordinate Capture` for keeping the output scrolled to the newest click notes when already at the bottom
- `Stay on top` for keeping the window above other windows
- `Refresh Output` for clearing click notes and redrawing the current snapshot
- `Restore Defaults` for resetting the inspector

## Magnifier Workflow

Use the magnifier when you need a closer look at the pixel under the cursor.

1. Move the pointer to the area you want to inspect.
2. Adjust the zoom level with the slider, preset menu, or zoom actions.
3. Pause capture if you want to freeze the current view.
4. Copy the snapshot text when you need to share the values with someone else.

## Platform Note

On Windows, the inspector uses Win32 APIs to resolve the window handle and title beneath the pointer. On other platforms, those fields may be unavailable, but the pointer, pixel, and magnifier readouts still work.

## Related Docs

- [Docs Index](../index.md)
- [GUI Preference Spec](gui_preference_spec.md#goal)
