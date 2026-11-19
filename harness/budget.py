"""Token estimates and the compaction boundary for an append-only run.

The request is re-sent every turn, so prompt size is a quadratic cost. The
estimate is deliberately cheap and conservative: three UTF-8 bytes per token,
which over-counts code and keeps the high watermark safe for tokenizers that
split identifiers. It never calls the API.
"""

import json


def est_text(text):
    if not text:
        return 0
    if not isinstance(text, str):
        text = json.dumps(text, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)
    return (len(text.encode("utf-8")) + 2) // 3


def est_message(msg):
    total = 8 + est_text(msg.get("role") or "")
    content = msg.get("content")
    if isinstance(content, str):
        total += est_text(content)
    for call in msg.get("tool_calls") or []:
        fn = call.get("function") or {}
        total += 12 + est_text(fn.get("name") or "")
        total += est_text(fn.get("arguments") or "")
    return total


def est_messages(msgs):
    return sum(est_message(m) for m in msgs)


def est_call(call):
    total = 8 + est_text(call.get("name") or "")
    total += est_text(call.get("args") or "")
    total += est_text(call.get("observation") or "")
    return total


def est_turn(ev):
    data = ev.get("data") or {}
    total = est_message(data.get("message") or {})
    total += sum(est_call(c) for c in data.get("calls") or [])
    return total + 8


def est_request(msgs, wire=None):
    total = est_messages(msgs) + 64
    if wire:
        total += est_text(wire.get("tools") or "")
        total += est_text(wire.get("system") or "")
    return total


def _turns(events, base):
    return [ev for ev in events
            if ev.get("type") == "turn"
            and int((ev.get("data") or {}).get("turn") or 0) > base]


def plan(events, base, low, keep, min_keep=4, force=False):
    """Highest turn to compact so the verbatim tail fits the low watermark.

    Returns `base` when there is nothing old enough to compact. Nudges and
    verify events are small and travel with the turn that follows them. A
    forced plan keeps only `min_keep` recent turns, which is the recovery
    path for a provider that rejects the full prompt as too long.
    """
    turns = _turns(events, base)
    keep = max(1, int(keep))
    min_keep = max(1, min(int(min_keep), keep))
    if len(turns) <= min_keep:
        return base
    used, chosen = 0, 0
    for ev in reversed(turns):
        chosen += 1
        used += est_turn(ev)
        if chosen >= min_keep and (force or used >= low or chosen >= keep):
            break
    if chosen >= len(turns):
        # The tail alone is below the low watermark, but the full prompt is
        # still over the high watermark. Keep only the floor turns so the
        # checkpoint removes what it can instead of doing nothing.
        chosen = min_keep
    first = len(turns) - chosen
    if first <= 0:
        return base
    return int(turns[first - 1]["data"]["turn"])


def tail_tokens(events, base):
    return sum(est_turn(ev) for ev in _turns(events, base))
