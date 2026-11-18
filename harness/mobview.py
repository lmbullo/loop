"""Workspace-scoped views for the mobile bridge.

Each read names one workspace.  A live daemon is asked through the existing
Unix socket; a stopped or unreachable daemon falls back to that workspace's
durable record bytes and explicitly reports that its queue is unknown.
"""

import os

from . import mobpaths, mobrecords, mobworkspaces, record, recread, runlog
from .moberr import ApiError

SCHEMA = "loop-mobile/1"


def _mobile(roots, target, aggregate=False, source="daemon"):
    return {"roots": mobpaths.normalize_roots(roots), "root": target,
            "scope": "aggregate" if aggregate else "workspace",
            "aggregate": bool(aggregate), "source": source}


def _offline(target, status):
    daemon = {"state": status["state"], "detail": status["detail"],
              "stale": bool(status.get("stale"))}
    return mobrecords.snapshot(target, status.get("entry"), daemon)


def _target(daemon, roots, value):
    if value:
        return mobpaths.owner(value, roots)
    return mobpaths.real(daemon.tree)


def snapshot(daemon, roots, value=None):
    roots = mobpaths.normalize_roots(roots)
    selected = mobpaths.select_root(value, roots) if value else mobpaths.real(daemon.tree)
    target = mobpaths.owner(selected, roots) if value else selected
    source = "daemon"
    if target == mobpaths.real(daemon.tree):
        data = daemon.snapshot_dict()
    else:
        status = mobworkspaces.daemon_state(target)
        if status["state"] == "running":
            try:
                data = mobworkspaces.call(target, {"cmd": "snapshot"})
            except mobworkspaces.WorkspaceError as exc:
                status = {"state": "offline", "detail": exc.text,
                          "entry": status.get("entry"), "stale": True}
                data, source = _offline(target, status), "disk"
            else:
                data["tree"] = target
        else:
            data, source = _offline(target, status), "disk"
    data["schema"] = SCHEMA
    data["mobile"] = _mobile(roots, target, source=source)
    data["mobile"]["selected"] = selected
    data["workspace"] = {"name": os.path.basename(target) or target, "path": target,
                         "selected": selected,
                         "state": data.get("daemon", {}).get("state"),
                         "source": source}
    return data


def _summary(path, snap):
    daemon = snap.get("daemon") or {}
    done = snap.get("done") or []
    return {"name": os.path.basename(path) or path, "path": path,
            "state": daemon.get("state", "unknown"),
            "detail": daemon.get("detail", ""),
            "running": 1 if snap.get("current") else 0,
            "queued": len(snap.get("queue") or []), "done": len(done),
            "cost": (snap.get("costs") or {}).get("total"),
            "tree": snap.get("tree"), "source": snap.get("source", "daemon")}


def overview(daemon, roots):
    roots = mobpaths.normalize_roots(roots)
    rows = []
    for path in mobpaths.discover(roots, [daemon.tree]):
        row = _summary(path, snapshot(daemon, roots, path))
        row["can_start"] = row["state"] != "running"
        rows.append(row)
    totals = {"workspaces": len(rows),
              "running": sum(row["running"] for row in rows),
              "queued": sum(row["queued"] for row in rows),
              "done": sum(row["done"] for row in rows),
              "cost": round(sum(float(row.get("cost") or 0.0) for row in rows), 6)}
    return {"schema": SCHEMA, "k": "overview", "aggregate": True,
            "workspaces": rows, "totals": totals,
            "mobile": _mobile(roots, None, aggregate=True, source="mixed")}


def workspaces(daemon, roots):
    data = overview(daemon, roots)
    data["k"] = "workspaces"
    return data


def start_workspace(roots, body):
    value = body.get("root") or body.get("path") if isinstance(body, dict) else None
    roots = mobpaths.normalize_roots(roots)
    try:
        selected = mobpaths.select_root(value, roots)
        target = mobpaths.owner(selected, roots)
    except mobpaths.PathError as exc:
        raise ApiError(exc.status, exc.text) from exc
    try:
        entry, created = mobworkspaces.start(target, roots)
    except mobworkspaces.WorkspaceError as exc:
        raise ApiError(exc.status, exc.text) from exc
    return {"schema": SCHEMA, "k": "workspace_started", "created": created,
            "workspace": {"path": target, "selected": selected, "state": "running",
                          "pid": entry.get("pid"), "address": entry.get("address")}}


def runs(daemon, roots, value=None):
    roots = mobpaths.normalize_roots(roots)
    target = _target(daemon, roots, value)
    source = "daemon"
    if target == mobpaths.real(daemon.tree):
        rows = recread.scan()
    else:
        status = mobworkspaces.daemon_state(target)
        if status["state"] == "running":
            try:
                rows = mobworkspaces.call(target, {"cmd": "runs"}).get("runs") or []
            except mobworkspaces.WorkspaceError:
                rows, source = mobrecords.scan(target, status.get("entry")), "disk"
        else:
            rows, source = mobrecords.scan(target, status.get("entry")), "disk"
    return {"schema": SCHEMA, "tree": target, "source": source, "runs": rows,
            "mobile": _mobile(roots, target, source=source)}


def run_log(run_id, root=None, entry=None):
    if not record.ID_RE.match(str(run_id or "")):
        raise ApiError(400, "bad run id")
    if root is None:
        path = record.record_path(run_id)
        if not os.path.isfile(path):
            raise ApiError(404, "no such run")
        data = runlog.load(run_id)
    else:
        path = os.path.join(mobrecords.runs_dir(root, entry), run_id, record.RECORD)
        if not os.path.isfile(path):
            raise ApiError(404, "no such run")
        data = mobrecords.log(root, run_id, entry)
    if data.get("state") == "corrupt" and data.get("entries") and \
            data["entries"][0].get("kind") == "error":
        raise ApiError(409, data["entries"][0].get("text") or "corrupt record")
    data["schema"] = SCHEMA
    if root is not None:
        data["tree"] = mobpaths.real(root)
    return data
