from .panes import fit, put, put_parts
from .prompt import display, swidth, wrap
from .rows import BLANK, DASH, SELECT, glyph, join_parts, log_parts, short_id
from . import indicator, theme


def header(data, n, vis, scroll):
    data = data or {}
    ident = short_id(data.get("id"))
    state = (data.get("state") or "?").lower()
    calls = sum(1 for entry in data.get("entries") or [] if entry.get("kind") == "call")
    tail = f"id={ident} \u00b7 {state} \u00b7 calls={calls}"
    if vis and n > vis:
        return f"logs: {scroll + 1}\u2013{min(n, scroll + vis)}/{n} \u00b7 {tail}"
    return f"logs: {tail}"


def paragraphs(text, first, rest):
    """Flow prose into display rows: first row `first` cells, later rows `rest`.

    Explicit newlines are kept as row breaks, so headings and blank lines in a
    final summary survive; tabs and control characters use `display` rules.
    """
    out = []
    width = max(1, first)
    for raw in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = display(raw).rstrip()
        if line.strip():
            out.extend(row["text"] for row in wrap(line, width))
        else:
            out.append("")
        width = max(1, rest)
    return out or [""]


def result_rows(entry, width):
    """The full final summary: a fitted head row plus every wrapped body row."""
    role = theme.state_role("complete")
    head = [(glyph("complete") + " ", role), ("result", role), (DASH, "body")]
    body = entry.get("result") or f"finish={entry.get('finish') or ''}"
    mark = swidth(BLANK)
    lines = paragraphs(body, width - mark - swidth(join_parts(head)),
                       width - mark)
    rows = [head + [(lines[0], "body")]]
    for line in lines[1:]:
        rows.append([(line, "body")])
    return rows


def entry_rows(entry, width):
    """Display rows for one entry; the final summary wraps, every call is one row."""
    if (entry or {}).get("kind") == "result":
        return result_rows(entry, width)
    return [log_parts(entry)]


def measure(items, width):
    """Flat display rows plus each entry's first row, for selection anchoring."""
    rows, first = [], {}
    for idx, entry in enumerate(items):
        first[idx] = len(rows)
        for k, parts in enumerate(entry_rows(entry, width)):
            rows.append((idx, k == 0, parts))
    return rows, first


def place(total, first, sel, scroll, vis, follow):
    """Clamp a row window and keep the selected entry anchored when following."""
    scroll = max(0, min(scroll, max(0, total - vis)))
    if not vis or not follow or not first:
        return scroll
    anchor = first.get(sel, 0)
    height = first.get(sel + 1, total) - anchor
    if anchor < scroll:
        scroll = anchor
    elif anchor >= scroll + vis:
        scroll = anchor - vis + 1
    if height > vis:
        scroll = min(anchor, max(0, total - vis))
    return max(0, min(scroll, max(0, total - vis)))


def log_block(scr, data, y, end, width, height, sel=0, scroll=0, follow=True):
    """Header plus tool-call rows and the wrapped final summary.

    Visible rows are exactly the rows the terminal has room for, so a taller
    terminal shows more calls and a shorter one shows fewer with no padding.
    A free-scrolled window (follow=False) keeps its offset even when the
    selected call is off screen. The selection stays on an entry; scroll is a
    display-row offset, so a wrapping summary can be read a screen at a time.
    """
    items = (data or {}).get("entries") or []
    room = max(0, end - y)
    vis = max(0, room - 1)
    rows, first = measure(items, width)
    total = len(rows)
    content_w = width
    if room > 0 and width > 1 and indicator.overflow(total, vis):
        content_w = width - 1
        rows, first = measure(items, content_w)
        total = len(rows)
    sel = max(0, min(int(sel or 0), max(0, len(items) - 1)))
    scroll = place(total, first, sel, int(scroll or 0), vis, follow)
    bar = indicator.bar(total, vis, scroll) if content_w < width else None
    out = {"n": total, "entries": len(items), "vis": vis, "sel": sel,
           "scroll": scroll, "follow": follow}
    if room <= 0:
        return out
    put(scr, y, 0, fit(header(data, total, vis, scroll), content_w), content_w,
        height, theme.attr("muted"))
    for k in range(min(vis, total - scroll)):
        idx, head, parts = rows[scroll + k]
        marked = idx == sel and head
        mark = SELECT if marked else BLANK
        put_parts(scr, y + 1 + k, 0, [(mark, "strong" if marked else "muted")] + parts,
                  content_w, height)
    indicator.paint(scr, y + 1, width - 1, bar, width, height)
    return out
