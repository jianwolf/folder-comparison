# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Overview

Single-file Python CLI that compares two directories recursively, producing a CSV report of file existence, size matches, and content matches.

## Architecture

```
scan_folder (×2 parallel) → set operations → compare_file_pair (parallel) → CSV
```

### Pipeline

1. **Scan**: Two threads scan directories via `os.walk`, building `FileInfo` dicts
2. **Categorize**: Set operations split paths into `only_in_1`, `only_in_2`, `common_paths`
3. **Compare**: ThreadPoolExecutor compares common files (size first, then content)
4. **Output**: Write sorted CSV, print summary

### Comparison Modes

| Mode | Flag | Function | Use Case |
|------|------|----------|----------|
| Byte-for-byte | (default) | `compare_bytes` | Local files, fastest |
| Checksum | `--checksum` | `compute_checksum` | Network mounts, need hashes |

### Result Semantics

- `content_same=True`: Content verified identical
- `content_same=False`: Content verified different
- `content_same=None`: Not checked (sizes differ) or read error

## Key Functions

- `scan_folder`: Recursively collect file paths and sizes
- `compare_file_pair`: Orchestrates size + content comparison
- `compare_bytes`: Byte-for-byte comparison, exits early on difference
- `compute_checksum`: BLAKE3 hash computation
- `compare_folders`: Main orchestrator

## Usage

```bash
# Basic comparison (outputs only differences)
python folder_comparison.py /path/to/folder1 /path/to/folder2

# Include identical files in output
python folder_comparison.py folder1 folder2 --all

# Use checksums (for network mounts)
python folder_comparison.py folder1 folder2 --checksum

# Custom output file and worker count
python folder_comparison.py folder1 folder2 -o results.csv -w 16
```

## Configuration

| Constant | Value | Purpose |
|----------|-------|---------|
| `EXCLUDED_FILES` | `.DS_Store` | macOS metadata to skip |
| `EXCLUDED_PREFIXES` | `._` | macOS resource forks to skip |
| `READ_BUFFER_SIZE` | 1 MB | I/O chunk size |
| `DEFAULT_WORKERS` | 8 | Parallel comparison threads |
| `PROGRESS_INTERVAL` | 500 | Progress update frequency |

## Git Conventions

- Do not include `Co-Authored-By` in commit messages
