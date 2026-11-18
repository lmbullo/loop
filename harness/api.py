import json
import urllib.request

from . import config

TOOLS = [
    {"type": "function", "function": {
        "name": "exec",
        "description": "Spawn argv directly; no shell. Returns exit code, stdout, stderr.",
        "parameters": {"type": "object", "properties": {
            "argv": {"type": "array", "items": {"type": "string"}},
            "cwd": {"type": "string"}, "stdin": {"type": "string"},
            "timeout_ms": {"type": "integer"}}, "required": ["argv"]}}},
    {"type": "function", "function": {
        "name": "write",
        "description": "Write UTF-8 data; append=true continues a large file.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "data": {"type": "string"},
            "append": {"type": "boolean"}}, "required": ["path", "data"]}}},
    {"type": "function", "function": {
        "name": "edit",
        "description": "Replace one occurrence; old+new is the smallest unique span.",
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
This repo is agent-facing: machine text, not human prose.

Messages are append-only: each turn appends one assistant message and one tool
message per call; no earlier entry is edited or re-sent. The record is append-only
JSONL, one event per turn, fsynced; `end` is the only completion marker. One run
per tree: the tree lock makes a second run busy.

Cost: the unchanged prefix is a cache hit; only the appended suffix is a miss;
completion tokens bill highest. Assistant prose is not re-sent; tool calls,
arguments, reasoning_content and observations persist.

Output is the budget. Decide the next action in one or two sentences, then call a
tool. Do not restate code, observations or a plan you can execute. Make the
smallest change that satisfies the task; no unrequested files, tests, docs or
prose. Prefer `edit` over rewriting a file; send at most ~4000 bytes per `write`
and continue with `append=true`. Keep `done.result` under 200 words.

Call done(result) when complete. A turn with no tool call ends the run: non-empty
text becomes end.result. Empty text gets one nudge; a second ends as no_tool_call.

Batch independent calls in one assistant message; they run in order. Chain only
calls whose arguments depend on an earlier result. Do not repeat a call or read
whose result is in the message list; when a probe would repeat, write it once as
a script and run the script.

Large observations become a shape summary: `shown a-b of N`, `elided c-d`, and a
`next: sed -n a,bp <saved>` slice; pass those argv tokens literally. `same=obs-N`
means byte-identical to an earlier observation.

Paths are relative to the working directory.

exec(argv, cwd?, stdin?, timeout_ms?) -> observation
  Spawns argv directly; no shell, globs, pipes or redirects unless you use
  ["sh","-c","..."]; no state persists.
write(path, data, append?) -> observation
edit(path, old, new) -> observation
  Replaces exactly one occurrence; fails unless the match count is 1.
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
