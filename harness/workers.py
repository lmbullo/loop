import os

from . import recread, regprobe, regstore, registry

SCHEMA = "loop-worker/1"


def directory():
    return os.path.join(registry.state_dir(), "workers")


def lock_path():
    return os.path.join(registry.state_dir(), "workers.lock")


def path(run_id):
    return os.path.join(directory(), f"{run_id}.json")


def _read(pathname):
    data = regstore.read_json(pathname, None)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return None
    return data


def write(entry):
    os.makedirs(directory(), exist_ok=True)
    payload = {"schema": SCHEMA, **entry}
    with regstore.locked(lock_path()):
        regstore.write_json(path(entry["run_id"]), payload)
    return payload


def update(run_id, **fields):
    with regstore.locked(lock_path()):
        entry = _read(path(run_id)) or {"schema": SCHEMA, "run_id": run_id}
        entry.update(fields)
        entry["schema"] = SCHEMA
        os.makedirs(directory(), exist_ok=True)
        regstore.write_json(path(run_id), entry)
        return entry


def read(run_id):
    return _read(path(run_id))


def entries():
    try:
        names = sorted(os.listdir(directory()))
    except OSError:
        return []
    out = []
    for name in names:
        if name.endswith(".json"):
            entry = _read(os.path.join(directory(), name))
            if entry is not None:
                out.append(entry)
    return out


def live(entry):
    if not isinstance(entry, dict) or entry.get("state") != "running":
        return False
    pid = entry.get("pid")
    if not regprobe.alive(pid):
        return False
    stamp = entry.get("proc_start")
    return not stamp or regprobe.fingerprint(pid) in (None, stamp)


def live_entries():
    return [e for e in entries() if live(e)]


def current():
    rows = live_entries()
    return rows[0] if rows else None


def find(run_id):
    for entry in entries():
        if entry.get("run_id") == run_id:
            return entry
    return None


def reap():
    gone = []
    with regstore.locked(lock_path()):
        for entry in entries():
            if live(entry):
                continue
            if entry.get("state") == "running":
                continue
            try:
                os.unlink(path(entry["run_id"]))
                gone.append(entry["run_id"])
            except OSError:
                pass
    return gone


def record_state(run_id):
    try:
        return recread.read(run_id)["state"]
    except Exception:
        return "missing"
