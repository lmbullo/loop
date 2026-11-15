import contextlib
import json
import os
import subprocess
import sys
import tempfile
import unittest.mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ID = "20240101T000000000Z-abcdef01"
ENV_KEYS = ("LOOP_ROOT", "LOOP_RUNS", "LOOP_REGISTRY", "LOOP_AUTH_FILE",
            "LOOP_API_KEY", "LOOP_MODEL", "LOOP_URL", "LOOP_MAX_TOKENS",
            "LOOP_MAX_INLINE", "LOOP_HTTP_TIMEOUT_S", "LOOP_MOBILE_TOKEN",
            "LOOP_MOBILE_ROOTS")

RUN_START = {"task": "test task", "root": "/tmp/root", "entrypoint": "api",
             "model": "fake", "tools": ["exec", "write", "edit", "done"],
             "max_inline": 32768, "record_source": "live"}
END = {"exit": 0, "finish": "done", "result": "ok", "turns": 1,
       "hit": 10, "miss": 20, "out": 30, "reasoning_c": 40, "cost": 0.5}
TURN = {"turn": 1, "finish_reason": "stop",
        "usage": {"hit": 10, "miss": 20, "out": 30, "reasoning_c": 40, "cost": 0.5},
        "message": {"role": "assistant", "content": None, "tool_calls": []},
        "calls": [], "done": None}
ERROR = {"code": 4, "text": "bad", "finish": "http_error"}
RESUME = {"from_seq": 1, "turn": 1, "messages": 2, "root": "/tmp/root", "by": "resume"}
NUDGE = {"text": "continue after the silent stop"}
INTERRUPTED = {"reason": "server_stop", "last_seq": 2, "by": "server"}


@contextlib.contextmanager
def sandbox():
    with tempfile.TemporaryDirectory(prefix="loop-test-") as tmp:
        env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
        env.update({
            "LOOP_ROOT": ROOT,
            "LOOP_RUNS": os.path.join(tmp, "logs"),
            "LOOP_REGISTRY": os.path.join(tmp, "registry.json"),
            "LOOP_AUTH_FILE": os.path.join(tmp, "auth.json"),
        })
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            yield tmp


def event(run_id, seq, kind, data):
    from harness import recschema
    return recschema.event(run_id, seq, kind, data, ts="2024-01-01T00:00:00.000Z")


def minimal_events(run_id=RUN_ID):
    return [event(run_id, 1, "run_start", dict(RUN_START)),
            event(run_id, 2, "end", dict(END))]


def write_record(run_id, events):
    from harness import record
    path = record.record_path(run_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev, sort_keys=True, separators=(",", ":")) + "\n")
    return path


def read_events(run_id):
    from harness import record
    with open(record.record_path(run_id), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_py(*args, env=None, input=None, timeout=60, cwd=ROOT):
    full = dict(os.environ)
    full.update(env or {})
    return subprocess.run([sys.executable, os.path.join(ROOT, "run.py")] + list(args),
                          cwd=cwd, input=input, text=True, capture_output=True,
                          timeout=timeout, env=full)
