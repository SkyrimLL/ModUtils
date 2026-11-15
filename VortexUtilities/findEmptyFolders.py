"""Find empty folders in a source directory.

Scans each immediate subfolder of a source directory and reports which ones
are empty. A folder is considered:

- "strict" empty: it contains no files and no subfolders at all.
- "recursive" empty (default): it contains no files anywhere in its tree
  (it may contain subfolders, but none of them hold any files).

Usage:
    python findEmptyFolders.py [SOURCE_DIR] [--strict] [--all] [--delete]

Examples:
    python findEmptyFolders.py "F:\\_VORTEX_MODS\\skyrimse"
    python findEmptyFolders.py "F:\\_VORTEX_MODS\\skyrimse" --strict
    python findEmptyFolders.py "F:\\_VORTEX_MODS\\skyrimse" --delete
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_SOURCE = r"F:\_VORTEX_MODS\skyrimse"


def is_strictly_empty(folder: Path) -> bool:
    """Return True if the folder has no entries at all."""
    with os.scandir(folder) as entries:
        return next(entries, None) is None


def has_any_file(folder: Path) -> bool:
    """Return True if the folder tree contains at least one file."""
    for _root, _dirs, files in os.walk(folder):
        if files:
            return True
    return False


def find_empty_folders(source: Path, strict: bool) -> list[Path]:
    """Return the immediate subfolders of source that are empty."""
    empty: list[Path] = []
    with os.scandir(source) as entries:
        subfolders = sorted(
            (Path(e.path) for e in entries if e.is_dir()),
            key=lambda p: p.name.lower(),
        )
    for folder in subfolders:
        if strict:
            if is_strictly_empty(folder):
                empty.append(folder)
        elif not has_any_file(folder):
            empty.append(folder)
    return empty


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Find empty folders in a source directory."
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=DEFAULT_SOURCE,
        help=f"Source directory to scan (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Only report folders that contain no files AND no subfolders.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="List every scanned subfolder with its status, not just empty ones.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete the empty folders found (prompts for confirmation).",
    )
    args = parser.parse_args(argv)

    source = Path(args.source)
    if not source.is_dir():
        print(f"Error: source directory not found: {source}", file=sys.stderr)
        return 1

    empty = find_empty_folders(source, strict=args.strict)
    mode = "strictly empty" if args.strict else "empty (no files)"

    if args.all:
        with os.scandir(source) as entries:
            subfolders = sorted(
                (Path(e.path) for e in entries if e.is_dir()),
                key=lambda p: p.name.lower(),
            )
        empty_set = set(empty)
        print(f"Scanned {len(subfolders)} folder(s) in {source}:\n")
        for folder in subfolders:
            status = "EMPTY" if folder in empty_set else "has files"
            print(f"  [{status:>9}] {folder.name}")
        print()

    print(f"Found {len(empty)} {mode} folder(s) in {source}:")
    for folder in empty:
        print(f"  {folder}")

    if args.delete and empty:
        answer = input(f"\nDelete these {len(empty)} folder(s)? [y/N] ").strip().lower()
        if answer == "y":
            for folder in empty:
                try:
                    if args.strict:
                        folder.rmdir()
                    else:
                        _remove_tree(folder)
                    print(f"Deleted: {folder}")
                except OSError as exc:
                    print(f"Failed to delete {folder}: {exc}", file=sys.stderr)
        else:
            print("Aborted. No folders deleted.")

    return 0


def _remove_tree(folder: Path) -> None:
    """Remove a folder tree that contains no files (only empty subfolders)."""
    for root, dirs, _files in os.walk(folder, topdown=False):
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(folder)


if __name__ == "__main__":
    raise SystemExit(main())
