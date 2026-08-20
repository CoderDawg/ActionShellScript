# Architecture

This section contains the architectural direction and system design notes for `ActionShellScript`.

## Start Here
- [North-Star Architecture](north_star_architecture.md)
- [Current Architecture Snapshot](current_architecture_snapshot.md)
- [Phase-by-Phase Dataflow](dataflow_diagram.md)

## Phase Boundaries
- [Phase 2 Interpretation Boundary](phase_2_interpretation_boundary.md)
- [Phase 3 Shaping Boundary](phase_3_shaping_boundary.md)
- [Phase 4 Script-Generation Boundary](phase_4_script_generation_boundary.md)
- [Phase 5 Script-Document Boundary](phase_5_document_boundary.md)
- [Phase 6 Playback Boundary](phase_6_document_boundary.md)
- [Phase 7 Debugger Boundary](phase_7_debugger_boundary.md)

## Cross-Cutting Systems
- [Filter Architecture](filter_architecture.md)
- [Diagnostic Logging Map](diagnostic_logging_map.md)
- [Desktop Help Engine](desktop_help_engine.md)
- [Persistence Architecture](persistence_architecture.md)
- [Struct Layout Contract](../user/struct_layout_contract.md)
- [Structs and DLL Interop](../user/structs_and_dlls.md)

Internal planning notes live under [`docs/internal`](../internal/index.md) and are intentionally omitted from the public architecture index.

## Purpose
Use the north-star architecture document as the primary reference for:

- workflow boundaries
- source-of-truth rules
- phase-by-phase system design
- target layering and directory structure
- migration direction for the fresh repo

Use the boundary notes and cross-cutting docs as the companion references for:

- workflow boundaries
- source-of-truth rules
- system behavior that is stable enough to document publicly
