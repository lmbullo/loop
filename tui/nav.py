from .rows import task_sel

SCROLL_UP = ("scroll_up", "wheel_up", "shift_up")
SCROLL_DOWN = ("scroll_down", "wheel_down", "shift_down")


def queue_sel(app):
    queue = app.snapshot()["queue"]
    if queue:
        app.qsel = min(app.qsel, len(queue) - 1)
    return queue


def sync_queue_sel(app):
    """Keep the queue cursor on the flat task selection without changing focus."""
    section, idx = task_sel(app.snapshot(), app.tsel)
    if section == "queue":
        app.qsel = idx


def toggle_focus(app):
    """Switch panes and carry one flat selection between the task row and the queue."""
    snap = app.snapshot()
    queue = snap["queue"]
    if app.focus == "queue":
        if queue:
            app.tsel = min(max(0, app.qsel), len(queue) - 1) + 1
        app.focus = "task"
    elif queue:
        section, idx = task_sel(snap, app.tsel)
        app.qsel = idx if section == "queue" else min(app.qsel, len(queue) - 1)
        app.focus = "queue"
    app.dirty = True


def _limit(total, visible):
    return max(0, int(total) - max(0, int(visible)))


def _visible(app, section):
    view = getattr(app, "tview", {}) or {}
    info = view.get(section) or {}
    if info.get("vis") is not None:
        return max(0, int(info["vis"]))
    return max(0, int(view.get("vis") or 0))


def scroll_task(app, key):
    """Move the task viewport without moving its selection."""
    snap = app.snapshot()
    section, _ = task_sel(snap, getattr(app, "tsel", 0))
    step = -1 if key in SCROLL_UP else 1
    if section == "queue" and snap.get("queue"):
        n = len(snap["queue"])
        vis = _visible(app, "queue")
        scroll = max(0, int(getattr(app, "qscroll", 0) or 0) + step)
        app.qscroll = min(scroll, _limit(n, vis))
        app.qfollow = False
    else:
        n = len(snap.get("done") or [])
        vis = _visible(app, "done")
        scroll = max(0, int(getattr(app, "tscroll", 0) or 0) + step)
        app.tscroll = min(scroll, _limit(n, vis))
        app.tfollow = False
    app.dirty = True


def scroll_queue(app, key):
    """Move the queue viewport without moving its cursor."""
    n = len(app.snapshot().get("queue") or [])
    vis = _visible(app, "queue")
    step = -1 if key in SCROLL_UP else 1
    scroll = max(0, int(getattr(app, "qscroll", 0) or 0) + step)
    app.qscroll = min(scroll, _limit(n, vis))
    app.qfollow = False
    app.dirty = True


def task_key(app, key):
    view = getattr(app, "tview", {}) or {}
    n = max(1, int(view.get("n") or 1))
    vis = max(1, int(view.get("vis") or 1))
    if key in ("up", "hist_prev"):
        app.tsel = max(0, app.tsel - 1)
    elif key in ("down", "hist_next"):
        app.tsel = min(n - 1, app.tsel + 1)
    elif key in ("left", "right"):
        toggle_focus(app)
    elif key == "page_up":
        app.tsel = max(0, app.tsel - vis)
    elif key == "page_down":
        app.tsel = min(n - 1, app.tsel + vis)
    elif key == "home":
        app.tsel = 0
    elif key == "end":
        app.tsel = n - 1
    elif key in SCROLL_UP + SCROLL_DOWN:
        scroll_task(app, key)
        return
    elif key == "ctrl_x":
        from .cancel import cancel_task
        cancel_task(app)
    elif key in ("tab", "backtab"):
        from .input import open_prompt
        open_prompt(app)
    elif key in ("enter", "newline"):
        from .loginput import open_log
        section, _ = task_sel(app.snapshot(), app.tsel)
        if section == "queue":
            app.say("queued task has no log yet")
        elif not open_log(app):
            from .input import open_prompt
            open_prompt(app)
    app.tfollow = True
    app.qfollow = True
    sync_queue_sel(app)
    app.dirty = True
