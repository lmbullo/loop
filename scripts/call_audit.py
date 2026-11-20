"""Audit one run's own tool calls: shapes, failures, redundancy, token split.

Usage: python3 scripts/call_audit.py [run_dir] [--json]
Prints a compact report so the loop can see where its own calls waste turns.

Turn usage is recorded as hit/miss/out/reasoning_c/cost, so prompt tokens are
hit+miss: `miss` is the appended suffix, not the whole request.
"""

import collections
import glob
import json
import os
import re
import sys

USAGE_KEYS = ("hit", "miss", "out", "reasoning_c", "cost")


def load(run):
    turns, header = [], []
    with open(os.path.join(run, "record.jsonl"), encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line).get("data") or {}
            if "calls" in r:
                turns.append(r)
            else:
                header.append(r)
    return turns, header


def tokens(turns):
    """hit/miss/out/reasoning_c/cost summed over the record's usage events."""
    usage = collections.Counter()
    for t in turns:
        u = t.get("usage") or {}
        for k in USAGE_KEYS:
            v = u.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                usage[k] = round(usage[k] + v, 6)
    usage["prompt"] = usage["hit"] + usage["miss"]
    return dict(usage)


def failures(calls):
    fails, examples = collections.Counter(), {}
    for c in calls:
        head = (c.get("observation") or "").split("\n", 1)[0]
        if head.startswith("err") or (head.startswith("exit=") and not head.startswith("exit=0")):
            key = (c["name"], head[:90])
            fails[key] += 1
            examples.setdefault(key, (c.get("args") or "")[:300])
    return fails, examples


def repeated_exec(calls):
    seen = collections.Counter()
    for c in calls:
        if c["name"] != "exec":
            continue
        try:
            a = json.loads(c.get("args") or "{}")
        except ValueError:
            continue
        seen[json.dumps(a.get("argv") or a.get("cmd"))] += 1
    return [(k, n) for k, n in seen.items() if n > 1]


def hot_paths(calls):
    paths = collections.Counter()
    for c in calls:
        m = re.search(r"sed -n '[0-9,]+p' (\S+)|cat (\S+)", c.get("args") or "")
        if m:
            paths[m.group(1) or m.group(2)] += 1
    return [(p, n) for p, n in paths.items() if n > 1]


def report(run):
    """One deterministic dict; the text renderer is a projection of it."""
    turns, _ = load(run)
    calls = [c for t in turns for c in t["calls"]]
    use = tokens(turns)
    per_call = max(1, len(calls))
    argb, obsb = collections.Counter(), collections.Counter()
    for c in calls:
        argb[c["name"]] += len(c.get("args") or "")
        obsb[c["name"]] += c.get("bytes") or len(c.get("observation") or "")
    fails, examples = failures(calls)
    rep, hot = repeated_exec(calls), hot_paths(calls)
    return {
        "schema": "loop-call-audit/1",
        "run": os.path.basename(os.path.normpath(run)),
        "turns": len(turns),
        "calls": len(calls),
        "tokens": dict(use, prompt_per_call=round(use["prompt"] / per_call),
                       out_per_call=round(use["out"] / per_call, 1)),
        "names": dict(collections.Counter(c["name"] for c in calls)),
        "arg_bytes": dict(argb),
        "obs_bytes": dict(obsb),
        "fail_kinds": len(fails),
        "fails": sum(fails.values()),
        "fails_top": [{"name": n, "head": h, "count": k, "sent": examples[(n, h)]}
                      for (n, h), k in fails.most_common(12)],
        "repeated_exec": len(rep),
        "repeated_extra_calls": sum(n - 1 for _, n in rep),
        "repeated_top": [{"call": k[:120], "count": n}
                         for k, n in sorted(rep, key=lambda x: -x[1])[:8]],
        "hot_paths": len(hot),
        "refetches": sum(n - 1 for _, n in hot),
        "chars": {"reasoning": sum(len(t.get("reasoning") or "") for t in turns),
                  "text": sum(len(t.get("text") or "") for t in turns),
                  "tool_args": sum(len(c.get("args") or "") for c in calls)},
    }


def render(r):
    t = r["tokens"]
    out = [f"run={r['run']} turns={r['turns']} calls={r['calls']}",
           f"tokens hit={t['hit']} miss={t['miss']} prompt={t['prompt']} "
           f"out={t['out']} reasoning_c={t['reasoning_c']} cost={t['cost']} "
           f"(prompt/call={t['prompt_per_call']} out/call={t['out_per_call']})",
           f"names {r['names']}",
           f"arg_bytes {r['arg_bytes']}",
           f"obs_bytes {r['obs_bytes']}",
           f"fail_kinds={r['fail_kinds']} fails={r['fails']}"]
    for f in r["fails_top"]:
        out += [f"  x{f['count']} {f['name']} {f['head']}",
                f"      sent: {f['sent']}"]
    out.append(f"repeated_exec={r['repeated_exec']} "
               f"extra_calls={r['repeated_extra_calls']}")
    for row in r["repeated_top"]:
        out.append(f"  x{row['count']} {row['call']}")
    out.append(f"hot_paths={r['hot_paths']} refetches={r['refetches']}")
    c = r["chars"]
    out.append(f"chars reasoning={c['reasoning']} text={c['text']} "
               f"tool_args={c['tool_args']}")
    return "\n".join(out)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    run = [a for a in argv if a != "--json"]
    if not run:
        found = sorted(glob.glob(os.path.join(".logs", "runs", "*")))
        if not found:
            print("err no runs under .logs/runs", file=sys.stderr)
            return 1
        run = [found[-1]]
    try:
        r = report(run[0])
    except OSError as e:
        print(f"err {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(json.dumps(r, sort_keys=True) if as_json else render(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
