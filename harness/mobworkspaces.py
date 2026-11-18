"""Workspace daemon lookup, routing and safe startup for the mobile bridge.

The daemon that owns the HTTP listener is only a router for other workspaces:
each workspace is an independent tree with its own daemon, queue, workers and
records.  A start uses the same detached daemon lifecycle as `server start`.
"""

import os
import subprocess
import sys
import time

from . import config, mobpaths, mobrecords, regprobe, regstore, srvwire


class WorkspaceError(Exception):
    def __init__(self, status, text):
        super().__init__(text)
        self.status = status
        self.text = text


def entry_for(tree):
    tree = mobpaths.real(tree)
    entry = regstore.entries().get(tree)
    if entry is None:
        entry = mobrecords.entry_from_local(tree)
    if isinstance(entry, dict):
        entry.setdefault("tree", tree)
        return entry
    return None


def daemon_state(tree):
    tree = mobpaths.real(tree)
    entry = entry_for(tree)
    if entry is None:
        return {"state": "stopped", "detail": "no daemon registered",
                "tree": tree, "entry": None, "stale": False}
    state, detail = regprobe.probe(entry)
    if state == "running":
        return {"state": "running", "detail": detail, "tree": tree,
                "entry": entry, "pid": entry.get("pid"), "stale": False}
    stopped = str(entry.get("state") or "") == "stopped"
    return {"state": "stopped" if stopped else "offline", "detail": detail,
            "tree": tree, "entry": entry, "pid": entry.get("pid"), "stale": True}


def call(tree, request, timeout=10.0):
    status = daemon_state(tree)
    if status["state"] != "running":
        raise WorkspaceError(409, f"workspace daemon is {status['state']}: "
                                  f"{status['detail']}")
    entry = status["entry"]
    try:
        reply = regprobe.call(entry["address"], request, timeout=timeout)
    except (OSError, ValueError) as exc:
        raise WorkspaceError(503, f"workspace daemon unreachable: "
                                  f"{type(exc).__name__}: {exc}") from exc
    if not isinstance(reply, dict):
        raise WorkspaceError(503, "workspace daemon returned no reply")
    if reply.get("k") == "error":
        raise WorkspaceError(409, str(reply.get("text") or "workspace refused"))
    return reply


def discover(roots, extra=()):
    return mobpaths.discover(roots, extra)


def start(value, roots):
    """Start a daemon for a permitted workspace and return (entry, created)."""
    try:
        path = mobpaths.select_root(value, roots)
    except mobpaths.PathError as exc:
        raise WorkspaceError(exc.status, exc.text) from exc
    if mobpaths.unsafe_state(path):
        raise WorkspaceError(403, "workspace state directory is outside home")
    status = daemon_state(path)
    if status["state"] == "running":
        return status["entry"], False
    logs = mobrecords.state_dir(path)
    os.makedirs(logs, exist_ok=True)
    with regstore.locked(os.path.join(logs, "mobile-start.lock")):
        status = daemon_state(path)
        if status["state"] == "running":
            return status["entry"], False
        if status["entry"] is not None:
            try:
                regstore.remove(path)
            except OSError:
                pass
        pid = _spawn(path, logs)
        entry = _wait(path, pid)
        if entry is None:
            raise WorkspaceError(503, f"workspace daemon for {path} did not start")
        return entry, True


def _spawn(path, logs):
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    env["LOOP_ROOT"] = path
    env["LOOP_RUNS"] = logs
    run_py = os.path.join(config.ROOT, "run.py")
    with open(os.path.join(logs, "server.log"), "ab", buffering=0) as out:
        proc = subprocess.Popen(
            [sys.executable, run_py, "server", "_daemon"],
            cwd=config.ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=out,
            start_new_session=True, close_fds=True, env=env)
    return proc.pid


def _wait(path, pid, timeout=srvwire.READY_TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = daemon_state(path)
        if status["state"] == "running":
            return status["entry"]
        if not regprobe.alive(pid):
            break
        time.sleep(0.05)
    return None
