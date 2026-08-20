# Array Helper Examples

This page collects runnable examples for the array helper surface: `ArrayLength()`, `ArrayInsert()`, `ArrayPush()`, `ArrayPop()`, `ArrayRemove()`, `ArrayContains()`, `ArrayContainsAll()`, `ArrayCount()`, `ArrayInitialize()`, `ArrayClear()`, `ArrayClone()`, `ArrayRemoveAll()`, `ArrayIndexOf()`, `ArrayLastIndexOf()`, `ArrayReverse()`, `ArraySort()`, `ArrayUnique()`, `ArrayToString()`, `ArrayJoin()`, and `ArraySlice()`.

## ArrayLength, ArrayInsert, ArrayPush, ArrayPop, ArrayRemove, ArrayContains, ArrayContainsAll, ArrayCount, ArrayInitialize, ArrayClear, ArrayClone, ArrayRemoveAll, ArrayIndexOf, ArrayLastIndexOf, ArrayReverse, ArraySort, ArrayUnique, ArrayToString, ArrayJoin, ArraySlice

`ArrayLength()` reports how many items are in an array.

`ArrayPush()` appends one or more values to the array you pass in, mutating that array in place and returning the new length.

`ArrayPop()` removes and returns the last item from the array. When the array is empty, it returns `Null` and sets `@Error = 1`.

`ArrayInsert()` inserts one or more values into the array in place at a zero-based index and returns the new length.

`ArrayRemove()` removes one or more values from the array in place and returns the removed value or values.

`ArrayContains()` returns `1` when the target value is present in the array, and `0` otherwise.

`ArrayContainsAll()` returns `1` when every requested value is present in the array, and `0` otherwise.

`ArrayCount()` returns how many times a value appears in the array.

`ArrayInitialize()` sets every element in the array to a single value in place and returns the array length after initialization.

`ArrayClear()` sets every element in the array to an empty string in place and returns the array length after clearing.

`ArrayClone()` returns a deep copy of the array so you can mutate the copy without affecting the original.

`ArrayRemoveAll()` removes every matching value from the array in place and returns the number of items removed.

`ArrayIndexOf()` returns the zero-based index of the first matching value, or `-1` when nothing matches.

`ArrayLastIndexOf()` returns the zero-based index of the last matching value, or `-1` when nothing matches.

`ArrayReverse()` returns a reversed copy of the array without modifying the original array.

`ArraySort()` returns a sorted copy of the array without modifying the original array.

`ArrayUnique()` returns a copy with duplicates removed while preserving first-seen order.

`ArrayJoin()` behaves exactly like `ArrayToString()` and is available as a more natural alias.

`ArraySlice()` returns a new zero-based slice without modifying the original array.

```ass
Dim values = [1, 2, 3]
Dim search_values = [1, 2, 3, 2, 1]
Dim after_insert = ArrayInsert(values, 1, 9)
Dim after_first_push = ArrayPush(values, 4)
Dim after_second_push = ArrayPush(values, 5, 6)
Dim popped = ArrayPop(values)
Dim removed = ArrayRemove(values, 1)
Dim has_three = ArrayContains(search_values, 3)
Dim has_all = ArrayContainsAll(search_values, 1, 2, 3)
Dim count_twos = ArrayCount(search_values, 2)
Dim initialized_twos = ArrayInitialize(search_values, 0)
Dim cleared_twos = ArrayClear(search_values)
Dim cloned_twos = ArrayClone(search_values)
Dim removed_twos = ArrayRemoveAll(search_values, 2)
Dim first_two = ArrayIndexOf(search_values, 2)
Dim last_two = ArrayLastIndexOf(search_values, 2)
Dim reversed_numbers = ArrayReverse([1, 2, 3])
Dim sorted_numbers = ArraySort([3, 1, 2])
Dim sorted_text = ArraySort(["Bravo", "alpha", "charlie"])
Dim unique_text = ArrayUnique(["Bravo", "alpha", "BRAVO", "alpha"])
Dim csv = ArrayToString(values)
Dim semicolon = ArrayToString(values, ";")
Dim joined = ArrayJoin(values, "|")
Dim slice = ArraySlice(values, 1, 2)

WriteLn("length_initial: " + ArrayLength([1, 2, 3]))
WriteLn("after_insert: " + after_insert)
WriteLn("after_first_push: " + after_first_push)
WriteLn("after_second_push: " + after_second_push)
WriteLn("popped: " + popped)
WriteLn("removed: " + removed)
WriteLn("has_three: " + has_three)
WriteLn("has_all: " + has_all)
WriteLn("count_twos: " + count_twos)
WriteLn("initialized_twos: " + initialized_twos)
WriteLn("cleared_twos: " + cleared_twos)
WriteLn("cloned_twos: " + ArrayLength(cloned_twos))
WriteLn("removed_twos: " + removed_twos)
WriteLn("first_two: " + first_two)
WriteLn("last_two: " + last_two)
WriteLn("reversed_numbers: " + reversed_numbers[0] + "," + reversed_numbers[1] + "," + reversed_numbers[2])
WriteLn("sorted_numbers: " + sorted_numbers[0] + "," + sorted_numbers[1] + "," + sorted_numbers[2])
WriteLn("sorted_text: " + sorted_text[0] + "," + sorted_text[1] + "," + sorted_text[2])
WriteLn("unique_text: " + unique_text[0] + "," + unique_text[1])
WriteLn("csv: " + csv)
WriteLn("semicolon: " + semicolon)
WriteLn("joined: " + joined)
WriteLn("length_after_pop: " + ArrayLength(values))
WriteLn("slice_0: " + slice[0])
WriteLn("slice_1: " + slice[1])
```

Expected output:

```text
length_initial: 3
after_insert: 4
after_first_push: 4
after_second_push: 6
popped: 6
removed: 9
has_three: 1
has_all: 1
count_twos: 2
initialized_twos: 5
cleared_twos: 5
cloned_twos: 5
removed_twos: 2
first_two: 1
last_two: 3
reversed_numbers: 3,2,1
sorted_numbers: 1,2,3
sorted_text: alpha,Bravo,charlie
unique_text: Bravo,alpha
csv: 1,2,3,4,5
semicolon: 1;2;3;4;5
joined: 1|2|3|4|5
length_after_pop: 5
slice_0: 2
slice_1: 3
```
