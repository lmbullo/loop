from . import theme
from .model import money
from .prompt import display

SELECT = "\u203a "          # the focused-row chevron
BLANK = "  "
SEP = " \u00b7 "            # between muted metadata fields
DASH = " \u2014 "           # between metadata and task text

GLYPH = {
    "running": "\u25cf",     # filled circle
    "complete": "\u2713",    # check
    "done": "\u2713",
    "interrupted": "\u25a0", # filled square
    "error": "\u2715",       # cross
    "corrupt": "\u2715",
    "queued": "\u25cb",      # hollow circle
    "waiting": "\u25cb",
}
FALLBACK = "\u00b7"


def glyph(state):
    return GLYPH.get((state or "").lower(), FALLBACK)


def one_line(value):
    return display(value or "").strip()


def short_id(value, keep=8, limit=12):
    text = str(value or "")
    return text if len(text) <= limit else "\u2026" + text[-keep:]


def join_parts(parts):
    return "".join(text for text, _ in parts)


def window(n, vis, sel=None, scroll=0):
    """Clamp a list window and move it so `sel` stays visible; None means no selection."""
    n = max(0, n)
    vis = max(0, vis)
    scroll = max(0, min(scroll, max(0, n - vis)))
    if not n or sel is None:
        return n, vis, None, scroll
    sel = max(0, min(sel, n - 1))
    if vis:
        if sel < scroll:
            scroll = sel
        elif sel >= scroll + vis:
            scroll = sel - vis + 1
    return n, vis, sel, scroll


def task_count(snap):
    """One flat list: the running row, then every queued item, then every done run."""
    snap = snap or {}
    return 1 + len(snap.get("queue") or []) + len(snap.get("done") or [])


def task_sel(snap, sel):
    """Map a flat task selection to (section, index); the running row is always 0."""
    snap = snap or {}
    queue = snap.get("queue") or []
    n = task_count(snap)
    sel = max(0, min(int(sel or 0), n - 1))
    if sel == 0:
        return "running", 0
    if sel <= len(queue):
        return "queue", sel - 1
    return "done", sel - 1 - len(queue)


def field_header(label, total=None, start=0, end=None):
    if total is None or total == 0:
        return label
    if end is not None and (start > 0 or end < total):
        return f"{label} {start + 1}\u2013{end}/{total}"
    return f"{label} {total}"


def task_role(snap):
    return theme.state_role(((snap or {}).get("current") or {}).get("state"))


def task_parts(snap):
    cur = snap["current"]
    if cur is None:
        return [("\u25cb ", "muted"), ("idle", "strong"),
                (SEP + "type a task and press ", "muted"), ("\u21b5", "strong")]
    state = (cur.get("state") or "running").lower()
    role = theme.state_role(state)
    parts = [(glyph(state) + " ", role),
             (f"id={short_id(cur.get('id'))}", "muted"),
             (SEP + f"turns={cur.get('turns') or 0}", "muted"),
             (SEP + f"cost={money(cur.get('cost'))}", "muted")]
    if cur.get("finish"):
        parts.append((SEP + f"finish={one_line(cur['finish'])}", "muted"))
    if cur.get("detail"):
        parts.append((SEP + one_line(cur["detail"]), "warn"))
    text = one_line(cur.get("text"))
    if text:
        parts.append((DASH + text, "strong"))
    return parts


def queue_parts(item, idw=7, selected=False):
    ident = str(item.get("id") or "")
    ident = f"{ident[:idw]:<{idw}}"
    text = one_line(item.get("text"))
    return [("\u25cb ", "muted"), (ident, "muted"),
            ("  " + text, "strong" if selected else "body")]


def log_parts(entry):
    """One fitted line per log entry: a tool call, then the final summary."""
    entry = entry or {}
    kind = entry.get("kind")
    if kind == "call":
        parts = [("\u25b8 ", "muted"), (f"t{entry.get('turn') or 0} ", "muted"),
                 (one_line(entry.get("name")) or "?", "strong")]
        args = one_line(entry.get("args"))
        if args:
            parts.append((DASH + args, "body"))
        obs = one_line(entry.get("obs"))
        if obs:
            parts.append((" \u2192 " + obs, "err" if entry.get("failed") else "muted"))
        return parts
    if kind == "result":
        role = theme.state_role("complete")
        text = one_line(entry.get("result")) or f"finish={one_line(entry.get('finish'))}"
        return [(glyph("complete") + " ", role), ("result", role), (DASH + text, "body")]
    if kind == "interrupted":
        return [(glyph("interrupted") + " ", "warn"), ("interrupted", "warn"),
                (DASH + (one_line(entry.get("reason")) or "no terminal event"), "body")]
    if kind == "error":
        text = one_line(entry.get("text")) or f"finish={one_line(entry.get('finish'))}"
        return [(glyph("error") + " ", "err"), ("error", "err"), (DASH + text, "body")]
    if kind == "torn":
        return [(glyph("interrupted") + " ", "warn"), (one_line(entry.get("text")), "warn")]
    return [(glyph("queued") + " ", "muted"),
            (one_line(entry.get("text")) or "pending", "muted")]


def done_parts(item):
    state = (item.get("state") or "complete").lower()
    role = theme.state_role(state)
    parts = [(glyph(state) + " ", role)]
    parts.append((f"id={short_id(item.get('id'))}", "muted"))
    parts.append((SEP + f"turns={item.get('turns') or 0}", "muted"))
    parts.append((SEP + f"cost={money(item.get('cost'))}", "muted"))
    finish = one_line(item.get("finish"))
    if finish and state not in ("complete", "done"):
        parts.append((SEP + f"finish={finish}", "muted"))
    detail = one_line(item.get("detail"))
    if detail:
        parts.append((SEP + detail, role if state not in ("complete", "done") else "muted"))
    text = one_line(item.get("text"))
    if text:
        parts.append((DASH + text, "body"))
    return parts
