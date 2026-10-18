import json
import os
import re
import time

from . import config

ROOT = "runs"
RECORD = "record.jsonl"
OBS = "obs"
LOCK = "record.lock"
ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}[0-9]{3}Z-[0-9a-f]{8}$")


class Corrupt(Exception):
    pass


class Missing(Exception):
    pass


class Busy(Exception):
    pass


class Sealed(Exception):
    pass


def runs_dir():
    return os.path.join(config.runs(), ROOT)


def run_dir(run_id):
    return os.path.join(runs_dir(), run_id)


def record_path(run_id):
    return os.path.join(run_dir(run_id), RECORD)


def obs_dir(run_id):
    return os.path.join(run_dir(run_id), OBS)


def lock_path(run_id):
    return os.path.join(run_dir(run_id), LOCK)


def new_id():
    while True:
        now = time.time()
        stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime(now))
        run_id = f"{stamp}{int(now * 1000) % 1000:03d}Z-{os.urandom(4).hex()}"
        if not os.path.exists(run_dir(run_id)):
            return run_id


def utc(ts=None):
    now = time.time() if ts is None else ts
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now)) + f".{int(now * 1000) % 1000:03d}Z"


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def ids():
    try:
        names = os.listdir(runs_dir())
    except OSError:
        return []
    return sorted(n for n in names if ID_RE.match(n) and os.path.isfile(record_path(n)))


def resolve(run_id=None):
    known = ids()
    if run_id is None or run_id == "":
        if not known:
            raise Missing(f"no runs under {config.display(runs_dir())}")
        return known[-1]
    if run_id in known:
        return run_id
    raise Missing(f"no record for run {run_id!r} under {config.display(runs_dir())}")
