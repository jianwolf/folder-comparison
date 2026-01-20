# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Overview

Two Python CLI tools for file comparison tasks:

| File | Purpose |
|------|---------|
| `folder_comparison.py` | Compare two directories, output differences to CSV |
| `find_duplicates.py` | Find duplicate files within one directory |

Both share common patterns: parallel I/O, size-first optimization, BLAKE3 checksums, macOS file exclusions.

## Architecture

### folder_comparison.py

```
scan_folder (×2 parallel) → set operations → compare_file_pair (parallel) → CSV
```

**Pipeline:**
1. **Scan**: Two threads scan directories via `os.walk`, building `dict[rel_path, FileInfo]`
2. **Categorize**: Set operations split paths into `only_in_1`, `only_in_2`, `common_paths`
3. **Compare**: ThreadPoolExecutor compares common files (size first, then content)
4. **Output**: Write sorted CSV, print summary

**Comparison modes:**
| Mode | Flag | Function | Use Case |
|------|------|----------|----------|
| Byte-for-byte | (default) | `compare_bytes` | Local files, fastest |
| Checksum | `--checksum` | `compute_checksum` | Network mounts |

### find_duplicates.py

```
scan_folder → group by size → compute_checksum (parallel) → group by checksum → CSV
```

**Pipeline:**
1. **Scan**: Single thread scans directory via `os.walk`, building `list[FileInfo]`
2. **Size filter**: Group by size; files with unique sizes skipped (can't be duplicates)
3. **Checksum**: ThreadPoolExecutor computes BLAKE3 for remaining candidates
4. **Group**: Collect files by checksum; groups with 2+ files are duplicates
5. **Output**: Write CSV sorted by size (largest first), print summary

## Key Functions

### Shared patterns (both files)

- `is_excluded(filename)` - Check against `EXCLUDED_FILES` and `EXCLUDED_PREFIXES`
- `scan_folder(folder)` - Recursive `os.walk`, collect `FileInfo(path, size)`
- `compute_checksum(filepath)` - BLAKE3 hash with buffered reads

### folder_comparison.py specific

- `compare_bytes(path1, path2)` - Byte-for-byte comparison, early exit on difference
- `compare_file_pair(rel_path, info1, info2)` - Orchestrates size + content comparison
- `make_result(...)` - Create comparison result dict
- `compare_folders(...)` - Main orchestrator

### find_duplicates.py specific

- `find_duplicates(folder, output_csv, workers, min_size)` - Main orchestrator
- `format_size(size)` - Human-readable byte formatting (e.g., "1.5 GB")

## Usage

### folder_comparison.py

```bash
# Basic (byte-for-byte, differences only)
python folder_comparison.py /path/to/folder1 /path/to/folder2

# Include identical files
python folder_comparison.py folder1 folder2 --all

# Use checksums (for network mounts)
python folder_comparison.py folder1 folder2 --checksum

# Custom output and workers
python folder_comparison.py folder1 folder2 -o results.csv -w 16
```

### find_duplicates.py

```bash
# Basic scan
python find_duplicates.py /path/to/folder

# Skip small files (>= 1MB only)
python find_duplicates.py folder --min-size 1048576

# Custom output and workers
python find_duplicates.py folder -o dupes.csv -w 16
```

## Configuration

Shared constants (defined in both files):

| Constant | Value | Purpose |
|----------|-------|---------|
| `EXCLUDED_FILES` | `{'.DS_Store'}` | macOS metadata to skip |
| `EXCLUDED_PREFIXES` | `('._',)` | macOS resource forks to skip |
| `READ_BUFFER_SIZE` | 1 MB | I/O chunk size |
| `DEFAULT_WORKERS` | 8 | Parallel threads |
| `PROGRESS_INTERVAL` | 500 | Progress update frequency |

## CSV Output

### folder_comparison.py

| Column | Values |
|--------|--------|
| `file_name` | Relative path |
| `exist_in_folder_1` | `True` / `False` |
| `exist_in_folder_2` | `True` / `False` |
| `size_same` | `True` / `False` / `None` |
| `content_same` | `True` / `False` / `None` |

`content_same=None` means not checked (sizes differ or read error).

### find_duplicates.py

| Column | Values |
|--------|--------|
| `checksum` | BLAKE3 hex digest |
| `size` | Bytes |
| `count` | Number of duplicates |
| `paths` | Pipe-separated paths |

## Git Conventions

- Do not include `Co-Authored-By` in commit messages
