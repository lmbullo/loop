import curses

from .prompt import cw, display, swidth
from .rows import (BLANK, SELECT, done_parts, field_header, join_parts,
                   queue_parts, task_parts, task_role, window)
from . import theme


def clip(text, cells):
    out, used = [], 0
    for ch in text:
        w = cw(ch)
        if used + w > cells:
            break
        out.append(ch)
        used += w
    return "".join(out)


def fit(text, cells, mark="\u2026"):
    cells = max(0, cells)
    if cells <= 0:
        return ""
    if swidth(text) <= cells:
        return text
    if swidth(mark) >= cells:
        return clip(mark, cells)
    out, used = [], 0
    room = cells - swidth(mark)
    for ch in text:
        w = cw(ch)
        if used + w > room:
            break
        out.append(ch)
        used += w
    return "".join(out).rstrip() + mark


def marked(text, cells, mark=""):
    return fit(mark + fit(text, max(0, cells - swidth(mark))), cells)


def rule(width, left="", right=""):
    if width <= 0:
        return ""
    left = clip(left, width)
    right = clip(right, width - swidth(left))
    fill = max(0, width - swidth(left) - swidth(right))
    return left + "\u2500" * fill + right


def put(scr, y, x, text, width, height, at=0):
    if y < 0 or y >= height or x < 0 or x >= width:
        return
    room = width - x
    if y == height - 1:
        room -= 1
    if room <= 0:
        return
    try:
        scr.addstr(y, x, clip(display(text), room), at)
    except curses.error:
        pass


def fit_parts(parts, cells):
    cells = max(0, cells)
    if sum(swidth(text) for text, _ in parts) <= cells:
        return parts
    room = max(0, cells - 1)
    out, used = [], 0
    for text, role in parts:
        if used >= room:
            break
        piece = clip(text, room - used)
        if piece:
            out.append((piece, role))
            used += swidth(piece)
    if cells:
        out.append(("\u2026", "muted"))
    return out


def put_parts(scr, y, x, parts, width, height):
    if y < 0 or y >= height or x < 0 or x >= width:
        return
    room = width - x
    if y == height - 1:
        room -= 1
    if room <= 0:
        return
    for text, role in fit_parts(parts, room):
        try:
            scr.addstr(y, x, text, theme.attr(role))
        except curses.error:
            return
        x += swidth(text)


def one_line(value):
    return display(value or "").strip()


def task_rows(snap, width):
    return [(fit(join_parts(task_parts(snap)), width), task_role(snap))]


def task_block(scr, snap, y, end, width, height, selected):
    total = max(0, end - y)
    if total <= 0:
        return {"n": 0, "vis": 0}
    vis = max(0, total - 1)
    label = "running:"
    if snap["current"] is not None:
        label = field_header(label, 1)
    put(scr, y, 0, fit(label, width), width, height, theme.attr("muted"))
    if vis:
        marked = selected and snap["current"] is not None
        mark = SELECT if marked else BLANK
        parts = [(mark, "strong" if marked else "muted")] + task_parts(snap)
        put_parts(scr, y + 1, 0, parts, width, height)
    return {"n": 1, "vis": vis}


def queue_block(scr, snap, y, end, width, height, qsel=None):
    """Draw queued tasks; the section disappears when the queue is empty."""
    queue = snap["queue"]
    if not queue or y >= end:
        return y
    room = max(0, end - y - 1)
    offset = 0
    if room:
        if qsel is not None:
            qsel = max(0, min(qsel, len(queue) - 1))
            offset = max(0, qsel - room + 1)
        else:
            offset = max(0, len(queue) - room)
    if room:
        shown = min(len(queue), offset + room)
        label = field_header("queued:", len(queue), offset, shown)
    else:
        label = "queued:"
    put(scr, y, 0, fit(label, width), width, height, theme.attr("muted"))
    idw = min(12, max(7, max(len(str(it.get("id") or "")) for it in queue)))
    for idx in range(offset, min(len(queue), offset + room)):
        item = queue[idx]
        selected = qsel is not None and idx == qsel
        mark = SELECT if selected else BLANK
        parts = [(mark, "strong" if selected else "muted")]
        parts += queue_parts(item, idw, selected)
        put_parts(scr, y + 1 + idx - offset, 0, parts, width, height)
    return min(end, y + 1 + min(len(queue) - offset, room))


def done_rows(snap, width):
    rows = []
    for item in snap.get("done") or []:
        rows.append((fit(join_parts(done_parts(item)), width),
                     theme.state_role(item.get("state"))))
    return rows


def done_block(scr, snap, y, end, width, height, sel=None, scroll=0):
    """Draw finished runs newest first; the header stays when the list is empty."""
    items = snap.get("done") or []
    total = max(0, end - y)
    n, vis, sel, scroll = window(len(items), max(0, total - 1), sel, scroll)
    if total <= 0:
        return {"n": n, "vis": vis, "sel": sel, "scroll": scroll}
    label = field_header("done:", n)
    if vis and n > vis:
        label = field_header("done:", n, scroll, min(n, scroll + vis))
    put(scr, y, 0, fit(label, width), width, height, theme.attr("muted"))
    for k in range(min(vis, n - scroll)):
        idx = scroll + k
        marked = sel is not None and idx == sel
        mark = SELECT if marked else BLANK
        parts = [(mark, "strong" if marked else "muted")] + done_parts(items[idx])
        put_parts(scr, y + 1 + k, 0, parts, width, height)
    return {"n": n, "vis": vis, "sel": sel, "scroll": scroll}
