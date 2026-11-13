import json
import os
import sys

MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")


def load():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def manifest_scenarios(manifest):
    return [s["id"] for s in manifest.get("scenarios", [])]


def usage(manifest):
    lines = ["usage: python3 run.py <command> [args]", "", manifest["purpose"]["summary"], ""]
    for e in manifest["entrypoints"]:
        net = "network" if e["network"] else "offline"
        lines.append(f"  {e['id']:<6} {e['args_usage']:<34} {net:<8} {e['role']}")
        for s in e.get("subcommands", []):
            lines.append(f"         {e['id']} {s['id']:<9}{s['usage']:<14} {s['role']}")
    lines += ["", "scenarios: " + ", ".join(manifest_scenarios(manifest))]
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
