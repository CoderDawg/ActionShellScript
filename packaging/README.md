# Packaging and Release Notes

This folder contains the scripts and definitions used to stage, bundle, and install `ActionShellScript` for Windows.

Project home: [CoderDawg/ActionShellScript](https://github.com/CoderDawg/ActionShellScript)

## Files

- `scripts/build_release.ps1`
- `scripts/sync-common.ps1`
- `scripts/sync-packaging.ps1`
- `scripts/sync-release.ps1`
- `scripts/sync-all.ps1`
- `pyinstaller/ActionShellScript.spec`
- `installer/ActionShellScript.iss`

## Requirements

- PowerShell 7 (`pwsh`) to run the packaging scripts.
- Python with the project dependencies installed.
- `PyInstaller` available on `PATH` or in the active Python environment.
- If `.\.venv\Scripts\pyinstaller.exe` is missing, `build_release.ps1` falls back to `python -m PyInstaller` through the selected interpreter.
- `Inno Setup 6` installed so `ISCC.exe` is available on `PATH`, or pass `-InnoCompilerPath` to `build_release.ps1`.
- A destination checkout path for the sync scripts, passed with `-OneDriveRepoRoot` or stored in `ASS_ONE_DRIVE_REPO_ROOT`.

## Release Pipeline

`scripts/build_release.ps1` supports three phases:

- `-Stage`
  - Copies the release-ready files into `release_stage`.
- `-PyInstaller`
  - Runs `pyinstaller` against `pyinstaller\ActionShellScript.spec`.
  - Uses the staged tree as the source when the full pipeline is running.
  - Prunes QtWebEngine debug payloads from `release_stage\dist` before the installer step so they do not bloat the shipped bundles or `ActionShellScript-Setup.exe`.
- `-Inno`
  - Compiles `installer\ActionShellScript.iss` with Inno Setup.

If you do not pass any step flags, the script runs the full pipeline:

1. Stage
2. PyInstaller
3. Inno Setup

## Release Naming

For the current pre-release line, use the same version token everywhere:

- Git tag: `v0.2.0a2`
- Release title: `ActionShellScript v0.2.0a2`
- Release note heading: `v0.2.0a2 - Alpha 2`
- Installer and package version: `0.2.0a2`
- Windows file version embedded in the installer: `0.2.0.1`

That keeps the repo history, installer metadata, and published artifacts aligned while still using a Windows-safe numeric file version for Inno Setup.

### Example commands

Run the full release pipeline:

```powershell
pwsh -File .\packaging\scripts\build_release.ps1 -Clean
```

Stage only:

```powershell
pwsh -File .\packaging\scripts\build_release.ps1 -Stage -Clean
```

PyInstaller only:

```powershell
pwsh -File .\packaging\scripts\build_release.ps1 -PyInstaller
```

Inno Setup only:

```powershell
pwsh -File .\packaging\scripts\build_release.ps1 -Inno
```

Packaging notes only:

```powershell
pwsh -File .\packaging\scripts\build_release.ps1 -PackagingNotesOnly
```

Use this when you just want the current project version, Git tag, installer/file version, and SHA256 for `ActionShellScript-Setup.exe` without running the release pipeline.

If Inno Setup is installed in a nonstandard location:

```powershell
pwsh -File .\packaging\scripts\build_release.ps1 -Inno -InnoCompilerPath "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

## Staging Layout

The staging root defaults to:

```text
<repo root>\release_stage
```

The scripts resolve `<repo root>` from the checkout they are run from, so the same commands work in a fresh Codex worktree without editing any paths.

The staging script copies the release-ready source tree and runtime assets into that folder, then writes:

- `stage-manifest.txt`

## Full Build Inputs and Outputs

### Inputs

For a full release build, the release script starts from the repo root and stages the release-ready files from:

- `apps\cli`
- `apps\desktop`
- `application`
- `core`
- `editor`
- `infrastructure`
- `docs`
- `samples`
- top-level files such as `README.md`, `pyproject.toml`, and `table_api.py`
- runtime assets under:
  - `apps\desktop\assets`
  - `assets`

The PyInstaller spec reads from the staged tree via `ASS_RELEASE_SOURCE_ROOT`.

The Inno Setup script installs from:

```text
release_stage\dist\*
```

### Outputs

For a full build, the output folders land here:

- Staged tree:
  - `release_stage`
- PyInstaller build output:
  - `release_stage\dist`
- PyInstaller work files:
  - `release_stage\build`
- Installer output:
  - `release_stage\installer`

The exact absolute path depends on the checkout, but it always resolves under that checkout's `release_stage` folder.

The installer output is expected to include the compiled setup executable:

```text
<repo root>\release_stage\installer\ActionShellScript-Setup.exe
```

## Uninstall Behavior

The Inno Setup installer is configured to clean up the app's default install and per-user
data locations during uninstall:

- the installed application tree under `{app}`
- the app-owned profile tree under `{userappdata}\ActionShellScript`

That covers the standard desktop settings file at `desktop_settings.json` as well as the
default recordings folders under the app-managed user data tree. Custom recording or log
paths that the user has pointed outside that tree are left alone.

## PyInstaller Spec

`pyinstaller\ActionShellScript.spec` builds these launchers:

- `ass-cli`
- `ass-record`
- `ass-interpret`
- `ass-record-interpret`
- `ass-shape`
- `ass-generate`
- `ass-open-script`
- `ass-play`
- `ass-debug`
- `ass-filter-recording`
- `ass-filter-interpretation`
- `ass-filter-shaping`
- `ass-filter-document`
- `ass-gui`
- `ass-help`

The desktop and help bundles also include the runtime data they need:

- `docs`
- `samples`
- `assets`
- `apps/desktop/assets`
- `apps/desktop/table_api/README.md`

The desktop PyInstaller bundle also installs a runtime hook that sets `ASS_DESKTOP_ASSET_ROOT`
to the bundled `apps/desktop/assets` directory so icon lookups stay explicit in the frozen app.

The same bundle also sets `ASS_SHARED_ASSET_ROOT` to the bundled top-level `assets` directory
for shared assets used outside the desktop-specific asset folder.

The release pipeline reads `packaging/asset_manifest.json` through the tiny
`packaging/asset_manifest.py` helper for the small set of packaging-time asset paths, then
generates the Inno Setup include file in the staged tree from that manifest so the installer stays
on the same source of truth as staging.

## Sync Scripts

These helper scripts mirror packaging artifacts between the worktree checkout and the OneDrive checkout:

- `scripts/sync-packaging.ps1`
  - Mirrors the `packaging` folder.
- `scripts/sync-release.ps1`
  - Mirrors the staged `release_stage` output.
- `scripts/sync-all.ps1`
  - Runs both sync steps and prints a compact summary.

The sync scripts resolve the current checkout automatically, so these commands work from a new Codex worktree without hardcoded worktree paths:

```powershell
pwsh -File .\packaging\scripts\sync-packaging.ps1 -OneDriveRepoRoot "C:\path\to\destination\ActionShellScript"
pwsh -File .\packaging\scripts\sync-release.ps1 -OneDriveRepoRoot "C:\path\to\destination\ActionShellScript"
pwsh -File .\packaging\scripts\sync-all.ps1 -OneDriveRepoRoot "C:\path\to\destination\ActionShellScript"
```

If you prefer, set `ASS_ONE_DRIVE_REPO_ROOT` once and omit the flag on later runs:

```powershell
$env:ASS_ONE_DRIVE_REPO_ROOT = "C:\path\to\destination\ActionShellScript"
```

Use `scripts/sync-all.ps1` after changing packaging files or after a release build if you want the staged output copied to the destination checkout.
