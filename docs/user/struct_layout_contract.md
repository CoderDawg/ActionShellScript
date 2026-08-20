# Struct Layout Contract

This page defines the current layout contract for `Struct` and is the single source of truth for struct layout and struct return ABI rules. The analyzer and runtime are expected to match this page exactly. The contract itself is platform-neutral; only the DLL interop backend is Windows-specific.

`Record` is intentionally outside this contract. Records are script-only value objects and may contain text or other non-ABI-friendly shapes, so they are not marshaled to native code.

## Default Layout

If no layout clause is present, structs use sequential field order.

```ass
Struct Point
    X As Int32
    Y As Int32
End Struct
```

Rules:

- field order is declaration order
- fields are laid out sequentially
- offsets are aligned per field type
- final struct size is rounded up to the struct alignment

## `Packed(n)`

`Packed(n)` caps field alignment at `n`.

```ass
Struct Point Packed(1)
    X As Int32
    Y As Int16
End Struct
```

Effect:

- each field alignment becomes `min(field_alignment, n)`
- the final struct alignment is also capped by `n`
- `n` must be positive
- the current analyzer expects power-of-two values for ABI-friendliness

## `Align(n)`

`Align(n)` requests a minimum final struct alignment. The current runtime treats this as a hard ABI rule only when it can truly honor the requested alignment; unsupported over-alignment is rejected.

```ass
Struct Vec4 Align(4)
    X As Float32
    Y As Float32
    Z As Float32
    W As Float32
End Struct
```

Effect:

- field order remains sequential
- field offsets still follow normal sequential layout
- the final struct alignment is at least `n`
- `n` must be positive
- the current analyzer expects power-of-two values for ABI-friendliness
- if the runtime cannot honor the requested alignment exactly, the declaration is rejected

## Mutual Exclusivity

Only one layout clause may appear on a struct.

- `Packed(n)` and `Align(n)` are mutually exclusive
- duplicate layout clauses are rejected

## Interop-Safe Field Types

Current DLL-friendly struct fields:

- integer types
- floating-point types
- `Bool`
- `Char`
- `Ptr`
- `IntPtr`
- nested structs that are themselves layout-safe

Rejected for ABI layout:

- `String`
- dynamic collections
- recursive layout cycles
- unknown field types

## ABI Notes

- `Bool` is modeled as a Win32-style integer-width boolean in the current interop layer.
- `Char` is modeled as a single wide character unit.
- Nested structs inherit their own layout rules.
- The runtime computes and caches field offsets, size, alignment, and blittability for layout-safe structs.
- User-declared ABI structs still reject `String` fields for native layout.
- The built-in `GetMonitorInfoEx()` wrapper is a separate script-level exception: it exposes `MonitorInfoEx.szDevice` as a normal script `String` field because the runtime fills the native monitor-name buffer internally. See [Monitor Info Wrapper Path](structs_and_dlls.md#monitor-info-wrapper-path) for the end-to-end flow and the sample demo.

## Narrow ABI Matrix

This matrix captures the current documented contract for the runtime. If a case is not listed here, treat it as unsupported until it is explicitly added.

## Edge Cases

- nested packed and aligned structs keep their own layout rules
- `Align(n)` is accepted only when the runtime can truly honor the requested alignment
- struct return-by-value is limited to fixed-layout, ABI-safe structs that fit in a native pointer-sized return slot
- oversized struct returns are rejected rather than silently downgraded

| Case | Example | Status | Notes |
| --- | --- | --- | --- |
| Default sequential struct | `Struct Point` | Supported | Field order is declaration order; size rounds up to natural alignment. |
| `Packed(1)` struct | `Struct Point Packed(1)` | Supported | Field alignment is capped at 1. |
| `Align(n)` where `n` is truly honored by the runtime | `Struct Vec4 Align(4)` | Supported | Accepted only when the runtime can prove the exact alignment. |
| `Align(n)` over-alignment the runtime cannot honor | `Struct TooWide Align(16)` | Rejected | Fails early instead of silently downgrading. |
| Nested packed structs | `Struct Outer Packed(1)` | Supported | Each nested struct keeps its own layout rules. |
| Nested aligned structs | `Struct Outer Align(4)` | Supported when each struct is individually honored | Alignment does not leak across struct boundaries. |

### Return-by-Value Examples

- Supported: `Struct Point` with `Func MakePoint()` returning `Point(1, 2)` when the struct fits in a native pointer-sized return slot.
- Rejected: `Struct BigRet` with `Func MakeBig()` returning `BigRet(1, 2, 3)` when the return shape is too large or otherwise unsupported.

## Rejection Matrix

These shapes are currently rejected when the backend cannot prove the ABI exactly:

| Shape | Example | Status | Notes |
| --- | --- | --- | --- |
| Oversized struct return-by-value | `BigRet` | Rejected | Use `ByRef` or reduce the struct to a pointer-sized safe subset. |
| Dynamic/native collections in structs | `Values As Array` | Rejected | Fixed-layout only; collections do not have a stable ABI layout here. |
| Function pointers / delegates | `Callback As FuncPtr` | Rejected | Native callable ABI shapes are not yet modeled. |
| Unknown field or return types | `Widget` | Rejected | Types must resolve to a canonical builtin or a declared struct. |
| Recursive layout cycles | `A -> B -> A` | Rejected | The runtime rejects cycles before marshaling. |

## Validation Coverage

The documented ABI contract is pinned by tests in:

- [tests/runtime/test_script_runtime_structs.py](../../tests/runtime/test_script_runtime_structs.py)
- [tests/runtime/test_script_runtime_external_functions.py](../../tests/runtime/test_script_runtime_external_functions.py)
- [tests/unit/test_semantic_analysis_service.py](../../tests/unit/test_semantic_analysis_service.py)

## Related Docs

- [Structs and DLL Interop](structs_and_dlls.md)
- [Monitor Info Wrapper Path](structs_and_dlls.md#monitor-info-wrapper-path)
- [Docs Index](../index.md)
