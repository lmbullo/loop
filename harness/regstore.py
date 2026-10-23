import fcntl
import json
import os

from . import registry


class Lock:
    def __init__(self, path):
        self.path = path
        self.fd = None

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        return False


def locked(path):
    return Lock(path)


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return default
    return data if isinstance(data, dict) else default


def write_json(path, data):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return path


def empty():
    return {"schema": registry.SCHEMA, "servers": {}}


def load(path=None):
    path = path or registry.global_path()
    data = read_json(path, None)
    if not data or not isinstance(data.get("servers"), dict):
        return empty()
    data.setdefault("schema", registry.SCHEMA)
    return data


def entries(path=None):
    got = load(path)["servers"]
    out = {}
    for key, value in got.items():
        if isinstance(value, dict):
            value.setdefault("tree", key)
            out[key] = value
    return out


def snapshot(path=None):
    got = entries(path)
    return [got[k] for k in sorted(got)]


def update(fn, path=None):
    path = path or registry.global_path()
    with locked(path + ".lock"):
        reg = load(path)
        result = fn(reg)
        write_json(path, reg)
        return result


def upsert(entry, path=None):
    key = entry["tree"]
    return update(lambda reg: reg["servers"].__setitem__(key, entry), path)


def remove(key, path=None):
    return update(lambda reg: reg["servers"].pop(key, None), path)


def write_local(entry):
    path = registry.local_path()
    with locked(path + ".lock"):
        write_json(path, {"schema": registry.SCHEMA, "servers": {entry["tree"]: entry}})
    return path


def current(root=None):
    key = registry.tree(root)
    for path in (registry.local_path(), registry.global_path()):
        entry = entries(path).get(key)
        if entry:
            return entry
    return None
