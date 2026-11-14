import json
import os
import sys

MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")
INDEX_SCHEMA = "loop-index/1"


def load():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def manifest_scenarios(manifest):
    return [s["id"] for s in manifest.get("scenarios", [])]


def _fields(row, names):
    return {name: row[name] for name in names if name in row}


def _entry(row):
    out = _fields(row, ("id", "module", "function", "network", "args_usage", "invoke", "role"))
    out["subcommands"] = [_fields(s, ("id", "usage", "role")) for s in row.get("subcommands", [])]
    return out


def agent_index(manifest):
    spec = manifest.get("agent_index") or {}
    files = manifest.get("files") or []
    return {
        "schema": spec.get("schema", INDEX_SCHEMA),
        "manifest": "manifest.json",
        "bootstrap": spec.get("argv", ["python3", "run.py", "--json"]),
        "purpose": manifest.get("purpose") or {},
        "runtime": manifest.get("runtime") or {},
        "entrypoints": [_entry(e) for e in manifest.get("entrypoints") or []],
        "checks": [
            _fields(c, ("id", "argv", "expect_exit", "network", "note"))
            for c in manifest.get("checks") or []
        ],
        "scenarios": [
            _fields(s, ("id", "sim", "fixture", "steps", "purpose"))
            for s in manifest.get("scenarios") or []
        ],
        "docs": [_fields(e, ("path", "role")) for e in files if e.get("kind") == "doc"],
        "invariants": manifest.get("invariants") or [],
        "env": manifest.get("env") or [],
        "layout": manifest.get("layout") or {},
        "record": _record(manifest.get("record") or {}),
        "wire": manifest.get("wire") or {},
    }


def _record(record):
    events = record.get("events") or {}
    return {
        "schema": record.get("schema"),
        "version": record.get("version"),
        "path": record.get("path"),
        "events": {name: bool(spec.get("terminal")) for name, spec in events.items()},
        "view_schema": (record.get("view") or {}).get("schema"),
    }


def usage(manifest):
    lines = ["usage: python3 run.py <command> [args]", "", manifest["purpose"]["summary"], ""]
    for e in manifest["entrypoints"]:
        net = "network" if e["network"] else "offline"
        lines.append(f"  {e['id']:<6} {e['args_usage']:<34} {net:<8} {e['role']}")
        for s in e.get("subcommands", []):
            lines.append(f"         {e['id']} {s['id']:<9}{s['usage']:<14} {s['role']}")
    lines += ["", "scenarios: " + ", ".join(manifest_scenarios(manifest))]
    lines += ["", "index: python3 run.py --json  (" + INDEX_SCHEMA + ", one compact line)"]
    lines += ["", "contract: manifest.json"]
    return "\n".join(lines)


def main(argv):
    try:
        manifest = load()
    except (OSError, ValueError, KeyError) as e:
        print(f"err manifest unreadable {MANIFEST}: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    entries = {e["id"]: e for e in manifest["entrypoints"]}
    if not argv:
        print(usage(manifest), file=sys.stderr)
        return 2
    if argv[0] == "--json":
        if len(argv) > 1:
            print("err --json takes no arguments", file=sys.stderr)
            return 2
        print(json.dumps(agent_index(manifest), sort_keys=True, separators=(",", ":")))
        return 0
    if argv[0] in ("-h", "--help", "help"):
        print(usage(manifest))
        return 0
    entry = entries.get(argv[0])
    if entry is None:
        print(f"err unknown command {argv[0]!r}\n{usage(manifest)}", file=sys.stderr)
        return 2
    module = __import__(entry["module"], fromlist=["main"])
    return int(module.main(argv[1:]) or 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
