import time

from . import queue, record, recread, registry

DONE_LIMIT = 50


def summary(run_id):
    try:
        rec = recread.read(run_id)
    except record.Corrupt as e:
        return {"id": run_id, "state": "corrupt", "turns": 0, "cost": None,
                "finish": None, "detail": str(e)[:200], "seq": 0}
    except record.Missing:
        return {"id": run_id, "state": "queued", "turns": 0, "cost": None,
                "finish": None, "detail": "", "seq": 0}
    events = rec["events"]
    turns = sum(1 for e in events if e["type"] == "turn")
    cost = sum(float((e["data"].get("usage") or {}).get("cost") or 0.0)
               for e in events if e["type"] == "turn")
    detail = ""
    if events:
        last = events[-1]
        if last["type"] == "end":
            return {"id": run_id, "state": "complete", "turns": turns,
                    "cost": float(last["data"].get("cost") or cost),
                    "finish": last["data"].get("finish"), "detail": "", "seq": rec["seq"]}
        if last["type"] == "interrupted":
            detail = str(last["data"].get("reason") or "")
        elif last["type"] == "error":
            detail = str(last["data"].get("text") or "")[:200]
    return {"id": run_id, "state": "running", "turns": turns, "cost": cost,
            "finish": None, "detail": detail, "seq": rec["seq"]}


def recent_done(rows, skip=None):
    """Terminal runs newest first; the current run is not listed as done."""
    out = []
    for row in reversed(rows):
        if skip and row["run_id"] == skip:
            continue
        out.append({"id": row["run_id"], "task": row.get("task"),
                    "state": row["state"], "turns": row.get("turns") or 0,
                    "cost": row.get("cost"), "finish": row.get("finish"),
                    "detail": row.get("detail") or ""})
        if len(out) >= DONE_LIMIT:
            break
    return out


def snapshot(snap, live, reconciled):
    by_run = {w.get("run_id"): w for w in live}
    current = snap.get("current")
    run = None
    if current:
        run = summary(current["run_id"])
        run["task"] = current.get("task")
        run["pid"] = (by_run.get(current["run_id"]) or {}).get("pid") or current.get("worker_pid")
        run["state"] = "running" if by_run.get(current["run_id"]) else run["state"]
    elif live:
        w = live[0]
        run = summary(w["run_id"])
        run["task"] = w.get("task")
        run["pid"] = w.get("pid")
        run["state"] = "running"
    rows = recread.scan()
    done = recent_done(rows, run["id"] if run else None)
    last = done[0] if done else None
    total = sum(float(r.get("cost") or 0.0) for r in rows)
    waiting = [{"id": it["id"], "run_id": it.get("run_id"), "text": it.get("task"),
                "state": "queued", "created_at": it.get("created_at")}
               for it in snap["items"]]
    return {"k": "snapshot", "tree": registry.tree(), "daemon": {"state": "running"},
            "current": run, "last": last, "done": done, "queue": waiting,
            "waiting": len(waiting),
            "costs": {"current": None if run is None else run.get("cost"),
                      "total": round(total, 6)},
            "workers_live": len(live), "version": int(time.time() * 10) + snap["seq"],
            "reconciled": list(reconciled)}


def status(daemon, live):
    snap = snapshot(queue.snapshot(), live, daemon.reconciled)
    rows = recread.scan()
    return {"k": "status", "pid": daemon.pid, "tree": daemon.tree,
            "address": "unix:" + registry.sock_path(),
            "started_at": registry.iso(daemon.started),
            "uptime_s": int(time.time() - daemon.started), "state": "running",
            "runs_on_disk": len(rows),
            "runs_interrupted": sum(1 for r in rows if r["state"] != "complete"),
            "latest_run": rows[-1]["run_id"] if rows else None,
            "reconciled": list(daemon.reconciled),
            "queue_waiting": snap["waiting"], "workers_live": len(live),
            "workers": [{"run_id": w.get("run_id"), "pid": w.get("pid"),
                         "state": w.get("state")} for w in live],
            "run": snap["current"]}
