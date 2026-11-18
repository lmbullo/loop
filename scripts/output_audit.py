#!/usr/bin/env python3
"""Offline output audit for one append-only run record.

Output tokens are completion tokens: private reasoning, tool-call arguments and
the final result. This script splits the recorded completion total into those
sources, names the most expensive turns, and counts truncated replies. It never
calls the API and never writes a record.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from harness import pricing, recread, record  # noqa: E402


def _args(message):
    total, per = 0, {}
    for call in message.get("tool_calls") or []:
        fn = call.get("function") or {}
        name = fn.get("name") or "?"
        size = len((fn.get("arguments") or "").encode("utf-8"))
        total += size
        per[name] = per.get(name, 0) + size
    return total, per


def audit(run_id, top=8):
    rec = recread.read(run_id)
    rows, tool_bytes, finishes = [], {}, {}
    result = ""
    for ev in rec["events"]:
        kind, data = ev["type"], ev["data"]
        if kind == "end":
            result = data.get("result") or ""
            continue
        if kind != "turn":
            continue
        usage = data.get("usage") or {}
        out = int(usage.get("out") or 0)
        reason_chars = int(usage.get("reasoning_c") or 0)
        arg_bytes, per = _args(data.get("message") or {})
        obs_bytes = sum(int(c.get("bytes") or 0) for c in (data.get("calls") or []))
        for name, size in per.items():
            bucket = tool_bytes.setdefault(name, {"calls": 0, "bytes": 0})
            bucket["calls"] += 1
            bucket["bytes"] += size
        finish = data.get("finish_reason") or ""
        finishes[finish] = finishes.get(finish, 0) + 1
        rows.append({"turn": int(data.get("turn") or 0), "out": out,
                     "reasoning_c": reason_chars, "arg_bytes": arg_bytes,
                     "obs_bytes": obs_bytes, "finish": finish,
                     "calls": list(per), "reasoning_est": round(reason_chars / 4.0, 1),
                     "args_est": round(arg_bytes / 4.0, 1)})
    hit = sum(int((e["data"].get("usage") or {}).get("hit") or 0)
              for e in rec["events"] if e["type"] == "turn")
    miss = sum(int((e["data"].get("usage") or {}).get("miss") or 0)
               for e in rec["events"] if e["type"] == "turn")
    out = sum(r["out"] for r in rows)
    reason_chars = sum(r["reasoning_c"] for r in rows)
    arg_bytes = sum(r["arg_bytes"] for r in rows)
    return {
        "run_id": run_id, "state": rec["state"], "turns": len(rows), "out": out,
        "out_per_turn": round(out / len(rows), 1) if rows else 0.0,
        "reasoning_c": reason_chars, "reasoning_est": round(reason_chars / 4.0, 1),
        "reasoning_share": round(min(reason_chars / 4.0, out) / out, 3) if out else 0.0,
        "arg_bytes": arg_bytes, "args_est": round(arg_bytes / 4.0, 1),
        "result_chars": len(result), "result_est": round(len(result) / 4.0, 1),
        "finish": finishes, "truncated": int(finishes.get("length") or 0),
        "tools": tool_bytes, "cost": round(pricing.cost(hit, miss, out), 6),
        "top": sorted(rows, key=lambda r: -r["out"])[:top],
    }


def main(argv):
    as_json, top, args = "--json" in argv, 8, []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--top" and i + 1 < len(argv):
            top = int(argv[i + 1]); i += 2; continue
        if arg.startswith("--top="):
            top = int(arg.split("=", 1)[1]); i += 1; continue
        if not arg.startswith("-"):
            args.append(arg)
        i += 1
    try:
        row = audit(record.resolve(args[0]) if args else record.resolve(), top)
    except (record.Missing, record.Corrupt) as e:
        print(f"err {e}", file=sys.stderr)
        return 2
    if as_json:
        print(record.canonical(row))
        return 0
    print(f"run={row['run_id']} state={row['state']} turns={row['turns']} "
          f"out={row['out']} out_per_turn={row['out_per_turn']} "
          f"reason_est={row['reasoning_est']} ({row['reasoning_share']:.0%}) "
          f"args_est={row['args_est']} result_est={row['result_est']} "
          f"truncated={row['truncated']} cost=${row['cost']:.6f}")
    for t in row["top"]:
        print(f"  turn={t['turn']} out={t['out']} reason_est={t['reasoning_est']:.0f} "
              f"args_est={t['args_est']:.0f} obs={t['obs_bytes']}B "
              f"finish={t['finish']} calls={','.join(t['calls']) or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
