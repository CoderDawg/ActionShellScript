# Phase-By-Phase Dataflow

Snapshot date: 2026-04-25

This diagram shows the current end-to-end dataflow from raw recording to playback. It reflects the present source-of-truth boundaries in the codebase, including the fact that playback can be derived from either a recorded session or an authoritative script document.

```mermaid
flowchart TD
    A["Phase 1<br/>Raw recording capture"] --> B["`RecordingSession`<br/>raw events + timestamps"]
    B --> C["Phase 2<br/>Interpretation"]
    C --> D["`InterpretedRecording`<br/>clicks, drags, holds, hotkeys"]
    D --> E["Phase 3<br/>Shaping"]
    E --> F["`ShapedActionSequence`<br/>normalized downstream actions"]
    F --> G["Phase 4<br/>Script generation"]
    G --> H["`GeneratedScript`<br/>derived script text"]
    H --> I["Phase 5<br/>Document conversion"]
    I --> J["`ScriptDocument`<br/>authoritative editable text"]
    J --> K["Phase 5<br/>Parse + diagnostics + formatting"]
    K --> L["Document language services"]

    B --> M["Phase 6<br/>Playback from recording"]
    J --> N["Phase 6<br/>Playback from script"]

    M --> O["`PlaybackPlan`<br/>derived executable events"]
    N --> O
    O --> P["`PlaybackEngine`"]
    P --> Q["Preview executor"]
    P --> R["Live executor"]
    Q --> S["Preview result"]
    R --> T["Host input events"]
    R --> U["Live result"]

    subgraph RecordingPath["Recording authority path"]
        A
        B
        C
        D
        E
        F
        G
        H
        I
        J
        K
        L
    end

    subgraph PlaybackPath["Playback authority paths"]
        M
        N
        O
        P
        Q
        R
        S
        T
        U
    end

    style A fill:#fdf2e9,stroke:#b45309,color:#111827
    style C fill:#eff6ff,stroke:#2563eb,color:#111827
    style E fill:#ecfeff,stroke:#0891b2,color:#111827
    style G fill:#f5f3ff,stroke:#7c3aed,color:#111827
    style I fill:#f0fdf4,stroke:#16a34a,color:#111827
    style M fill:#fff7ed,stroke:#ea580c,color:#111827
    style N fill:#fff7ed,stroke:#ea580c,color:#111827
    style P fill:#f8fafc,stroke:#334155,color:#111827
    style Q fill:#f8fafc,stroke:#334155,color:#111827
    style R fill:#f8fafc,stroke:#334155,color:#111827
```

## What The Diagram Means

- Phase 1 is the only place raw desktop events enter the system.
- Phase 2 derives semantic meaning from raw recording without mutating the original session.
- Phase 3 rewrites interpreted truth into a representation better suited for generation and playback.
- Phase 4 renders derived actions into script text.
- Phase 5 turns that derived text into an authoritative `ScriptDocument` and then analyzes the document as a document, not as a recording artifact.
- Phase 6 can derive playback either from the recording source or from the script source, but it always produces an explicit `PlaybackPlan` before execution.
- Preview playback records the executed events in memory, while live playback routes through the OS input adapter.

## Current Boundary Notes

- `RecordingSession` remains the source of truth for raw input.
- `GeneratedScript` is still derived until it is converted into `ScriptDocument`.
- Playback does not infer the source; the CLI and service layer require an explicit source kind.
- The runtime compiler path is already used by script playback, but the full execution surface is still partially stubbed in `core/runtime/script_runtime.py`.
