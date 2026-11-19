import json
import urllib.request

from . import config

TOOLS = [
    {"type": "function", "function": {
        "name": "exec",
        "description": "Run argv (list) with no shell, or cmd (str) through sh -c. "
                       "Read-like output stays contiguous up to the read bound.",
        "parameters": {"type": "object", "properties": {
            "argv": {"type": "array", "items": {"type": "string"}},
            "cmd": {"type": "string"},
            "cwd": {"type": "string"}, "stdin": {"type": "string"},
            "timeout_ms": {"type": "integer"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "write",
        "description": "Write UTF-8 data; append=true continues a chunked file. "
                       "Prefer edit when a small span changes.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "data": {"type": "string"},
            "append": {"type": "boolean"}}, "required": ["path", "data"]}}},
    {"type": "function", "function": {
        "name": "edit",
        "description": "Replace one occurrence; old is the smallest unique span. "
                       "Batch independent edits as calls in one message.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "old": {"type": "string"},
            "new": {"type": "string"}}, "required": ["path", "old", "new"]}}},
    {"type": "function", "function": {
        "name": "done",
        "description": "End the run with compact evidence: changed paths, checks, risk.",
        "parameters": {"type": "object", "properties": {
            "result": {"type": "string"}}, "required": ["result"]}}},
]
WIRE_SCHEMA = "loop-wire/1"

BASE = """\
This repo is agent-facing: machine text, not human prose.

You are the loop. A turn either calls tools or ends the run. Messages are
append-only and re-sent: the unchanged prefix is a cache hit, completion tokens
cost most. Think only until the next call is determined; a routine turn is one
short thought, then action. Do not restate observations, plans, or code you can
write with a tool.

Act in the fewest turns:
- batch independent calls in one message; they run in order
- prefer edit over write; write append=true for a file larger than one reply
- never re-read a path whose bytes are already in the message list
- when a probe would repeat, write one script that answers every branch
- observations are shaped: `shown a-b of N`; run the printed `next:` command to
  advance. Read-like commands (cat, sed, head, tail, grep, ls, git diff) keep up
  to 8 KiB contiguous, so ask for a range in one call.
- `same=obs-N` is a byte-identical earlier observation; do not fetch it again
- a failed call explains the fix; do not send it unchanged

Output is billed. Never echo file contents, diffs or long lists into tool
arguments or done.result. done.result = changed paths, checks run, residual
risk. There is no turn or time cap; call done(result) when the task is done.

exec(argv | cmd, cwd?, stdin?, timeout_ms?) -> observation
  argv is literal; cmd runs through sh -c. One call can batch independent work.
write(path, data, append?) -> observation
edit(path, old, new) -> observation
  old must match exactly once.
done(result) -> finishes the run.
"""


def model():
    return config.env("LOOP_MODEL", "deepseek-flash")


def url():
    return config.env("LOOP_URL", "https://api.deepseek.com/chat/completions")


def header():
    return BASE


def thinking():
    return {"type": "enabled", "budget_tokens": config.think_budget()}


def max_tokens():
    return config.max_tokens()


def snapshot():
    """Snapshot the request-static prefix once per run.

    A soft reload may re-import this module mid-run. The worker passes the
    snapshot back into call(), so the system header, tool schemas, model,
    thinking budget and reasoning-replay policy cannot change between turns
    of one run.
    """
    spec = {"schema": WIRE_SCHEMA, "system": header(),
            "tools": json.dumps(TOOLS, sort_keys=True, separators=(",", ":")),
            "thinking": json.dumps(thinking(), sort_keys=True, separators=(",", ":")),
            "model": model(), "max_tokens": max_tokens(),
            "renderer": config.RENDERER,
            "replay_reasoning": config.replay_reasoning()}
    return dict(spec, sha=_sha(spec))


def _sha(spec):
    import hashlib
    body = {k: spec[k] for k in ("system", "tools", "thinking", "model",
                                 "max_tokens", "renderer", "replay_reasoning")}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def call(msgs, key, wire=None, max_tokens=None):
    spec = wire or snapshot()
    ceiling = int(spec["max_tokens"])
    limit = ceiling if max_tokens is None else min(int(max_tokens), ceiling)
    body = json.dumps({
        "model": spec["model"], "messages": msgs,
        "tools": json.loads(spec["tools"]),
        "max_tokens": limit,
        "thinking": json.loads(spec["thinking"]),
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    req = urllib.request.Request(url(), body, {
        "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    timeout = config.http_timeout_s()
    with urllib.request.urlopen(req, timeout=timeout or None) as r:
        return json.load(r)
