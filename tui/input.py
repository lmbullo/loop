from .loginput import close_log, log_key, open_log
from .nav import queue_sel, sync_queue_sel, toggle_focus
from .rows import task_sel


def prompt_return(app):
    """The view the prompt overlays: a log stays open, a queue keeps its cursor."""
    prev = getattr(app, "prompt_from", "task")
    if prev == "log" and getattr(app, "log", None) is not None:
        return "log"
    if prev == "queue":
        return "queue" if app.snapshot().get("queue") else "task"
    return "task"


def open_prompt(app, text=""):
    if app.focus != "prompt":
        keep_log = app.focus == "log" and getattr(app, "log", None) is not None
        app.prompt_from = "log" if keep_log else (
            "task" if app.focus == "log" else app.focus)
    keep_log = app.focus == "log" or (
        app.focus == "prompt" and getattr(app, "prompt_from", "") == "log")
    if not keep_log:
        close_log(app)
    app.focus = "prompt"
    if text:
        app.prompt.insert(text)
    app.dirty = True


def close_prompt(app, clear=True):
    if clear:
        app.prompt.clear()
    app.focus = prompt_return(app)
    app.dirty = True


def submit(app):
    text = app.prompt.text
    if not text.strip():
        app.say("empty task ignored")
        close_prompt(app)
        return
    app.worker.enqueue(text)
    app.prompt.remember()
    app.prompt.clear()
    app.focus = "task"
    app.tsel = app.tscroll = 0
    app.dirty = True


def drop(app):
    snap = app.snapshot()
    queue = snap["queue"]
    if not queue:
        return
    app.qsel = min(app.qsel, len(queue) - 1)
    item = queue[app.qsel]
    app.worker.drop(item["id"])
    snap = app.snapshot()
    app.qsel = max(0, min(app.qsel, len(snap["queue"]) - 1))
    if not snap["queue"]:
        app.focus = "task"


def queue_key(app, key):
    queue = queue_sel(app)
    if key in ("up", "hist_prev"):
        app.qsel = max(0, app.qsel - 1)
    elif key in ("down", "hist_next"):
        app.qsel = min(max(0, len(queue) - 1), app.qsel + 1)
    elif key == "shift_up" and queue:
        app.worker.move(queue[app.qsel]["id"], -1)
        app.qsel = max(0, app.qsel - 1)
    elif key == "shift_down" and queue:
        app.worker.move(queue[app.qsel]["id"], 1)
        app.qsel = min(len(queue) - 1, app.qsel + 1)
    elif key in ("left", "right"):
        toggle_focus(app)
    elif key == "home":
        app.qsel = 0
    elif key == "end":
        app.qsel = max(0, len(queue) - 1)
    elif key in ("delete", "backspace"):
        drop(app)
    elif key in ("enter", "newline", "tab", "backtab"):
        open_prompt(app)
    elif key == "esc":
        app.focus = "task"
    app.dirty = True


def prompt_key(app, key):
    if key == "enter":
        submit(app)
        return
    if key == "newline":
        app.prompt.insert("\n")
        app.dirty = True
        return
    if key in ("tab", "backtab"):
        close_prompt(app, clear=False)
        return
    width = app.content_width()
    height = app.layout["height"] if app.layout else 10
    moves = {
        "backspace": app.prompt.backspace, "delete": app.prompt.delete,
        "left": app.prompt.left, "right": app.prompt.right,
        "home": lambda: app.prompt.home(width), "end": lambda: app.prompt.end(width),
        "word_left": app.prompt.word_left, "word_right": app.prompt.word_right,
        "word_back": app.prompt.word_back, "word_next": app.prompt.word_next,
        "kill_start": app.prompt.kill_start, "kill_end": app.prompt.kill_end,
        "hist_prev": app.prompt.prev, "hist_next": app.prompt.next,
        "up": lambda: app.prompt.vertical(-1, width),
        "down": lambda: app.prompt.vertical(1, width),
        "page_up": lambda: app.prompt.page(-1, width, height),
        "page_down": lambda: app.prompt.page(1, width, height),
    }
    if key in moves:
        moves[key]()
    app.dirty = True


def task_key(app, key):
    n = max(1, app.tview.get("n") or 1)
    vis = max(1, app.tview.get("vis") or 1)
    if key in ("up", "hist_prev", "shift_up"):
        app.tsel = max(0, app.tsel - 1)
    elif key in ("down", "hist_next", "shift_down"):
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
    elif key in ("tab", "backtab"):
        open_prompt(app)
    elif key in ("enter", "newline"):
        section, _ = task_sel(app.snapshot(), app.tsel)
        if section == "queue":
            app.say("queued task has no log yet")
        elif not open_log(app):
            open_prompt(app)
    sync_queue_sel(app)
    app.dirty = True


def handle(app, ev):
    kind, value = ev
    if kind == "paste":
        open_prompt(app, value)
        return
    if kind == "text":
        open_prompt(app, value)
        return
    if value == "ctrl_q":
        app.quit = True
    elif value == "ctrl_c":
        app.prompt.clear()
        app.say("input cleared")
    elif value == "redraw":
        app.scr.clear()
        app.dirty = True
    elif value == "retry":
        app.worker.retry()
        app.say("daemon retry queued")
    elif value == "esc":
        if app.focus == "prompt":
            close_prompt(app)
        elif app.focus == "log":
            close_log(app)
        else:
            app.focus = "task"
            app.dirty = True
    elif value == "focus_queue":
        if queue_sel(app) and app.focus != "queue":
            app.focus = "queue"
        else:
            app.focus = "task"
        app.dirty = True
    elif value in ("tab", "backtab") and app.focus in ("task", "queue", "log"):
        open_prompt(app)
    elif app.focus == "queue":
        queue_key(app, value)
    elif app.focus == "prompt":
        prompt_key(app, value)
    elif app.focus == "log":
        log_key(app, value)
    else:
        task_key(app, value)
