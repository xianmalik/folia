"""Subprocess plumbing for the build and ATS flows."""
from __future__ import annotations

import os
import re
import subprocess
import sys

from . import config

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def python() -> str:
    """The repo venv's interpreter, falling back to the server's own."""
    return str(config.VENV_PY) if config.VENV_PY.exists() else sys.executable


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def load_env() -> dict[str, str]:
    """Subprocess environment: venv on PATH plus KEY=value pairs from .env."""
    env = dict(os.environ)
    env["PATH"] = f"{config.REPO_ROOT / '.venv' / 'bin'}:{env.get('PATH', '')}"
    env_file = config.REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env.setdefault(key.strip(), value.strip())
    return env


def run(args: list[str], timeout: int = config.SUBPROCESS_TIMEOUT) -> tuple[int, str]:
    """Run a repo script; return (exit code, combined ANSI-stripped output).

    Failures to launch or finish are reported in-band (nonzero code plus a
    message) rather than raised, so tools can surface them to the model.
    """
    try:
        proc = subprocess.run(
            args,
            cwd=config.REPO_ROOT,
            env=load_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, f"Timed out after {timeout}s: {' '.join(args)}"
    except OSError as exc:
        return 127, f"Failed to launch {' '.join(args)}: {exc}"
    output = strip_ansi(proc.stdout + ("\n" + proc.stderr if proc.stderr else ""))
    return proc.returncode, output.strip()
