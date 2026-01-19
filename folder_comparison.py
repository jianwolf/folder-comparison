#!/usr/bin/env python3
"""
Folder Comparison Tool

Compares two directories recursively and outputs a CSV report showing:
- Which files exist in each folder
- Whether files present in both have matching sizes and checksums

Uses parallel processing for both folder scanning and checksum computation.
"""

import argparse
import csv
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import blake3

# Files to exclude from comparison (macOS metadata files)
EXCLUDED_FILES = {'.DS_Store'}
EXCLUDED_PREFIXES = ('._',)

# Performance tuning
READ_BUFFER_SIZE = 1048576  # 1MB chunks for checksum computation
DEFAULT_WORKERS = 8
PROGRESS_INTERVAL = 500  # Print progress every N files

# CSV output columns
CSV_FIELDS = ['file_name', 'exist_in_folder_1', 'exist_in_folder_2', 'size_same', 'checksum_same']


@dataclass(slots=True)
class FileInfo:
    """Stores file path and size for comparison."""
    path: Path
    size: int


def is_excluded(filename: str) -> bool:
    """Check if file should be excluded from comparison."""
    return filename in EXCLUDED_FILES or filename.startswith(EXCLUDED_PREFIXES)


def scan_folder(folder: Path) -> dict[str, FileInfo]:
    """
    Recursively scan a folder and collect file metadata.

    Returns a dict mapping relative paths to FileInfo objects.
    """
    files = {}
    folder_str = str(folder)
    prefix_len = len(folder_str) + 1

    for root, _, filenames in os.walk(folder):
        for filename in filenames:
            if is_excluded(filename):
                continue
            full_path = Path(root) / filename
            try:
                size = full_path.stat().st_size
                rel_path = str(full_path)[prefix_len:]
                files[rel_path] = FileInfo(full_path, size)
            except OSError:
                continue
    return files


def compute_checksum(filepath: Path) -> str | None:
    """Compute BLAKE3 checksum of a file."""
    try:
        hasher = blake3.blake3()
        with open(filepath, 'rb', buffering=0) as f:
            while chunk := f.read(READ_BUFFER_SIZE):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return None


def make_result(rel_path: str, in_1: bool, in_2: bool,
                size_same: bool | None = None, checksum_same: bool | None = None) -> dict:
    """Create a comparison result dict."""
    return {
        'file_name': rel_path,
        'exist_in_folder_1': in_1,
        'exist_in_folder_2': in_2,
        'size_same': size_same,
        'checksum_same': checksum_same,
    }


def compare_file_pair(rel_path: str, file1: FileInfo, file2: FileInfo) -> dict:
    """
    Compare two files with the same relative path.

    Compares size first; only computes checksums if sizes match.
    """
    size_same = file1.size == file2.size

    if size_same:
        checksum1 = compute_checksum(file1.path)
        checksum2 = compute_checksum(file2.path)
        checksum_same = (checksum1 == checksum2) if (checksum1 and checksum2) else None
    else:
        checksum_same = False

    return make_result(rel_path, True, True, size_same, checksum_same)


def compare_folders(folder1: Path, folder2: Path, output_csv: Path, workers: int) -> None:
    """Compare two folders and write results to CSV."""

    # Scan both folders in parallel
    print("Scanning folders...")
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(scan_folder, folder1)
        future2 = executor.submit(scan_folder, folder2)
        files1 = future1.result()
        files2 = future2.result()

    print(f"  Folder 1: {len(files1)} files")
    print(f"  Folder 2: {len(files2)} files")

    # Categorize files using set operations
    keys1, keys2 = set(files1), set(files2)
    only_in_1 = keys1 - keys2
    only_in_2 = keys2 - keys1
    in_both = keys1 & keys2

    print(f"Comparing {len(in_both)} common files...")

    # Build results list
    results = []

    # Files unique to each folder
    for rel_path in only_in_1:
        results.append(make_result(rel_path, True, False))

    for rel_path in only_in_2:
        results.append(make_result(rel_path, False, True))

    # Compare common files in parallel
    in_both_list = list(in_both)
    completed = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(compare_file_pair, rel_path, files1[rel_path], files2[rel_path]): rel_path
            for rel_path in in_both_list
        }
        for future in as_completed(futures):
            results.append(future.result())
            completed += 1
            if completed % PROGRESS_INTERVAL == 0:
                print(f"  Compared {completed}/{len(in_both_list)}...")

    results.sort(key=lambda r: r['file_name'])

    # Write CSV
    print(f"Writing results to: {output_csv}")
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    # Summary
    same_content = sum(1 for r in results if r['checksum_same'] is True)
    diff_content = sum(1 for r in results if r['checksum_same'] is False)

    print("\nSummary:")
    print(f"  Only in folder 1: {len(only_in_1)}")
    print(f"  Only in folder 2: {len(only_in_2)}")
    print(f"  In both folders: {len(in_both)}")
    print(f"    - Same content: {same_content}")
    print(f"    - Different content: {diff_content}")


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

    args = parser.parse_args()

    if not args.folder1.is_dir():
        print(f"Error: {args.folder1} is not a directory", file=sys.stderr)
        return 1

    if not args.folder2.is_dir():
        print(f"Error: {args.folder2} is not a directory", file=sys.stderr)
        return 1

    compare_folders(args.folder1, args.folder2, args.output, args.workers)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
