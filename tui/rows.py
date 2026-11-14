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


def field_header(label, total=None, start=0, end=None):
    if total is None or total == 0:
        return label
    if end is not None and end < total:
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
             (state, role),
             (SEP + f"id={short_id(cur.get('id'))}", "muted"),
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
