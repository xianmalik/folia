"""Box-drawing primitives for ATS terminal output.

Single source of truth for box width and border style.
All box-shaped sections in renderer.py and ats_check.py use this module.
"""
from __future__ import annotations

WIDTH     = 76          # ─ characters between corner pieces
CONTENT_W = WIDTH - 4  # usable text width inside  │  …  │  (2 spaces each side)

_BOLD  = "\033[1m"
_WHITE = "\033[1;37m"
_NC    = "\033[0m"


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
        print(f"{ind}{c(col)}╭{'─' * WIDTH}╮{c(_NC)}")
        if title:
            pad = max(WIDTH - 2 - len(title), 0)
            print(
                f"{ind}{c(col)}│{c(_BOLD)}{c(_WHITE)}  {title}"
                f"{' ' * pad}{c(_NC)}{c(col)}│{c(_NC)}"
            )
            self.sep()
        return self

    def sep(self) -> "Box":
        """Mid separator  ├───┤."""
        c, col, ind = self._c, self._col, self._ind
        print(f"{ind}{c(col)}├{'─' * WIDTH}┤{c(_NC)}")
        return self

    def close(self) -> None:
        """Bottom border  ╰───╯."""
        c, col, ind = self._c, self._col, self._ind
        print(f"{ind}{c(col)}╰{'─' * WIDTH}╯{c(_NC)}")

    # ── content rows ───────────────────────────────────────────────────────

    def row(self, text: str, color: str = "", bold: bool = False) -> "Box":
        """One content row. *text* must be plain (no ANSI) for padding calc."""
        c, col, ind = self._c, self._col, self._ind
        pad = max(CONTENT_W - len(text), 0)
        if color or bold:
            inner = f"{c(color)}{c(_BOLD) if bold else ''}{text}{c(_NC)}"
        else:
            inner = text
        print(f"{ind}{c(col)}│{c(_NC)}  {inner}{' ' * pad}  {c(col)}│{c(_NC)}")
        return self

    def raw_row(self, rendered: str, visible_len: int) -> "Box":
        """Row where *rendered* already contains ANSI codes.
        *visible_len* is the printable character count (no escape sequences).
        """
        c, col, ind = self._c, self._col, self._ind
        pad = max(CONTENT_W - visible_len, 0)
        print(f"{ind}{c(col)}│{c(_NC)}  {rendered}{' ' * pad}  {c(col)}│{c(_NC)}")
        return self


def rule(color: str, c, indent: str = "  ") -> None:
    """Horizontal rule that aligns with box outer edges (WIDTH + 2 wide)."""
    print(f"{indent}{c(color)}{'─' * (WIDTH + 2)}{c(_NC)}")
