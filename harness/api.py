"""The wire: tool schemas, the static system header, one model call.

The schema, the header, the model and the limits are one snapshot per run, so
the prefix stays a cache hit; only a task or an observation is ever appended.
Argument order mirrors `tools.SIGNATURES`, and every schema carries the failure
contract in its own description: a tool that cannot say how it fails costs a
turn to learn.
"""

import json
import urllib.request

from . import config, tools

TOOLS = [
    {"type": "function", "function": {
        "name": "exec",
        "description": "Run cmd (str) through sh -c for pipes, globs and compound "
                       "lines, or argv (list) for literal spawn. Read-like output "
                       "stays contiguous up to 8 KiB; larger output is saved and "
                       "shaped with one runnable next: call.",
        "parameters": {"type": "object", "properties": {
            "cmd": {"type": "string",
                    "description": "one shell line, e.g. 'cd sub && grep -n x f | head'"},
            "argv": {"type": "array", "items": {"type": "string"},
                     "description": "literal argv, no shell: ['git','status']"},
            "cwd": {"type": "string", "description": "relative to the workspace root"},
            "stdin": {"type": "string"},
            "timeout_ms": {"type": "integer"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "read",
        "description": "Numbered lines of one file, paged: start/end for a range, "
                       "find (+ctx) for pattern hits, offset for a long single line. "
                       "Prints shown a-b of N and a runnable next: call.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "start": {"type": "integer", "description": "first line, 1-based"},
            "end": {"type": "integer", "description": "last line, inclusive"},
            "find": {"type": "string", "description": "regex; returns matching ranges"},
            "ctx": {"type": "integer", "description": "context lines around a find hit"},
            "offset": {"type": "integer", "description": "byte offset into the file"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write",
        "description": "Write UTF-8 data; append=true continues a chunked file. "
                       "Whole-file write; use edit for a small span.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "data": {"type": "string"},
            "append": {"type": "boolean"}}, "required": ["path", "data"]}}},
    {"type": "function", "function": {
        "name": "edit",
        "description": "Replace unique spans in one atomic call: old+new, or "
                       "edits:[{old,new}], all-or-nothing. A miss reports match "
                       "count, line numbers and the fix, never a traceback.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "old": {"type": "string"}, "new": {"type": "string"},
            "edits": {"type": "array", "description": "batch of {old,new} hunks",
                      "items": {"type": "object", "properties": {
                          "old": {"type": "string"}, "new": {"type": "string"}},
                          "required": ["old", "new"]}},
            "replace_all": {"type": "boolean"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "done",
        "description": "End the run with compact evidence: changed paths, checks, risk.",
        "parameters": {"type": "object", "properties": {
            "result": {"type": "string"}}, "required": ["result"]}}},
]
WIRE_SCHEMA = "loop-wire/2"

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
- observations are shaped: `shown a b of N`; the printed `next:` line is the
  exact call that continues it, so copy it instead of deriving a range.
  Read-like commands keep up to 8 KiB contiguous; run one command per call.
- `same=obs-N` is a byte-identical earlier observation; do not fetch it again
- a failed call explains the fix; do not send it unchanged

Output is billed. Never echo file contents, diffs or long lists into tool
arguments or done.result. done.result = changed paths, checks run, residual
risk. There is no turn or time cap; call done(result) when the task is done.
"""

# One note per signature; the call lines themselves come from tools.SIGNATURES so
# the header cannot describe a tool the dispatcher does not have.
NOTES = {
    "exec": "  cmd is one shell line through sh -c; argv is literal, no shell. Either key\n"
            "  alone works. cwd defaults to the workspace root and persists nowhere, so put\n"
            "  `cd sub &&` inside one cmd instead of a separate call.",
    "read": "  Numbered lines plus one executable next: call; no shell quoting needed.",
    "write": "  Whole-file write; append=true continues a chunked file.",
    "edit": "  old+new or edits:[{old,new}], all-or-nothing; returns a numbered window.",
    "done": "  Ends the run.",
}


def model():
    return config.env("LOOP_MODEL", config.DEFAULT_MODEL)


def url():
    return config.env("LOOP_URL", config.DEFAULT_URL)


def signatures():
    """Call lines in dispatch order, each with its one-line note."""
    order = ("exec", "read", "write", "edit", "done")
    return "\n" + "\n".join(tools.SIGNATURES[name] + "\n" + NOTES[name] for name in order)


def header():
    return BASE + signatures() + "\n"


def thinking():
    return {"type": "enabled", "budget_tokens": config.think_budget()}


def max_tokens():
    return config.max_tokens()


def snapshot():
    spec = {"schema": WIRE_SCHEMA, "system": header(),
            "tools": json.dumps(TOOLS, sort_keys=True, separators=(",", ":")),
            "thinking": json.dumps(thinking(), sort_keys=True, separators=(",", ":")),
            "model": model(), "max_tokens": max_tokens(),
            "renderer": config.RENDERER, "replay_reasoning": config.replay_reasoning()}
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
