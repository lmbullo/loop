import curses
import time

from .prompt import swidth
from .panes import attr, fit, init_colors, put, queue_block, rule, task_block


def status_line(snap, width, focus):
    if width <= 0:
        return ""
    daemon = snap["daemon"]
    state = daemon["state"].upper()
    detail = daemon.get("detail") or ""
    left = f"agent tui focus={focus} daemon={state}"
    if daemon.get("pid"):
        left += f" pid={daemon['pid']}"
    if state != "RUNNING" and detail:
        left += f"  {detail}"
    notice = snap.get("notice") or ""
    if notice and time.time() - (snap.get("notice_at") or 0) < 3.0:
        right = notice
    elif focus == "task":
        right = "up/down scroll  tab prompt  ctrl+q quit"
    elif focus == "queue":
        right = "up/down select  K/J reorder  del drop"
    else:
        right = "esc cancel  enter submit  tab queue"
    right = fit(right, max(1, width))
    left = fit(left, max(0, width - swidth(right) - 1))
    space = max(0, width - swidth(left) - swidth(right))
    return left + " " * space + right


def prompt_block(scr, prompt, top, width, height, focus, content_w, max_rows):
    lay = prompt.layout(content_w, max_rows)
    rows, scroll, n, h = lay["rows"], lay["scroll"], lay["n"], lay["height"]
    up = f"\u2191 {scroll} " if scroll > 0 else ""
    below = max(0, n - scroll - h)
    if n <= h:
        down = " 1/1 " if n <= 1 else f" 1-{n}/{n} "
    else:
        down = f" {scroll + 1}-{min(n, scroll + h)}/{n}"
        if below:
            down += f" \u2193 {below}"
        down += " "
    label = " prompt " if focus == "prompt" else " prompt (tab) "
    put(scr, top, 0, rule(width, label, up), width, height, attr("rule"))
    for k in range(h):
        idx = scroll + k
        text = rows[idx]["text"] if idx < len(rows) else ""
        text = fit(text, content_w, mark="")
        put(scr, top + 1 + k, 0, text + " " * max(0, content_w - swidth(text)),
            width, height)
    put(scr, top + h + 1, 0, rule(width, "", down), width, height, attr("rule"))
    return lay


def draw(scr, snap, prompt, width, height, focus, qsel, tsel=0, tscroll=0):
    if width < 2 or height < 3:
        return None
    scr.erase()
    content_w = max(1, width)
    max_rows = max(1, height - 2)
    lay = prompt.layout(content_w, max_rows)
    open_prompt = focus == "prompt"
    ph = lay["height"] + 2 if open_prompt else 0
    ptop = max(0, height - ph)
    put(scr, 0, 0, status_line(snap, width, focus), width, height, attr("status"))
    body_start = 1 if ptop >= 2 else ptop
    body_end = ptop
    tv = {"n": 0, "vis": 0, "sel": 0, "scroll": 0}
    if body_end > body_start:
        queue = snap["queue"]
        reserve = 0
        if queue:
            span = body_end - body_start
            reserve = min(len(queue) + 2, max(3, span // 2))
            if focus == "task":
                reserve = min(reserve, max(2, span // 3))
        task_end = max(body_start + 1, body_end - reserve)
        tv = task_block(scr, snap, body_start, task_end, width, height,
                        focus, tsel, tscroll)
        if task_end < body_end:
            queue_block(scr, snap, task_end, body_end, width, height, focus, qsel)
    if open_prompt:
        lay = prompt_block(scr, prompt, ptop, width, height, focus, content_w, max_rows)
        row = ptop + 1 + lay["cursor_row"] - lay["scroll"]
        col = min(width - 1, max(0, lay["cursor_col"]))
        if 0 <= row < height:
            try:
                scr.move(row, col)
            except curses.error:
                pass
    try:
        curses.curs_set(1 if open_prompt else 0)
    except curses.error:
        pass
    lay["task"] = tv
    lay["prompt_open"] = open_prompt
    lay["prompt_top"] = ptop
    try:
        scr.noutrefresh()
        curses.doupdate()
    except curses.error:
        pass
    return lay
