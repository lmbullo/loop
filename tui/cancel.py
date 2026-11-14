from .nav import queue_sel
from .rows import task_sel


def cancel_running(app):
    current = app.snapshot().get("current")
    if not current or not current.get("id"):
        app.say("nothing to cancel")
        return
    app.worker.cancel(current["id"])


def cancel_task(app):
    """Cancel the flat task selection: drop a queued row, signal a live run."""
    snap = app.snapshot()
    section, idx = task_sel(snap, app.tsel)
    if section == "running":
        cancel_running(app)
    elif section == "queue":
        queue = snap.get("queue") or []
        if 0 <= idx < len(queue):
            app.worker.cancel(queue[idx].get("id"))
    else:
        app.say("run already finished")


def cancel_queue(app):
    queue = queue_sel(app)
    if not queue:
        app.say("nothing to cancel")
        return
    app.qsel = min(app.qsel, len(queue) - 1)
    app.worker.cancel(queue[app.qsel].get("id"))
