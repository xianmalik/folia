#!/usr/bin/env python3

import os
import glob
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "dist"
CORE_DIR = REPO_ROOT / "core"


def find_files(patterns):
    for pattern in patterns:
        for path in glob.glob(pattern):
            if os.path.isfile(path):
                yield path


def main() -> int:
    print("")
    print("🧹 Cleaning LaTeX auxiliary files...")

    extensions = [
        "aux",
        "bcf",
        "log",
        "run.xml",
        "bbl",
        "blg",
        "fdb_latexmk",
        "fls",
        "toc",
        "out",
        "nav",
        "snm",
        "synctex.gz",
        "xdv",
    ]

    total_removed = 0

    # Dist directory
    if DIST_DIR.is_dir():
        for ext in extensions:
            matches = list(find_files([str(DIST_DIR / f"*.{ext}")]))
            if matches:
                print(f"  🗑️  Removing {len(matches)} .{ext} file(s)")
                for m in matches:
                    try:
                        os.remove(m)
                        total_removed += 1
                    except OSError:
                        pass

    # Core directory (where XeLaTeX runs — catches any stray aux files)
    for ext in extensions:
        matches = list(find_files([str(CORE_DIR / f"*.{ext}")]))
        if matches:
            print(f"  🗑️  Removing {len(matches)} .{ext} file(s) from core/")
            for m in matches:
                try:
                    os.remove(m)
                    total_removed += 1
                except OSError:
                    pass

    if total_removed == 0:
        print("✨ No auxiliary files found - already clean!")
    else:
        print(f"✅ Cleaned up {total_removed} auxiliary file(s)")

    if DIST_DIR.is_dir():
        print("")
        print("📂 Remaining files in dist/:")
        for name in sorted(os.listdir(DIST_DIR)):
            try:
                path = DIST_DIR / name
                size = os.path.getsize(path)
                print(f"   {name}  {size} bytes")
            except OSError:
                print(f"   {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


