#!/usr/bin/env python3

import argparse
import os
import sys
import glob
import time
import shutil
import subprocess
import threading
from pathlib import Path


# Color definitions (ANSI)
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
PURPLE = "\033[0;35m"
RED = "\033[0;31m"
WHITE = "\033[1;37m"
GRAY = "\033[0;37m"
NC = "\033[0m"  # No Color
BOLD = "\033[1m"
# 256-color orange (falls back gracefully if unsupported)
ORANGE = "\033[38;5;208m"


# Directory layout (location-independent — anchored at the repo root)
REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = REPO_ROOT / "core"
SCRIPTS_DIR = CORE_DIR / "scripts"
SOURCE_DIR = REPO_ROOT / "source"
DIST_DIR = REPO_ROOT / "dist"


def read_version() -> str:
    """Read version from VERSION file"""
    version_file = REPO_ROOT / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.0.0"


def print_banner(version: str) -> None:
    print(f"{CYAN}╭─────────────────────────────────────────────────────────────────────╮{NC}")
    print(f"{CYAN}│{WHITE} XeLaTeX CV Builder                                                  {CYAN}│{NC}")
    print(f"{CYAN}│                                                                     │{NC}")
    print(f"{CYAN}│{YELLOW} Version: {GREEN}v{version}{WHITE}                                                     {CYAN}│{NC}")
    print(f"{CYAN}│{YELLOW} Compiling: {GREEN}resume.tex{WHITE} → {GREEN}dist/resume-v{version}.pdf{WHITE}                      {CYAN}│{NC}")
    print(f"{CYAN}│{YELLOW} Engine: {BLUE}XeLaTeX{WHITE}                                                     {CYAN}│{NC}")
    print(f"{CYAN}│{YELLOW} Postbuild: {GRAY}Auto cleanup of auxiliary files after successful build   {CYAN}│{NC}")
    print(f"{CYAN}│                                                                     │{NC}")
    print(f"{CYAN}│{YELLOW} Usage: {GREEN}./core/scripts/build.py{WHITE}                                      {CYAN}│{NC}")
    print(f"{CYAN}│{YELLOW} Author: {PURPLE}@xianmalik{WHITE}                                                  {CYAN}│{NC}")
    print(f"{CYAN}╰─────────────────────────────────────────────────────────────────────╯{NC}")
    print("")


def ensure_output_dir() -> None:
    os.makedirs(DIST_DIR, exist_ok=True)


def check_command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def generate_from_yaml_if_possible() -> None:
    # Mirrors the bash behavior: if python3 exists and generate.py is present,
    # ensure PyYAML is installed and source/*.yml exists, then run the generator.
    if not check_command_exists("python3"):
        return

    generate_script = SCRIPTS_DIR / "generate.py"
    if not generate_script.is_file():
        return

    # Verify PyYAML
    try:
        import yaml  # noqa: F401
    except Exception:
        print(f"{RED}PyYAML not installed.{NC} Install with: {YELLOW}python3 -m pip install -r requirements.txt{NC}")
        sys.exit(1)

    # Verify source directory exists with at least one .yml
    if not SOURCE_DIR.is_dir() or len(glob.glob(str(SOURCE_DIR / "*.yml"))) == 0:
        print(f"{RED}No YAML data found in {WHITE}source/{NC}. Add files like {WHITE}source/00-summary.yml{NC}.")
        sys.exit(1)

    try:
        subprocess.run([sys.executable or "python3", str(generate_script)], check=True)
    except subprocess.CalledProcessError:
        print(f"{RED}Data generation failed.{NC}")
        sys.exit(1)


def run_step_with_spinner(title: str, work_fn, color: str = GREEN) -> any:
    """Run a step showing a spinner (yellow) and finalize with a green checkmark.

    The provided work_fn is executed in a background thread; its return value
    is returned to the caller after completion.
    """
    spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    result_container = {"value": None, "error": None}

    def _runner():
        try:
            result_container["value"] = work_fn()
        except BaseException as exc:  # propagate later
            result_container["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()

    i = 0
    # initial line
    sys.stdout.write(f"{color}{spinner_chars[i]} {title}{NC}")
    sys.stdout.flush()
    i = (i + 1) % len(spinner_chars)
    while thread.is_alive():
        time.sleep(0.1)
        sys.stdout.write(f"\r{color}{spinner_chars[i]} {title}{NC}")
        sys.stdout.flush()
        i = (i + 1) % len(spinner_chars)
    thread.join()

    if result_container["error"] is not None:
        # keep the line, but move to new line with error
        sys.stdout.write("\r")
        sys.stdout.flush()
        raise result_container["error"]

    # Replace spinner with a green checkmark on the same line
    sys.stdout.write(f"\r{color}✓ {title}{NC} {BOLD}{WHITE}DONE!{NC}\n")
    sys.stdout.flush()
    return result_container["value"]



def cleanup_aux_files() -> None:
    patterns = [
        str(DIST_DIR / "*.aux"),
        str(DIST_DIR / "*.log"),
        str(DIST_DIR / "*.out"),
        str(DIST_DIR / "*.fls"),
        str(DIST_DIR / "*.fdb_latexmk"),
    ]
    for pattern in patterns:
        for path in glob.glob(pattern):
            try:
                os.remove(path)
            except OSError:
                pass


def main() -> int:
    version = read_version()
    print_banner(version)
    ensure_output_dir()
    # Step 1: Generate TeX from YAML (if possible)
    def _maybe_generate():
        generate_from_yaml_if_possible()
    run_step_with_spinner("Generating TeX from YAML...", _maybe_generate, color=GREEN)

    # Step 2: Starting XeLaTeX
    def _start_xelatex() -> subprocess.Popen:
        # Start and immediately return; the next step will wait.
        # Run from core/ so resume.tex's relative \input{sections/…},
        # \fontdir[font/], and the class partials all resolve, while the
        # output (PDF + aux) is written to the repo-level dist/ directory.
        log_path_local = DIST_DIR / "resume.log"
        with open(log_path_local, "w") as log_file_local:
            proc = subprocess.Popen(
                [
                    "xelatex",
                    "-interaction=nonstopmode",
                    f"-output-directory={DIST_DIR}",
                    "resume.tex",
                ],
                cwd=str(CORE_DIR),
                stdout=log_file_local,
                stderr=subprocess.STDOUT,
            )
        return proc

    process = run_step_with_spinner("Starting XeLaTeX...", _start_xelatex, color=GREEN)

    # Step 3: Compiling...
    def _wait_compile() -> int:
        return process.wait() or 0

    run_step_with_spinner("Compiling...", _wait_compile, color=GREEN)
    exit_code = process.returncode or 0
    pdf_path = str(DIST_DIR / "resume.pdf")
    versioned_pdf_path = str(DIST_DIR / f"resume-v{version}.pdf")

    if exit_code == 0 and os.path.isfile(pdf_path):
        # Rename to versioned filename
        shutil.copy2(pdf_path, versioned_pdf_path)

        # Step 4: Cleaning up aux files (delegate to clean.py)
        def _clean():
            subprocess.run(
                [sys.executable or "python3", str(SCRIPTS_DIR / "clean.py")],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        run_step_with_spinner("Cleaning up auxiliary files...", _clean, color=GREEN)
        print("")
        print(f"{GREEN}✓ CV compiled successfully to: 📄{WHITE}{versioned_pdf_path}{NC}")
        print(f"{GRAY}  (Also available at: {pdf_path}){NC}")
        print("")
        return 0
    else:
        print(f"{RED}✗ Compilation failed{NC}")
        _print_latex_errors(str(DIST_DIR / "resume.log"))
        return 1


def _print_latex_errors(log_path: str) -> None:
    """Parse XeLaTeX log and print each error with surrounding context."""
    try:
        with open(log_path, "r", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        print(f"{GRAY}Log file not found: {log_path}{NC}")
        return

    error_indices = [i for i, l in enumerate(lines) if l.startswith("!")]
    if not error_indices:
        print(f"{GRAY}See {log_path} for details{NC}")
        return

    print(f"{YELLOW}LaTeX errors:{NC}")
    shown = set()
    for idx in error_indices:
        start = max(0, idx - 2)
        end = min(len(lines), idx + 4)
        for i in range(start, end):
            if i in shown:
                continue
            shown.add(i)
            line = lines[i].rstrip()
            if lines[i].startswith("!"):
                print(f"  {RED}{line}{NC}")
            else:
                print(f"  {GRAY}{line}{NC}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build resume.tex → dist/resume.pdf using XeLaTeX.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 core/scripts/build.py          # standard build\n"
            "  python3 core/scripts/build.py --open   # build and open PDF\n"
            "  make build                              # via Makefile"
        ),
    )
    parser.add_argument(
        "--open", action="store_true", help="open the PDF after a successful build"
    )
    args = parser.parse_args()
    exit_code = main()
    if exit_code == 0 and args.open:
        pdf = str(DIST_DIR / "resume.pdf")
        if sys.platform == "darwin":
            subprocess.run(["open", pdf], check=False)
        else:
            subprocess.run(["xdg-open", pdf], check=False)
    sys.exit(exit_code)


