"""Screen-cell highlight geometry for the frame buffer (no curses calls)."""


def spans(raw, width, height):
    """Clamp and merge ``(row, x0, x1)`` reverse-video spans."""
    rows = {}
    for y, x0, x1 in raw or []:
        x0, x1 = max(0, x0), min(width, x1)
        if x1 > x0 and 0 <= y < height:
            rows.setdefault(y, []).append((x0, x1))
    out = []
    for y, ranges in rows.items():
        ranges.sort()
        a, b = ranges[0]
        for c, d in ranges[1:]:
            if c <= b:
                b = max(b, d)
            else:
                out.append((y, a, b))
                a, b = c, d
        out.append((y, a, b))
    return sorted(out)


def row_marks(marks, y):
    return [(x0, x1) for row, x0, x1 in marks if row == y]


def pieces(x, text, attr, marks, mark_attr=0):
    """Split one draw op at highlight boundaries, OR-ing ``mark_attr`` inside."""
    out, i = [], 0
    while i < len(text):
        col = x + i
        span = next(((a, b) for a, b in marks if a <= col < b), None)
        j = i + 1
        if span:
            while j < len(text) and span[0] <= x + j < span[1]:
                j += 1
            out.append((col, text[i:j], attr | mark_attr))
        else:
            while j < len(text) and not any(a <= x + j < b for a, b in marks):
                j += 1
            out.append((col, text[i:j], attr))
        i = j
    return out


def row_text(ops, y, width):
    """The characters committed on one row, spaces included."""
    cells = [" "] * max(0, width)
    for x, text, _ in ops:
        for i, ch in enumerate(text):
            if 0 <= x + i < len(cells):
                cells[x + i] = ch
    return "".join(cells)
