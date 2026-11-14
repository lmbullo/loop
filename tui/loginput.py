import time

from .rows import task_sel


def selected_run(snap, sel):
    """Map the flat task selection to a run id; queued rows have no log yet."""
    snap = snap or {}
    section, idx = task_sel(snap, sel)
    if section == "running":
        current = snap.get("current")
        return current.get("id") if current else None
    if section == "queue":
        return None
    done = snap.get("done") or []
    return done[idx].get("id") if 0 <= idx < len(done) else None


def open_log(app):
    """Open the selected run's log; return False when there is no run row."""
    snap = app.snapshot()
    ident = selected_run(snap, app.tsel)
    if not ident:
        return False
    data = app.worker.log(ident)
    live = bool((snap.get("current") or {}).get("id") == ident)
    if live and data.get("state") == "interrupted":
        data = dict(data, state="running")
    n = len(data.get("entries") or [])
    app.log = {"id": ident, "data": data, "sel": max(0, n - 1) if live else 0,
               "scroll": 0, "vis": 1, "follow": True, "tail": live,
               "live": live, "at": time.time()}
    app.focus = "log"
    app.dirty = True
    return True


def close_log(app):
    if getattr(app, "log", None) is None:
        return False
    app.log = None
    app.focus = "task"
    app.dirty = True
    return True


def refresh_log(app, now, interval=0.25):
    """Re-read a live run's record on a timer; terminal runs are not re-read.

    A live log tail-follows: the selection stays on the newest entry until the
    user moves it, so appended calls appear without touching the scroll offset.
    The frame buffer sorts out which rows actually changed.
    """
    log = getattr(app, "log", None)
    if log is None or now - log.get("at", 0.0) < interval:
        return
    if (log.get("data") or {}).get("terminal"):
        return
    log["at"] = now
    data = app.worker.log(log["id"])
    if data is None:
        return
    if log.get("live") and data.get("state") == "interrupted":
        data = dict(data, state="running")
    if log.get("tail"):
        n = len(data.get("entries") or [])
        if n:
            log["sel"] = n - 1
    if data != log.get("data"):
        log["data"] = data
        app.dirty = True


def log_key(app, key):
    log = getattr(app, "log", None)
    if log is None:
        app.focus = "task"
        app.dirty = True
        return
    n = len((log.get("data") or {}).get("entries") or [])
    vis = max(1, int(log.get("vis") or 1))
    sel = max(0, min(int(log.get("sel") or 0), max(0, n - 1)))
    scroll = max(0, int(log.get("scroll") or 0))
    follow = bool(log.get("follow", True))
    tail = bool(log.get("tail", False))
    if key in ("up", "hist_prev"):
        sel, follow, tail = max(0, sel - 1), True, False
    elif key in ("down", "hist_next"):
        sel, follow, tail = min(max(0, n - 1), sel + 1), True, False
    elif key == "page_up":
        sel, follow, tail = max(0, sel - vis), True, False
    elif key == "page_down":
        sel, follow, tail = min(max(0, n - 1), sel + vis), True, False
    elif key == "home":
        sel, follow, tail = 0, True, False
    elif key == "end":
        sel, follow, tail = max(0, n - 1), True, True
    elif key in ("scroll_up", "wheel_up", "shift_up"):
        scroll = max(0, scroll - 1)
        follow, tail = False, False
    elif key in ("scroll_down", "wheel_down", "shift_down"):
        scroll = min(max(0, n - vis), scroll + 1)
        follow, tail = False, False
    elif key in ("tab", "backtab"):
        from .input import open_prompt
        open_prompt(app)
        return
    elif key in ("enter", "newline", "esc", "left"):
        close_log(app)
        return
    log["sel"] = sel
    log["scroll"] = scroll
    log["follow"] = follow
    log["tail"] = tail
    app.dirty = True
