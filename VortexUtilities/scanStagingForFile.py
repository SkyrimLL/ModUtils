"""Scan the Vortex staging directory for target file patterns.

Scans each immediate subfolder (mod) of the Vortex staging directory and
reports which mods contain files matching one or more glob patterns anywhere
in their tree.

Usage:
    python scanStagingForFile.py [SOURCE_DIR] [--pattern PATTERN ...] [--no-list-files]

Examples:
    python scanStagingForFile.py
    python scanStagingForFile.py "F:\\_VORTEX_MODS\\skyrimse"
    python scanStagingForFile.py --pattern dialoguemenu.swf --pattern *.esp
    python scanStagingForFile.py --no-list-files
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys
from pathlib import Path

from colorama import Fore, init as colorama_init

DEFAULT_SOURCE = r"F:\_VORTEX_MODS\skyrimse"
DEFAULT_PATTERNS = ["*\\meshes\\actors\\character\\character assets\\skeleton.*"]


def matches_any(path: Path, patterns: list[str]) -> bool:
    """Return True if path matches any of the patterns (case-insensitive).

    Patterns containing a path separator (\\ or /) are matched against the
    full path; plain patterns are matched against the file name only.
    """
    name = path.name.lower()
    full = str(path).lower()
    for pattern in patterns:
        lowered = pattern.lower()
        target = full if ("\\" in lowered or "/" in lowered) else name
        if fnmatch.fnmatch(target, lowered):
            return True
    return False


def find_matches(folder: Path, patterns: list[str]) -> list[Path]:
    """Return every file within folder whose path matches a pattern."""
    hits: list[Path] = []
    for root, _dirs, files in os.walk(folder):
        for name in files:
            path = Path(root) / name
            if matches_any(path, patterns):
                hits.append(path)
    return hits


def scan_staging(
    source: Path, patterns: list[str]
) -> list[tuple[Path, list[Path]]]:
    """Return (mod_folder, matching_files) for each mod that has matches."""
    results: list[tuple[Path, list[Path]]] = []
    with os.scandir(source) as entries:
        subfolders = sorted(
            (Path(e.path) for e in entries if e.is_dir()),
            key=lambda p: p.name.lower(),
        )
    for folder in subfolders:
        hits = find_matches(folder, patterns)
        if hits:
            results.append((folder, hits))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan the Vortex staging directory for target file patterns."
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=DEFAULT_SOURCE,
        help=f"Staging directory to scan (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        metavar="PATTERN",
        help=(
            "Glob file pattern to search for (case-insensitive). "
            "Repeat to search multiple patterns. "
            f"Default: {', '.join(DEFAULT_PATTERNS)}"
        ),
    )
    parser.add_argument(
        "--list-files",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="List every matching file path, not just the mod folders.",
    )
    args = parser.parse_args(argv)

    colorama_init(autoreset=True)

    source = Path(args.source)
    if not source.is_dir():
        print(f"Error: source directory not found: {source}", file=sys.stderr)
        return 1

    patterns = args.patterns or DEFAULT_PATTERNS
    results = scan_staging(source, patterns)

    print(
        f"Scanning {source} for pattern(s): {', '.join(patterns)}\n"
    )

    total_files = sum(len(hits) for _folder, hits in results)
    print(f"Found matches in {len(results)} mod(s) ({total_files} file(s)):")
    for folder, hits in results:
        print(f"  {Fore.BLUE}{folder.name}{Fore.RESET}  ({len(hits)} file(s))")
        if args.list_files:
            for hit in hits:
                print(f"      {Fore.WHITE}{hit.relative_to(source)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
