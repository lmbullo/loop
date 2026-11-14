import json
import os
import socket

from harness import config, regprobe, regstore, srvctl, srvwire


def _path(address):
    return address[5:] if address.startswith("unix:") else address


def _call(entry, request, timeout=3.0):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(_path(entry["address"]))
        sock.sendall(srvwire.line(request))
        reader = sock.makefile("rb")
        try:
            raw = reader.readline()
        finally:
            reader.close()
        return json.loads(raw.decode("utf-8")) if raw.strip() else None
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _running():
    entry = regstore.current()
    if not entry or regprobe.probe(entry)[0] != "running":
        return None
    return entry


def down(detail="no daemon"):
    return {"daemon": {"state": "down", "detail": detail, "pid": 0},
            "current": None, "last": None, "done": [], "queue": [], "costs": {}, "version": 0}


def snapshot():
    entry = _running()
    if entry is None:
        return down()
    try:
        reply = _call(entry, {"cmd": "snapshot"})
    except (OSError, ValueError) as e:
        return down(f"snapshot {type(e).__name__}")
    if not isinstance(reply, dict) or reply.get("k") != "snapshot":
        return down("daemon sent no snapshot")
    reply.setdefault("daemon", {})
    reply["daemon"].update({"state": "running", "detail": "ok",
                            "pid": reply.get("pid") or entry.get("pid")})
    return reply


def ensure():
    return srvctl.start()


def _ensure():
    return ensure()


def enqueue(text):
    entry, created = _ensure()
    env = {key: os.environ[key] for key in srvwire.ENV_KEYS if key in os.environ}
    reply = _call(entry, {"cmd": "enqueue", "task": text, "root": config.root(), "env": env})
    return created, reply


def drop(item_id):
    entry = _running()
    if entry is None:
        return None
    return _call(entry, {"cmd": "drop", "id": item_id})


def move(item_id, delta):
    entry = _running()
    if entry is None:
        return None
    return _call(entry, {"cmd": "move", "id": item_id, "delta": int(delta)})
