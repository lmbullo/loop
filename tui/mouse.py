"""Mouse reporting decode and copy-on-select for the TUI.

A left press anchors a selection, motion extends it, and release copies the
covered screen text to the clipboard and drops the highlight. Coordinates on
the wire are 1-based; the app uses 0-based screen cells.
"""

from . import clipboard, select

WHEEL = {64: "scroll_up", 65: "scroll_down"}


def wheel(button):
    """Strip shift/meta/ctrl bits; xterm reports the wheel as buttons 64/65."""
    return WHEEL.get(button & ~(4 | 8 | 16))


def decode(button, x, y, release=False):
    """One event for a wheel tick or a left-button press/drag/release."""
    tick = wheel(button)
    if tick:
        return ("key", tick)
    if button & 4:
        return None
    held = button & 3
    if release or held == 3:
        return ("mouse", ("up", x - 1, y - 1))
    if held != 0:
        return None
    action = "drag" if button & 32 else "down"
    return ("mouse", (action, x - 1, y - 1))


def sgr_mouse(seq):
    if not seq.startswith(b"\x1b[<") or seq[-1:] not in (b"M", b"m"):
        return None
    parts = seq[3:-1].decode("ascii", "ignore").split(";")
    if len(parts) != 3:
        return None
    try:
        button, x, y = (int(part) for part in parts)
    except ValueError:
        return None
    return decode(button, x, y, release=seq.endswith(b"m"))


def x10_mouse(b):
    if len(b) < 6:
        return None
    return decode(b[3] - 32, b[4] - 32, b[5] - 32)


def _cell(app, x, y):
    return (max(0, min(x, app.w - 1)), max(0, min(y, app.h - 1)))


def down(app, x, y):
    app.sel = {"a": _cell(app, x, y), "b": _cell(app, x, y)}
    app.dirty = True


def drag(app, x, y):
    if getattr(app, "sel", None) is None:
        return
    app.sel["b"] = _cell(app, x, y)
    app.dirty = True


def up(app, x, y, copy=None):
    sel, app.sel = getattr(app, "sel", None), None
    app.dirty = True
    if not sel:
        return False
    sel["b"] = _cell(app, x, y)
    if sel["a"] == sel["b"]:
        return False
    text = select.text(sel, app.w, app.frame.row_text)
    if not text.strip():
        return False
    if (copy or clipboard.copy)(text):
        app.say(f"copied {len(text)} chars")
        return True
    app.say("clipboard copy failed")
    return False


def handle(app, value):
    action, x, y = value
    if action == "down":
        down(app, x, y)
    elif action == "drag":
        drag(app, x, y)
    elif action == "up":
        up(app, x, y)
