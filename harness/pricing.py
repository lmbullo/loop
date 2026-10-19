import json
import os

from . import config

_fingerprint = None
_rates = None


def _load():
    global _fingerprint, _rates
    path = config.asset("manifest.json")
    try:
        st = os.stat(path)
        fingerprint = (st.st_mtime_ns, st.st_size)
        if fingerprint != _fingerprint or _rates is None:
            with open(path, encoding="utf-8") as f:
                manifest = json.load(f)
            _rates = dict(manifest["cost_model"]["pricing_per_1M"])
            _fingerprint = fingerprint
    except (OSError, ValueError, KeyError):
        if _rates is None:
            _rates = {"cache_hit": 0.006, "cache_miss": 0.3, "completion": 1.2}
    return _rates


def rates():
    return dict(_load())


def cost(hit, miss, out):
    rate = _load()
    return (hit * float(rate["cache_hit"]) + miss * float(rate["cache_miss"])
            + out * float(rate["completion"])) / 1e6
