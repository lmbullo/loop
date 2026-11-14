"""A one-cell vertical scroll indicator for overflowing viewports.

The track and thumb are drawn in the rightmost cell of the rows a block
actually uses.  Blocks shrink their content by one cell while the bar is
visible, so the indicator never covers text and disappears as soon as every
row fits.
"""

import curses

from . import theme

TRACK = "\u2502"
THUMB = "\u2503"


def overflow(total, visible):
    total, visible = max(0, int(total)), max(0, int(visible))
    return visible > 0 and total > visible


def window(total, visible, scroll):
    """Return ``(start, size)`` for the thumb, or ``None`` when all rows fit."""
    total, visible = max(0, int(total)), max(0, int(visible))
    if not overflow(total, visible):
        return None
    scroll = max(0, min(int(scroll), total - visible))
    size = max(1, min(visible, int(visible * visible / total + 0.5)))
    span = visible - size
    start = int(span * scroll / (total - visible) + 0.5) if span else 0
    return max(0, min(start, span)), size


def bar(total, visible, scroll):
    """A track/thumb string exactly ``visible`` cells long, or ``None``."""
    win = window(total, visible, scroll)
    if win is None:
        return None
    start, size = win
    return (TRACK * start + THUMB * size +
            TRACK * (max(0, int(visible)) - start - size))


def layout(width, total, visible, scroll):
    """Return ``(content_width, bar)``; content loses one cell when a bar shows."""
    width = max(0, int(width))
    text = bar(total, visible, scroll) if width > 1 else None
    if text is None:
        return width, None
    return width - 1, text


def paint(scr, y, x, text, width, height):
    """Draw a prepared bar column, skipping the unsafe bottom-right cell."""
    width, height = max(0, int(width)), max(0, int(height))
    if not text or x < 0 or x >= width:
        return False
    for k, ch in enumerate(text):
        row = y + k
        if row < 0 or row >= height:
            continue
        if row == height - 1 and x >= width - 1:
            continue
        role = "strong" if ch == THUMB else "muted"
        try:
            scr.addstr(row, x, ch, theme.attr(role))
        except curses.error:
            pass
    return True
