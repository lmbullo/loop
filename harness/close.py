import sys

from . import auth, config, fold, pricing, verifier


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


USAGE = "usage: python3 run.py api [--verify CMD] [--json] [--] [TASK|-]"


def api_error(message):
    print(f"err {message}\n{USAGE}", file=sys.stderr)
    return 2
