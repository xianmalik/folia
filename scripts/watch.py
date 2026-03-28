#!/usr/bin/env python3

import sys
import subprocess
from datetime import datetime
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent
except ImportError:
    print("watchdog not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

BLUE = "\033[0;34m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
WHITE = "\033[1;37m"
NC = "\033[0m"

REPO_ROOT = Path(__file__).resolve().parents[1]

WATCHED_FILES = {
    REPO_ROOT / "resume.tex",
    REPO_ROOT / "xianmalik.cls",
}
WATCHED_DIRS = {REPO_ROOT / "data"}


def run_build() -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n{YELLOW}[{ts}] File changed, rebuilding...{NC}")
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "build.py")],
        check=False,
    )
    print(f"{GREEN}✓ Done{NC}\n")


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
            if path.is_relative_to(d) and path.suffix == ".yml":
                run_build()
                return


def main() -> int:
    print("Running initial build...")
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "build.py")],
        check=False,
    )
    print("")
    print("Watching: resume.tex, xianmalik.cls, and data/*.yml ...")
    print("Will automatically rebuild when files are saved")
    print("Press Ctrl+C to stop watching\n")

    handler = ResumeHandler()
    observer = Observer()

    # Watch the repo root non-recursively for top-level files
    observer.schedule(handler, str(REPO_ROOT), recursive=False)
    # Watch data/ recursively for YAML changes
    observer.schedule(handler, str(REPO_ROOT / "data"), recursive=True)

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
