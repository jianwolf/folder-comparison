# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Single-file Python CLI tool comparing two directories recursively, outputting CSV report with file existence, size matches, and checksum matches.

## Architecture

The tool uses a parallel processing pipeline:

1. **Parallel folder scanning** (`scan_folder`): Two threads scan both directories simultaneously using `os.walk`, collecting file paths and sizes into `FileInfo` dataclasses
2. **Set operations**: Categorizes files into `only_in_1`, `only_in_2`, and `in_both` using set difference/intersection
3. **Parallel checksum comparison** (`compare_file_pair`): ThreadPoolExecutor compares files in both folders - size checked first, BLAKE3 checksum only computed if sizes match (optimization)
4. **CSV output**: Results sorted by filename, columns defined in `CSV_FIELDS`

## Configuration Constants

- `EXCLUDED_FILES` / `EXCLUDED_PREFIXES`: macOS metadata files to skip
- `READ_BUFFER_SIZE`: 1MB chunks for checksum I/O
- `DEFAULT_WORKERS`: 8 threads for parallel comparison
- `PROGRESS_INTERVAL`: Print progress every N files
- `CSV_FIELDS`: Output column names
