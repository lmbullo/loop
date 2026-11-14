"""Row-diffed frame buffer for flicker-free curses updates.

The app draws each frame into a ``Frame`` instead of writing the curses window
directly. ``flush`` compares every row with the previous frame and rewrites
only the rows that changed, so a live log appending one call touches one or
two rows rather than repainting the whole screen.

On terminals that implement synchronized output (DEC private mode 2026) the
``doupdate`` is wrapped in one atomic block, which is the standard cure for
tearing while a log is growing. Unsupported terminals ignore the mode.
"""

import curses
import os
import sys

from . import highlight

SYNC_BEGIN = b"\x1b[?2026h"
SYNC_END = b"\x1b[?2026l"
HIGHLIGHT = curses.A_REVERSE


def sync_supported():
    if os.environ.get("LOOP_TUI_SYNC", "1") == "0":
        return False
    if os.environ.get("TERM", "") in ("", "dumb"):
        return False
    try:
        return sys.stdout.isatty()
    except (AttributeError, OSError):
        return False


def _write(data):
    try:
        os.write(1, data)
    except OSError:
        pass


class Frame:
    """A tiny row-addressed screen with an addstr/move/erase surface.

    ``rows`` keeps the draw operations for the current frame in call order, so
    overlapping writes replay exactly like direct curses calls. ``prev`` keeps
    the last committed frame; a resize or ``invalidate`` forces a full repaint.
    """

    def __init__(self, target, sync=False):
        self.target = target
        self.sync = sync
        self.width = 0
        self.height = 0
        self.rows = []
        self.prev = None
        self.marks = []
        self.prev_marks = []
        self.cursor = None
        self.visible = None

    def resize(self, width, height):
        width, height = max(0, width), max(0, height)
        if (width, height) == (self.width, self.height):
            return False
        self.width, self.height = width, height
        self.rows = [[] for _ in range(height)]
        self.prev = None
        self.cursor = None
        return True

    def invalidate(self):
        """Drop the previous frame so the next flush repaints every row."""
        self.prev = None

    def highlight(self, spans):
        """Reverse-video spans ``(row, x0, x1)`` in screen cells, merged per row."""
        self.marks = highlight.spans(spans, self.width, self.height)

    def row_text(self, y, width=None):
        """The characters committed on row ``y``, spaces included."""
        if not (0 <= y < self.height):
            return ""
        return highlight.row_text(self.rows[y], y,
                                  self.width if width is None else width)

    def erase(self):
        self.rows = [[] for _ in range(self.height)]

    clear = erase

    def addstr(self, y, x, text, attr=0):
        if not (0 <= y < self.height and 0 <= x < self.width):
            return
        room = self.width - x
        if y == self.height - 1:
            room -= 1
        if room <= 0:
            return
        text = text[:room]
        if text:
            self.rows[y].append((x, text, attr))

    def move(self, y, x):
        if 0 <= y < self.height and 0 <= x < self.width:
            self.cursor = (y, x)

    def flush(self, show_cursor=False):
        """Commit changed rows, then update the real terminal exactly once."""
        self._visibility(bool(show_cursor))
        moved = set()
        if self.prev_marks != self.marks:
            moved = {y for y, _, _ in self.prev_marks + self.marks}
        if self.prev is None:
            moved = set()
        for y, ops in enumerate(self.rows):
            if self.prev is not None and self.prev[y] == ops and y not in moved:
                continue
            self._paint(y, ops, self._marks(y))
        self.prev = [list(ops) for ops in self.rows]
        self.prev_marks = list(self.marks)
        if show_cursor and self.cursor is not None:
            try:
                self.target.move(self.cursor[0], self.cursor[1])
            except (curses.error, AttributeError):
                pass
        try:
            self.target.noutrefresh()
        except (curses.error, AttributeError):
            return
        begin = self.sync and sync_supported()
        if begin:
            _write(SYNC_BEGIN)
        try:
            curses.doupdate()
        except curses.error:
            pass
        finally:
            if begin:
                _write(SYNC_END)

    def _marks(self, y):
        return highlight.row_marks(self.marks, y)

    def _visibility(self, on):
        if self.visible == on:
            return
        try:
            curses.curs_set(1 if on else 0)
        except curses.error:
            pass
        self.visible = on

    def _paint(self, y, ops, marks=()):
        room = self.width
        if y == self.height - 1:
            room -= 1
        if room <= 0:
            return
        try:
            self.target.addstr(y, 0, " " * room)
        except curses.error:
            return
        for x0, x1 in marks:
            x0, x1 = max(0, min(x0, room)), max(0, min(x1, room))
            if x1 > x0:
                try:
                    self.target.addstr(y, x0, " " * (x1 - x0), HIGHLIGHT)
                except curses.error:
                    break
        for x, text, attr in ops:
            for px, piece, pattr in highlight.pieces(x, text, attr, marks,
                                                     HIGHLIGHT):
                try:
                    self.target.addstr(y, px, piece, pattr)
                except curses.error:
                    return
