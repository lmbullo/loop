"""Budget-filling shape for one observation above the inline bound.

Read-like output keeps a contiguous head; failures spend part of the allowance
on the stderr tail; a long single line falls back to a byte offset. Every shape
ends in one executable `next:` command that resumes without losing bytes.
"""

import hashlib

HEAD_LINES = 8
TAIL_LINES = 4
LINE_WIDTH = 200
STDERR_SEP = b"\n--stderr--\n"

def clip(line, width=LINE_WIDTH):
    """Return (shown text, bytes consumed) for one rendered line."""
    head = line[:width * 4]
    truncated = len(head) < len(line)
    try:
        text = head.decode("utf-8")
        used = len(head)
    except UnicodeDecodeError as e:
        used = max(1, e.start)
        text = head[:used].decode("utf-8", "replace")
        truncated = True
    if len(text) > width and used == len(text.encode("utf-8")):
        text = text[:width]
        used = len(text.encode("utf-8"))
        truncated = True
    shown = text.replace("\t", " ").rstrip()
    return shown, (min(used, len(line)) if truncated else len(line))

def cut(line, width=LINE_WIDTH):
    return clip(line, width)[0]

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

def offsets(lines):
    pos, out = 0, []
    for line in lines:
        out.append(pos)
        pos += len(line) + 1
    return out

def cut_hint(lines, starts, blocks, path):
    """The first displayed line that was clipped, as a tail -c continuation."""
    for base, rows in blocks:
        for j in range(base, base + len(rows)):
            _, used = clip(lines[j])
            if used < len(lines[j]):
                return f"tail -c +{starts[j] + used + 1} {path}"
    return None

def take_bytes(line, budget):
    """Largest UTF-8 prefix of line that fits budget bytes."""
    n = min(len(line), max(1, budget))
    for _ in range(4):
        if n <= 0:
            break
        try:
            return line[:n].decode("utf-8"), n
        except UnicodeDecodeError:
            n -= 1
    for end in range(1, min(4, len(line)) + 1):
        try:
            return line[:end].decode("utf-8"), end
        except UnicodeDecodeError:
            pass
    return line[:1].decode("utf-8", "replace"), 1

def _small(lines, path):
    if len(lines) <= HEAD_LINES + TAIL_LINES + 2:
        top, bottom = lines, []
    else:
        top, bottom = lines[:HEAD_LINES], lines[-TAIL_LINES:]
    body = []
    if top:
        body += ["head:"] + [" " + cut(x) for x in top]
    if bottom:
        body += ["tail:"] + [" " + cut(x) for x in bottom]
    hint = cut_hint(lines, offsets(lines),
                    [(0, top), (len(lines) - len(bottom), bottom)], path)
    if hint:
        body.append("next: " + hint)
    return body, top + bottom

def _split(raw):
    if STDERR_SEP not in raw:
        return raw, b""
    return tuple(raw.rsplit(STDERR_SEP, 1))

def summary(raw, path, max_inline, mode="mixed"):
    lines = raw.split(b"\n")
    if lines and lines[-1] == b"":
        lines = lines[:-1]
    sha = hashlib.sha256(raw).hexdigest()[:12]
    header = f"obs bytes={len(raw)} lines={len(lines)} sha={sha} saved={path}"
    if len(lines) == 1 and len(lines[0]) > max_inline:
        room = max_inline - len(header.encode()) - len(b"shown 1-1 of 1\nhead:\n")
        text, used = take_bytes(lines[0], max(1, room - len(path) - 40))
        if used >= len(lines[0]):
            return "\n".join([header, "shown 1-1 of 1", "head:", text])
        return "\n".join([header, "shown 1-1 of 1", "head:", text,
                          f"next: tail -c +{used + 1} {path}"])
    if max_inline < 512:
        body, shown = _small(lines, path)
        err = stderr(raw)
        if err and err not in b"\n".join(shown):
            rows = [r for r in err.rstrip(b"\n").split(b"\n") if r][-2:]
            body += ["stderr_tail:"] + [" " + cut(row) for row in rows]
        return "\n".join([header] + body)

    stdout, err = _split(raw)
    out_lines = stdout.split(b"\n")
    if out_lines and out_lines[-1] == b"":
        out_lines = out_lines[:-1]
    starts = offsets(out_lines)
    budget = max(300, max_inline - len(header.encode()) - 90)
    erows, eused = [], 0
    if err:
        err_lines = [x for x in err.rstrip(b"\n").split(b"\n") if x]
        erows, eused, _ = take(err_lines, len(err_lines) - 1, -1, -1,
                               int(budget * 0.45))
        erows.reverse()
    read_mode = mode == "read" or not err
    top_budget = budget - eused if read_mode else int((budget - eused) * 0.62)
    top, used, next_i = take(out_lines, 0, len(out_lines), 1, max(120, top_budget))
    bottom = []
    if not read_mode:
        bottom, _, _ = take(out_lines, len(out_lines) - 1, next_i - 1, -1,
                            max(100, budget - eused - used))
        bottom.reverse()

    def render():
        hidden_from = len(top) + 1
        hidden_to = len(out_lines) - len(bottom)
        elided = hidden_to - hidden_from + 1 if hidden_to >= hidden_from else 0
        title = (f"shown 1-{len(top)} of {len(out_lines)}" +
                 (f"; elided {hidden_from}-{hidden_to}" if elided else ""))
        body = [header, title]
        if top:
            body += ["head:"] + [" " + x for x in top]
        if erows:
            body += ["stderr_tail:"] + [" " + x for x in erows]
        if bottom:
            body += ["tail:"] + [" " + x for x in bottom]
        hint = cut_hint(out_lines, starts, [(0, top)], path) if top else None
        if hint is None and elided:
            end = next_range(out_lines, hidden_from - 1, budget)
            hint = f"sed -n {hidden_from},{end}p {path}"
        if hint is None and bottom:
            hint = cut_hint(out_lines, starts,
                            [(len(out_lines) - len(bottom), bottom)], path)
        if hint:
            body.append("next: " + hint)
        return "\n".join(body)

    while True:
        text = render()
        if len(text.encode()) <= max_inline:
            return text
        if bottom:
            bottom.pop(0)
        elif erows:
            erows.pop(0)
        elif top:
            top.pop()
        else:
            return text
