"""Transport-neutral API for the private-network mobile client.

mobserve owns HTTP and authentication.  This module owns directory browsing,
task submission and the route table, then hands workspace-scoped reads to
mobview.  Each workspace request is routed to the daemon that owns that tree;
the mobile bridge has no queue, run id or log state of its own.
"""

import os

from . import mobpaths, mobrecords, mobview, mobworkspaces, queue, regstore, srvwire
from .moberr import ApiError

SCHEMA = "loop-mobile/1"
TASK_LIMIT = 20000
DIR_LIMIT = 500
HIDDEN = mobpaths.HIDDEN


def real(path):
    return mobpaths.real(path)


def normalize_roots(paths):
    return mobpaths.normalize_roots(paths)


def inside(path, roots):
    return any(mobpaths.inside(path, root) for root in roots)


def select_root(value, roots):
    try:
        return mobpaths.select_root(value, roots)
    except mobpaths.PathError as exc:
        raise ApiError(exc.status, exc.text) from exc


def _row(path):
    return {"name": os.path.basename(path) or path, "path": path}


def _parent(path, roots):
    for root in roots:
        if path == root:
            return None
        if path.startswith(root + os.sep):
            parent = os.path.dirname(path)
            return parent if inside(parent, roots) else None
    return None


def list_dirs(roots, value=None):
    roots = normalize_roots(roots)
    if not roots:
        raise ApiError(503, "no mobile roots are configured")
    rows, path, parent, truncated = [], None, None, False
    if value:
        path = select_root(value, roots)
        parent = _parent(path, roots)
        try:
            entries = sorted(os.scandir(path), key=lambda e: e.name.lower())
        except OSError as exc:
            raise ApiError(404, f"cannot read directory: {type(exc).__name__}") from exc
        for entry in entries:
            if len(rows) >= DIR_LIMIT:
                truncated = True
                break
            if entry.name.startswith(".") or entry.name in HIDDEN:
                continue
            try:
                if not entry.is_dir(follow_symlinks=True):
                    continue
            except OSError:
                continue
            child = real(entry.path)
            if inside(child, roots):
                rows.append(_row(child))
    return {"schema": SCHEMA, "path": path, "parent": parent,
            "roots": [_row(root) for root in roots], "dirs": rows,
            "truncated": truncated}


def _env():
    return {key: os.environ[key] for key in srvwire.ENV_KEYS if key in os.environ}


def enqueue(daemon, roots, body=None):
    legacy = body is None
    if legacy:
        body, daemon = daemon, None
    task = body.get("task") if isinstance(body, dict) else None
    if not isinstance(task, str) or not task.strip():
        raise ApiError(400, "task is required")
    task = task.strip()
    if len(task) > TASK_LIMIT:
        raise ApiError(413, "task is too large")
    selected = select_root(body.get("root") or body.get("path"),
                           normalize_roots(roots))
    target = mobpaths.owner(selected, normalize_roots(roots))
    if legacy or target == real(daemon.tree):
        item = queue.add(task, selected, _env(), front=False)
        return {"schema": SCHEMA, "k": "queued", "item": item}
    status = mobworkspaces.daemon_state(target)
    if status["state"] == "running":
        try:
            reply = mobworkspaces.call(target, {"cmd": "enqueue", "task": task,
                                              "root": selected, "env": _env()})
        except mobworkspaces.WorkspaceError as exc:
            raise ApiError(exc.status, exc.text) from exc
        return {"schema": SCHEMA, "k": "queued", "item": reply.get("item"),
                "workspace": _row(target), "selected": selected}
    # Compatibility for a programmatic bridge with no registry at all.  A real
    # served daemon is always registered, so this cannot capture another tree.
    if not regstore.snapshot() and not os.path.isdir(mobrecords.state_dir(target)):
        item = queue.add(task, selected, _env(), front=False)
        return {"schema": SCHEMA, "k": "queued", "item": item, "legacy": True}
    raise ApiError(409, f"workspace daemon is {status['state']}; start it first")


def snapshot(daemon, roots, value=None):
    return mobview.snapshot(daemon, roots, value)


def overview(daemon, roots):
    return mobview.overview(daemon, roots)


def workspaces(daemon, roots):
    return mobview.workspaces(daemon, roots)


def run_log(run_id, root=None, entry=None):
    return mobview.run_log(run_id, root, entry)


def _q(query, name):
    value = (query or {}).get(name) or []
    return value[0] if value else None


def dispatch(daemon, method, parts, query, body, roots):
    """Return a JSON object.  `parts` is the decoded path below /v1."""
    root = (_q(query, "root") or _q(query, "workspace") or
            _q(query, "path"))
    if parts == ["health"] and method == "GET":
        return {"schema": SCHEMA, "ok": True, "tree": daemon.tree,
                "pid": daemon.pid, "roots": normalize_roots(roots),
                "home": mobpaths.home()}
    if parts == ["dirs"] and method == "GET":
        return list_dirs(roots, ((query or {}).get("path") or [None])[0])
    if parts == ["workspaces"] and method == "GET":
        return mobview.workspaces(daemon, roots)
    if parts in (["workspaces"], ["workspaces", "start"], ["start"],
                 ["workspace", "start"]) and method == "POST":
        return mobview.start_workspace(roots, body)
    if parts == ["overview"] and method == "GET":
        return mobview.overview(daemon, roots)
    if parts in (["snapshot"], ["workspace"]) and method == "GET":
        return mobview.snapshot(daemon, roots, root)
    if parts == ["runs"] and method == "GET":
        return mobview.runs(daemon, roots, root)
    if len(parts) == 2 and parts[0] == "runs" and method == "GET":
        if not root:
            return mobview.run_log(parts[1])
        target = mobpaths.owner(select_root(root, normalize_roots(roots)),
                                normalize_roots(roots))
        entry = None
        if target != real(daemon.tree):
            entry = mobworkspaces.daemon_state(target).get("entry")
        return mobview.run_log(parts[1], target, entry)
    if parts == ["tasks"] and method == "POST":
        return enqueue(daemon, roots, body)
    raise ApiError(404, "unknown route")
