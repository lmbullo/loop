import curses

from .prompt import cw, display, swidth
from .model import money

PAIR = {"status": 1, "label": 2, "dim": 3, "sel": 4, "rule": 5, "err": 6,
        "ok": 7, "accent": 8}

# Gruvbox 256-color approximations on a grey base. Every pair keeps the
# terminal background (-1), so the user's background is never repainted.
GRUVBOX = {
    "status": 250,  # light2 #d5c4a1
    "label": 208,   # orange #fe8019
    "dim": 245,     # gray   #928374
    "sel": 214,     # yellow #fabd2f
    "rule": 243,    # dark4  #7c6f64
    "err": 167,     # red    #fb4934
    "ok": 142,      # green  #b8bb26
    "accent": 108,  # aqua   #8ec07c
}
BASE = {  # eight-color terminals: grey from white, gruvbox hues elsewhere
    "status": curses.COLOR_WHITE,
    "label": curses.COLOR_YELLOW,
    "dim": curses.COLOR_WHITE,
    "sel": curses.COLOR_YELLOW,
    "rule": curses.COLOR_WHITE,
    "err": curses.COLOR_RED,
    "ok": curses.COLOR_GREEN,
    "accent": curses.COLOR_CYAN,
}


def init_colors():
    try:
        curses.start_color()
        curses.use_default_colors()
        fg = GRUVBOX if curses.COLORS >= 256 else BASE
    except curses.error:
        return
    for name, pair in PAIR.items():
        try:
            curses.init_pair(pair, fg[name], -1)
        except curses.error:
            pass


def attr(name):
    try:
        return curses.color_pair(PAIR[name])
    except curses.error:
        return 0


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


def rule(width, left="", right=""):
    if width <= 0:
        return ""
    left = clip(left, width)
    right = clip(right, width - swidth(left))
    fill = max(0, width - swidth(left) - swidth(right))
    return left + "\u2500" * fill + right


STATE = {"running": "accent", "complete": "ok", "corrupt": "err"}


def task_rows(snap, width):
    cur = snap["current"]
    if cur is None:
        return [(fit("idle - type a task and press enter", width), "dim")]
    info = (f"id={cur['id']} state={cur['state']} turns={cur['turns']} "
            f"cost={money(cur['cost'])}")
    if cur.get("finish"):
        info += f" finish={cur['finish']}"
    rows = [(fit(info, width), STATE.get(cur["state"], "label"))]
    if cur.get("detail"):
        rows.append((fit(display(cur["detail"]), width), "err"))
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
    label = "TASK IN AGENT"
    if n > vis:
        label += f"  {scroll + 1}-{min(n, scroll + vis)}/{n}"
    put(scr, y, 0, fit(label, width), width, height, attr("label") | curses.A_BOLD)
    for k in range(vis):
        idx = scroll + k
        if idx >= n:
            break
        text, style = rows[idx]
        at = attr(style) if style else 0
        if focus == "task" and idx == sel:
            at |= curses.A_REVERSE
        put(scr, y + 1 + k, 0, fit(text, width), width, height, at)
    return {"n": n, "vis": vis, "sel": sel, "scroll": scroll}


def queue_block(scr, snap, y, end, width, height, focus, qsel):
    queue = snap["queue"]
    label = f"QUEUE {len(queue)} waiting"
    put(scr, y, 0, label, width, height, attr("label") | curses.A_BOLD)
    y += 1
    if y >= end:
        return y
    room = max(0, end - y)
    if not queue:
        put(scr, y, 0, "empty", width, height, attr("dim"))
        return y + 1
    offset = max(0, qsel - room + 1) if focus else 0
    for idx in range(offset, min(len(queue), offset + room)):
        item = queue[idx]
        first = (item.get("text") or "").replace("\n", " ").replace("\r", " ")
        mark = ">" if focus and idx == qsel else " "
        line = f"{mark} {item['id']:<8} {item['state']:<8} {first}"
        at = (attr("sel") | curses.A_BOLD) if focus and idx == qsel else 0
        put(scr, y, 0, fit(line, width), width, height, at)
        y += 1
    return y
