"""Pure per-run log projection for the TUI: tool calls plus the final summary.

The record stays the source of truth; this module only selects the events the
log view shows (one entry per tool call, then one terminal entry). It reads no
clock, network, daemon or cwd, so it can be called from the TUI poll loop.
"""

import json

from . import record, recread

ARGS_LIMIT = 240
OBS_LIMIT = 160
TEXT_LIMIT = 240
TAIL_KINDS = ("end", "interrupted")


def one(value, limit):
    text = "" if value is None else str(value)
    text = text.replace("\r", "\n").replace("\t", " ")
    return " ".join(text.split())[:limit]


def _args(message, call_id):
    for call in (message or {}).get("tool_calls") or []:
        if call.get("id") != call_id:
            continue
        raw = (call.get("function") or {}).get("arguments") or "{}"
        try:
            return one(record.canonical(json.loads(raw)), ARGS_LIMIT)
        except (ValueError, TypeError):
            return one(raw, ARGS_LIMIT)
    return ""


def calls(events):
    """One entry per recorded tool call, in sequence order."""
    out = []
    for ev in events:
        if ev["type"] != "turn":
            continue
        data = ev["data"]
        for call in data.get("calls") or []:
            obs = one(call.get("observation"), OBS_LIMIT)
            out.append({"kind": "call", "turn": int(data.get("turn") or 0),
                        "name": one(call.get("name"), 40) or "?",
                        "args": _args(data.get("message"), call.get("id")),
                        "obs": obs, "failed": obs.startswith("err ")})
    return out


def tail(events, state, torn=0):
    """The terminal entry: final result, interruption, error or a pending row."""
    end = None
    for ev in events:
        if ev["type"] == "end":
            end = ev
    if end is not None:
        data = end["data"]
        return [{"kind": "result", "result": one(data.get("result"), TEXT_LIMIT),
                 "finish": one(data.get("finish"), 80)}]
    last = events[-1] if events else None
    if last is not None and last["type"] == "interrupted":
        reason = one(last["data"].get("reason"), TEXT_LIMIT) or "interrupted"
        return [{"kind": "interrupted", "reason": reason}]
    if last is not None and last["type"] == "error":
        data = last["data"]
        return [{"kind": "error", "finish": one(data.get("finish"), 80),
                 "text": one(data.get("text"), TEXT_LIMIT)}]
    out = [{"kind": "pending",
            "text": "summary pending" if events else "no events yet"}]
    if torn:
        out.append({"kind": "torn", "text": f"torn tail bytes={int(torn)}"})
    return out


def entries(events, torn=0):
    return calls(events) + tail(events, recread.state(events), torn)


def load(run_id):
    """Read one record and return the log view payload; never raises on bytes."""
    try:
        rec = recread.read(run_id)
    except record.Corrupt as e:
        return {"id": run_id, "state": "corrupt", "turns": 0, "terminal": True,
                "entries": [{"kind": "error", "text": one(e, TEXT_LIMIT)}]}
    events = rec["events"]
    state = recread.state(events)
    last = events[-1]["type"] if events else ""
    return {"id": run_id, "state": state, "turns": recread.turns(events),
            "terminal": state == "complete" or last in TAIL_KINDS,
            "entries": entries(events, rec["torn_tail_bytes"])}
