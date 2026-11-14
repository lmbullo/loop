from .rows import task_sel


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
