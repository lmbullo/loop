from .panes import fit, put, put_parts
from .rows import BLANK, SELECT, log_parts, short_id, window
from . import theme


def header(data, n, vis, scroll):
    data = data or {}
    ident = short_id(data.get("id"))
    state = (data.get("state") or "?").lower()
    calls = sum(1 for entry in data.get("entries") or [] if entry.get("kind") == "call")
    tail = f"id={ident} \u00b7 {state} \u00b7 calls={calls}"
    if vis and n > vis:
        return f"logs: {scroll + 1}\u2013{min(n, scroll + vis)}/{n} \u00b7 {tail}"
    return f"logs: {tail}"


def log_block(scr, data, y, end, width, height, sel=0, scroll=0):
    """One line per tool call plus the final summary; the window fills the body.

    Visible rows are exactly the rows the terminal has room for, so a taller
    terminal shows more calls and a shorter one shows fewer with no padding.
    """
    items = (data or {}).get("entries") or []
    total = max(0, end - y)
    n, vis, sel, scroll = window(len(items), max(0, total - 1), sel, scroll)
    out = {"n": n, "vis": vis, "sel": sel, "scroll": scroll}
    if total <= 0:
        return out
    put(scr, y, 0, fit(header(data, n, vis, scroll), width), width, height,
        theme.attr("muted"))
    for k in range(min(vis, n - scroll)):
        idx = scroll + k
        marked = idx == sel
        mark = SELECT if marked else BLANK
        parts = [(mark, "strong" if marked else "muted")] + log_parts(items[idx])
        put_parts(scr, y + 1 + k, 0, parts, width, height)
    return out
