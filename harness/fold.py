from . import api
from .turn import is_length_nudge

ZERO = {"hit": 0, "miss": 0, "out": 0, "reasoning_c": 0}


def totals_of(events):
    t = dict(ZERO)
    for ev in events:
        if ev["type"] == "turn":
            u = ev["data"].get("usage") or {}
            for k in t:
                t[k] += int(u.get(k) or 0)
    return t


def wire(events):
    for ev in events:
        if ev["type"] == "wire":
            return ev["data"]
    return None


def compact_of(events):
    latest = None
    for ev in events:
        if ev["type"] == "compact":
            latest = ev["data"]
    return latest


def derive(events):
    task = root = max_inline = None
    turn = obs_n = 0
    done = None
    nudged = pending = False
    compact = None
    for ev in events:
        d = ev["data"]
        if ev["type"] == "run_start":
            task, root = d.get("task"), d.get("root")
            max_inline = d.get("max_inline")
        elif ev["type"] == "turn":
            turn = int(d.get("turn") or turn)
            obs_n += len(d.get("calls") or [])
            done = d.get("done")
            # A silent-stop retry is spent only by a consecutive silent turn;
            # real work resets it so a later stall still gets one nudge.
            if done is not None or d.get("calls"):
                pending = False
        elif ev["type"] == "nudge":
            if not is_length_nudge(d.get("text")):
                nudged = pending = True
        elif ev["type"] == "compact":
            compact = d
        elif ev["type"] == "resume" and root is None:
            root = d.get("root")
    return {"task": task, "root": root, "turn": turn, "obs_n": obs_n,
            "done": done, "max_inline": max_inline, "nudged": nudged, "nudge_pending": pending,
            "wire": wire(events), "base_turn": int((compact or {}).get("after") or 0),
            "compacted": int((compact or {}).get("count") or 0),
            "compact_prompt": int((compact or {}).get("prompt") or 0),
            "compact_state": (compact or {}).get("state")}


def pending_verify(events):
    cmd = None
    for ev in events:
        if ev["type"] == "verify":
            cmd = None if ev["data"]["ran"] else ev["data"]["command"]
    return cmd


def _message(data, spec):
    message = dict(data["message"])
    if data.get("finish_reason") == "length":
        # A length stop is not a usable assistant turn: its arguments may be
        # cut mid-JSON and its reasoning is runaway. Keep the nudge retry clean.
        message["content"] = ""
        message["reasoning_content"] = ""
        message.pop("tool_calls", None)
        return message
    message.setdefault("reasoning_content", "")
    if spec is None or not spec.get("replay_reasoning", True):
        # The field must be present in thinking mode, but an empty value is
        # accepted. Replaying it would re-bill every old private thought.
        message["reasoning_content"] = ""
    if not message.get("tool_calls"):
        # The API rejects tool_calls:[]; omit it on a silent stop so the nudge
        # can produce a real assistant turn.
        message.pop("tool_calls", None)
    return message


def context(events, task, wire_spec=None):
    spec = wire_spec or wire(events)
    system = spec["system"] if spec else api.header()
    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": task or ""}]
    start, digest = 0, None
    for index, ev in enumerate(events):
        if ev["type"] == "compact":
            start, digest = index + 1, ev["data"].get("digest")
            msgs = msgs[:2]
    if digest:
        msgs.append({"role": "user", "content": digest})
    for ev in events[start:]:
        if ev["type"] == "nudge":
            msgs.append({"role": "user", "content": ev["data"]["text"]})
        elif ev["type"] == "turn":
            msgs.append(_message(ev["data"], spec))
            for call in ev["data"].get("calls") or []:
                msgs.append({"role": "tool", "tool_call_id": call["id"],
                             "content": call["observation"]})
    return msgs
