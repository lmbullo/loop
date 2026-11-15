#!/usr/bin/env python3
"""Offline cache audit for one append-only run record.

Rebuilds every request prefix from record bytes, asserts the prefix only grows,
and reports the token/cost split plus any turn whose cache miss is much larger
than the bytes that turn appended. This is a non-model control-plane check: it
never calls the API and never writes a record.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from harness import fold, pricing, recread, record  # noqa: E402


def _bytes(msgs):
    return len(json.dumps(msgs, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def audit(run_id):
    rec = recread.read(run_id)
    events = rec["events"]
    task = fold.derive(events)["task"] or ""
    spec = fold.wire(events)
    rows = []
    prev = None
    ratio_samples = []
    reuse = 0
    for ev in events:
        if ev["type"] != "turn":
            continue
        now = fold.context(events[:ev["seq"] - 1], task, spec)
        prefix_ok = prev is None or now[:len(prev)] == prev
        usage = ev["data"].get("usage") or {}
        hit = int(usage.get("hit") or 0)
        miss = int(usage.get("miss") or 0)
        out = int(usage.get("out") or 0)
        appended = now if prev is None else (now[len(prev):] if prefix_ok else [])
        appended_bytes = sum(_bytes([m]) for m in appended)
        rows.append({"turn": int(ev["data"].get("turn") or 0),
                     "hit": hit, "miss": miss, "out": out,
                     "prefix_ok": prefix_ok, "prompt_bytes": _bytes(now),
                     "appended_bytes": appended_bytes})
        if prev is not None and appended_bytes > 200 and miss > 0:
            ratio_samples.append(miss / appended_bytes)
        for call in ev["data"].get("calls") or []:
            if (call.get("observation") or "").startswith("same="):
                reuse += 1
        prev = now
    ratio = sorted(ratio_samples)[len(ratio_samples) // 2] if ratio_samples else 0.25
    breaks = []
    for row in rows:
        expected = row["appended_bytes"] * ratio + 172
        if row["turn"] > 1 and row["miss"] > expected * 2 + 256:
            breaks.append({"turn": row["turn"], "miss": row["miss"],
                           "expected": round(expected)})
    hit = sum(r["hit"] for r in rows)
    miss = sum(r["miss"] for r in rows)
    out = sum(r["out"] for r in rows)
    total = hit + miss
    return {"run_id": run_id, "state": rec["state"], "wire_sha": (spec or {}).get("sha"),
            "turns": len(rows), "hit": hit, "miss": miss, "out": out,
            "hit_frac": round(hit / total, 6) if total else 0.0,
            "miss_per_turn": round(miss / len(rows), 2) if rows else 0.0,
            "context_bytes_max": max((r["prompt_bytes"] for r in rows), default=0),
            "prefix_ok": all(r["prefix_ok"] for r in rows),
            "reuse_refs": reuse, "cache_breaks": breaks,
            "cost": round(pricing.cost(hit, miss, out), 6)}


def main(argv):
    as_json = "--json" in argv
    args = [a for a in argv if not a.startswith("-")]
    try:
        run_id = record.resolve(args[0]) if args else record.resolve()
        row = audit(run_id)
    except (record.Missing, record.Corrupt) as e:
        print(f"err {e}", file=sys.stderr)
        return 2
    print(record.canonical(row) if as_json else
          (f"run={row['run_id']} state={row['state']} turns={row['turns']} "
           f"hit_frac={row['hit_frac']:.4f} hit={row['hit']} miss={row['miss']} "
           f"out={row['out']} cost=${row['cost']:.6f} "
           f"ctx_max={row['context_bytes_max']}B reuse={row['reuse_refs']} "
           f"prefix_ok={row['prefix_ok']} breaks={len(row['cache_breaks'])}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
