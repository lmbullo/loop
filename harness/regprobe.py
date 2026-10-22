import json
import os
import socket

from . import regstore, registry


def alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            data = f.read()
        if data[data.rindex(b")") + 2:data.rindex(b")") + 3] in (b"Z", b"X"):
            return False
    except (OSError, ValueError, IndexError):
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def fingerprint(pid):
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            data = f.read()
        return data[data.rindex(b")") + 2:].split()[19].decode()
    except (OSError, IndexError, ValueError):
        return None


def call(address, request, timeout=registry.PROBE_TIMEOUT):
    path = address[5:] if isinstance(address, str) and address.startswith("unix:") else address
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(path)
        sock.sendall((json.dumps(request) + "\n").encode())
        buf = b""
        while b"\n" not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
        if not buf:
            return None
        return json.loads(buf.split(b"\n", 1)[0].decode())
    finally:
        try:
            sock.close()
        except OSError:
            pass


def ping(address, timeout=registry.PROBE_TIMEOUT):
    try:
        reply = call(address, {"cmd": "ping"}, timeout)
    except (OSError, ValueError):
        return None
    return reply if isinstance(reply, dict) and reply.get("k") == "hello" else None


def probe(entry, timeout=registry.PROBE_TIMEOUT):
    if not isinstance(entry, dict):
        return "dead", "corrupt entry"
    target, pid, address = entry.get("tree"), entry.get("pid"), entry.get("address")
    if not isinstance(target, str) or not target:
        return "dead", "no tree"
    if not alive(pid):
        return "dead", "pid not running"
    stamp = entry.get("proc_start")
    if stamp and fingerprint(pid) not in (None, stamp):
        return "dead", "pid reused"
    hello = ping(address, timeout) if isinstance(address, str) else None
    if not hello:
        return "dead", "socket unreachable"
    if hello.get("pid") != pid:
        return "dead", f"socket pid {hello.get('pid')} != {pid}"
    if hello.get("tree") != target:
        return "dead", f"socket tree {hello.get('tree')} != {target}"
    return "running", "ok"


def live(path=None):
    return [e for e in regstore.snapshot(path) if probe(e)[0] == "running"]


def describe(entry, state=None):
    state = state or probe(entry)[0]
    return (f"tree={entry.get('tree')} pid={entry.get('pid')} state={state} "
            f"addr={entry.get('address')} started={entry.get('started_at')} "
            f"log={entry.get('log')}")
