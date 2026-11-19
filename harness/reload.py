import importlib
import os
import sys

from . import record, regstore, registry

SCHEMA = "loop-reload/1"
MODULES = ("harness.config", "harness.api", "harness.bound", "harness.observe",
           "harness.spawn", "harness.tools", "harness.ledger", "harness.pricing",
           "harness.budget", "harness.memo", "harness.retry")
_seen = None


def path():
    return os.path.join(registry.state_dir(), "reload.json")


def load():
    data = regstore.read_json(path(), None)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return {"schema": SCHEMA, "generation": 0, "at": None, "by": None}
    data.setdefault("generation", 0)
    return data


def generation():
    return int(load().get("generation") or 0)


def bump(by="server"):
    with regstore.locked(path() + ".lock"):
        data = load()
        data["generation"] = int(data.get("generation") or 0) + 1
        data["at"] = record.utc()
        data["by"] = by
        os.makedirs(registry.state_dir(), exist_ok=True)
        regstore.write_json(path(), data)
        return data


def baseline():
    global _seen
    _seen = generation()
    return _seen


def apply():
    reloaded = []
    for name in MODULES:
        module = sys.modules.get(name)
        if module is not None:
            importlib.reload(module)
            reloaded.append(name)
    return reloaded


def maybe():
    global _seen
    current = generation()
    if _seen is None:
        _seen = current
        return False
    if current == _seen:
        return False
    _seen = current
    apply()
    return True
