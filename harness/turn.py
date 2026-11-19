"""One model turn: parse the response, run its calls, decide the next step.

The run loop owns record events, credentials and settlement. This module owns
the shape of a single turn so the stop policy has one home: a terminal turn
with no text and no tool call is a silent stop, not a result.
"""

import json

from . import tools

NUDGE = ("No tool call was received. If the task is complete, call "
         "done(result) with the final result. Otherwise continue with the "
         "next tool call; do not reply with prose.")
LENGTH_HEAD = "The last reply hit max_tokens"
LENGTH_NUDGE = (LENGTH_HEAD + " before a usable tool call; that "
                "turn was not executed. Re-send the needed call now. If a write "
                "is too large, split it into append=true chunks and verify the "
                "tail with a read.")


def is_length_nudge(text):
    return isinstance(text, str) and text.startswith(LENGTH_HEAD)


def parse_args(raw):
    """Parse a tool-call argument string, tolerating a fenced or prefixed object."""
    if isinstance(raw, dict):
        return raw, None
    if not isinstance(raw, str):
        return None, f"arguments are {type(raw).__name__}, not object"
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    candidates = [text]
    start = text.find("{")
    if start > 0:
        candidates.append(text[start:])
    for candidate in candidates:
        try:
            args = json.loads(candidate, strict=False)
        except (ValueError, TypeError):
            continue
        if isinstance(args, dict):
            return args, None
        return None, f"arguments are {type(args).__name__}, not object"
    return None, "malformed_arguments expected one JSON object"


def canonical_args(raw):
    args, err = parse_args(raw)
    if err is not None:
        return raw if isinstance(raw, str) and raw else "{}"
    try:
        return json.dumps(args, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError):
        return raw if isinstance(raw, str) and raw else "{}"


def record_args(fn, args):
    """A small, deterministic audit record; file bodies stay in the workspace."""
    try:
        if fn == "exec":
            data = {"argv": args.get("argv") or args.get("cmd") or [],
                    "cwd": args.get("cwd")}
            if "stdin" in args:
                data["stdin_bytes"] = len(str(args.get("stdin")).encode())
            if "timeout_ms" in args:
                data["timeout_ms"] = args.get("timeout_ms")
        elif fn == "write":
            text = args.get("data") if isinstance(args.get("data"), str) else ""
            data = {"path": args.get("path"), "bytes": len(text.encode()),
                    "append": args.get("append") is True}
        elif fn == "edit":
            old = args.get("old") if isinstance(args.get("old"), str) else ""
            new = args.get("new") if isinstance(args.get("new"), str) else ""
            data = {"path": args.get("path"), "old_bytes": len(old.encode()),
                    "new_bytes": len(new.encode())}
        else:
            data = {}
        return json.dumps(data, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)[:1000]
    except (TypeError, ValueError):
        return ""


def read_turn(r, turn=0):
    usage = r.get("usage") or {}
    hit = int(usage.get("prompt_cache_hit_tokens", 0) or 0)
    miss = int(usage.get("prompt_cache_miss_tokens", 0) or 0)
    out = int(usage.get("completion_tokens", 0) or 0)
    choice = (r.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    message = {"role": "assistant", "content": None, "tool_calls": [],
               "reasoning_content": msg.get("reasoning_content") or ""}
    for index, call in enumerate(msg.get("tool_calls") or []):
        fn = call.get("function") or {}
        message["tool_calls"].append({
            "id": f"c{turn}.{index}" if turn else (call.get("id") or ""),
            "type": call.get("type") or "function",
            "function": {"name": fn.get("name") or "",
                         "arguments": canonical_args(fn.get("arguments") or "{}")}})
    text = msg.get("content")
    if not message["tool_calls"] and not (isinstance(text, str) and text.strip()):
        # A silent stop may be followed by the nudge; an empty assistant turn
        # is valid where a null content with no calls can be rejected.
        message["content"] = ""
    return (hit, miss, out, len(msg.get("reasoning_content") or ""),
            choice.get("finish_reason"), message, text)


def run_calls(message, obs_dir, root, obs_n, max_inline=None, ledger=None,
              read_inline=None):
    calls = []
    done = None
    for call in message["tool_calls"]:
        fn = call["function"]["name"]
        args, err = parse_args(call["function"]["arguments"])
        if err is not None:
            obs = f"err {err}" if err.startswith("bad_args") else f"err malformed_arguments {err}"
            calls.append({"id": call["id"], "name": fn, "observation": obs,
                          "bytes": len(obs.encode()), "saved": None})
            continue
        audit = record_args(fn, args)
        if fn == "done":
            result = args.get("result", "")
            if not isinstance(result, str):
                obs = (f"err bad_args done requires result:str, got "
                       f"{type(result).__name__}")
                calls.append({"id": call["id"], "name": fn, "observation": obs,
                              "bytes": len(obs.encode()), "saved": None})
                continue
            done = {"id": call["id"], "result": result}
            break
        obs_n += 1
        saved = []
        try:
            obs = tools.dispatch(fn, args, obs_dir, f"obs-{obs_n}", root,
                                 rel_base=root, saved=saved, max_inline=max_inline,
                                 ledger=ledger, obs_id=f"obs-{obs_n}",
                                 read_inline=read_inline)
        except Exception as e:
            obs = (f"err harness {type(e).__name__}: {e}; "
                   f"exec argv or cmd, write path+data, edit path+old+new")
        entry = {"id": call["id"], "name": fn, "observation": obs,
                 "bytes": len(obs.encode()), "saved": saved[0] if saved else None}
        if audit:
            entry["args"] = audit
        calls.append(entry)
    return calls, done, obs_n


def stop(message, text, turn, nudged, finish_reason=None):
    """Return the terminal action for a turn with no done call, or None.

    ('done', result)        non-empty assistant text is the answer
    ('nudge', NUDGE)        empty stop after real work gets one retry
    ('nudge', LENGTH_NUDGE) a truncated reply always gets a retry; a turn that
                            ran out of output is unfinished work, not a stop
    ('no_tool_call', None)  empty stop with no prior work or after one nudge
    None                    the turn has tool calls; execute and continue
    """
    if finish_reason == "length":
        return "nudge", LENGTH_NUDGE
    if message["tool_calls"]:
        return None
    if isinstance(text, str) and text.strip():
        return "done", text.strip()
    if turn > 1 and not nudged:
        return "nudge", NUDGE
    return "no_tool_call", None
