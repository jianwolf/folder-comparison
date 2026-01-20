#!/usr/bin/env python3
"""
Folder Comparison Tool

Compares two directories recursively and outputs a CSV report showing:
- Which files exist in each folder
- Whether files present in both have matching sizes and content

Uses parallel processing for scanning and comparison.
Default comparison is byte-for-byte; use --checksum for BLAKE3 hashing.
"""

import argparse
import csv
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

import blake3

# Configuration
EXCLUDED_FILES = {'.DS_Store'}
EXCLUDED_PREFIXES = ('._',)
DEFAULT_WORKERS = 8
PROGRESS_INTERVAL = 500
READ_BUFFER_SIZE = 1024 * 1024  # 1 MB
CSV_FIELDS = ['file_name', 'exist_in_folder_1', 'exist_in_folder_2', 'size_same', 'content_same']

# Types
ComparisonResult: TypeAlias = dict[str, str | bool | None]


@dataclass(slots=True)
class FileInfo:
    """File metadata: absolute path and size in bytes."""
    path: Path
    size: int


# File Operations


def is_excluded(filename: str) -> bool:
    """Check if file should be excluded (macOS metadata files)."""
    return filename in EXCLUDED_FILES or filename.startswith(EXCLUDED_PREFIXES)


def scan_folder(folder: Path) -> dict[str, FileInfo]:
    """
    Recursively scan a folder and collect file metadata.

    Returns a dict mapping relative paths to FileInfo objects.
    Files that cannot be accessed (permission errors, etc.) are silently skipped.
    """
    files = {}
    for root, _, filenames in os.walk(folder):
        for filename in filenames:
            if is_excluded(filename):
                continue
            full_path = Path(root) / filename
            try:
                size = full_path.stat().st_size
                rel_path = str(full_path.relative_to(folder))
                files[rel_path] = FileInfo(full_path, size)
            except OSError:
                continue  # Skip inaccessible files
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


def compare_bytes(path1: Path, path2: Path) -> bool | None:
    """
    Compare two files byte-for-byte.

    Returns True if identical, False if different, None on read error.
    Exits early on first difference, making it faster than checksums for local files.
    """
    try:
        with open(path1, 'rb', buffering=0) as f1, open(path2, 'rb', buffering=0) as f2:
            while True:
                chunk1 = f1.read(READ_BUFFER_SIZE)
                chunk2 = f2.read(READ_BUFFER_SIZE)
                if chunk1 != chunk2:
                    return False
                if not chunk1:  # Both empty = EOF reached
                    return True
    except OSError:
        return None


# Comparison Logic


def make_result(rel_path: str, in_1: bool, in_2: bool,
                size_same: bool | None = None,
                content_same: bool | None = None) -> ComparisonResult:
    """Create a comparison result dict for CSV output."""
    return {
        'file_name': rel_path,
        'exist_in_folder_1': in_1,
        'exist_in_folder_2': in_2,
        'size_same': size_same,
        'content_same': content_same,
    }


def is_identical(result: ComparisonResult) -> bool:
    """Check if a comparison result represents identical files (size and content match)."""
    return result['size_same'] is True and result['content_same'] is True


def compare_file_pair(rel_path: str, info1: FileInfo, info2: FileInfo,
                      use_checksum: bool = False) -> ComparisonResult:
    """
    Compare two files with the same relative path.

    Compares size first; if sizes differ, content check is skipped (content_same=None).
    """
    if info1.size != info2.size:
        return make_result(rel_path, True, True, size_same=False, content_same=None)

    # Sizes match - compare content
    if use_checksum:
        hash1, hash2 = compute_checksum(info1.path), compute_checksum(info2.path)
        content_same = (hash1 == hash2) if (hash1 and hash2) else None
    else:
        content_same = compare_bytes(info1.path, info2.path)

    return make_result(rel_path, True, True, size_same=True, content_same=content_same)


def compare_folders(folder1: Path, folder2: Path, output_csv: Path, workers: int,
                    include_all: bool = False, use_checksum: bool = False) -> None:
    """Compare two folders and write results to CSV."""

    # Scan both folders in parallel
    print("Scanning folders...")
    print(f"  Folder 1: {folder1}")
    print(f"  Folder 2: {folder2}")
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(scan_folder, folder1)
        future2 = executor.submit(scan_folder, folder2)
        scan1 = future1.result()
        scan2 = future2.result()

    print(f"  Found {len(scan1)} + {len(scan2)} files")

    # Categorize files using set operations
    paths1, paths2 = set(scan1), set(scan2)
    only_in_1 = paths1 - paths2
    only_in_2 = paths2 - paths1
    common_paths = paths1 & paths2

    comparison_method = "checksum" if use_checksum else "byte-for-byte"
    print(f"Comparing {len(common_paths)} common files ({comparison_method})...")

    # Record unique files
    results: list[ComparisonResult] = []
    results.extend(make_result(p, in_1=True, in_2=False) for p in only_in_1)
    results.extend(make_result(p, in_1=False, in_2=True) for p in only_in_2)

    # Compare common files in parallel
    common_count = len(common_paths)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(compare_file_pair, p, scan1[p], scan2[p], use_checksum): p
            for p in common_paths
        }
        for i, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if i % PROGRESS_INTERVAL == 0:
                print(f"  Compared {i}/{common_count}...")

    results.sort(key=lambda r: r['file_name'])

    # Write CSV (filter to differences unless --all)
    output_results = results if include_all else [r for r in results if not is_identical(r)]
    print(f"\nWriting results to: {output_csv}")
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(output_results)

    # Print summary
    identical_count = sum(1 for r in results if is_identical(r))
    different_count = common_count - identical_count
    print("\nSummary:")
    print(f"  Only in folder 1: {len(only_in_1)}")
    print(f"  Only in folder 2: {len(only_in_2)}")
    print(f"  In both folders:  {common_count}")
    print(f"    - Identical:    {identical_count}")
    print(f"    - Different:    {different_count}")


# CLI Entry Point


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Compare two folders and output differences to CSV'
    )
    parser.add_argument('folder1', type=Path, help='First folder to compare')
    parser.add_argument('folder2', type=Path, help='Second folder to compare')
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path('comparison_results.csv'),
        help='Output CSV file (default: comparison_results.csv)'
    )
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=DEFAULT_WORKERS,
        help=f'Number of worker threads (default: {DEFAULT_WORKERS})'
    )
    parser.add_argument(
        '-a', '--all',
        action='store_true',
        help='Include identical files in output (by default only differences are shown)'
    )
    parser.add_argument(
        '-c', '--checksum',
        action='store_true',
        help='Use BLAKE3 checksum instead of byte-for-byte comparison'
    )

    args = parser.parse_args()

    for folder in (args.folder1, args.folder2):
        if not folder.is_dir():
            print(f"Error: {folder} is not a directory", file=sys.stderr)
            return 1

    compare_folders(args.folder1, args.folder2, args.output, args.workers, args.all, args.checksum)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
