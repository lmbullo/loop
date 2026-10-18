import json

from . import record, recschema


def parse(raw, run_id):
    events = []
    pos, size = 0, len(raw)
    while pos < size:
        nl = raw.find(b"\n", pos)
        if nl < 0:
            return events, size - pos
        line = raw[pos:nl]
        start = pos
        pos = nl + 1
        if not line.strip():
            raise record.Corrupt(f"run={run_id} byte={start}: blank line")
        try:
            ev = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise record.Corrupt(f"run={run_id} byte={start}: {type(e).__name__}: {e}")
        recschema.check(ev, run_id, len(events) + 1)
        events.append(ev)
    return events, 0


def read_raw(path, run_id):
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        return [], 0
    return parse(raw, run_id)


def state(events):
    if not events:
        return "empty"
    if events[-1]["type"] == "end":
        return "complete"
    return "interrupted"


def read(run_id):
    path = record.record_path(run_id)
    events, torn = read_raw(path, run_id)
    return {"run_id": run_id, "path": path, "events": events,
            "torn_tail_bytes": torn, "seq": events[-1]["seq"] if events else 0,
            "state": state(events)}


def turns(events):
    return sum(1 for e in events if e["type"] == "turn")


def summary_row(rec):
    events = rec["events"]
    start = next((e["data"] for e in events if e["type"] == "run_start"), {})
    end = next((e["data"] for e in events if e["type"] == "end"), {})
    return {"run_id": rec["run_id"], "state": rec["state"], "seq": rec["seq"],
            "turns": turns(events), "ts": events[-1]["ts"] if events else None,
            "entrypoint": start.get("entrypoint"), "task": start.get("task"),
            "finish": end.get("finish"), "cost": end.get("cost"),
            "torn_tail_bytes": rec["torn_tail_bytes"]}


def scan():
    rows = []
    for run_id in record.ids():
        try:
            rows.append(summary_row(read(run_id)))
        except record.Corrupt as e:
            rows.append({"run_id": run_id, "state": "corrupt", "seq": 0, "turns": 0,
                         "ts": None, "entrypoint": None, "task": None,
                         "finish": None, "cost": None, "detail": str(e)[:300]})
    return rows
