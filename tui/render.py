import curses
import time

from .prompt import swidth
from .logview import log_block
from .panes import done_block, fit, put, queue_block, rule, task_block
from .rows import task_sel
from . import theme


def status_line(snap, width, focus):
    if width <= 0:
        return ""
    daemon = snap["daemon"]
    state = daemon["state"].lower()
    detail = daemon.get("detail") or ""
    dot = "\u25cf" if state == "running" else "\u2715"
    if state in ("starting", "attaching"):
        dot = "\u25cb"
    left = f"{dot} daemon {state}"
    if state != "running" and detail:
        left += f" \u00b7 {detail}"
    notice = snap.get("notice") or ""
    if notice and time.time() - (snap.get("notice_at") or 0) < 3.0:
        right = notice
    elif focus == "task":
        action = "logs" if snap.get("current") or snap.get("done") else "type"
        right = f"\u21b5 {action} \u00b7 ^Q quit"
        if snap.get("current") or snap.get("queue") or snap.get("done"):
            right = "\u2191\u2193 tasks \u00b7 " + right
        if snap.get("queue"):
            right = "\u2192 queue \u00b7 " + right
    elif focus == "queue":
        right = ("\u2190 task \u00b7 \u2191\u2193 select \u00b7 "
                 "\u21e7\u2191\u2193 move \u00b7 del drop \u00b7 \u21b5 type")
    elif focus == "log":
        right = "esc back \u00b7 \u2191\u2193 calls \u00b7 \u21b5 close"
    else:
        right = "esc cancel \u00b7 \u21b5 submit"
    right = fit(right, max(1, width))
    left = fit(left, max(0, width - swidth(right) - 1))
    space = max(0, width - swidth(left) - swidth(right))
    return left + " " * space + right


def prompt_block(scr, prompt, top, width, height, focus, content_w, max_rows):
    lay = prompt.layout(content_w, max_rows)
    rows, scroll, n, h = lay["rows"], lay["scroll"], lay["n"], lay["height"]
    label = " prompt "
    if n > h or scroll:
        label += f"{scroll + 1}-{min(n, scroll + h)}/{n} "
    role = theme.PROMPT_FOCUS if focus == "prompt" else theme.PROMPT_IDLE
    at = theme.attr(role)
    hint = " \u21b5 " if focus == "prompt" else ""
    put(scr, top, 0, rule(width, label, hint), width, height, at)
    for k in range(h):
        idx = scroll + k
        text = rows[idx]["text"] if idx < len(rows) else ""
        text = fit(text, content_w, mark="")
        put(scr, top + 1 + k, 0,
            text + " " * max(0, content_w - swidth(text)), width, height, at)
    put(scr, top + h + 1, 0, rule(width), width, height, at)
    return lay


def body_spans(snap, top, end):
    """Rows for running/queued; queued keeps its own rows above done."""
    span = max(0, end - top)
    running = min(2, span)
    rest = span - running
    queued = snap["queue"]
    done = snap.get("done") or []
    queue_h = 0
    if queued and rest > 0:
        if done:
            queue_h = min(len(queued) + 1, max(2, rest // 2))
            queue_h = min(queue_h, max(0, rest - 2))
        else:
            queue_h = rest
    return running, queue_h


def draw(scr, snap, prompt, width, height, focus, qsel, tsel=0, tscroll=0,
         log=None):
    if width < 2 or height < 3:
        return None
    scr.erase()
    content_w = max(1, width)
    max_rows = max(1, height - 2)
    lay = prompt.layout(content_w, max_rows)
    open_prompt = focus == "prompt"
    ph = lay["height"] + 2 if open_prompt else 0
    ptop = max(0, height - ph)
    put(scr, 0, 0, status_line(snap, width, focus), width, height,
        theme.attr(theme.status_role(snap)))
    if log is not None and focus == "log":
        info = log_block(scr, log.get("data"), 1, height, width, height,
                         log.get("sel", 0), log.get("scroll", 0))
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        try:
            scr.noutrefresh()
            curses.doupdate()
        except curses.error:
            pass
        return {"log": info, "prompt_open": False, "height": height,
                "prompt_top": 0}
    body_start = 1 if ptop >= 2 else ptop
    body_end = ptop
    nq = len(snap.get("queue") or [])
    section, idx = task_sel(snap, tsel) if focus == "task" else (None, None)
    qsel = idx if section == "queue" else (qsel if focus == "queue" else None)
    tv = {"n": 1, "vis": 0}
    qvis = 0
    dv = {"n": len(snap.get("done") or []), "vis": 0, "sel": None, "scroll": tscroll}
    if body_end > body_start:
        run_h, queue_h = body_spans(snap, body_start, body_end)
        task_end = body_start + run_h
        tv = task_block(scr, snap, body_start, task_end, width, height,
                        focus == "task" and tsel == 0)
        queue_end = queue_block(scr, snap, task_end, task_end + queue_h,
                                width, height, qsel)
        qvis = max(0, queue_end - task_end - 1) if nq else 0
        dsel = idx if section == "done" else None
        dv = done_block(scr, snap, queue_end, body_end, width, height, dsel, tscroll)
    n = 1 + nq + dv["n"]
    tv = {"n": n, "vis": max(1, tv.get("vis", 0) + qvis + dv["vis"]),
          "sel": max(0, min(tsel, n - 1)), "scroll": dv["scroll"]}
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
