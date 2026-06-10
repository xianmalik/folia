#!/usr/bin/env python3

import sys
import subprocess
from datetime import datetime
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("watchdog not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

BLUE = "\033[0;34m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
WHITE = "\033[1;37m"
NC = "\033[0m"

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = REPO_ROOT / "core"
SCRIPTS_DIR = CORE_DIR / "scripts"

WATCHED_FILES = {
    CORE_DIR / "resume.tex",
    CORE_DIR / "xianmalik.cls",
}
WATCHED_DIRS = {REPO_ROOT / "source", CORE_DIR / "partials"}


def run_build() -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n{YELLOW}[{ts}] File changed, rebuilding...{NC}")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "build.py")],
        check=False,
    )
    if result.returncode == 0:
        print(f"{GREEN}✓ Build succeeded{NC}\n")
    else:
        print(f"{RED}✗ Build failed (exit {result.returncode}){NC}\n")


class ResumeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        self._handle(event)

    def on_created(self, event):
        self._handle(event)

    def _handle(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path).resolve()
        if path in WATCHED_FILES:
            run_build()
            return
        for d in WATCHED_DIRS:
            if path.is_relative_to(d) and path.suffix in (".yml", ".tex"):
                run_build()
                return


def main() -> int:
    print("Running initial build...")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "build.py")],
        check=False,
    )
    if result.returncode != 0:
        print(f"{RED}✗ Initial build failed{NC}")

    print("")
    print("Watching: core/resume.tex, core/xianmalik.cls, core/partials/*.tex, and source/*.yml ...")
    print("Will automatically rebuild when files are saved")
    print("Press Ctrl+C to stop watching\n")

    handler = ResumeHandler()
    observer = Observer()

    # Watch core/ non-recursively for resume.tex and xianmalik.cls
    observer.schedule(handler, str(CORE_DIR), recursive=False)
    # Watch source/ recursively for YAML changes
    observer.schedule(handler, str(REPO_ROOT / "source"), recursive=True)
    # Watch core/partials/ recursively for LaTeX class partial changes
    observer.schedule(handler, str(CORE_DIR / "partials"), recursive=True)

    observer.start()
    try:
        observer.join()
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
        print("Stopped watching.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
