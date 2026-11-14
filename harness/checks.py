import json
import os
import sys

from . import config

LIMIT = 200
USAGE = "usage: python3 run.py check <lines|tui>"


def manifest():
    with open(os.path.join(config.ROOT, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


AUDIT_KINDS = ("module", "entry", "test", "tool")


def sources():
    """Only code kinds are size-audited; contract, data and docs are not."""
    out = []
    for entry in manifest()["files"]:
        path = entry["path"]
        if entry.get("kind") not in AUDIT_KINDS:
            continue
        if path.endswith(".py"):
            out.append(path)
    return out


def line_count(path):
    try:
        with open(os.path.join(config.ROOT, path), "rb") as f:
            return len(f.read().decode("utf-8").splitlines())
    except OSError:
        return -1


def audit_lines():
    rows = [(path, line_count(path)) for path in sources()]
    rows.sort(key=lambda row: (-row[1], row[0]))
    bad = [row for row in rows if row[1] > LIMIT or row[1] < 0]
    return rows, bad


def check_tui():
    from tui.panes import fit, task_rows
    from tui.prompt import Prompt, swidth
    from tui.render import status_line
    from tui.rows import window

    bad = []

    def want(ok, msg):
        if not ok:
            bad.append(msg)

    for text, cells in (("hello", 5), ("hello", 4), ("hello", 1),
                        ("\u4f60\u597d\u4e16\u754c", 5), ("x" * 400, 37)):
        out = fit(text, cells)
        want(swidth(out) <= cells, f"fit overflow {text!r} {cells} -> {out!r}")
        if swidth(text) > cells:
            want(out.endswith("\u2026"), f"fit lost mark {text!r} {cells} -> {out!r}")
        else:
            want(out == text, f"fit changed short text {text!r} {cells} -> {out!r}")

    snap = {"current": {"id": "run", "state": "running", "turns": 3, "cost": 0.0,
                        "detail": "bad\nnews", "text": ("task line " * 80) + "\nmore"}}
    for width in (1, 7, 24, 80, 200):
        rows = task_rows(snap, width)
        want(len(rows) == 1, f"task rows {width}: {len(rows)} != 1")
        for text, _ in rows:
            want(swidth(text) <= width, f"task row {width} overflow {text!r}")
            want("\n" not in text, f"task row {width} is multiline {text!r}")
    wide = task_rows(snap, 200)[0][0]
    for field in ("id=run", "turns=3", "cost=$0.000000", "bad news"):
        want(field in wide, f"task line {field!r} missing from {wide!r}")
    want("running" not in wide, f"task line repeats the section state: {wide!r}")
    for mark in ("\u25cf", "\u00b7"):
        want(mark in wide, f"task line lost {mark!r} from {wide!r}")

    prompt = Prompt()
    prompt.set(" ".join(f"word{i}" for i in range(50)))
    narrow = prompt.layout(40)["height"]
    wide = prompt.layout(200)["height"]
    want(wide < narrow, f"prompt did not reflow 40={narrow} 200={wide}")
    for width in (39, 40, 119, 199):
        for row in prompt.layout(width)["rows"]:
            want(not row["text"].startswith(" "), f"prompt gap at {width}: {row['text']!r}")

    snap = {"daemon": {"state": "running", "detail": "", "pid": 7},
            "notice": "", "notice_at": 0}
    for width in (1, 5, 20, 80):
        left = status_line(snap, width, "prompt")
        want(swidth(left) == width, f"status width {width}")
    want("\u21b5" in status_line(snap, 80, "prompt"),
         "status line lost the enter glyph")

    want(window(6, 4, 5, 0) == (6, 4, 5, 2), "selection window does not follow sel")
    want(window(6, 4, None, 2) == (6, 4, None, 2), "selection window moved without sel")
    want(window(0, 4, 3, 9) == (0, 4, None, 0), "empty window kept a selection")

    for msg in bad:
        print("err tui " + msg, file=sys.stderr)
    return 1 if bad else 0


def main(argv):
    if argv == ["tui"]:
        return check_tui()
    if argv != ["lines"]:
        print(USAGE, file=sys.stderr)
        return 2
    rows, bad = audit_lines()
    for path, n in rows:
        print(f"{n} {path}")
    peak = max([n for _, n in rows if n >= 0] or [0])
    print(f"max={peak} limit={LIMIT} files={len(rows)} over={len(bad)}")
    for path, n in bad:
        print(f"err lines {path} {n} > {LIMIT}" if n >= 0 else f"err missing {path}", file=sys.stderr)
    return 1 if bad else 0
