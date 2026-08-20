# Path Helper Examples

This page collects runnable examples for `DirectoryList()` and `FileList()`. The helpers return full paths, so the example uses `FileName()` to keep the printed output stable across machines.

## DirectoryList And FileList

`DirectoryList(path[, pattern])` returns the immediate child directories inside `path`, sorted by child name. `FileList(path[, pattern])` does the same for files.

Both helpers accept an optional shell-style `pattern` that matches the child name, so `*`, `?`, and character classes work the same way they do in the runtime's glob-style matcher.

```ass
Dim sample_dir = @ScriptDirectory
Dim repo_root = PathCombine(sample_dir, "..")
Dim files = FileList(sample_dir, "read_file_demo.*")
Dim directories = DirectoryList(repo_root, "samples")

WriteLn("file_0: " + FileName(files[0]))
WriteLn("file_1: " + FileName(files[1]))
WriteLn("directory_0: " + FileName(directories[0]))
```

Expected output:

```text
file_0: read_file_demo.ass
file_1: read_file_demo.txt
directory_0: samples
```

## RemoveDir And DirectoryDelete

`RemoveDir(path[, recursive])` removes a directory path. `DirectoryDelete(path[, recursive])` is an alias with the same behavior.

When `recursive` is omitted or `0`, only empty directories are removed. When `recursive` is nonzero, the helper removes the directory and everything under it.

```ass
Dim scratch = PathCombine(@WorkingDir, "__remove_dir_demo__")
Dim nested = PathCombine(scratch, "nested")

CreateDir(nested)
WriteLn("before: " + DirExists(scratch))
RemoveDir(scratch, 1)
WriteLn("after: " + DirExists(scratch))
```

Expected output:

```text
before: 1
after: 0
```

## CopyFile And CopyDir

`CopyFile(source, destination[, overwrite])` copies one file to a target file path. `CopyDir(source, destination[, overwrite])` copies a directory tree to a target directory path.

When `overwrite` is omitted or `0`, the helper fails if the target already exists. When `overwrite` is nonzero, the helper replaces the existing target.

```ass
Dim scratch = PathCombine(@WorkingDir, "__copy_demo__")
Dim source_dir = PathCombine(scratch, "source")
Dim copied_dir = PathCombine(scratch, "copied")
Dim source_file = PathCombine(source_dir, "message.txt")
Dim copied_file = PathCombine(scratch, "message_copy.txt")

CreateDir(source_dir)
WriteFile(source_file, "hello")
CopyFile(source_file, copied_file)
CopyDir(source_dir, copied_dir)
WriteLn("file_exists: " + FileExists(copied_file))
WriteLn("dir_exists: " + DirExists(copied_dir))
WriteLn("copied_text: " + ReadFile(copied_file))
RemoveDir(scratch, 1)
```

Expected output:

```text
file_exists: 1
dir_exists: 1
copied_text: hello
```

## MoveFile And MoveDir

`MoveFile(source, destination[, overwrite])` moves one file to a target file path. `MoveDir(source, destination[, overwrite])` moves a directory tree to a target directory path.

When `overwrite` is omitted or `0`, the helper fails if the target already exists. When `overwrite` is nonzero, the helper replaces the existing target.

```ass
Dim scratch = PathCombine(@WorkingDir, "__move_demo__")
Dim source_dir = PathCombine(scratch, "source")
Dim moved_dir = PathCombine(scratch, "moved")
Dim source_file = PathCombine(source_dir, "message.txt")
Dim moved_file = PathCombine(scratch, "message_moved.txt")

CreateDir(source_dir)
WriteFile(source_file, "hello")
MoveFile(source_file, moved_file)
MoveDir(source_dir, moved_dir)
WriteLn("file_exists_after_move: " + FileExists(moved_file))
WriteLn("dir_exists_after_move: " + DirExists(moved_dir))
WriteLn("moved_text: " + ReadFile(moved_file))
RemoveDir(scratch, 1)
```

Expected output:

```text
file_exists_after_move: 1
dir_exists_after_move: 1
moved_text: hello
```

## FileSize, FileTime, And FileInfo

`FileSize(path)` returns the size in bytes of a file, or the recursive size of a directory tree. `FileTime(path[, kind])` returns a numeric timestamp, and `FileInfo(path)` returns a `Record<FileInfo>` with path, size, and timestamp fields.

```ass
Dim scratch = PathCombine(@WorkingDir, "__metadata_demo__")
Dim data_file = PathCombine(scratch, "payload.txt")

CreateDir(scratch)
WriteFile(data_file, "hello world")

Dim info = FileInfo(data_file)
WriteLn("size: " + FileSize(data_file))
WriteLn("dir_size: " + FileSize(scratch))
WriteLn("file_name: " + info.Name)
WriteLn("is_dir: " + info.IsDirectory)
WriteLn("time_is_float: " + StringIsFloat(FileTime(data_file)))
RemoveDir(scratch, 1)
```

Expected output:

```text
size: 11
dir_size: 11
file_name: payload.txt
is_dir: 0
time_is_float: 1
```

## FileHash And FileChecksum

`FileHash(path[, algorithm])` returns a lowercase hex digest for the file contents, and `FileChecksum(path[, algorithm])` returns a lowercase hex checksum.

```ass
Dim scratch = PathCombine(@WorkingDir, "__metadata_demo__")
Dim data_file = PathCombine(scratch, "payload.txt")

CreateDir(scratch)
WriteFile(data_file, "hello world")

WriteLn("sha256: " + FileHash(data_file))
WriteLn("md5: " + FileHash(data_file, "md5"))
WriteLn("crc32: " + FileChecksum(data_file))
WriteLn("adler32: " + FileChecksum(data_file, "adler32"))
RemoveDir(scratch, 1)
```

Expected output:

```text
sha256: b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
md5: 5eb63bbbe01eeed093cb22bb8f5acdc3
crc32: 0d4a1185
adler32: 1a0b045d
```

## FileCompare

`FileCompare(left, right)` compares the binary contents of two files and returns `0` when identical, `-1` when the left file sorts before the right file, and `1` when the left file sorts after the right file.

```ass
Dim scratch = PathCombine(@WorkingDir, "__compare_demo__")
Dim same_a = PathCombine(scratch, "same_a.txt")
Dim same_b = PathCombine(scratch, "same_b.txt")
Dim less = PathCombine(scratch, "less.txt")
Dim greater = PathCombine(scratch, "greater.txt")

CreateDir(scratch)
WriteFile(same_a, "same")
WriteFile(same_b, "same")
WriteFile(less, "abc")
WriteFile(greater, "abd")

WriteLn("same: " + FileCompare(same_a, same_b))
WriteLn("less: " + FileCompare(less, greater))
WriteLn("greater: " + FileCompare(greater, less))
RemoveDir(scratch, 1)
```

Expected output:

```text
same: 0
less: -1
greater: 1
```

## WalkDir And EnumerateFiles

`WalkDir(path[, pattern])` returns recursive child directories beneath `path`, and `EnumerateFiles(path[, pattern])` returns recursive child files beneath `path`.

```ass
Dim scratch = PathCombine(@WorkingDir, "__traverse_demo__")
Dim root = PathCombine(scratch, "root")
Dim nested = PathCombine(root, "nested")
Dim deep = PathCombine(nested, "deep")
Dim root_file = PathCombine(root, "alpha.txt")
Dim nested_file = PathCombine(nested, "beta.txt")
Dim deep_file = PathCombine(deep, "omega.log")

CreateDir(deep)
WriteFile(root_file, "root")
WriteFile(nested_file, "nested")
WriteFile(deep_file, "deep")

Dim dirs = WalkDir(root)
Dim files = EnumerateFiles(root, "*.txt")

WriteLn("dir_0: " + FileName(dirs[0]))
WriteLn("dir_1: " + FileName(dirs[1]))
WriteLn("files_0: " + FileName(files[0]))
WriteLn("files_1: " + FileName(files[1]))
RemoveDir(scratch, 1)
```

Expected output:

```text
dir_0: nested
dir_1: deep
files_0: alpha.txt
files_1: beta.txt
```

## Related Docs

- [Builtin Coverage Map](builtin_coverage_map.md)
- [Language Reference](language_reference.md)
