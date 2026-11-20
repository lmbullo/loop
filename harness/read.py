"""Path-addressed text: numbered lines, ranges, patterns and byte offsets.

`exec` reaches a file through shell quoting and, past the inline bound, through
a second `sed` turn. A numbered read makes the same bytes addressable: the
caller sees `shown 1-140 of 200` and resumes with the printed `next:` call, so a
200-line module is one call and a follow-up never re-derives a line range.

One call answers the three common probes: `find` locates a pattern with context
(no grep-then-sed pair), `start`/`end` take an exact range, `offset` pages a
single long line by byte.
"""

import os
import re

from . import bound, config, observe

MATCH_CAP = 12


def _split(data):
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines = lines[:-1]
    return lines


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _range(a, total):
    """(first, last) 1-based inclusive from start/end, clamped to the file."""
    start = min(max(1, _int(a.get("start"), 1)), total)
    end = _int(a.get("end"), 0)
    end = total if end <= 0 else min(end, total)
    return start, max(start, end)


def _hits(a, lines):
    """(match count, merged ranges) for a find pattern plus context lines."""
    pat = a.get("find")
    try:
        rx = re.compile(pat)
    except (re.error, TypeError):
        rx = None
    ctx = max(0, _int(a.get("ctx"), 0))
    total, hits, groups = len(lines), 0, []
    for i, line in enumerate(lines, 1):
        text = line.decode("utf-8", "replace")
        if not (rx.search(text) if rx is not None else isinstance(pat, str) and pat in text):
            continue
        hits += 1
        lo, hi = max(1, i - ctx), min(total, i + ctx)
        if groups and lo <= groups[-1][1] + 1:
            groups[-1] = (groups[-1][0], max(groups[-1][1], hi))
        elif len(groups) < MATCH_CAP:
            groups.append((lo, hi))
    return hits, groups


def _quote(path):
    return f'"{path}"' if " " in path or '"' in path else path


def _next(path, start=None, offset=None):
    if offset is not None:
        return f"read(path={_quote(path)}, offset={offset})"
    return f"read(path={_quote(path)}, start={start})"


def _render(path_arg, lines, groups, budget):
    """Numbered rows that fit the budget plus one executable continuation."""
    total = len(lines)
    width = len(str(total))
    head = f"obs {path_arg} lines={total} bytes={len(b''.join(lines)) + total}"
    rows, nums, used, nxt = [], [], len(head.encode()) + 40, None
    for lo, hi in groups:
        for n in range(lo, hi + 1):
            row = f"{n:>{width}}| {bound.cut(lines[n - 1])}"
            cost = len(row.encode()) + 1
            if rows and used + cost > budget:
                nxt = n
                break
            rows.append(row)
            nums.append(n)
            used += cost
        if nxt is not None:
            break
    spans = []
    for n in nums:
        if spans and n == spans[-1][1] + 1:
            spans[-1] = (spans[-1][0], n)
        else:
            spans.append((n, n))
    shown = ",".join(f"{a}-{b}" if a != b else str(a) for a, b in spans)
    body = [head, f"shown {shown} of {total}"] + rows
    if nxt is not None:
        body.append("next: " + _next(path_arg, start=nxt))
    return "\n".join(body)


def _dir(path_arg, path, budget):
    try:
        names = sorted(os.listdir(path))
    except OSError as e:
        return f"err read {path_arg}: {e.strerror or e}"
    rows, used = [], len(path_arg) + 20
    for name in names:
        full = os.path.join(path, name)
        row = name + ("/" if os.path.isdir(full) else "")
        if rows and used + len(row) + 1 > budget:
            return (f"obs {path_arg} kind=dir entries={len(names)}\n" + " ".join(rows)
                    + f"\nnext: read(path={_quote(path_arg)}, start={len(rows) + 1})")
        rows.append(row)
        used += len(row) + 1
    return f"obs {path_arg} kind=dir entries={len(names)}\n" + " ".join(rows)


def _offset(path_arg, data, offset, budget):
    """Page one long line by byte offset, so a cut line resumes without loss."""
    start = min(max(0, offset), len(data))
    room = max(64, budget - len(path_arg) - 80)
    text, used = bound.take_bytes(data[start:], room)
    head = f"obs {path_arg} bytes={len(data)} offset={start}"
    body = [head, text]
    if start + used < len(data):
        body.append("next: " + _next(path_arg, offset=start + used))
    return "\n".join(body)


def do_read(a, sandbox=None, max_inline=None):
    path_arg = a.get("path")
    if not isinstance(path_arg, str) or not path_arg:
        return ('err bad_args read requires path:str; optional start, end, find, '
                'ctx, offset — or use exec for commands')
    path = config.resolve(path_arg, sandbox)
    budget = config.read_inline() if max_inline is None else max_inline
    if os.path.isdir(path):
        return _dir(path_arg, path, budget)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        return f"err read {path_arg}: {e.strerror or e}"
    if observe.is_binary(data):
        return f"kind=binary {path_arg} " + observe.digest(data)
    if a.get("offset") is not None:
        return _offset(path_arg, data, _int(a.get("offset"), 0), budget)
    lines = _split(data)
    total = len(lines)
    if total == 0:
        return f"obs {path_arg} lines=0 bytes=0\n(empty)"
    if isinstance(a.get("find"), str):
        hits, groups = _hits(a, lines)
        if not hits:
            return (f"obs {path_arg} lines={total} matches=0 "
                    f"hint=check find, or pass start/end")
        head = (f"matches={hits}" if len(groups) < MATCH_CAP
                else f"matches={hits} groups>{len(groups)}")
        return head + "\n" + _render(path_arg, lines, groups, budget)
    start, end = _range(a, total)
    return _render(path_arg, lines, [(start, end)], budget)
