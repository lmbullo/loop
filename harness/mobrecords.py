"""Read one workspace's durable records without changing process globals.

A workspace is an independent loop tree.  Its records, worker registry and
queue live under its own state directory, so the mobile bridge must never use
the served daemon's paths when it reports another workspace.  Everything here
takes an explicit tree; nothing falls back to the current process environment.
"""

import os

from . import record, recread, regprobe, regstore, runlog

DONE_LIMIT = 50
TERMINAL = {"complete", "interrupted", "error", "corrupt", "done"}


def state_dir(tree, entry=None):
    value = (entry or {}).get("runs")
    if isinstance(value, str) and value.strip():
        return os.path.realpath(os.path.abspath(os.path.expanduser(value)))
    return os.path.join(os.path.realpath(tree), ".logs")


def runs_dir(tree, entry=None):
    return os.path.join(state_dir(tree, entry), "runs")


def entry_from_local(tree):
    """Read a workspace's own registry mirror when the global one is absent."""
    data = regstore.read_json(os.path.join(state_dir(tree), "registry.json"), None)
    servers = data.get("servers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        return None
    entry = servers.get(os.path.realpath(tree))
    return entry if isinstance(entry, dict) else None


def worker_entries(tree, entry=None):
    directory = os.path.join(state_dir(tree, entry), "workers")
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []
    rows = []
    for name in names:
        if not name.endswith(".json"):
            continue
        row = regstore.read_json(os.path.join(directory, name), None)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def worker_live(entry):
    if not isinstance(entry, dict) or entry.get("state") != "running":
        return False
    pid = entry.get("pid")
    if not regprobe.alive(pid):
        return False
    stamp = entry.get("proc_start")
    return not stamp or regprobe.fingerprint(pid) in (None, stamp)


def live_workers(tree, entry=None):
    return [row for row in worker_entries(tree, entry) if worker_live(row)]


def _cost(events):
    total = sum(float((ev["data"].get("usage") or {}).get("cost") or 0.0)
                for ev in events if ev["type"] == "turn")
    for ev in events:
        if ev["type"] == "end":
            end = ev["data"]
            return float(end.get("cost") or total), end.get("finish")
    return total, None


def _row(run_id, events, torn, live):
    start = next((ev["data"] for ev in events if ev["type"] == "run_start"), {})
    end = next((ev["data"] for ev in events if ev["type"] == "end"), {})
    state = recread.state(events)
    if state != "complete" and live:
        state = "running"
    detail = ""
    if events:
        last = events[-1]
        if last["type"] == "interrupted":
            detail = str(last["data"].get("reason") or "")
        elif last["type"] == "error":
            detail = str(last["data"].get("text") or "")[:200]
    cost, finish = _cost(events)
    return {"run_id": run_id, "state": state, "seq": events[-1]["seq"] if events else 0,
            "turns": recread.turns(events), "ts": events[-1]["ts"] if events else None,
            "entrypoint": start.get("entrypoint"), "task": start.get("task"),
            "finish": finish or end.get("finish"), "cost": cost,
            "detail": detail, "torn_tail_bytes": torn}


def scan(tree, entry=None):
    live = {row.get("run_id") for row in live_workers(tree, entry)}
    directory = runs_dir(tree, entry)
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []
    rows = []
    for run_id in names:
        if not record.ID_RE.match(run_id):
            continue
        path = os.path.join(directory, run_id, record.RECORD)
        if not os.path.isfile(path):
            continue
        try:
            events, torn = recread.read_raw(path, run_id)
            rows.append(_row(run_id, events, torn, run_id in live))
        except record.Corrupt as exc:
            rows.append({"run_id": run_id, "state": "corrupt", "seq": 0,
                         "turns": 0, "ts": None, "entrypoint": None, "task": None,
                         "finish": None, "cost": None, "detail": str(exc)[:300]})
    return rows


def recent_done(rows, skip=None):
    if isinstance(skip, str):
        skip = (skip,)
    skip = set(skip or ())
    out = []
    for row in reversed(rows):
        if row.get("run_id") in skip or row.get("state") not in TERMINAL:
            continue
        out.append({"id": row["run_id"], "task": row.get("task"),
                    "state": row["state"], "turns": row.get("turns") or 0,
                    "cost": row.get("cost"), "finish": row.get("finish"),
                    "detail": row.get("detail") or ""})
        if len(out) >= DONE_LIMIT:
            break
    return out


def log(tree, run_id, entry=None):
    path = os.path.join(runs_dir(tree, entry), run_id, record.RECORD)
    try:
        events, torn = recread.read_raw(path, run_id)
    except record.Corrupt as exc:
        return {"id": run_id, "state": "corrupt", "turns": 0, "terminal": True,
                "entries": [{"kind": "error",
                             "text": runlog.one(exc, runlog.TEXT_LIMIT)}]}
    live = any(row.get("run_id") == run_id and worker_live(row)
               for row in worker_entries(tree, entry))
    state = recread.state(events)
    if state != "complete" and live:
        state = "running"
    last = events[-1]["type"] if events else ""
    return {"id": run_id, "state": state, "turns": recread.turns(events),
            "terminal": state == "complete" or last in runlog.TAIL_KINDS,
            "entries": runlog.entries(events, torn)}


def snapshot(tree, entry=None, daemon=None):
    """Build a snapshot from durable bytes; never claim a live queue."""
    workers = live_workers(tree, entry)
    rows = scan(tree, entry)
    by_run = {row["run_id"]: row for row in rows}
    current = None
    if workers:
        wanted = workers[0].get("run_id")
        source = by_run.get(wanted)
        if source:
            current = {"id": wanted, "task": workers[0].get("task") or source.get("task"),
                       "state": "running", "turns": source.get("turns") or 0,
                       "cost": source.get("cost"), "finish": None,
                       "detail": source.get("detail") or ""}
    done = recent_done(rows, current["id"] if current else None)
    total = sum(float(row.get("cost") or 0.0) for row in rows)
    daemon = daemon or {"state": "offline", "detail": "daemon not running"}
    waiting = []
    return {"k": "snapshot", "tree": os.path.realpath(tree), "daemon": daemon,
            "current": current, "last": done[0] if done else None, "done": done,
            "queue": waiting, "waiting": 0, "queue_known": False,
            "costs": {"current": None if current is None else current.get("cost"),
                      "total": round(total, 6)},
            "workers_live": len(workers),
            "workers": [{"run_id": w.get("run_id"), "pid": w.get("pid"),
                         "state": w.get("state")} for w in workers],
            "version": 0, "reconciled": [], "source": "disk"}
