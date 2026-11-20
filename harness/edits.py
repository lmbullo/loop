"""Atomic multi-hunk edit: one call replaces N unique spans.

A batch is all-or-nothing: every hunk must match, hunks apply in order to the
evolving bytes, and the file is written once at the end. The observation carries
the match lines and a numbered window, so a caller verifies without a read turn.

A failure is a report, not an exception: it names the hunk index, the match
count, the lines that did match and the one-flag fix (`replace_all`), so the
retry never has to re-read the file.
"""

import os

from . import config

HINT_ALL = "hint=extend old with adjacent unique text, or pass replace_all=true"
HINT_CRLF = "hint=file uses CRLF; include \\r\\n in old"


def _line_numbers(data, needle, limit=8):
    out, start = [], 0
    while len(out) < limit:
        i = data.find(needle, start)
        if i < 0:
            break
        n = data.count(b"\n", 0, i) + 1
        if n not in out:
            out.append(n)
        start = i + 1
    return out


def _whitespace_near(data, old):
    """Line where the stripped old lines occur in order, if any."""
    pos, first = 0, None
    for part in old.splitlines():
        part = part.strip()
        if not part:
            continue
        i = data.find(part, pos)
        if i < 0:
            return None
        if first is None:
            first = data.count(b"\n", 0, i) + 1
        pos = i + len(part)
    return first


def edit_error(data, old, path):
    """Explain a non-unique match without spending a read turn."""
    count = data.count(old)
    if count == 1:
        return None
    out = [f"err match={count} expected=1 {path}"]
    if count == 0 and b"\r\n" in data and b"\r" not in old:
        crlf = old.replace(b"\n", b"\r\n")
        if data.count(crlf) == 1:
            out.append(HINT_CRLF)
            return " ".join(out)
    near = _whitespace_near(data, old) if count == 0 else None
    if near is not None:
        out.append(f"near={near} hint=check whitespace/indent")
        return " ".join(out)
    lines = _line_numbers(data, old) if count else []
    if not lines and count == 0:
        for part in old.splitlines():
            part = part.strip()
            if part:
                lines = _line_numbers(data, part, 2)
                if lines:
                    out.append("hint=old text differs from this line")
                    break
    if lines:
        out.append("lines=" + ",".join(str(n) for n in lines))
    if not lines and count == 0:
        out.append("hint=old not found; read the file and copy its exact bytes")
    if count > 1:
        out.append(HINT_ALL)
    return " ".join(out)


def hunks(a):
    """(pairs, replace_all, err) from old+new or the edits[] batch form."""
    batch = a.get("edits")
    if batch is not None:
        if not isinstance(batch, list) or not batch:
            return None, False, "err bad_args edit edits must be a non-empty list of {old,new}"
        pairs = []
        for i, h in enumerate(batch):
            if (not isinstance(h, dict) or not isinstance(h.get("old"), str)
                    or not isinstance(h.get("new"), str)):
                return None, False, f"err bad_args edit edits[{i}] needs old:str and new:str"
            pairs.append((h["old"], h["new"]))
    elif isinstance(a.get("old"), str) and isinstance(a.get("new"), str):
        pairs = [(a["old"], a["new"])]
    elif isinstance(a.get("find"), str) and isinstance(a.get("replace"), str):
        pairs = [(a["find"], a["replace"])]
    else:
        return None, False, ("err bad_args edit needs path, then old:str + new:str, "
                             "or edits:[{old,new}], or find:str + replace:str")
    if any(old == "" for old, _ in pairs):
        return None, False, "err bad_args edit old must not be empty"
    return pairs, a.get("replace_all") is True, None


def _window(data, line, span=1):
    """Numbered lines around one match line, so the caller need not re-read."""
    rows = data.split(b"\n")
    lo, hi = max(0, line - 1 - span), min(len(rows), line + span)
    return "\n".join(f"{i + 1}: {rows[i].decode('utf-8', 'replace')}" for i in range(lo, hi))


def apply(a, sandbox=None):
    pairs, replace_all, err = hunks(a)
    if err is not None:
        return err
    path = config.resolve(a["path"], sandbox)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        hint = "" if e.errno != 2 else f" hint=create it with write(path={a['path']}, data=...)"
        return f"err {type(e).__name__}: {e.strerror or e} {a['path']}{hint}"
    cur, minus, plus, marks = data, 0, 0, []
    for i, (old, new) in enumerate(pairs):
        ob, nb = old.encode(), new.encode()
        count = cur.count(ob)
        if count == 0 or (count > 1 and not replace_all):
            text = edit_error(cur, ob, a["path"])
            return f"hunk={i + 1}/{len(pairs)} " + text if len(pairs) > 1 else text
        at = cur.find(ob)
        marks.append(cur.count(b"\n", 0, at) + 1)
        cur = cur.replace(ob, nb) if replace_all else cur.replace(ob, nb, 1)
        minus += len(ob) * (count if replace_all else 1)
        plus += len(nb) * (count if replace_all else 1)
    try:
        with open(path, "wb") as f:
            f.write(cur)
    except OSError as e:
        return f"err {type(e).__name__}: {e}"
    head = f"ok -{minus} +{plus} {a['path']}"
    if len(pairs) > 1:
        head = f"ok edits={len(pairs)} -{minus} +{plus} {a['path']}"
    if replace_all:
        head += " all=true"
    return f"{head} lines={','.join(str(n) for n in marks)}\n" + _window(cur, marks[0])
