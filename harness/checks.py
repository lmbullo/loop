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
    want(window(6, 4, 0, 2, False) == (6, 4, 0, 2),
         "free-scroll window moved back to the selection")

    from tui.logview import entry_rows, log_block
    from tui.rows import join_parts, log_parts

    class LogScreen:
        def __init__(self):
            self.rows = {}

        def addstr(self, y, x, text, at=0):
            self.rows[y] = self.rows.get(y, "") + text

    log_data = {"id": "run", "state": "complete", "entries": [
        {"kind": "call", "turn": 1, "name": "exec", "args": "x" * 400,
         "obs": "ok " * 200, "failed": False},
        {"kind": "result", "result": "y" * 400, "finish": "done"}]}
    want("\n" not in join_parts(log_parts(log_data["entries"][0])),
         "log call row is multiline")
    long = {"kind": "result", "finish": "done",
            "result": ("summary " * 60) + "\n\n" + "LAST-PARAGRAPH"}
    for width in (24, 80):
        rows = entry_rows(long, width)
        want(len(rows) > 1, f"summary did not wrap at {width}")
        body = " ".join(join_parts(parts) for parts in rows)
        want("LAST-PARAGRAPH" in body, f"summary lost its tail at {width}")
        for parts in rows:
            want(swidth(join_parts(parts)) <= width,
                 f"summary row {width} overflow {join_parts(parts)!r}")
    for width in (1, 7, 24, 80):
        screen = LogScreen()
        info = log_block(screen, log_data, 0, 12, width, 13)
        want(info["vis"] == 11, f"log window {width}: vis {info['vis']} != 11")
        for row in screen.rows.values():
            want(swidth(row) <= width, f"log row {width} overflow {row!r}")
    entries = [{"kind": "call", "turn": 1, "name": "exec", "args": "a",
                "obs": "", "failed": False} for _ in range(20)]
    entries.append({"kind": "result", "result": "ok", "finish": "done"})
    log_data = {"id": "run", "state": "complete", "entries": entries}
    short, tall = LogScreen(), LogScreen()
    log_block(short, log_data, 0, 6, 40, 7)
    log_block(tall, log_data, 0, 40, 40, 41)
    want(len(short.rows) == 6, f"short log drew {len(short.rows)} rows")
    want(len(tall.rows) == 22, f"tall log drew {len(tall.rows)} rows")
    free = LogScreen()
    info = log_block(free, log_data, 0, 8, 40, 9, sel=0, scroll=5,
                     follow=False)
    want((info["sel"], info["scroll"], info["follow"]) == (0, 5, False),
         "free-scroll log moved its selection or offset")

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
