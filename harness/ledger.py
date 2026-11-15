"""Content-addressed observation memory for one run.

The message list is append-only, so an observation that is byte-identical to
an earlier one is already present in context. The ledger lets the renderer
replace the duplicate with a one-line reference instead of appending the same
payload again. Entries are derived from record events, never from process
state, so resume rebuilds exactly the same map.
"""

import hashlib
import os

from . import config


def sha(raw):
    return hashlib.sha256(raw or b"").hexdigest()


def _saved(raw, root):
    if not raw:
        return None
    path = raw if os.path.isabs(raw) else os.path.join(root or config.root(), raw)
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def call_raw(call, root=None):
    """Recover the pre-render payload for a recorded call, if available."""
    saved = call.get("saved")
    if saved:
        return _saved(saved, root)
    obs = call.get("observation") or ""
    if call.get("name") == "exec" and obs.startswith("exit="):
        nl = obs.find("\n")
        return (obs[nl + 1:] if nl >= 0 else "").encode()
    return obs.encode()


class Ledger:
    def __init__(self):
        self.by_sha = {}

    @classmethod
    def from_events(cls, events, root=None):
        led = cls()
        n = 0
        for ev in events:
            if ev["type"] != "turn":
                continue
            for call in ev["data"].get("calls") or []:
                n += 1
                raw = call_raw(call, root)
                if raw is not None:
                    led.add(raw, f"obs-{n}", call.get("saved"), call.get("saved") is None)
        return led

    def add(self, raw, obs_id, saved=None, inline=False):
        entry = {"id": obs_id, "saved": saved, "inline": bool(inline),
                 "bytes": len(raw or b"")}
        self.by_sha[sha(raw)] = entry
        return entry

    def get(self, raw):
        return self.by_sha.get(sha(raw)) if raw is not None else None
