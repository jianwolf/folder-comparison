# Folder Comparison Tool

A fast Python CLI tool to compare two directories and output a detailed CSV report.

## Features

- Parallel folder scanning and checksum computation
- BLAKE3 checksums (faster than MD5/SHA on large files)
- Size-first comparison (skips checksum if sizes differ)
- Excludes macOS metadata files (`.DS_Store`, `._*`)

## Requirements

- Python 3.10+
- blake3

```bash
pip install blake3
```

## Usage

```bash
python folder_comparison.py <folder1> <folder2> [-o output.csv] [-w workers]
```

**Arguments:**
- `folder1`, `folder2`: Directories to compare
- `-o, --output`: Output CSV file (default: `comparison_results.csv`)
- `-w, --workers`: Number of worker threads (default: 8)

**Example:**
```bash
python folder_comparison.py ~/Documents/backup1 ~/Documents/backup2 -o diff.csv
```

## Output

CSV with columns:
| Column | Description |
|--------|-------------|
| `file_name` | Relative path |
| `exist_in_folder_1` | `True` / `False` |
| `exist_in_folder_2` | `True` / `False` |
| `size_same` | `True` / `False` (empty if file only in one folder) |
| `checksum_same` | `True` / `False` (empty if file only in one folder) |
