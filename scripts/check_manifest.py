#!/usr/bin/env python3
"""Validate manifest.json against the tree and the importable entry points."""
import importlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
MANIFEST = os.path.join(ROOT, "manifest.json")
KINDS = {"fixture", "module", "manifest", "record", "entry", "data",
         "doc", "test", "tool", "config", "ci"}
SCALARS = {"int", "num", "str", "bool"}
SOURCE_DIRS = ("harness", "tui", "tests", "scripts")


def add(errors, text):
    errors.append(text)


def rel_ok(path):
    return isinstance(path, str) and path and not os.path.isabs(path) and ".." not in path.split("/")


def local(path):
    return os.path.join(ROOT, path)


def check_files(manifest, errors):
    paths = set()
    files = manifest.get("files")
    if not isinstance(files, list):
        add(errors, "files is not a list")
        return paths
    for index, entry in enumerate(files):
        if not isinstance(entry, dict):
            add(errors, f"files[{index}] is not an object")
            continue
        path, kind, role = entry.get("path"), entry.get("kind"), entry.get("role")
        if not rel_ok(path):
            add(errors, f"files[{index}] bad path {path!r}")
            continue
        if path in paths:
            add(errors, f"duplicate path {path}")
        paths.add(path)
        if kind not in KINDS:
            add(errors, f"{path} unknown kind {kind!r}")
        if not isinstance(role, str) or not role.strip():
            add(errors, f"{path} missing role")
        if not os.path.isfile(local(path)):
            add(errors, f"{path} missing on disk")
    for name in SOURCE_DIRS:
        base = local(name)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                path = os.path.relpath(os.path.join(dirpath, filename), ROOT)
                if path.replace(os.sep, "/") not in paths:
                    add(errors, f"unregistered source {path}")
    return paths


def check_entrypoints(manifest, errors):
    ids = set()
    for entry in manifest.get("entrypoints") or []:
        eid = entry.get("id")
        if not eid or eid in ids:
            add(errors, f"entrypoint bad or duplicate id {eid!r}")
            continue
        ids.add(eid)
        module_name = entry.get("module")
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            add(errors, f"entry {eid}: import {module_name}: {type(e).__name__}: {e}")
            continue
        function = entry.get("function", "main")
        if not callable(getattr(module, function, None)):
            add(errors, f"entry {eid}: {module_name}.{function} is not callable")
        if entry.get("network") not in (True, False):
            add(errors, f"entry {eid}: network must be bool")
    return ids


def type_ok(spec, types):
    if not isinstance(spec, str):
        return False
    base = spec[:-5] if spec.endswith("|null") else spec
    if base in SCALARS or base in types:
        return True
    return base.startswith("list<") and base.endswith(">") and type_ok(base[5:-1], types)


def check_record(manifest, errors):
    record = manifest.get("record")
    if not isinstance(record, dict):
        add(errors, "record is not an object")
        return
    if not record.get("schema") or not isinstance(record.get("version"), int):
        add(errors, "record needs schema and int version")
    types = record.get("types")
    events = record.get("events")
    if not isinstance(types, dict) or not isinstance(events, dict):
        add(errors, "record.types and record.events must be objects")
        return
    for name, fields in types.items():
        if not isinstance(fields, dict):
            add(errors, f"record.types.{name} is not an object")
            continue
        for field, spec in fields.items():
            if not type_ok(spec, types):
                add(errors, f"record.types.{name}.{field} bad type {spec!r}")
    for name, spec in events.items():
        if not isinstance(spec, dict) or not isinstance(spec.get("data"), dict):
            add(errors, f"record.events.{name} malformed")
            continue
        for field, sub in spec["data"].items():
            if not type_ok(sub, types):
                add(errors, f"record.events.{name}.{field} bad type {sub!r}")
    if not any(spec.get("terminal") for spec in events.values() if isinstance(spec, dict)):
        add(errors, "record has no terminal event")


def check_checks(manifest, errors):
    ids = set()
    for check in manifest.get("checks") or []:
        cid = check.get("id")
        if not cid or cid in ids:
            add(errors, f"check bad or duplicate id {cid!r}")
            continue
        ids.add(cid)
        argv = check.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
            add(errors, f"check {cid}: argv must be a non-empty list of strings")
        if not isinstance(check.get("expect_exit"), int):
            add(errors, f"check {cid}: expect_exit must be int")
        if check.get("network") not in (True, False):
            add(errors, f"check {cid}: network must be bool")


def check_scenarios(manifest, errors):
    files = {entry["path"] for entry in manifest.get("files") or []
             if isinstance(entry, dict) and entry.get("kind") == "data"}
    for row in manifest.get("scenarios") or []:
        sid = row.get("id")
        path = f"scenarios/{sid}.json"
        if path not in files:
            add(errors, f"scenario {sid}: {path} not registered as data")
            continue
        try:
            with open(local(path), encoding="utf-8") as f:
                scenario = json.load(f)
        except (OSError, ValueError) as e:
            add(errors, f"scenario {sid}: {type(e).__name__}: {e}")
            continue
        if scenario.get("sim") != row.get("sim"):
            add(errors, f"scenario {sid}: sim {scenario.get('sim')!r} != {row.get('sim')!r}")
        if len(scenario.get("steps") or []) != row.get("steps"):
            add(errors, f"scenario {sid}: steps {len(scenario.get('steps') or [])} != {row.get('steps')}")
        fixture = scenario.get("fixture", row.get("fixture", "ws1"))
        if not os.path.isdir(local(os.path.join("fixtures", fixture))):
            add(errors, f"scenario {sid}: fixture {fixture} missing")


def main(argv=None):
    errors = []
    try:
        with open(MANIFEST, encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError) as e:
        print(f"err manifest {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if manifest.get("schema") != "harness-manifest/1":
        add(errors, f"schema {manifest.get('schema')!r}")
    for key in ("purpose", "runtime", "entrypoints", "files", "record",
                "checks", "layout", "env", "scenarios", "agent_index"):
        if key not in manifest:
            add(errors, f"missing top-level {key}")
    paths = check_files(manifest, errors)
    check_entrypoints(manifest, errors)
    check_record(manifest, errors)
    check_checks(manifest, errors)
    check_scenarios(manifest, errors)
    if errors:
        for text in errors:
            print(f"err {text}", file=sys.stderr)
        print(f"failed manifest errors={len(errors)}", file=sys.stderr)
        return 1
    print(f"ok manifest files={len(paths)} entrypoints={len(manifest['entrypoints'])} "
          f"checks={len(manifest['checks'])} scenarios={len(manifest['scenarios'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
