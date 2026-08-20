# String Helper Examples

This page collects runnable examples for the string helper surface: `StringCompare()`, `StringInStr()`, `StringReplace()`, the regex helpers, the prefix/suffix/split/join helpers, the string slicing and trimming helpers, and the string-friendly runtime values.

## StringCompare

`StringCompare()` compares two strings and returns:

- `0` when the strings are equal
- a value greater than `0` when the first string sorts after the second
- a value less than `0` when the first string sorts before the second

Use `compare_type = 0` for case-insensitive comparison, or `compare_type = 1` for case-sensitive comparison.

```ass
Dim exact_match = StringCompare("Alpha", "Alpha")
Dim case_insensitive_default = StringCompare("Alpha", "alpha")
Dim case_insensitive = StringCompare("Alpha", "alpha", 0)
Dim case_sensitive_explicit = StringCompare("Alpha", "alpha", 1)

WriteLn("exact_match: " + exact_match)
WriteLn("case_insensitive_default: " + case_insensitive_default)
WriteLn("case_insensitive: " + case_insensitive)
WriteLn("case_sensitive_explicit: " + case_sensitive_explicit)
```

Expected output:

```text
exact_match: 0
case_insensitive_default: 0
case_insensitive: 0
case_sensitive_explicit: -1
```

## StringInStr

`StringInStr()` returns the 1-based position of the first matching substring, or `0` when the search misses.

```ass
Dim case_insensitive = StringInStr("Hello World", "world")
Dim case_sensitive = StringInStr("Hello World", "world", 1)
Dim second_match = StringInStr("one two one two", "one", 0, 2)
Dim rightmost_match = StringInStr("one two one two one", "one", 0, -1)
Dim bounded_search = StringInStr("the string to search", "string", 0, 1, 1, 11)

WriteLn("case_insensitive: " + case_insensitive)
WriteLn("case_sensitive: " + case_sensitive)
WriteLn("second_match: " + second_match)
WriteLn("rightmost_match: " + rightmost_match)
WriteLn("bounded_search: " + bounded_search)
```

Expected output:

```text
case_insensitive: 7
case_sensitive: 0
second_match: 9
rightmost_match: 17
bounded_search: 5
```

Notes:

- `case_sensitive` accepts `0` for case-insensitive search or `1` for case-sensitive search.
- `occurrence` can be positive to search from the left or negative to search from the right.
- `start` is 1-based.
- `count` limits the search window and must not be shorter than the needle.

## StringReplace

`StringReplace()` supports two modes:

- search-and-replace mode replaces matching substrings and updates `@Extended` with the replacement count
- start-position mode replaces characters beginning at a 1-based position and ignores the occurrence and case-sensitivity arguments

```ass
Dim text = "one two one two"
Dim replace_all = StringReplace(text, "one", "1")
Dim replace_second = StringReplace(text, "one", "1", 2)
Dim replace_from_right = StringReplace(text, "one", "1", -1)
Dim replace_from_start = StringReplace("abcdef", 3, "XYZ")

WriteLn("replace_all: " + replace_all)
WriteLn("replace_second: " + replace_second)
WriteLn("replace_from_right: " + replace_from_right)
WriteLn("replace_from_start: " + replace_from_start)
WriteLn("@Extended: " + @Extended)
```

Expected output:

```text
replace_all: 1 two 1 two
replace_second: one two 1 two
replace_from_right: one two 1 two
replace_from_start: abXYZef
@Extended: 1
```

Notes:

- `occurrence = 0` replaces all matches.
- positive `occurrence` values replace from left to right.
- negative `occurrence` values replace from right to left.
- `casesense = 0` performs a case-insensitive search, and `casesense = 1` performs a case-sensitive search.
- start-position mode returns an empty string and sets `@Error = 1` if the replacement would run past the end of the string.

## RegexEscape

`RegexEscape()` returns literal text with regex metacharacters escaped so it can be embedded safely in a pattern.

```ass
Dim escaped = RegexEscape("a.b")

WriteLn("escaped: " + escaped)
```

Expected output:

```text
escaped: a\.b
```

## RegexIsMatch

`RegexIsMatch()` returns `1` when the regex matches anywhere in the text and `0` when it does not. Like the other regex helpers, it accepts an optional `options` argument for regex flags.

```ass
Dim matched = RegexIsMatch("Ada Lovelace", "(\w+)\s+(\w+)")
Dim case_insensitive = RegexIsMatch("Hello World", "world", "i")

WriteLn("matched: " + matched)
WriteLn("case_insensitive: " + case_insensitive)
```

Expected output:

```text
matched: 1
case_insensitive: 1
```

## RegexInStr

`RegexInStr()` returns the 1-based position of the first regex match, or `0` when there is no match. The optional `start` argument is 1-based, and an optional `options` argument can supply regex flags.

```ass
Dim position = RegexInStr("one two one two one", "one", 5)

WriteLn("position: " + position)
```

Expected output:

```text
position: 9
```

## Prefix, Suffix, Contains, Split, Join

These helpers cover the common string-shaping cases that sit between `StringInStr()` and `StringReplace()`.

Like the rest of the string search helpers, the prefix/suffix/contains helpers are case-insensitive by default and accept `1` for case-sensitive matching.

```ass
Dim text = "ActionShellScript"
Dim parts = StringSplit("Ada Lovelace", " ")
Dim joined = StringJoin(parts, ", ")

WriteLn("starts_with: " + StringStartsWith(text, "Action"))
WriteLn("ends_with: " + StringEndsWith("report.csv", ".csv"))
WriteLn("contains: " + StringContains("Hello World", "world"))
WriteLn("split_first: " + parts[0])
WriteLn("split_second: " + parts[1])
WriteLn("joined: " + joined)
```

Expected output:

```text
starts_with: 1
ends_with: 1
contains: 1
split_first: Ada
split_second: Lovelace
joined: Ada, Lovelace
```

## RegexMatch

`RegexMatch()` returns `Null` when the pattern does not match. When it does match, the result is an array where element `0` is the full match and the remaining elements are the capture groups in order.

```ass
Dim text = "Ada Lovelace"
Dim match = RegexMatch(text, "(\w+)\s+(\w+)")

If match != Null Then
    WriteLn("full_match: " + match[0])
    WriteLn("first_name: " + match[1])
    WriteLn("last_name: " + match[2])
End If
```

Expected output:

```text
full_match: Ada Lovelace
first_name: Ada
last_name: Lovelace
```

## RegexReplace

`RegexReplace()` supports `$0`, `$1`, `$2`, and so on for replacement backreferences. `$$` emits a literal dollar sign.

Regex matching is case-sensitive by default. Pass `i` in the optional `options` argument when you want case-insensitive matching.

Regex patterns support normal character classes such as `[abc]`, `[a-z]`, `[^abc]`, `\d`, `\w`, and `\s`.

```ass
Dim text = "Ada Lovelace"
Dim swapped = RegexReplace(text, "(\w+)\s+(\w+)", "$2, $1")
Dim numbered = RegexReplace("a1b2c3", "(\d)", "[$1]")

WriteLn("swapped: " + swapped)
WriteLn("numbered: " + numbered)
```

Expected output:

```text
swapped: Lovelace, Ada
numbered: a[1]b[2]c[3]
```

## StringIsAlpha, StringIsAlphaNumeric, StringIsASCII, StringIsDigit, StringIsFloat, StringIsInt, StringIsLower, StringIsSpace, StringIsUpper, StringLength, StringLeft, StringReverse, StringRight, StringMid, StringTrimLeft, StringTrimRight

These helpers cover the common string slicing and trimming cases:

- `StringIsAlpha()` returns `1` when the string contains only alphabetic characters and `0` otherwise.
- Any whitespace in the string causes `StringIsAlpha()` to return `0`.
- `StringIsAlphaNumeric()` returns `1` when the string contains only alphabetic characters and digits and `0` otherwise.
- Any whitespace in the string causes `StringIsAlphaNumeric()` to return `0`.
- `StringIsASCII()` returns `1` when the string contains only ASCII characters in the `0x00-0x7f` range and `0` otherwise.
- `StringIsDigit()` returns `1` when the string contains only digits and `0` otherwise.
- `StringIsFloat()` returns `1` when the value converts to a decimal string with exactly one period and an optional leading `+` or `-`, otherwise `0`.
- `StringIsFloat()` accepts non-string values by converting them to strings first.
- `StringIsInt()` returns `1` when the string contains only an optional leading sign and digits, or when the input is already an integer expression.
- `StringIsLower()` returns `1` when the string contains only lowercase characters and `0` otherwise.
- Digits, punctuation, and whitespace cause `StringIsLower()` to return `0`.
- `StringIsSpace()` returns `1` when the string contains only whitespace characters, including `Chr(0)`, and `0` otherwise.
- `StringIsUpper()` returns `1` when the string contains only uppercase characters and `0` otherwise.
- Digits, punctuation, and whitespace cause `StringIsUpper()` to return `0`.
- `StringLength()` returns the number of characters in a string.
- `StringLeft()` returns the leftmost characters, or the entire string when `count` is larger than the string length.
- `StringReverse()` returns the string with the character order reversed.
- `StringRight()` returns the rightmost characters, or the entire string when `count` is larger than the string length.
- `StringMid()` returns a substring starting at a 1-based position and uses the remainder of the string when `count` is omitted.
- `StringTrimLeft()` returns the string with `count` characters removed from the left.
- `StringTrimRight()` returns the string with `count` characters removed from the right.
- `StringTrimLeft()` and `StringTrimRight()` return an empty string when `count` is out of bounds.

```ass
Dim text = "Hello World"

Dim alpha_only = StringIsAlpha("Café")
Dim alpha_numeric_only = StringIsAlphaNumeric("Café42")
Dim ascii_only = StringIsASCII("ASCII text")
Dim digit_only = StringIsDigit("012345")
Dim float_only = StringIsFloat(1.25)
Dim int_only = StringIsInt(42)
Dim lower_only = StringIsLower("lowercase")
Dim space_only = StringIsSpace(" \t\r\n")
Dim upper_only = StringIsUpper("UPPERCASE")
Dim length_value = StringLength(text)
Dim left_value = StringLeft(text, 5)
Dim reverse_value = StringReverse(text)
Dim right_value = StringRight(text, 5)
Dim mid_value = StringMid(text, 7, 5)
Dim trim_left_value = StringTrimLeft(text, 6)
Dim trim_right_value = StringTrimRight(text, 6)

WriteLn("alpha_only: " + alpha_only)
WriteLn("alpha_numeric_only: " + alpha_numeric_only)
WriteLn("ascii_only: " + ascii_only)
WriteLn("digit_only: " + digit_only)
WriteLn("float_only: " + float_only)
WriteLn("int_only: " + int_only)
WriteLn("lower_only: " + lower_only)
WriteLn("space_only: " + space_only)
WriteLn("upper_only: " + upper_only)
WriteLn("length_value: " + length_value)
WriteLn("left_value: " + left_value)
WriteLn("reverse_value: " + reverse_value)
WriteLn("right_value: " + right_value)
WriteLn("mid_value: " + mid_value)
WriteLn("trim_left_value: " + trim_left_value)
WriteLn("trim_right_value: " + trim_right_value)
```

Expected output:

```text
alpha_only: 1
alpha_numeric_only: 1
ascii_only: 1
digit_only: 1
float_only: 1
int_only: 1
lower_only: 1
space_only: 1
upper_only: 1
length_value: 11
left_value: Hello
reverse_value: dlroW olleH
right_value: World
mid_value: World
trim_left_value: World
trim_right_value: Hello
```

## Runtime Values

The runtime also exposes string-friendly `@` values such as `@CR`, `@LF`, `@CRLF`, `@TAB`, `@ScriptName`, `@ScriptDirectory`, and `@WorkingDir`. `@Error` carries the last runtime error code, and `@Extended` carries the replacement count from `StringReplace()`.

```ass
WriteLn(@ScriptName)
WriteLn(@ScriptDirectory)
WriteLn(@WorkingDir)
WriteLn("A" & @TAB & "B")
WriteLn("Line 1" & @CRLF & "Line 2")
```

The exact directory values vary by script location and launch directory, so the output depends on your machine.

## Related Docs

- [Builtin Coverage Map](builtin_coverage_map.md)
- [Docs Index](../index.md)
