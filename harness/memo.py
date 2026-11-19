"""Deterministic checkpoint digest for compacted turns.

Compaction is a pure function of record bytes: the state is merged from the
previous checkpoint and the turns being dropped, then rendered to a bounded
text block. No model call, no clock and no process state, so a resumed run
rebuilds the same digest and the same cached prefix.
"""

import json
import re

MAX_DIGEST = 6000
MAX_FILES = 40
MAX_CMDS = 16
MAX_FAILS = 12

WRITE_RE = re.compile(r"^ok wrote \d+B (\S+)")
EDIT_RE = re.compile(r"^ok -\d+ \+\d+ (\S+)")


def args_of(call):
    raw = call.get("args")
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        value = json.loads(raw, strict=False)
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def parse_state(raw):
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _first(obs):
    return (obs or "").split("\n", 1)[0][:140]


def _failed(obs):
    text = obs or ""
    if text.startswith("err ") or text.startswith("exit=TIMEOUT"):
        return True
    if text.startswith("exit="):
        try:
            return int(text[5:].split(None, 1)[0]) != 0
        except (ValueError, IndexError):
            return True
    return False


def _path(call, name):
    arg = args_of(call)
    path = arg.get("path")
    if isinstance(path, str) and path:
        return path
    obs = call.get("observation") or ""
    match = (WRITE_RE if name == "write" else EDIT_RE).match(obs)
    return match.group(1) if match else ""


def _size(call, name):
    arg = args_of(call)
    if name == "write":
        if isinstance(arg.get("bytes"), int):
            return arg["bytes"]
        data = arg.get("data")
        return len(data.encode("utf-8")) if isinstance(data, str) else 0
    old = arg.get("old_bytes")
    new = arg.get("new_bytes")
    if isinstance(old, int) and isinstance(new, int):
        return (old, new)
    old, new = arg.get("old"), arg.get("new")
    return (len(old.encode()) if isinstance(old, str) else 0,
            len(new.encode()) if isinstance(new, str) else 0)


def _cmd(call):
    arg = args_of(call)
    argv = arg.get("argv", arg.get("cmd"))
    if isinstance(argv, str):
        text = argv
    elif isinstance(argv, list):
        text = " ".join(str(x) for x in argv)
    else:
        text = ""
    return text[:120] or "?"


def _trim(state):
    files = state.get("files") or {}
    if len(files) > MAX_FILES:
        keep = sorted(files.items(), key=lambda kv: kv[1][1], reverse=True)[:MAX_FILES]
        state["files"] = dict(keep)
    state["cmds"] = list(state.get("cmds") or [])[-MAX_CMDS:]
    state["fails"] = list(state.get("fails") or [])[-MAX_FAILS:]
    return state


def collect(events, base, upto, prior=None):
    """Merge turns in (base, upto] into a cumulative checkpoint state."""
    old = prior or {}
    state = {"after": int(upto), "count": int(old.get("count") or 0),
             "files": dict(old.get("files") or {}),
             "cmds": list(old.get("cmds") or []),
             "fails": list(old.get("fails") or [])}
    for ev in events:
        if ev.get("type") != "turn":
            continue
        turn = int((ev.get("data") or {}).get("turn") or 0)
        if not (base < turn <= upto):
            continue
        state["count"] += 1
        for call in ev["data"].get("calls") or []:
            name = call.get("name") or "?"
            obs = call.get("observation") or ""
            if name in ("write", "edit") and obs.startswith("ok"):
                path = _path(call, name)
                if path:
                    state["files"][path] = [name, turn, _size(call, name)]
            if name == "exec":
                cmd = _cmd(call)
                status = _first(obs)
                state["cmds"].append([turn, cmd, status])
                if _failed(obs):
                    state["fails"].append([turn, f"{cmd} -> {status}"])
            elif _failed(obs):
                state["fails"].append([turn, f"{name} {_first(obs)}"])
    return _trim(state)


def render(state, limit=MAX_DIGEST):
    def build(st):
        files = sorted((st.get("files") or {}).items(),
                       key=lambda kv: kv[1][1], reverse=True)
        lines = [f"[loop checkpoint] compacted={st.get('count', 0)} "
                 f"through=T{st.get('after', 0)}",
                 "note: summary only; read mutable state before continuing a sequence"]
        if files:
            lines.append("files: " + " ".join(
                f"{path}({item[0]}@{item[1]}" + _measure(item[2]) + ")" for path, item in files[:MAX_FILES]))
        if st.get("fails"):
            lines.append("fails:")
            lines.extend(" " + _one(item) for item in st["fails"][-MAX_FAILS:])
        if st.get("cmds"):
            lines.append("cmds:")
            lines.extend(" " + _one(item) for item in st["cmds"][-MAX_CMDS:])
        return "\n".join(lines)

    st = {"after": state.get("after", 0), "count": state.get("count", 0),
          "files": dict(state.get("files") or {}),
          "cmds": list(state.get("cmds") or []),
          "fails": list(state.get("fails") or [])}
    text = build(st)
    while len(text.encode("utf-8")) > limit and (st["cmds"] or st["fails"] or st["files"]):
        if st["cmds"]:
            st["cmds"] = st["cmds"][1:]
        elif st["fails"]:
            st["fails"] = st["fails"][1:]
        else:
            oldest = sorted(st["files"].items(), key=lambda kv: kv[1][1])
            st["files"].pop(oldest[0][0], None)
        text = build(st)
    return text[:limit]


def _measure(size):
    if isinstance(size, int) and size:
        return f",{size}B"
    if isinstance(size, (list, tuple)) and len(size) == 2:
        return f",-{size[0]}+{size[1]}"
    return ""


def _one(item):
    if isinstance(item, list) and len(item) == 3:
        return f"T{item[0]} {item[1]} -> {item[2]}"[:180]
    if isinstance(item, list) and len(item) == 2:
        return f"T{item[0]} {item[1]}"[:180]
    return str(item)[:180]


def build(events, base, upto, prior=None, limit=MAX_DIGEST):
    state = collect(events, base, upto, prior)
    return state, render(state, limit)
