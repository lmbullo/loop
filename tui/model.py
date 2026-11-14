import threading
import time

TERMINAL = ("complete", "interrupted", "error", "corrupt")
WAITING = ("queued", "waiting")


def money(value):
    return "-" if value is None else f"${value:.6f}"


def view(item):
    if not isinstance(item, dict):
        return None
    out = dict(item)
    out.setdefault("text", out.get("task") or "")
    out.setdefault("turns", 0)
    out.setdefault("cost", None)
    out.setdefault("detail", "")
    out.setdefault("state", "queued")
    return out


class Model:
    def __init__(self):
        self.lock = threading.RLock()
        self.cv = threading.Condition(self.lock)
        self.snap = {"current": None, "last": None, "done": [], "queue": [],
                     "daemon": {"state": "starting", "detail": "attaching", "pid": 0},
                     "notice": "", "notice_at": 0.0, "version": 0}
        self.notice = ""
        self.notice_at = 0.0
        self.version = 0
        self.stop = False

    def bump(self):
        self.version += 1
        self.snap["version"] = self.version
        self.snap["notice"] = self.notice
        self.snap["notice_at"] = self.notice_at
        self.cv.notify_all()

    def apply(self, raw):
        with self.lock:
            self.snap["current"] = view(raw.get("current"))
            self.snap["last"] = view(raw.get("last"))
            self.snap["done"] = [view(item) for item in raw.get("done") or []]
            self.snap["queue"] = [view(item) for item in raw.get("queue") or []]
            self.snap["daemon"] = dict(raw.get("daemon") or
                                       {"state": "running", "detail": "ok", "pid": 0})
            self.snap["costs"] = dict(raw.get("costs") or {})
            self.bump()
            return self.snap

    def set_down(self, detail="daemon down"):
        with self.lock:
            self.snap["daemon"] = {"state": "down", "detail": detail, "pid": 0}
            self.bump()

    def say(self, text):
        with self.lock:
            self.notice, self.notice_at = text, time.time()
            self.bump()

    def snapshot(self):
        with self.lock:
            return {"current": self.snap["current"], "last": self.snap["last"],
                    "done": list(self.snap["done"]),
                    "queue": list(self.snap["queue"]), "daemon": dict(self.snap["daemon"]),
                    "costs": dict(self.snap.get("costs") or {}),
                    "notice": self.notice, "notice_at": self.notice_at,
                    "version": self.version}
