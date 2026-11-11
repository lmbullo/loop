#!/usr/bin/env python3
"""Local environment health for agents. Never starts the control plane."""
import importlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def load_manifest():
    with open(os.path.join(ROOT, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def probe_imports(manifest):
    for entry in manifest.get("entrypoints") or []:
        module = importlib.import_module(entry["module"])
        if not callable(getattr(module, entry.get("function", "main"), None)):
            raise RuntimeError(f"{entry['id']} has no callable main")


def daemon_state():
    from harness import regprobe, regstore
    entry = regstore.current()
    if not entry:
        return "warn", "no registered daemon for this tree"
    state, detail = regprobe.probe(entry)
    return ("ok", f"{state} pid={entry.get('pid')} addr={entry.get('address')}") \
        if state == "running" else ("warn", f"{state}: {detail}")


def worker_state():
    from harness import workers
    rows = workers.live_entries()
    if not rows:
        return "ok", "no live workers"
    return "warn", ", ".join(f"{w.get('run_id')} pid={w.get('pid')}" for w in rows)


def auth_state():
    from harness import auth
    try:
        auth.api_key()
    except (OSError, KeyError, TypeError, ValueError) as e:
        return "warn", f"no credentials ({type(e).__name__}); offline work only"
    return "ok", f"credentials loaded from {auth.auth_file()}"


def git_state():
    try:
        proc = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "warn", f"git unavailable: {type(e).__name__}"
    dirty = [line for line in proc.stdout.splitlines() if line.strip()]
    return ("warn" if dirty else "ok", f"dirty_files={len(dirty)}")


def main(argv=None):
    checks = []
    checks.append(("ok", f"python={sys.version.split()[0]}"))
    if sys.version_info < (3, 8):
        checks[-1] = ("FAIL", f"python={sys.version.split()[0]} needs >=3.8")
    try:
        manifest = load_manifest()
        checks.append(("ok", f"manifest entries={len(manifest.get('entrypoints') or [])} "
                             f"files={len(manifest.get('files') or [])}"))
    except (OSError, ValueError, KeyError) as e:
        checks.append(("FAIL", f"manifest unreadable: {type(e).__name__}: {e}"))
        manifest = None
    if manifest:
        try:
            probe_imports(manifest)
            checks.append(("ok", "all entrypoint modules import"))
        except Exception as e:
            checks.append(("FAIL", f"entrypoint import: {type(e).__name__}: {e}"))
        deps = (manifest.get("runtime") or {}).get("third_party_deps") or []
        checks.append(("ok" if not deps else "warn", f"third_party_deps={deps or []}"))
        checks.append(worker_state())
        checks.append(daemon_state())
        checks.append(auth_state())
    else:
        checks.append(("warn", "skipping runtime probes"))
    checks.append(git_state())
    failed = 0
    for level, text in checks:
        if level == "FAIL":
            failed += 1
        print(f"{level:<4} {text}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
