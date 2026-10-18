import json
import os

from . import config, record

MANIFEST = os.path.join(config.ROOT, "manifest.json")
ENVELOPE = ("schema", "v", "run_id", "seq", "ts", "type", "data")
_doc = None


def doc():
    global _doc
    if _doc is None:
        with open(MANIFEST, encoding="utf-8") as f:
            manifest = json.load(f)
        _doc = manifest["record"]
    return _doc


def schema():
    return doc()["schema"]


def version():
    return int(doc()["version"])


def view_doc():
    return doc()["view"]


def _valid(value, spec, types, path):
    nullable = spec.endswith("|null")
    if nullable and value is None:
        return
    base = spec[:-5] if nullable else spec
    if base == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise record.Corrupt(f"{path}: expected int, got {type(value).__name__}")
    elif base == "num":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise record.Corrupt(f"{path}: expected number, got {type(value).__name__}")
    elif base == "str":
        if not isinstance(value, str):
            raise record.Corrupt(f"{path}: expected str, got {type(value).__name__}")
    elif base == "bool":
        if not isinstance(value, bool):
            raise record.Corrupt(f"{path}: expected bool, got {type(value).__name__}")
    elif base.startswith("list<") and base.endswith(">"):
        if not isinstance(value, list):
            raise record.Corrupt(f"{path}: expected list, got {type(value).__name__}")
        for idx, item in enumerate(value):
            _valid(item, base[5:-1], types, f"{path}[{idx}]")
    elif base in types:
        if not isinstance(value, dict) or set(value) != set(types[base]):
            raise record.Corrupt(f"{path}: expected fields {sorted(types[base])}")
        for key, sub in types[base].items():
            _valid(value[key], sub, types, f"{path}.{key}")
    else:
        raise record.Corrupt(f"{path}: schema type {spec!r} is not declared")


def check(ev, run_id, seq):
    if not isinstance(ev, dict) or set(ev) != set(ENVELOPE):
        raise record.Corrupt(f"run={run_id} seq={seq}: envelope fields {sorted(ev) if isinstance(ev, dict) else type(ev).__name__}")
    d = doc()
    if ev["schema"] != d["schema"]:
        raise record.Corrupt(f"run={run_id} seq={seq}: schema {ev['schema']!r}")
    if ev["v"] != int(d["version"]) or isinstance(ev["v"], bool):
        raise record.Corrupt(f"run={run_id} seq={seq}: version {ev['v']!r}")
    if ev["run_id"] != run_id:
        raise record.Corrupt(f"run={run_id} seq={seq}: run_id {ev['run_id']!r}")
    if ev["seq"] != seq or isinstance(ev["seq"], bool):
        raise record.Corrupt(f"run={run_id} seq={seq}: seq {ev['seq']!r} (expected {seq})")
    if not isinstance(ev["ts"], str):
        raise record.Corrupt(f"run={run_id} seq={seq}: ts not a string")
    spec = d["events"].get(ev["type"])
    if not isinstance(spec, dict):
        raise record.Corrupt(f"run={run_id} seq={seq}: unknown event type {ev['type']!r}")
    fields = spec["data"]
    data = ev["data"]
    if not isinstance(data, dict) or set(data) != set(fields):
        raise record.Corrupt(f"run={run_id} seq={seq}: {ev['type']} payload fields {sorted(data) if isinstance(data, dict) else type(data).__name__} != {sorted(fields)}")
    for key, sub in fields.items():
        _valid(data[key], sub, d["types"], f"{ev['type']}.{key}")


def event(run_id, seq, kind, data, ts=None):
    ev = {"schema": schema(), "v": version(), "run_id": run_id, "seq": int(seq),
          "ts": ts or record.utc(), "type": kind, "data": data}
    check(ev, run_id, int(seq))
    return ev
