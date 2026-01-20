# Folder Comparison Tools

Python CLI tools for comparing directories and finding duplicate files.

## Tools

| Tool | Purpose |
|------|---------|
| `folder_comparison.py` | Compare two directories, report differences |
| `find_duplicates.py` | Find duplicate files within a directory |

## Requirements

- Python 3.10+
- blake3

```bash
pip install blake3
```

## folder_comparison.py

Compares two directories recursively and outputs a CSV report of differences.

### Usage

```bash
python folder_comparison.py <folder1> <folder2> [options]
```

**Options:**
- `-o, --output FILE` - Output CSV file (default: `comparison_results.csv`)
- `-w, --workers N` - Worker threads (default: 8)
- `-a, --all` - Include identical files (default: only differences)
- `-c, --checksum` - Use BLAKE3 checksum instead of byte-for-byte comparison

**Examples:**
```bash
# Compare two folders (byte-for-byte, outputs only differences)
python folder_comparison.py ~/backup1 ~/backup2

# Include identical files in output
python folder_comparison.py folder1 folder2 --all

# Use checksums (useful for network mounts)
python folder_comparison.py folder1 folder2 --checksum -o results.csv
```

### Output

CSV columns:

| Column | Description |
|--------|-------------|
| `file_name` | Relative path |
| `exist_in_folder_1` | `True` / `False` |
| `exist_in_folder_2` | `True` / `False` |
| `size_same` | `True` / `False` / empty |
| `content_same` | `True` / `False` / empty |

By default, only files with differences are included. Use `-a` to include all files.

## find_duplicates.py

Scans a directory recursively to find files with identical content.

### Usage

```bash
python find_duplicates.py <folder> [options]
```

**Options:**
- `-o, --output FILE` - Output CSV file (default: `duplicates.csv`)
- `-w, --workers N` - Worker threads (default: 8)
- `-m, --min-size BYTES` - Minimum file size to consider (default: 0)

**Examples:**
```bash
# Find all duplicates
python find_duplicates.py ~/Documents

# Only check files >= 1MB
python find_duplicates.py ~/Downloads --min-size 1048576

# Custom output file
python find_duplicates.py ~/Photos -o photo_duplicates.csv
```

### Output

CSV columns:

| Column | Description |
|--------|-------------|
| `checksum` | BLAKE3 hash of the file content |
| `size` | File size in bytes |
| `count` | Number of duplicate files |
| `paths` | Pipe-separated list of file paths |

## Performance

Both tools use several optimizations:

- **Parallel processing** - Configurable worker threads for I/O operations
- **Size-first filtering** - Files with unique sizes skip content comparison
- **Early exit** - Byte-for-byte comparison exits on first difference
- **BLAKE3** - Fast cryptographic hash when checksums are needed

## Excluded Files

Both tools automatically exclude:
- `.DS_Store` (macOS metadata)
- `._*` files (macOS resource forks)
