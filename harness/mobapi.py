"""Transport-neutral API for the local-network mobile client.

mobserve owns HTTP and authentication.  This module owns the allowlist of
workspace directories and maps requests onto the existing queue, record and
snapshot functions.  It never starts a run and it keeps no state of its own.
"""

import os

from . import queue, record, recread, runlog, srvwire

SCHEMA = "loop-mobile/1"
TASK_LIMIT = 20000
DIR_LIMIT = 500
HIDDEN = {".git", ".hg", ".svn", "node_modules", "__pycache__"}


class ApiError(Exception):
    def __init__(self, status, text):
        super().__init__(text)
        self.status = status
        self.text = text


def real(path):
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def normalize_roots(paths):
    """Keep existing, unique real directories from a configured allowlist."""
    out = []
    for value in paths or ():
        if not isinstance(value, str) or not value.strip():
            continue
        path = real(value)
        if os.path.isdir(path) and path not in out:
            out.append(path)
    return out


def inside(path, roots):
    path = real(path)
    return any(path == root or path.startswith(root + os.sep) for root in roots)


def select_root(value, roots):
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, "root is required")
    path = real(value)
    if not inside(path, roots):
        raise ApiError(403, "root is outside the mobile allowlist")
    if not os.path.isdir(path):
        raise ApiError(404, "root is not a directory")
    return path


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
    rows = []
    path = None
    parent = None
    truncated = False
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


def enqueue(body, roots):
    task = body.get("task") if isinstance(body, dict) else None
    if not isinstance(task, str) or not task.strip():
        raise ApiError(400, "task is required")
    task = task.strip()
    if len(task) > TASK_LIMIT:
        raise ApiError(413, "task is too large")
    root = select_root(body.get("root"), normalize_roots(roots))
    item = queue.add(task, root, _env(), front=False)
    return {"schema": SCHEMA, "k": "queued", "item": item}


def snapshot(daemon, roots):
    data = daemon.snapshot_dict()
    data["schema"] = SCHEMA
    data["mobile"] = {"roots": list(roots)}
    return data


def run_log(run_id):
    if not record.ID_RE.match(str(run_id or "")):
        raise ApiError(400, "bad run id")
    if not os.path.isfile(record.record_path(run_id)):
        raise ApiError(404, "no such run")
    data = runlog.load(run_id)
    if data.get("state") == "corrupt" and data.get("entries") and \
            data["entries"][0].get("kind") == "error":
        raise ApiError(409, data["entries"][0].get("text") or "corrupt record")
    data["schema"] = SCHEMA
    return data


def dispatch(daemon, method, parts, query, body, roots):
    """Return a JSON object.  `parts` is the decoded path below /v1."""
    if parts == ["health"] and method == "GET":
        return {"schema": SCHEMA, "ok": True, "tree": daemon.tree,
                "pid": daemon.pid, "roots": normalize_roots(roots)}
    if parts == ["dirs"] and method == "GET":
        return list_dirs(roots, (query.get("path") or [None])[0])
    if parts == ["snapshot"] and method == "GET":
        return snapshot(daemon, normalize_roots(roots))
    if parts == ["runs"] and method == "GET":
        return {"schema": SCHEMA, "runs": recread.scan()}
    if len(parts) == 2 and parts[0] == "runs" and method == "GET":
        return run_log(parts[1])
    if parts == ["tasks"] and method == "POST":
        return enqueue(body, roots)
    raise ApiError(404, "unknown route")
