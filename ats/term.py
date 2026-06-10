"""Shared terminal output primitives for the ATS package.

Single source of truth for ANSI color codes, step/done progress lines,
and box-drawing (border style + width). Used by renderer.py and the
ats_check CLI.
"""
from __future__ import annotations

import os
import sys

# ── ANSI codes — matches the build.py palette ─────────────────────────────────
CYAN   = "\033[0;36m"
GREEN  = "\033[0;32m"
YELLOW = "\033[1;33m"
RED    = "\033[0;31m"
WHITE  = "\033[1;37m"
GRAY   = "\033[0;37m"
BOLD   = "\033[1m"
NC     = "\033[0m"


def is_tty() -> bool:
    return hasattr(sys.stdout, "fileno") and os.isatty(sys.stdout.fileno())


def make_resolver(use_color: bool):
    """Return c(code) that yields the ANSI code or "" depending on use_color."""
    return (lambda code: code) if use_color else (lambda code: "")


# ── inline progress steps ─────────────────────────────────────────────────────

STEP_W = 52  # fixed width for the label column


def step(label: str) -> None:
    pad = max(1, STEP_W - 2 - len(label))
    print(f"  {label}{' ' * pad}", end="", flush=True)


def done(note: str = "") -> None:
    note_str = f"  {GRAY}{note}{NC}" if note else ""
    print(f"{GREEN}✓{NC}{note_str}")


# ── box drawing ───────────────────────────────────────────────────────────────

WIDTH     = 76          # ─ characters between corner pieces
CONTENT_W = WIDTH - 4  # usable text width inside  │  …  │  (2 spaces each side)


class Box:
    """Context for drawing one bordered box.

    Parameters
    ----------
    color   ANSI code for border/title color.
    c       Color resolver — c(ansi_code) returns "" or ansi_code depending
            on whether color output is enabled.
    indent  Prefix prepended to every line. Default "  " (2 spaces) for
            content boxes; pass "" for full-width banner cards.
    """

    def __init__(self, color: str, c, indent: str = "  ") -> None:
        self._col = color
        self._c   = c
        self._ind = indent

    # ── structure ──────────────────────────────────────────────────────────

    def open(self, title: str = "") -> "Box":
        """Top border. If *title* is given, prints a bold title row + ├─ sep."""
        c, col, ind = self._c, self._col, self._ind
        print(f"{ind}{c(col)}╭{'─' * WIDTH}╮{c(NC)}")
        if title:
            pad = max(WIDTH - 2 - len(title), 0)
            print(
                f"{ind}{c(col)}│{c(BOLD)}{c(WHITE)}  {title}"
                f"{' ' * pad}{c(NC)}{c(col)}│{c(NC)}"
            )
            self.sep()
        return self

    def sep(self) -> "Box":
        """Mid separator  ├───┤."""
        c, col, ind = self._c, self._col, self._ind
        print(f"{ind}{c(col)}├{'─' * WIDTH}┤{c(NC)}")
        return self

    def close(self) -> None:
        """Bottom border  ╰───╯."""
        c, col, ind = self._c, self._col, self._ind
        print(f"{ind}{c(col)}╰{'─' * WIDTH}╯{c(NC)}")

    # ── content rows ───────────────────────────────────────────────────────

    def row(self, text: str, color: str = "", bold: bool = False) -> "Box":
        """One content row. *text* must be plain (no ANSI) for padding calc."""
        c, col, ind = self._c, self._col, self._ind
        pad = max(CONTENT_W - len(text), 0)
        if color or bold:
            inner = f"{c(color)}{c(BOLD) if bold else ''}{text}{c(NC)}"
        else:
            inner = text
        print(f"{ind}{c(col)}│{c(NC)}  {inner}{' ' * pad}  {c(col)}│{c(NC)}")
        return self

    def raw_row(self, rendered: str, visible_len: int) -> "Box":
        """Row where *rendered* already contains ANSI codes.
        *visible_len* is the printable character count (no escape sequences).
        """
        c, col, ind = self._c, self._col, self._ind
        pad = max(CONTENT_W - visible_len, 0)
        print(f"{ind}{c(col)}│{c(NC)}  {rendered}{' ' * pad}  {c(col)}│{c(NC)}")
        return self


def rule(color: str, c, indent: str = "  ") -> None:
    """Horizontal rule that aligns with box outer edges (WIDTH + 2 wide)."""
    print(f"{indent}{c(color)}{'─' * (WIDTH + 2)}{c(NC)}")
