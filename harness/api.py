import json
import urllib.request

from . import config

TOOLS = [
    {"type": "function", "function": {
        "name": "exec",
        "description": "Spawn argv directly. Returns exit code, stdout, stderr.",
        "parameters": {"type": "object", "properties": {
            "argv": {"type": "array", "items": {"type": "string"}},
            "cwd": {"type": "string"}, "stdin": {"type": "string"},
            "timeout_ms": {"type": "integer"}}, "required": ["argv"]}}},
    {"type": "function", "function": {
        "name": "write",
        "description": "Write data to path as UTF-8.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "data": {"type": "string"},
            "append": {"type": "boolean"}}, "required": ["path", "data"]}}},
    {"type": "function", "function": {
        "name": "edit",
        "description": "Replace exactly one occurrence of old with new.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "old": {"type": "string"},
            "new": {"type": "string"}}, "required": ["path", "old", "new"]}}},
    {"type": "function", "function": {
        "name": "done",
        "description": "Finish the task with a result string; call this instead of stopping silently.",
        "parameters": {"type": "object", "properties": {
            "result": {"type": "string"}}, "required": ["result"]}}},
]
WIRE_SCHEMA = "loop-wire/1"

BASE = """\
This repo and its artifacts are agent-facing. The code in it is machine text
that agents read and edit: human readability is not a goal.

The message list is append-only: every turn appends one assistant message and
one tool message per call; earlier entries are never edited, reordered or
re-sent in a new form. The run record is append-only as well: one JSONL line
per event, fsynced before the next turn, and `end` is the only completion
marker.

One run per tree. The run you are in holds the tree lock, so starting another
run in this tree fails with busy naming the holder pid. argv is passed
literally: no shell, so no globs, pipes or redirects unless you use sh -c.

Cost: the whole message list is re-sent each turn, so the unchanged prefix is a
cache hit and only the appended suffix is a cache miss; output tokens bill
highest. reasoning_content is replayed because thinking mode requires it; after
the turn it is part of the cached prefix.

Assistant prose text is not re-sent; tool calls, their arguments,
reasoning_content and observations persist.
Call done(result) when the task is complete. A turn with no tool call also ends
the run: non-empty text becomes end.result. An empty reply gets one nudge to
call done or continue; a second empty reply finishes it as no_tool_call.

Issue independent tool calls together in one assistant message; they run in the
order given. Chain only calls whose arguments depend on an earlier result, and do
not re-run a call whose result is already in the message list. When the same
probe or probe pair is about to repeat, write it once as a script and run the
script; repeated single-step probing costs a turn each time.

Large observations are replaced by a shape summary; the raw bytes are saved
under the run's obs directory. A summary reports `shown a-b of N` and, when it
elides lines, a ready `next: sed -n a,bp <path>` command; pass those argv tokens
as-is (exec argv is literal, so no quoting) to get the next slice verbatim. Do
not re-read a file you already have; an observation marked same=obs-N is byte
identical to that earlier observation. Prefer one read of the range you need
over many small probes.

Paths are relative to the working directory.

exec(argv: [str], cwd?: str, stdin?: str, timeout_ms?: int) -> observation
  Spawns argv directly. No shell: no pipes, globs, redirects, expansion. Use
  ["sh","-c","..."] when needed. No state persists between calls.

write(path: str, data: str, append?: bool) -> observation
edit(path: str, old: str, new: str) -> observation
  Replaces exactly one occurrence. Fails if match count != 1. Returns hunk.
done(result: str) -> finishes the task; call this instead of stopping silently.
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
    return config.env_int("LOOP_MAX_TOKENS", 65536)


def snapshot():
    """Snapshot the request-static prefix once per run.

    A soft reload may re-import this module mid-run. The worker passes the
    snapshot back into call(), so the system header, tool schemas, model and
    thinking budget cannot change between turns of one run.
    """
    spec = {"schema": WIRE_SCHEMA, "system": header(),
            "tools": json.dumps(TOOLS, sort_keys=True, separators=(",", ":")),
            "thinking": json.dumps(thinking(), sort_keys=True, separators=(",", ":")),
            "model": model(), "max_tokens": max_tokens(),
            "renderer": config.RENDERER}
    return dict(spec, sha=_sha(spec))


def _sha(spec):
    import hashlib
    body = {k: spec[k] for k in ("system", "tools", "thinking", "model",
                                 "max_tokens", "renderer")}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def call(msgs, key, wire=None):
    spec = wire or snapshot()
    body = json.dumps({
        "model": spec["model"], "messages": msgs,
        "tools": json.loads(spec["tools"]),
        "max_tokens": int(spec["max_tokens"]),
        "thinking": json.loads(spec["thinking"]),
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    req = urllib.request.Request(url(), body, {
        "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=config.env_int("LOOP_HTTP_TIMEOUT_S", 1800)) as r:
        return json.load(r)
