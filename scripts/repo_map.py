#!/usr/bin/env python3
"""Print a compact, manifest-driven map of the tree for agents."""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "manifest.json")


def load():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def line_count(path):
    try:
        with open(os.path.join(ROOT, path), "rb") as f:
            return len(f.read().decode("utf-8", "replace").splitlines())
    except OSError:
        return -1


def build(manifest):
    files = []
    for entry in manifest.get("files") or []:
        row = dict(entry)
        row["lines"] = line_count(entry["path"])
        files.append(row)
    entrypoints = []
    for entry in manifest.get("entrypoints") or []:
        entrypoints.append({"id": entry.get("id"), "module": entry.get("module"),
                            "network": bool(entry.get("network")),
                            "role": entry.get("role")})
    checks = []
    for check in manifest.get("checks") or []:
        checks.append({"id": check.get("id"), "network": bool(check.get("network")),
                       "argv": check.get("argv"), "expect_exit": check.get("expect_exit")})
    return {"schema": "loop-map/1", "root": ROOT, "files": files,
            "entrypoints": entrypoints, "checks": checks,
            "scenarios": manifest.get("scenarios") or []}


def text(doc):
    by_kind = {}
    for row in doc["files"]:
        by_kind.setdefault(row.get("kind", "?"), []).append(row)
    out = [f"root={doc['root']}"]
    for kind in sorted(by_kind):
        rows = sorted(by_kind[kind], key=lambda r: r["path"])
        out.append(f"\n[{kind}] {len(rows)}")
        for row in rows:
            out.append(f"  {row['lines']:>5}  {row['path']}  {row.get('role', '')}")
    out.append(f"\n[entrypoints] {len(doc['entrypoints'])}")
    for row in sorted(doc["entrypoints"], key=lambda r: r["id"] or ""):
        net = "network" if row["network"] else "offline"
        out.append(f"  {row['id']:<8} {net:<8} {row['module']}  {row['role']}")
    out.append(f"\n[checks] {len(doc['checks'])}")
    for row in doc["checks"]:
        net = "network" if row["network"] else "offline"
        out.append(f"  {row['id']:<18} {net:<8} exit={row['expect_exit']}")
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--kind", action="append", default=[], metavar="KIND")
    args = parser.parse_args(argv)
    doc = build(load())
    if args.kind:
        wanted = set(args.kind)
        doc["files"] = [row for row in doc["files"] if row.get("kind") in wanted]
    if args.json:
        print(json.dumps(doc, indent=1, sort_keys=True))
    else:
        print(text(doc), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
