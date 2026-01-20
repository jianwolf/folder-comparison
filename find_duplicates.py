#!/usr/bin/env python3
"""
Duplicate File Finder

Scans a directory recursively and outputs a CSV report showing:
- Groups of files with identical content (duplicates)
- Total wasted space from duplicate files

Uses parallel processing for scanning and checksum computation.
Size-based pre-filtering skips checksumming files with unique sizes.
"""

import argparse
import csv
import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import blake3

# Configuration
EXCLUDED_FILES = {'.DS_Store'}
EXCLUDED_PREFIXES = ('._',)
DEFAULT_WORKERS = 8
PROGRESS_INTERVAL = 500
READ_BUFFER_SIZE = 1024 * 1024  # 1 MB
CSV_FIELDS = ['checksum', 'size', 'count', 'paths']


@dataclass(slots=True)
class FileInfo:
    """File path and size for scanning."""
    path: Path
    size: int


# File Operations


def is_excluded(filename: str) -> bool:
    """Check if file should be excluded from scanning."""
    return filename in EXCLUDED_FILES or filename.startswith(EXCLUDED_PREFIXES)


def scan_folder(folder: Path) -> list[FileInfo]:
    """
    Recursively scan a folder and collect file metadata.

    Returns a list of FileInfo objects.
    Files that cannot be accessed (permission errors, etc.) are silently skipped.
    """
    files = []
    for root, _, filenames in os.walk(folder):
        for filename in filenames:
            if is_excluded(filename):
                continue
            full_path = Path(root) / filename
            try:
                size = full_path.stat().st_size
                files.append(FileInfo(full_path, size))
            except OSError:
                continue
    return files


def compute_checksum(filepath: Path) -> str | None:
    """Compute BLAKE3 checksum of a file. Returns None on error."""
    try:
        hasher = blake3.blake3()
        with open(filepath, 'rb', buffering=0) as f:
            while chunk := f.read(READ_BUFFER_SIZE):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return None


# Duplicate Detection Logic


def find_duplicates(folder: Path, output_csv: Path, workers: int,
                    min_size: int = 0) -> None:
    """Scan folder for duplicate files and write results to CSV."""

    print(f"Scanning folder: {folder}")
    files = scan_folder(folder)
    print(f"  Found {len(files)} files")

    # Filter by minimum size
    if min_size > 0:
        files = [f for f in files if f.size >= min_size]
        print(f"  {len(files)} files >= {min_size} bytes")

    # Group by size first (optimization: files with unique sizes can't be duplicates)
    size_groups: dict[int, list[FileInfo]] = defaultdict(list)
    for f in files:
        size_groups[f.size].append(f)

    # Only checksum files that share a size with at least one other file
    candidates = [f for group in size_groups.values() if len(group) > 1 for f in group]
    unique_by_size = len(files) - len(candidates)
    print(f"  {unique_by_size} files unique by size (skipping checksum)")
    print(f"  {len(candidates)} files to checksum...")

    if not candidates:
        print("\nNo potential duplicates found.")
        return

    # Compute checksums in parallel
    checksum_map: dict[str, list[FileInfo]] = defaultdict(list)
    errors = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(compute_checksum, f.path): f for f in candidates}
        for i, future in enumerate(as_completed(futures), 1):
            file_info = futures[future]
            checksum = future.result()
            if checksum:
                checksum_map[checksum].append(file_info)
            else:
                errors += 1
            if i % PROGRESS_INTERVAL == 0:
                print(f"  Checksummed {i}/{len(candidates)}...")

    if errors:
        print(f"  {errors} files could not be read")

    # Filter to only duplicate groups (2+ files with same checksum)
    duplicates = {k: v for k, v in checksum_map.items() if len(v) > 1}

    # Prepare CSV output
    rows = []
    total_wasted = 0
    for checksum, group in sorted(duplicates.items(), key=lambda x: -x[1][0].size):
        size = group[0].size
        paths = [str(f.path) for f in sorted(group, key=lambda f: f.path)]
        rows.append({
            'checksum': checksum,
            'size': size,
            'count': len(group),
            'paths': '|'.join(paths),
        })
        total_wasted += size * (len(group) - 1)

    print(f"\nWriting results to: {output_csv}")
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    # Print summary
    total_dup_files = sum(len(g) for g in duplicates.values())
    print("\nSummary:")
    print(f"  Total files scanned: {len(files)}")
    print(f"  Duplicate groups:    {len(duplicates)}")
    print(f"  Files in duplicates: {total_dup_files}")
    print(f"  Wasted space:        {format_size(total_wasted)}")


def format_size(size: int) -> str:
    """Format byte size as human-readable string."""
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != 'B' else f"{size} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


# CLI Entry Point


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Find duplicate files in a folder'
    )
    parser.add_argument('folder', type=Path, help='Folder to scan for duplicates')
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path('duplicates.csv'),
        help='Output CSV file (default: duplicates.csv)'
    )
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=DEFAULT_WORKERS,
        help=f'Number of worker threads (default: {DEFAULT_WORKERS})'
    )
    parser.add_argument(
        '-m', '--min-size',
        type=int,
        default=0,
        help='Minimum file size in bytes to consider (default: 0)'
    )

    args = parser.parse_args()

    if not args.folder.is_dir():
        print(f"Error: {args.folder} is not a directory", file=sys.stderr)
        return 1

    find_duplicates(args.folder, args.output, args.workers, args.min_size)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
