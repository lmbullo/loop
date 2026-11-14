import curses

from .prompt import cw, display, swidth
from .model import money

SELECT = "> "
BLANK = "  "


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


def task_rows(snap, width):
    cur = snap["current"]
    if cur is None:
        return [(fit("idle - type a task and press enter", width), None)]
    info = (f"id={cur['id']} state={cur['state']} turns={cur['turns']} "
            f"cost={money(cur['cost'])}")
    if cur.get("finish"):
        info += f" finish={cur['finish']}"
    rows = [(fit(info, width), None)]
    if cur.get("detail"):
        rows.append((fit(display(cur["detail"]), width), None))
    text = display(cur.get("text") or "")
    if text:
        rows.append((fit("  " + text, width), None))
    return rows


def task_block(scr, snap, y, end, width, height, focus, sel, scroll):
    total = max(0, end - y)
    if total <= 0:
        return {"n": 0, "vis": 0, "sel": 0, "scroll": 0}
    rows = task_rows(snap, width)
    n = len(rows)
    vis = max(0, total - 1)
    sel = max(0, min(sel, n - 1))
    scroll = max(0, min(scroll, max(0, n - vis)))
    if vis:
        if sel < scroll:
            scroll = sel
        if sel >= scroll + vis:
            scroll = sel - vis + 1
    label = "task"
    if n > vis:
        label += f" {scroll + 1}-{min(n, scroll + vis)}/{n}"
    put(scr, y, 0, fit(label, width), width, height)
    for k in range(vis):
        idx = scroll + k
        if idx >= n:
            break
        text, _ = rows[idx]
        mark = SELECT if focus == "task" and idx == sel else BLANK
        put(scr, y + 1 + k, 0, marked(text, width, mark), width, height)
    return {"n": n, "vis": vis, "sel": sel, "scroll": scroll}


def queue_block(scr, snap, y, end, width, height, focus, qsel):
    queue = snap["queue"]
    put(scr, y, 0, fit(f"queue {len(queue)}" if queue else "queue", width),
        width, height)
    y += 1
    if y >= end:
        return y
    room = max(0, end - y)
    if not queue:
        return y
    offset = max(0, qsel - room + 1) if focus else 0
    for idx in range(offset, min(len(queue), offset + room)):
        item = queue[idx]
        first = (item.get("text") or "").replace("\n", " ").replace("\r", " ")
        mark = SELECT if focus and idx == qsel else BLANK
        line = f"{item['id']:<8} {item['state']:<8} {first}"
        put(scr, y, 0, marked(line, width, mark), width, height)
        y += 1
    return y
