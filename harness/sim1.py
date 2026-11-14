import json
import os
import sys

from . import assets, config, observe, pricing, spawn

HEADER = """\
tool: exec(argv:[str], cwd?:str, stdin?:str, timeout_ms?:int) -> observation
tool: done(result:str)
obs wire: "$ code=<int|TIMEOUT|127> out=<bytes> dur=<ms>" then payload.
payload is truncated to head+tail; full copy written to obs/<id> under the run dir.
edit files by writing a program; no state persists between calls.
"""


def do_exec(call, name, ws, obs_dir):
    code, out, err, dur = spawn.spawn(
        call["argv"], config.resolve(call.get("cwd") or ".", ws),
        call.get("stdin", ""), call.get("timeout_ms", 10000))
    payload = out + (b"\n--stderr--\n" + err if err else b"")
    body, nbytes, trunc = observe.render_v1(payload, obs_dir, name)
    return body, nbytes, code, dur, trunc


def run(sc):
    label = sc["label"]
    run_dir = os.path.join(config.runs(), "sim1", label)
    ws = assets.mount(run_dir, sc["fixture"])
    obs_dir = os.path.join(run_dir, "obs")
    log = [{"t": "header", "v": HEADER}]
    prev = 0
    print(f"\n=== {sc['id']} ===")
    for n, call in enumerate(sc["steps"], 1):
        if call["tool"] == "done":
            log.append({"t": "done", "v": call.get("result", "")})
            print(f"[turn {n}] DONE {call.get('result', '')}")
            break
        body, nbytes, code, dur, trunc = do_exec(call, f"{label}-{n}", ws, obs_dir)
        log.append({"t": "obs", "call": call["argv"], "code": code})
        wire = f"$ code={code} out={nbytes}B dur={dur}ms\n{body}"
        print(f"[turn {n}] {' '.join(call['argv'])[:70]}")
        print("  " + wire.replace("\n", "\n  ")[:900])
        whole = sum(len(json.dumps(e)) for e in log)
        appended = whole - prev
        prev = whole
        tot_tok = whole / 4
        miss_tok = appended / 4
        hit = 100 * (1 - miss_tok / tot_tok) if tot_tok else 0
        cost = pricing.cost(tot_tok - miss_tok, miss_tok, 0)
        print(f"  <cache prefix={tot_tok:.0f}t miss={miss_tok:.0f}t hit={hit:.0f}% cost=${cost*1000:.4f}/call>")
    log_path = os.path.join(run_dir, "log.json")
    assets.write_json(log_path, log)
    summary = {"entrypoint": "sim1", "scenario": sc["id"], "turns": len(log) - 1,
               "run_dir": config.display(run_dir), "log": config.display(log_path),
               "bytes_log": os.path.getsize(log_path)}
    print("summary: " + json.dumps(summary, sort_keys=True))
    return summary


def main(argv):
    if len(argv) != 1:
        print("usage: python3 run.py sim1 <scenario>  available: " + ", ".join(assets.available()), file=sys.stderr)
        return 2
    try:
        sc = assets.load_scenario(argv[0], expect_sim="sim1")
    except FileNotFoundError:
        print(f"err unknown scenario {argv[0]!r} available: {', '.join(assets.available())}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"err {e}", file=sys.stderr)
        return 2
    run(sc)
    return 0
