import os
import time

from . import record, regstore, registry

SCHEMA = "loop-queue/1"


def path():
    return os.path.join(registry.state_dir(), "queue.json")


def lock_path():
    return path() + ".lock"


def empty():
    return {"schema": SCHEMA, "seq": 0, "current": None, "items": []}


def _load():
    data = regstore.read_json(path(), None)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return empty()
    data.setdefault("seq", 0)
    data.setdefault("current", None)
    if not isinstance(data.get("items"), list):
        data["items"] = []
    return data


def _save(data):
    regstore.write_json(path(), data)


def _mutate(fn):
    os.makedirs(registry.state_dir(), exist_ok=True)
    with regstore.locked(lock_path()):
        data = _load()
        result = fn(data)
        _save(data)
        return result


def load():
    with regstore.locked(lock_path()):
        return _load()


def add(task, root, env, front=False, run_id=None, verify=None):
    def fn(data):
        data["seq"] = int(data.get("seq") or 0) + 1
        item = {
            "id": f"q{data['seq']:06d}",
            "run_id": run_id or record.new_id(),
            "task": task,
            "root": root,
            "env": dict(env or {}),
            "verify": verify,
            "state": "queued",
            "created_at": record.utc(),
            "created_ts": time.time(),
            "worker_pid": None,
            "started_at": None,
        }
        if front:
            data["items"].insert(0, item)
        else:
            data["items"].append(item)
        return item
    return _mutate(fn)


def current():
    return load().get("current")


def waiting():
    data = load()
    return [] if data.get("current") else list(data.get("items") or [])


def promote():
    def fn(data):
        if data.get("current") is not None or not data.get("items"):
            return data.get("current")
        item = data["items"].pop(0)
        item["state"] = "running"
        item["started_at"] = record.utc()
        data["current"] = item
        return item
    return _mutate(fn)


def set_current(item):
    def fn(data):
        data["current"] = item
        data["items"] = [x for x in data.get("items") or [] if x.get("id") != item.get("id")]
        return item
    return _mutate(fn)


def update(item_id, **fields):
    def fn(data):
        for key in ("current",):
            item = data.get(key)
            if isinstance(item, dict) and item.get("id") == item_id:
                item.update(fields)
                return item
        for item in data.get("items") or []:
            if item.get("id") == item_id:
                item.update(fields)
                return item
        return None
    return _mutate(fn)


def finish(state, **fields):
    def fn(data):
        item = data.get("current")
        if not isinstance(item, dict):
            return None
        item.update(fields)
        item["state"] = state
        item["finished_at"] = record.utc()
        data["current"] = None
        return item
    return _mutate(fn)


def drop(item_id):
    def fn(data):
        before = len(data.get("items") or [])
        data["items"] = [x for x in data.get("items") or [] if x.get("id") != item_id]
        return len(data.get("items") or []) != before
    return _mutate(fn)


def move(item_id, delta):
    def fn(data):
        items = data.get("items") or []
        ids = [x.get("id") for x in items]
        if item_id not in ids:
            return False
        i = ids.index(item_id)
        j = max(0, min(len(items) - 1, i + int(delta)))
        if i == j:
            return False
        items[i], items[j] = items[j], items[i]
        return True
    return _mutate(fn)


def snapshot():
    data = load()
    current_item = data.get("current")
    return {
        "seq": int(data.get("seq") or 0),
        "current": current_item,
        "items": list(data.get("items") or []),
    }
