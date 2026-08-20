# Math Builtin Examples

The runtime now supports numeric helper builtins like `Int()`, `Round()`, `Ceiling()`, `Floor()`, `Exp()`, and `Mod()`. These work in normal `.ass` scripts just like the other function calls in the language.

```ass
Dim value = 3.2
Dim signed_value = -3.7
Dim other = 10

WriteLn("Int: " + Int(value))
WriteLn("Round default: " + Round(value))
WriteLn("Round 1 place: " + Round(1.25, 1))
WriteLn("Round tens: " + Round(123.5, -1))
WriteLn("Ceiling: " + Ceiling(value))
WriteLn("Ceiling negative: " + Ceiling(-1.2))
WriteLn("Floor: " + Floor(value))
WriteLn("Floor negative: " + Floor(-1.2))
WriteLn("Exp: " + Exp(1))
WriteLn("Mod: " + Mod(other, 3))
WriteLn("Int negative: " + Int(signed_value))
WriteLn("Round negative: " + Round(-1.25, 1))
```

Expected output:

```text
Int: 3
Round default: 3
Round 1 place: 1.3
Round tens: 120
Ceiling: 4
Ceiling negative: -1
Floor: 3
Floor negative: -2
Exp: 2.718281828459045
Mod: 1
Int negative: -3
Round negative: -1.3
```

Notes:

- `Int()` returns the integer part of a numeric value by dropping the fractional portion.
- `Round()` rounds to the requested decimal places, including negative positions to the left of the decimal point.
- `Ceiling()` rounds up to the next integer.
- `Floor()` rounds down to the closest integer.
- `Ceiling()` and `Floor()` preserve the same direction for negative values, so `Ceiling(-1.2)` becomes `-1` and `Floor(-1.2)` becomes `-2`.
- `Exp()` returns `e` raised to the given power.
- `Mod()` returns the modulus of two numeric values.

## Related Docs

- [Builtin Coverage Map](builtin_coverage_map.md)
- [Docs Index](../index.md)
