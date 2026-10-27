import json
import os
import sys

from . import assets, config, observe, spawn


def do_exec(call, n, ws, obs_dir):
    code, out, err, dur = spawn.spawn(
        call["argv"], config.resolve(call.get("cwd") or ".", ws),
        call.get("stdin", ""), call.get("timeout_ms", 10000))
    body, nbytes = observe.render_v2(out, err, obs_dir, f"o{n}")
    return body, nbytes, code, dur


def do_edit(call, ws):
    path = config.resolve(call["path"], ws)
    try:
        with open(path, "rb") as f:
            s = f.read()
    except OSError as e:
        return f"err={e.strerror}", 0, 1
    old, new = call["old"].encode(), call["new"].encode()
    c = s.count(old)
    if c != 1:
        return f"err=no_unique_match found={c}", 0, 1
    s2 = s.replace(old, new, 1)
    with open(path, "wb") as f:
        f.write(s2)
    i = s2.find(new)
    ctx = s2[max(0, i - 40):i + len(new) + 40].decode("utf-8", "replace")
    return f"ok -{len(old)} +{len(new)} @{call['path']}\n{ctx}", 0, 0


def run(sc):
    label = sc["label"]
    run_dir = os.path.join(config.runs(), "sim2", label)
    ws = assets.mount(run_dir, sc["fixture"])
    obs_dir = os.path.join(run_dir, "obs")
    log = [{"t": "hdr"}]
    prev = 0
    miss_tot = 0
    print(f"\n=== {sc['id']} ===")
    for n, call in enumerate(sc["steps"], 1):
        if call["tool"] == "done":
            log.append({"t": "done", "v": call.get("result", "")})
            print(f"[{n}] DONE")
            break
        if call["tool"] == "edit":
            body, nb, code = do_edit(call, ws)
        else:
            body, nb, code, dur = do_exec(call, n, ws, obs_dir)
        log.append({"t": "obs", "b": body})
        whole = sum(len(json.dumps(e)) for e in log)
        appended = whole - prev
        prev = whole
        miss = appended / 4
        tot = whole / 4
        miss_tot += miss
        print(f"[{n}] {call.get('argv', call.get('path', ''))}")
        print(f"  $ code={code} out={nb}B " + body.replace("\n", "\n  ")[:500])
        print(f"  <miss={miss:.0f}t hit={100*(1-miss/tot):.0f}%>")
    print(f"  TOTAL MISS ~{miss_tot:.0f}t  $" + "{:.5f}".format(miss_tot * 0.30 / 1e6))
    log_path = os.path.join(run_dir, "log.json")
    assets.write_json(log_path, log)
    summary = {"entrypoint": "sim2", "scenario": sc["id"], "turns": len(log) - 1,
               "miss_tokens": round(miss_tot), "miss_cost_usd": round(miss_tot * 0.30 / 1e6, 6),
               "run_dir": config.display(run_dir), "log": config.display(log_path),
               "bytes_log": os.path.getsize(log_path)}
    print("summary: " + json.dumps(summary, sort_keys=True))
    return summary


def main(argv):
    if len(argv) != 1:
        print("usage: python3 run.py sim2 <scenario>  available: " + ", ".join(assets.available()), file=sys.stderr)
        return 2
    try:
        sc = assets.load_scenario(argv[0], expect_sim="sim2")
    except FileNotFoundError:
        print(f"err unknown scenario {argv[0]!r} available: {', '.join(assets.available())}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"err {e}", file=sys.stderr)
        return 2
    run(sc)
    return 0
