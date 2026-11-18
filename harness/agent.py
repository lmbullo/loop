import sys
import urllib.error

from . import api, auth, config, fold, ledger, pricing, record, recread, reload, verifier
from .turn import is_length_nudge, read_turn, run_calls, stop

totals_of = fold.totals_of
derive = fold.derive
context = fold.context


def cost_of(totals):
    return pricing.cost(totals["hit"], totals["miss"], totals["out"])


def finish(writer, emit, events, turn, finish, result, exit_code):
    totals = fold.totals_of(events)
    summary = {"exit": int(exit_code), "finish": finish, "result": result,
               "turns": int(turn), "hit": totals["hit"], "miss": totals["miss"],
               "out": totals["out"], "reasoning_c": totals["reasoning_c"],
               "cost": round(cost_of(totals), 6)}
    emit(writer.append("end", summary))
    writer.seal()
    return {"run_id": writer.run_id, "entrypoint": "api", **summary}


def stopped(writer, events, turn):
    totals = fold.totals_of(events)
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


def settle(writer, emit, events, turn, cmd, root, kind, result, code):
    if cmd:
        ok, note = verifier.run(root or config.root(), cmd)
        ev = writer.append("verify", {"command": cmd, "ran": True, "exit": ok, "note": note})
        emit(ev)
        events = events + [ev]
    return finish(writer, emit, events, turn, kind, result, code)


def run_task(writer, emit, task=None, root=None, should_stop=None, verify=None):
    events = recread.read(writer.run_id)["events"]
    if not events:
        ev = writer.append("run_start", {"task": task or "No task.",
                                         "root": root or config.root(),
                                         "entrypoint": "api", "model": api.model(),
                                         "tools": [t["function"]["name"] for t in api.TOOLS],
                                         "max_inline": config.max_inline(),
                                         "record_source": "live"})
        emit(ev)
        events = [ev]
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
        return settle(writer, emit, events, st["turn"], cmd, root, "done", st["done"]["result"], 0)
    key = credentials(writer, emit, events)
    if key is None:
        return {"run_id": writer.run_id, "entrypoint": "api", "exit": 3}
    turn, obs_n = st["turn"], st["obs_n"]
    nudged = st["nudged"]
    obs_dir = record.obs_dir(writer.run_id)
    seen = ledger.Ledger.from_events(events, root)
    while True:
        if should_stop is not None and should_stop():
            return stopped(writer, events, turn)
        reload.maybe()
        msgs = fold.context(events, st["task"], wire)
        turn += 1
        try:
            r = api.call(msgs, key, wire)
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", "replace")[:300]
            except OSError:
                body = ""
            ev = writer.append("error", {"code": 4, "text": f"api HTTP {e.code}: {body}",
                                         "finish": "http_error"})
            emit(ev)
            return finish(writer, emit, events + [ev], turn, "http_error", None, 4)
        hit, miss, out, reason, finish_reason, message, text = read_turn(r, turn)
        if finish_reason == "length":
            calls, done = [], None
        else:
            calls, done, obs_n = run_calls(message, obs_dir, root, obs_n, max_inline, seen)
        ev = writer.append("turn", {
            "turn": turn, "finish_reason": finish_reason,
            "usage": {"hit": hit, "miss": miss, "out": out, "reasoning_c": reason,
                      "cost": round(pricing.cost(hit, miss, out), 6)},
            "message": message, "calls": calls, "done": done})
        emit(ev)
        events = events + [ev]
        if done is not None:
            return settle(writer, emit, events, turn, cmd, root, "done", done["result"], 0)
        action = stop(message, text, turn, nudged, finish_reason)
        if action is None:
            continue
        kind, result = action
        if kind == "nudge":
            ev = writer.append("nudge", {"text": result})
            emit(ev)
            events = events + [ev]
            nudged = nudged or not is_length_nudge(result)
            continue
        return settle(writer, emit, events, turn, cmd, root, kind, result, 0)


USAGE = "usage: python3 run.py api [--verify CMD] [--json] [--] [TASK|-]"


def _api_error(message):
    print(f"err {message}\n{USAGE}", file=sys.stderr)
    return 2


def main(argv):
    as_json, verify, args, i, options = False, None, [], 0, True
    while i < len(argv):
        arg = argv[i]
        if options and arg == "--":
            options = False
        elif options and arg in ("-h", "--help"):
            print(USAGE)
            return 0
        elif options and arg == "--json":
            as_json = True
        elif options and arg == "--verify":
            if i + 1 >= len(argv):
                return _api_error("--verify needs a command string")
            verify = argv[i + 1]
            i += 1
        elif options and arg.startswith("-") and arg != "-":
            hint = (" (did you mean --verify? top-level --version prints the release)"
                    if "--verify".startswith(arg) else "")
            return _api_error(f"unknown option {arg!r}{hint}")
        else:
            args.append(arg)
        i += 1
    if len(args) > 1:
        return _api_error(f"unexpected argument {args[1]!r}")
    task = args[0] if args else "No task."
    if task == "-":
        task = sys.stdin.read()
    from . import srvclient
    return srvclient.run_local(task, as_json, verify)
