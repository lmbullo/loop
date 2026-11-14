"""Mouse text selection: ordered range, screen spans and plain text."""


def ordered(sel):
    """The two anchor cells in reading order; both ends are inclusive."""
    a, b = sel["a"], sel["b"]
    if (b[1], b[0]) < (a[1], a[0]):
        return b, a
    return a, b


def spans(sel, width):
    """``(row, x0, x1)`` half-open spans covering the selection."""
    if not sel:
        return []
    (x0, y0), (x1, y1) = ordered(sel)
    out = []
    for y in range(y0, y1 + 1):
        a = x0 if y == y0 else 0
        b = x1 + 1 if y == y1 else width
        a, b = max(0, min(a, width)), max(0, min(b, width))
        if b > a:
            out.append((y, a, b))
    return out


def text(sel, width, row_text):
    """The selected characters, one line per screen row, trailing space trimmed."""
    if not sel:
        return ""
    (x0, y0), (x1, y1) = ordered(sel)
    lines = []
    for y in range(y0, y1 + 1):
        line = (row_text(y) or "").ljust(width)
        a = x0 if y == y0 else 0
        b = x1 + 1 if y == y1 else width
        lines.append(line[a:b].rstrip())
    return "\n".join(lines)
