import os
import signal
import subprocess
import sys
import time

from . import config, regprobe, regstore, registry, srvwire


def spawn_daemon():
    os.makedirs(registry.state_dir(), exist_ok=True)
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    with open(registry.log_path(), "ab", buffering=0) as out:
        proc = subprocess.Popen(
            [sys.executable, os.path.join(config.ROOT, "run.py"), "server", "_daemon"],
            cwd=config.ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=out,
            start_new_session=True, close_fds=True, env=env)
    return proc.pid


def clean_stale():
    removed = []
    sock = registry.sock_path()
    if os.path.exists(sock) and regprobe.ping(sock) is None:
        try:
            os.unlink(sock)
            removed.append(config.display(sock))
        except OSError:
            pass
    pid_file = registry.pid_path()
    if os.path.exists(pid_file):
        try:
            with open(pid_file, encoding="utf-8") as f:
                pid = int(f.read().strip() or 0)
        except (OSError, ValueError):
            pid = 0
        if not regprobe.alive(pid):
            try:
                os.unlink(pid_file)
                removed.append(config.display(pid_file))
            except OSError:
                pass
    entry = regstore.current()
    if entry and regprobe.probe(entry)[0] != "running":
        regstore.remove(registry.tree())
        try:
            regstore.write_local({"tree": registry.tree(), "pid": 0, "state": "stale",
                                  "address": "unix:" + sock, "started_at": None,
                                  "log": config.display(registry.log_path())})
        except OSError:
            pass
        removed.append("registry")
    return removed


def wait_ready(pid, timeout=srvwire.READY_TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        entry = regstore.current()
        if entry and regprobe.probe(entry)[0] == "running":
            return entry
        if not regprobe.alive(pid):
            break
        time.sleep(0.05)
    return None


def start(wait=srvwire.READY_TIMEOUT):
    os.makedirs(registry.state_dir(), exist_ok=True)
    with regstore.locked(registry.lock_path()):
        entry = regstore.current()
        if entry and regprobe.probe(entry)[0] == "running":
            return entry, False
        clean_stale()
        pid = spawn_daemon()
        ready = wait_ready(pid, wait)
        if ready is None:
            tail = log_tail(8)
            raise RuntimeError(f"daemon pid={pid} did not answer within {wait:.0f}s "
                               f"alive={regprobe.alive(pid)}\n{tail}")
        return ready, True


def stop(force=False, shutdown=False, timeout=srvwire.STOP_TIMEOUT):
    entry = regstore.current()
    state = regprobe.probe(entry)[0] if entry else "dead"
    if state != "running":
        clean_stale()
        return False
    pid = entry["pid"]
    request = {"cmd": "shutdown"} if shutdown else {"cmd": "stop", "force": bool(force)}
    reply = None
    try:
        reply = regprobe.call(entry["address"], request, timeout=10.0)
    except (OSError, ValueError):
        pass
    if isinstance(reply, dict) and reply.get("k") == "error":
        text = str(reply.get("text") or "")
        if request.get("cmd") == "shutdown" and "unknown cmd" in text:
            try:
                reply = regprobe.call(entry["address"], {"cmd": "stop"}, timeout=10.0)
            except (OSError, ValueError):
                reply = None
        if not isinstance(reply, dict) or reply.get("k") == "error":
            raise RuntimeError(text or "daemon refused")
    deadline = time.time() + timeout
    while time.time() < deadline and regprobe.alive(pid):
        time.sleep(0.05)
    if regprobe.alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        for _ in range(100):
            if not regprobe.alive(pid):
                break
            time.sleep(0.02)
    clean_stale()
    regstore.remove(registry.tree())
    for path in (registry.sock_path(), registry.pid_path()):
        try:
            os.unlink(path)
        except OSError:
            pass
    try:
        regstore.write_local({"tree": registry.tree(), "pid": 0, "state": "stopped",
                              "address": "unix:" + registry.sock_path(), "started_at": None,
                              "log": config.display(registry.log_path())})
    except OSError:
        pass
    return True


def log_tail(lines=40):
    path = registry.log_path()
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return ""
    rows = data.decode("utf-8", "replace").splitlines()
    if lines and lines > 0:
        rows = rows[-lines:]
    return "\n".join(rows)
