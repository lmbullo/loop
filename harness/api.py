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
highest, and reasoning is never re-sent, so it costs nothing after the turn.

Assistant text is not re-sent; only tool calls and their observations persist.
Call done(result) when the task is complete. A turn with no tool call also ends
the run: non-empty text becomes end.result, and an empty reply finishes it as
no_tool_call.

Issue independent tool calls together in one assistant message; they run in the
order given. Chain only calls whose arguments depend on an earlier result, and do
not re-run a call whose result is already in the message list.

Large observations are replaced by a shape summary; the raw bytes are saved
under the run's obs directory. Grep for the line you need or read a small range;
do not dump the whole file again.

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


def call(msgs, key):
    body = json.dumps({
        "model": model(), "messages": msgs, "tools": TOOLS,
        "max_tokens": config.env_int("LOOP_MAX_TOKENS", 384000),
        "thinking": {"type": "enabled", "budget_tokens": config.THINK_BUDGET},
    }).encode()
    req = urllib.request.Request(url(), body, {
        "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=config.env_int("LOOP_HTTP_TIMEOUT_S", 1800)) as r:
        return json.load(r)
