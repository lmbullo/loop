from . import api

ZERO = {"hit": 0, "miss": 0, "out": 0, "reasoning_c": 0}


def totals_of(events):
    t = dict(ZERO)
    for ev in events:
        if ev["type"] == "turn":
            u = ev["data"].get("usage") or {}
            for k in t:
                t[k] += int(u.get(k) or 0)
    return t


def derive(events):
    task = root = max_inline = None
    turn = obs_n = 0
    done = None
    nudged = False
    for ev in events:
        d = ev["data"]
        if ev["type"] == "run_start":
            task, root = d.get("task"), d.get("root")
            max_inline = d.get("max_inline")
        elif ev["type"] == "turn":
            turn = int(d.get("turn") or turn)
            obs_n += len(d.get("calls") or [])
            done = d.get("done")
        elif ev["type"] == "nudge":
            nudged = True
        elif ev["type"] == "resume" and root is None:
            root = d.get("root")
    return {"task": task, "root": root, "turn": turn, "obs_n": obs_n,
            "done": done, "max_inline": max_inline, "nudged": nudged}


def pending_verify(events):
    cmd = None
    for ev in events:
        if ev["type"] == "verify":
            cmd = None if ev["data"]["ran"] else ev["data"]["command"]
    return cmd


def context(events, task):
    msgs = [{"role": "system", "content": api.header()},
            {"role": "user", "content": task or ""}]
    for ev in events:
        if ev["type"] == "nudge":
            msgs.append({"role": "user", "content": ev["data"]["text"]})
            continue
        if ev["type"] != "turn":
            continue
        msgs.append(ev["data"]["message"])
        for call in ev["data"].get("calls") or []:
            msgs.append({"role": "tool", "tool_call_id": call["id"],
                         "content": call["observation"]})
    return msgs
