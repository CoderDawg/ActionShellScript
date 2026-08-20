# Desktop Help Engine

This document describes the built-in help browser used by the desktop app and the Pixel Inspector tool.

## Purpose

The help engine gives ASS a local, in-app documentation surface instead of sending users to an external browser for built-in docs.

It is intended to:

- keep help content inside the desktop workflow
- provide a searchable table of contents over the bundled docs
- open a guide at a specific section when a tool has a natural landing point
- reuse the same theme-aware styling language as the rest of the desktop UI

## Ownership

The help engine is owned by the desktop frontend.

It lives in [apps/desktop/help_browser.py](../../apps/desktop/help_browser.py) and is reused by:

- [apps/desktop/window.py](../../apps/desktop/window.py) for the main workbench Documentation action
- [apps/desktop/pixel_inspector_window.py](../../apps/desktop/pixel_inspector_window.py) for the Pixel Inspector Documentation action
- [apps/desktop/help_main.py](../../apps/desktop/help_main.py) for the standalone `ass-help` launcher

## Behavior

The help browser loads local markdown and HTML files from the bundled `docs` tree.

It provides:

- a left-side table of contents
- live search across both topic titles and guide body text
- snippet rendering and match highlighting in the topic list
- theme-aware accent styling for the toolbar, navigation header, cards, and empty-state callouts
- section-aware opening for guides that define a natural landing heading

When a guide is opened with a section target, the browser:

1. loads the document
2. injects stable heading IDs into rendered markdown pages
3. scrolls to the requested heading by `id` when possible
4. falls back to matching the visible heading text when an explicit ID is not available

## Section-Aware Opening

The browser exposes two related entry points:

- `open_document(path, anchor_id=..., anchor_text=...)`
- `open_at_section(path, section_id, anchor_text=...)`

Use `open_at_section(...)` when a caller knows the target section up front.

Use `open_document(...)` when the caller only has a path or needs the more general behavior.

The current built-in guide defaults are:

- Generate Script Guide -> `what-ass-generate-does`
- Open Script Guide -> `what-ass-open-script-does`
- Struct and DLL Quickstart -> `what-you-can-write`
- Structs and DLL Interop -> `monitor-info-wrapper-path`
- Struct Layout Contract -> `abi-notes`
- Monitor Info Wrapper Demo -> `monitor-info-wrapper-demo`
- GUI Preference Spec -> `goal`
- Pixel Inspector Guide -> `main-controls`
- CLI Cheat Sheet -> `phase-1-record`

These anchors are used by the help browser home page, the TOC navigation, and the docs landing page links.

## Link Handling

Local links inside the help browser stay inside the app when they point at bundled docs.

If a link contains a fragment, the browser treats that fragment as a section target and tries to jump to the matching heading.

External links still go through the system browser.

## Why This Exists

This browser keeps the documentation path consistent across the app:

- users can browse docs without leaving ASS
- tools can launch their guide at the most relevant section
- the help browser can run as its own desktop surface without starting the main workbench
- the same docs tree powers the workbench home page, the TOC, and the linked guides

It also reduces duplication by giving the desktop app one shared help implementation instead of one-off per-window documentation dialogs.
