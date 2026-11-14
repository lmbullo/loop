import json
import sys
import urllib.error

from . import api, auth, config, pricing, record, recread, reload, tools

ZERO = {"hit": 0, "miss": 0, "out": 0, "reasoning_c": 0}
TOOL_NAMES = [t["function"]["name"] for t in api.TOOLS]


def cost_of(totals):
    return pricing.cost(totals["hit"], totals["miss"], totals["out"])


def totals_of(events):
    t = dict(ZERO)
    for ev in events:
        if ev["type"] == "turn":
            u = ev["data"].get("usage") or {}
            for k in t:
                t[k] += int(u.get(k) or 0)
    return t


def derive(events):
    task = root = None
    turn = obs_n = 0
    done = None
    for ev in events:
        d = ev["data"]
        if ev["type"] == "run_start":
            task, root = d.get("task"), d.get("root")
        elif ev["type"] == "turn":
            turn = int(d.get("turn") or turn)
            obs_n += len(d.get("calls") or [])
            done = d.get("done")
        elif ev["type"] == "resume" and root is None:
            root = d.get("root")
    return {"task": task, "root": root, "turn": turn, "obs_n": obs_n, "done": done}


def context(events, task):
    msgs = [{"role": "system", "content": api.header()},
            {"role": "user", "content": task or ""}]
    for ev in events:
        if ev["type"] != "turn":
            continue
        msgs.append(ev["data"]["message"])
        for call in ev["data"].get("calls") or []:
            msgs.append({"role": "tool", "tool_call_id": call["id"],
                         "content": call["observation"]})
    return msgs


def finish(writer, emit, events, turn, finish, result, exit_code):
    totals = totals_of(events)
    summary = {"exit": int(exit_code), "finish": finish, "result": result,
               "turns": int(turn), "hit": totals["hit"], "miss": totals["miss"],
               "out": totals["out"], "reasoning_c": totals["reasoning_c"],
               "cost": round(cost_of(totals), 6)}
    emit(writer.append("end", summary))
    writer.seal()
    return {"run_id": writer.run_id, "entrypoint": "api", **summary}


def stopped(writer, events, turn):
    totals = totals_of(events)
    return {"run_id": writer.run_id, "entrypoint": "api", "exit": 130,
            "finish": "stopped", "result": None, "turns": int(turn),
            "hit": totals["hit"], "miss": totals["miss"], "out": totals["out"],
            "reasoning_c": totals["reasoning_c"], "cost": round(cost_of(totals), 6)}


def credentials(writer, emit, events):
    try:
        return auth.api_key()
    except (OSError, KeyError, TypeError, ValueError) as e:
        text = (f"err auth source={auth.auth_file()} detail={type(e).__name__}: {e} "
                f"fix=LOOP_API_KEY or LOOP_AUTH_FILE")
        ev = writer.append("error", {"code": 3, "text": text, "finish": "no_credentials"})
        emit(ev)
        finish(writer, emit, events + [ev], 0, "no_credentials", None, 3)
        return None


def read_turn(r):
    usage = r.get("usage") or {}
    hit = int(usage.get("prompt_cache_hit_tokens", 0) or 0)
    miss = int(usage.get("prompt_cache_miss_tokens", 0) or 0)
    out = int(usage.get("completion_tokens", 0) or 0)
    choice = (r.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    message = {"role": "assistant", "content": None, "tool_calls": []}
    for call in msg.get("tool_calls") or []:
        fn = call.get("function") or {}
        message["tool_calls"].append({
            "id": call.get("id") or "", "type": call.get("type") or "function",
            "function": {"name": fn.get("name") or "",
                         "arguments": fn.get("arguments") or "{}"}})
    return hit, miss, out, len(msg.get("reasoning_content") or ""), choice.get("finish_reason"), message, msg.get("content")


def run_calls(message, obs_dir, run_dir, root, obs_n):
    calls = []
    done = None
    for call in message["tool_calls"]:
        fn = call["function"]["name"]
        try:
            args = json.loads(call["function"]["arguments"], strict=False)
            if not isinstance(args, dict):
                raise ValueError(f"arguments are {type(args).__name__}, not object")
        except (ValueError, TypeError) as e:
            obs = f"err malformed_arguments {e}"
            calls.append({"id": call["id"], "name": fn, "observation": obs,
                          "bytes": len(obs.encode()), "saved": None})
            continue
        if fn == "done":
            done = {"id": call["id"], "result": args.get("result", "")}
            break
        obs_n += 1
        saved = []
        try:
            obs = tools.dispatch(fn, args, obs_dir, f"obs-{obs_n}", root, run_dir, saved)
        except Exception as e:
            obs = (f"err harness {type(e).__name__}: {e}; "
                   f"exec argv, write path+data, edit path+old+new")
        calls.append({"id": call["id"], "name": fn, "observation": obs,
                      "bytes": len(obs.encode()), "saved": saved[0] if saved else None})
    return calls, done, obs_n


def run_task(writer, emit, task=None, root=None, should_stop=None):
    events = recread.read(writer.run_id)["events"]
    if not events:
        if task is None:
            task = "No task."
        ev = writer.append("run_start", {"task": task, "root": root or config.root(),
                                         "entrypoint": "api", "model": api.model(),
                                         "tools": list(TOOL_NAMES),
                                         "max_inline": config.max_inline(),
                                         "record_source": "live"})
        emit(ev)
        events = [ev]
    st = derive(events)
    if st["done"] is not None:
        return finish(writer, emit, events, st["turn"], "done", st["done"]["result"], 0)
    key = credentials(writer, emit, events)
    if key is None:
        return {"run_id": writer.run_id, "entrypoint": "api", "exit": 3}
    turn, obs_n = st["turn"], st["obs_n"]
    obs_dir = record.obs_dir(writer.run_id)
    run_dir = record.run_dir(writer.run_id)
    while True:
        if should_stop is not None and should_stop():
            return stopped(writer, events, turn)
        reload.maybe()
        msgs = context(events, st["task"])
        turn += 1
        try:
            r = api.call(msgs, key)
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", "replace")[:300]
            except OSError:
                body = ""
            ev = writer.append("error", {"code": 4, "text": f"api HTTP {e.code}: {body}",
                                         "finish": "http_error"})
            emit(ev)
            return finish(writer, emit, events + [ev], turn, "http_error", None, 4)
        hit, miss, out, reason, finish_reason, message, text = read_turn(r)
        calls, done, obs_n = run_calls(message, obs_dir, run_dir, root or st["root"], obs_n)
        ev = writer.append("turn", {
            "turn": turn, "finish_reason": finish_reason,
            "usage": {"hit": hit, "miss": miss, "out": out, "reasoning_c": reason,
                      "cost": round(pricing.cost(hit, miss, out), 6)},
            "message": message, "calls": calls, "done": done})
        emit(ev)
        events = events + [ev]
        if done is not None:
            return finish(writer, emit, events, turn, "done", done["result"], 0)
        if not message["tool_calls"]:
            ok = isinstance(text, str) and text.strip()
            return finish(writer, emit, events, turn, "done" if ok else "no_tool_call",
                          text.strip() if ok else None, 0)


def main(argv):
    as_json = False
    args = []
    for arg in argv:
        if arg == "--json":
            as_json = True
        else:
            args.append(arg)
    task = args[0] if args else "No task."
    if task == "-":
        task = sys.stdin.read()
    from . import srvclient
    return srvclient.run_local(task, as_json)
