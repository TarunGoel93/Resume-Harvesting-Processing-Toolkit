"""
Duplicate File Cleaner for the L folder
----------------------------------------
Deletes files that are duplicates of originals.
Duplicates are files with names like:
  786259 (1).pdf, 786259 (2).docx, etc.

The original (e.g., 786259.pdf) is KEPT.
All "(n)" copies are DELETED.

Usage:
    python delete_duplicates.py
    python delete_duplicates.py --dry-run        # Preview only, no deletion
    python delete_duplicates.py --folder "D:\\L"  # Custom folder path
"""

import os
import re
import argparse
from pathlib import Path
from collections import defaultdict


def find_and_delete_duplicates(folder_path: str, dry_run: bool = False):
    folder = Path(folder_path)

    if not folder.exists():
        print(f"[ERROR] Folder not found: {folder_path}")
        return

    if not folder.is_dir():
        print(f"[ERROR] Path is not a folder: {folder_path}")
        return

    # Pattern to detect duplicate files: "filename (1).ext", "filename (2).ext", etc.
    duplicate_pattern = re.compile(r'^(.+?)\s*\(\d+\)(\.[^.]+)?$')

    # Supported extensions
    supported_extensions = {'.pdf', '.doc', '.docx'}

    all_files = list(folder.iterdir())
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Scanning: {folder_path}")
    print(f"Total items in folder: {len(all_files)}\n")

    duplicates_to_delete = []
    originals_missing = []   # Duplicates whose original doesn't exist
    skipped = []

    for file in all_files:
        if not file.is_file():
            continue

        ext = file.suffix.lower()
        if ext not in supported_extensions:
            skipped.append(file.name)
            continue

        match = duplicate_pattern.match(file.stem)
        if match:
            # This file is a duplicate (has " (n)" in name)
            base_name = match.group(1).strip()
            original_name = base_name + ext

            original_path = folder / original_name

            if original_path.exists():
                duplicates_to_delete.append((file, original_path))
            else:
                # Original doesn't exist — flag it but don't delete
                originals_missing.append((file, original_name))

    # --- Summary before deletion ---
    print(f"Found {len(duplicates_to_delete)} duplicate(s) to delete.")
    print(f"Found {len(originals_missing)} file(s) with no original (will be KEPT).")
    print(f"Skipped {len(skipped)} file(s) with unsupported extension.\n")

    if not duplicates_to_delete:
        print("Nothing to delete. Folder is already clean!")
        return

    # --- Show what will be deleted ---
    print("=" * 60)
    print("FILES TO BE DELETED:")
    print("=" * 60)
    for dup, orig in duplicates_to_delete:
        print(f"  DELETE : {dup.name}  (original: {orig.name})")

    if originals_missing:
        print("\n" + "=" * 60)
        print("KEPT (no original found — safer to keep):")
        print("=" * 60)
        for dup, orig_name in originals_missing:
            print(f"  KEEP   : {dup.name}  (missing original: {orig_name})")

    print()

    # --- Confirm and delete ---
    if dry_run:
        print("[DRY RUN] No files were deleted. Remove --dry-run to actually delete.")
        return

    confirm = input(f"Proceed to delete {len(duplicates_to_delete)} file(s)? (yes/no): ").strip().lower()
    if confirm not in ('yes', 'y'):
        print("Aborted. No files deleted.")
        return

    deleted_count = 0
    error_count = 0

    for dup, orig in duplicates_to_delete:
        try:
            dup.unlink()
            print(f"  DELETED: {dup.name}")
            deleted_count += 1
        except Exception as e:
            print(f"  ERROR deleting {dup.name}: {e}")
            error_count += 1

    print("\n" + "=" * 60)
    print(f"Done! Deleted: {deleted_count} | Errors: {error_count} | Kept (no original): {len(originals_missing)}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Delete duplicate files (those with ' (1)', ' (2)' in name) from a folder."
    )
    parser.add_argument(
        '--folder',
        type=str,
        default=r'C:\Users\Tarun\Downloads\L',  # <-- Change this if needed
        help='Path to the L folder (default: C:\\Users\\Tarun\\Downloads\\L)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be deleted without actually deleting anything'
    )

    args = parser.parse_args()
    find_and_delete_duplicates(args.folder, dry_run=args.dry_run)


if __name__ == '__main__':
    main()