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
    app.log = {"id": ident, "data": data, "sel": 0, "scroll": 0, "vis": 1,
               "follow": True, "live": live, "at": time.time()}
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


def refresh_log(app, now, interval=0.75):
    """Re-read a live run's record on a timer; terminal runs are not re-read."""
    log = getattr(app, "log", None)
    if log is None or now - log.get("at", 0.0) < interval:
        return
    if (log.get("data") or {}).get("terminal"):
        return
    log["at"] = now
    data = app.worker.log(log["id"])
    if data is not None:
        if log.get("live") and data.get("state") == "interrupted":
            data = dict(data, state="running")
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
    if key in ("up", "hist_prev"):
        sel, follow = max(0, sel - 1), True
    elif key in ("down", "hist_next"):
        sel, follow = min(max(0, n - 1), sel + 1), True
    elif key == "page_up":
        sel, follow = max(0, sel - vis), True
    elif key == "page_down":
        sel, follow = min(max(0, n - 1), sel + vis), True
    elif key == "home":
        sel, follow = 0, True
    elif key == "end":
        sel, follow = max(0, n - 1), True
    elif key in ("scroll_up", "wheel_up", "shift_up"):
        scroll = max(0, scroll - 1)
        follow = False
    elif key in ("scroll_down", "wheel_down", "shift_down"):
        scroll = min(max(0, n - vis), scroll + 1)
        follow = False
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
    app.dirty = True
