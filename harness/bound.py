"""Budget-filling shape for one observation that exceeded the inline bound.

The old shape showed 6 head and 3 tail lines regardless of the 2048-byte
allowance, so one read of a 100-line file came back as 9 lines and the model
spent more turns re-reading. This module spends the allowance on whole lines
and appends a byte-sized `next: sed -n` command that is guaranteed to render
verbatim when followed.
"""

import hashlib

HEAD_LINES = 6
TAIL_LINES = 3
LINE_WIDTH = 120
STDERR_SEP = b"\n--stderr--\n"


def cut(line, width=LINE_WIDTH):
    text = line[:width * 4].decode("utf-8", "replace")[:width]
    return text.replace("\t", " ").rstrip()


def stderr(raw):
    if STDERR_SEP not in raw:
        return b""
    return raw.rsplit(STDERR_SEP, 1)[1]


def take(lines, first, stop, step, budget):
    """Take whole rendered lines while they fit the byte budget."""
    rows, used, i = [], 0, first
    while (i < stop if step > 0 else i > stop):
        row = cut(lines[i])
        cost = len(row.encode()) + 1
        if rows and used + cost > budget:
            break
        rows.append(row)
        used += cost
        i += step
    return rows, used, i


def next_range(lines, first, budget):
    """End (exclusive, 1-based) of a raw slice that fits the budget."""
    used, end = 0, first
    for i in range(first, len(lines)):
        used += len(lines[i]) + 1
        if used > budget and i > first:
            return end
        end = i + 1
    return end


def _small(lines):
    if len(lines) <= HEAD_LINES + TAIL_LINES + 2:
        top, bottom = lines, []
    else:
        top, bottom = lines[:HEAD_LINES], lines[-TAIL_LINES:]
    body = []
    if top:
        body += ["head:"] + [" " + cut(x) for x in top]
    if bottom:
        body += ["tail:"] + [" " + cut(x) for x in bottom]
    return body, top + bottom


def summary(raw, path, max_inline):
    lines = raw.split(b"\n")
    if lines and lines[-1] == b"":
        lines = lines[:-1]
    sha = hashlib.sha256(raw).hexdigest()[:12]
    header = f"obs bytes={len(raw)} lines={len(lines)} sha={sha} saved={path}"
    if max_inline < 512:
        body, shown = _small(lines)
        err = stderr(raw)
        if err and err not in b"\n".join(shown):
            rows = [r for r in err.rstrip(b"\n").split(b"\n") if r][-2:]
            body += ["stderr_tail:"] + [" " + cut(row) for row in rows]
        return "\n".join([header] + body)
    budget = max(400, max_inline - 520)
    top, used, next_i = take(lines, 0, len(lines), 1, int(budget * 0.68))
    bottom, _, _ = take(lines, len(lines) - 1, next_i - 1, -1, budget - used)
    bottom.reverse()
    err = stderr(raw)
    rows = []
    shown = lines[:len(top)] + (lines[len(lines) - len(bottom):] if bottom else [])
    if err and err not in b"\n".join(shown):
        rows = [r for r in err.rstrip(b"\n").split(b"\n") if r][-2:]

    def render():
        elided = len(lines) - len(top) - len(bottom)
        start = len(top) + 1
        out = [header, f"shown 1-{len(top)} of {len(lines)}" +
               (f"; elided {start}-{len(lines) - len(bottom)}" if elided else "")]
        if top:
            out += ["head:"] + [" " + x for x in top]
        if bottom:
            out += ["tail:"] + [" " + x for x in bottom]
        if rows:
            out += ["stderr_tail:"] + [" " + cut(row) for row in rows]
        if elided:
            end = next_range(lines, start - 1, budget)
            out.append(f"next: sed -n {start},{end}p {path}")
        return "\n".join(out)

    while True:
        text = render()
        if len(text.encode()) <= max_inline:
            return text
        if bottom:
            bottom.pop(0)
        elif top:
            top.pop()
        else:
            return text
