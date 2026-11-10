#!/usr/bin/env python3
"""Run the offline checks declared in manifest.checks[].

No shell is used: each check's argv is executed literally from the repo root.
Checks with network=true are never selected. Checks that need the control
plane can be skipped with --skip-server.
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "manifest.json")
SERVER_TOKENS = ("server", "api")


def load():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def needs_server(check):
    return any(token in (check.get("argv") or []) for token in SERVER_TOKENS)


def select(checks, only, skip_server):
    out = []
    for check in checks:
        if check.get("network"):
            continue
        if skip_server and needs_server(check):
            continue
        if only and check.get("id") not in only:
            continue
        out.append(check)
    return out


def tail(text, lines=12, limit=4000):
    text = (text or "").strip()
    if len(text) > limit:
        text = text[-limit:]
    rows = text.splitlines()
    return "\n".join(rows[-lines:])


def run_one(check, timeout):
    argv = [str(v) for v in check["argv"]]
    start = time.time()
    try:
        proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                              timeout=timeout)
        code, out, err = proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError as e:
        code, out, err = 127, "", f"{type(e).__name__}: {e}"
    except subprocess.TimeoutExpired as e:
        code, out, err = "TIMEOUT", e.stdout or "", e.stderr or ""
    return {"id": check.get("id"), "argv": argv, "expect": int(check["expect_exit"]),
            "code": code, "ok": code == check["expect_exit"],
            "seconds": round(time.time() - start, 3),
            "stdout": out if isinstance(out, str) else out.decode("utf-8", "replace"),
            "stderr": err if isinstance(err, str) else err.decode("utf-8", "replace")}


def render(row):
    mark = "ok  " if row["ok"] else "FAIL"
    return f"{mark} {row['id']:<18} {row['seconds']:>7.3f}s exit={row['code']}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list selected checks")
    parser.add_argument("--only", action="append", default=[], metavar="ID")
    parser.add_argument("--skip-server", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args(argv)
    manifest = load()
    checks = select(manifest.get("checks") or [], set(args.only), args.skip_server)
    if not checks:
        print("err no checks selected", file=sys.stderr)
        return 2
    if args.list:
        for check in checks:
            print(f"{check['id']:<18} exit={check['expect_exit']} "
                  f"network={str(bool(check.get('network'))).lower()} "
                  + " ".join(str(v) for v in check["argv"]))
        return 0
    rows = []
    for check in checks:
        row = run_one(check, args.timeout)
        rows.append(row)
        if not args.json:
            print(render(row))
            if not row["ok"]:
                for text in (row["stdout"], row["stderr"]):
                    if text.strip():
                        print(tail(text))
        if not row["ok"] and args.fail_fast:
            break
    failed = [row for row in rows if not row["ok"]]
    summary = {"schema": "loop-verify/1", "total": len(rows),
               "passed": len(rows) - len(failed), "failed": len(failed),
               "skipped": len((manifest.get("checks") or [])) - len(checks),
               "results": rows}
    if args.json:
        print(json.dumps(summary, indent=1, sort_keys=True))
    else:
        print(f"summary: passed={summary['passed']} failed={summary['failed']} "
              f"selected={summary['total']} skipped={summary['skipped']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
