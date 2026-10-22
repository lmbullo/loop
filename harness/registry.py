import hashlib
import os
import tempfile
import time

from . import config

SCHEMA = "loop-registry/1"
PROBE_TIMEOUT = 2.0


def state_dir():
    return config.runs()


def sock_path():
    path = os.path.join(state_dir(), "server.sock")
    if len(path.encode()) <= 100:
        return path
    digest = hashlib.sha256(state_dir().encode()).hexdigest()[:16]
    return os.path.join(tempfile.gettempdir(), f"loop-{digest}.sock")


def pid_path():
    return os.path.join(state_dir(), "server.pid")


def log_path():
    return os.path.join(state_dir(), "server.log")


def lock_path():
    return os.path.join(state_dir(), "server.lock")


def local_path():
    return os.path.join(state_dir(), "registry.json")


def global_path():
    override = config.env("LOOP_REGISTRY")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    base = config.env("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(os.path.abspath(base), "loop", "registry.json")


def tree(root=None):
    return os.path.realpath(root or config.ROOT)


def iso(ts=None):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts if ts is not None else time.time()))
