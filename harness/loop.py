"""The turn loop: context budget, transport, tools and settlement.

The loop owns no memory of its own. Every decision is derived from record
events, so a resume rebuilds the same messages and the same cached prefix.
Compaction is the only intentional prefix break; everything else appends.
"""

import json

from . import (api, budget, close, config, fold, ledger, memo, record, recread,
               reload, retry, turn)


def compact(writer, emit, events, wire, force=False):
    st = fold.derive(events)
    base = st["base_turn"]
    high = config.context_high()
    low = max(1000, high // 8) if force else config.context_low()
    keep = 2 if force else config.keep_turns()
    upto = budget.plan(events, base, low, keep, min_keep=keep, force=force)
    if upto <= base:
        return None
    prior = memo.parse_state(st.get("compact_state"))
    state, digest = memo.build(events, base, upto, prior)
    preview = events + [{"type": "compact", "data": {"digest": digest}}]
    prompt = budget.est_request(fold.context(preview, st["task"], wire), wire)
    ev = writer.append("compact", {
        "after": int(upto), "from": int(base), "count": int(state["count"]),
        "digest": digest, "state": json.dumps(
            state, sort_keys=True, separators=(",", ":")),
        "bytes": len(digest.encode()), "tokens": budget.est_text(digest),
        "prompt": int(prompt)})
    emit(ev)
    return ev


def ensure(writer, emit, events, wire, last_prompt, force=False):
    msgs = fold.context(events, fold.derive(events)["task"], wire)
    high = config.context_high()
    floor = fold.derive(events)["compact_prompt"]
    trigger = high if floor < high else floor + max(1024, high // 4)
    over = force or budget.est_request(msgs, wire) > trigger or last_prompt > trigger
    if over:
        ev = compact(writer, emit, events, wire, force=force)
        if ev is not None:
            events = events + [ev]
            msgs = fold.context(events, fold.derive(events)["task"], wire)
    return events, msgs


def start(writer, emit, task, root):
    ev = writer.append("run_start", {
        "task": task or "No task.", "root": root or config.root(),
        "entrypoint": "api", "model": api.model(),
        "tools": [t["function"]["name"] for t in api.TOOLS],
        "max_inline": config.max_inline(), "record_source": "live"})
    emit(ev)
    return [ev]


def run_task(writer, emit, task=None, root=None, should_stop=None, verify=None):
    events = recread.read(writer.run_id)["events"]
    if not events:
        events = start(writer, emit, task, root)
    if fold.wire(events) is None:
        ev = writer.append("wire", api.snapshot())
        emit(ev)
        events = events + [ev]
    wire = fold.wire(events) or api.snapshot()
    st = fold.derive(events)
    root = root or st["root"]
    max_inline = st.get("max_inline")
    if max_inline is None:
        max_inline = config.max_inline()
    cmd = fold.pending_verify(events) or verify
    if cmd and not any(ev["type"] == "verify" for ev in events):
        ev = writer.append("verify", {"command": cmd, "ran": False, "exit": None, "note": None})
        emit(ev)
        events = events + [ev]
    if st["done"] is not None:
        return close.settle(writer, emit, events, st["turn"], cmd, root,
                            "done", st["done"]["result"], 0)
    key = close.credentials(writer, emit, events)
    if key is None:
        return {"run_id": writer.run_id, "entrypoint": "api", "exit": 3}
    turn_no, obs_n = st["turn"], st["obs_n"]
    nudged = st["nudge_pending"]
    obs_dir = record.obs_dir(writer.run_id)
    seen = ledger.Ledger.from_events(events, root)
    cap = max(1, min(config.turn_tokens(), int(wire["max_tokens"])))
    length_streak = ctx_retries = 0
    last_prompt = 0
    for ev in reversed(events):
        if ev["type"] == "compact":
            last_prompt = 0
            break
        if ev["type"] == "turn":
            usage = ev["data"].get("usage") or {}
            last_prompt = int(usage.get("hit") or 0) + int(usage.get("miss") or 0)
            break
    while True:
        if should_stop is not None and should_stop():
            return close.stopped(writer, events, turn_no)
        reload.maybe()
        before = len(events)
        events, msgs = ensure(writer, emit, events, wire, last_prompt)
        if len(events) > before:
            last_prompt = 0
        turn_no += 1

        def on_retry(attempt, code, delay, text):
            nonlocal events
            ev = writer.append("retry", {"attempt": int(attempt), "code": int(code),
                                         "delay_ms": int(delay), "text": text[:300]})
            emit(ev)
            events = events + [ev]

        try:
            r = retry.call(msgs, key, wire, max_tokens=cap, on_retry=on_retry)
        except retry.Error as exc:
            if retry.is_context(exc.text) and ctx_retries < 4:
                ev = compact(writer, emit, events, wire, force=True)
                if ev is not None:
                    events = events + [ev]
                    ctx_retries += 1
                    last_prompt = 0
                    turn_no -= 1
                    continue
            ev = writer.append("error", {"code": 4, "finish": "http_error",
                                         "text": f"api code={exc.code} {exc.text[:300]}"})
            emit(ev)
            return close.finish(writer, emit, events + [ev], turn_no, "http_error", None, 4)
        hit, miss, out, reason, finish_reason, message, text = turn.read_turn(r, turn_no)
        last_prompt = hit + miss
        ctx_retries = 0
        if finish_reason == "length":
            calls, done = [], None
        else:
            calls, done, obs_n = turn.run_calls(
                message, obs_dir, root, obs_n, max_inline, seen,
                read_inline=config.read_inline())
        ev = writer.append("turn", {
            "turn": turn_no, "finish_reason": finish_reason,
            "usage": {"hit": hit, "miss": miss, "out": out, "reasoning_c": reason,
                      "cost": round(close.pricing.cost(hit, miss, out), 6)},
            "message": message, "calls": calls, "done": done})
        emit(ev)
        events = events + [ev]
        if done is not None:
            return close.settle(writer, emit, events, turn_no, cmd, root,
                                "done", done["result"], 0)
        action = turn.stop(message, text, turn_no, nudged, finish_reason)
        if action is None:
            length_streak = 0
            nudged = False
            cap = max(1, min(config.turn_tokens(), int(wire["max_tokens"])))
            continue
        kind, result = action
        if kind == "nudge":
            if finish_reason == "length":
                length_streak += 1
                if length_streak > config.length_retries():
                    ev = writer.append("error", {
                        "code": 4, "finish": "output_limit",
                        "text": f"max_tokens exhausted {length_streak} times; split the call"})
                    emit(ev)
                    return close.finish(writer, emit, events + [ev], turn_no,
                                        "output_limit", None, 4)
                cap = int(wire["max_tokens"])
            else:
                nudged = True
            ev = writer.append("nudge", {"text": result})
            emit(ev)
            events = events + [ev]
            continue
        return close.settle(writer, emit, events, turn_no, cmd, root, kind, result, 0)
