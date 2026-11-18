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
LENGTH_NUDGE = ("The last reply hit max_tokens before a usable tool call. "
                "Reply with one tool call and no private reasoning. Split a "
                "large write into append=true calls under 4000 bytes.")


def canonical_args(raw):
    try:
        args = json.loads(raw, strict=False)
    except (ValueError, TypeError):
        return raw or "{}"
    if not isinstance(args, dict):
        return raw or "{}"
    try:
        return json.dumps(args, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError):
        return raw or "{}"


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


def run_calls(message, obs_dir, root, obs_n, max_inline=None, ledger=None):
    calls = []
    done = None
    for call in message["tool_calls"]:
        fn = call["function"]["name"]
        try:
            args = json.loads(call["function"]["arguments"], strict=False)
            if not isinstance(args, dict):
                raise ValueError(f"arguments are {type(args).__name__}, not object")
        except (ValueError, TypeError) as e:
            obs = f"err malformed_arguments {e}"
            calls.append({"id": call["id"], "name": fn, "observation": obs,
                          "bytes": len(obs.encode()), "saved": None})
            continue
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
                                 ledger=ledger, obs_id=f"obs-{obs_n}")
        except Exception as e:
            obs = (f"err harness {type(e).__name__}: {e}; "
                   f"exec argv, write path+data, edit path+old+new")
        calls.append({"id": call["id"], "name": fn, "observation": obs,
                      "bytes": len(obs.encode()), "saved": saved[0] if saved else None})
    return calls, done, obs_n


def stop(message, text, turn, nudged, finish_reason=None):
    """Return the terminal action for a turn with no done call, or None.

    ('done', result)        non-empty assistant text is the answer
    ('nudge', NUDGE)        empty stop after real work gets one retry
    ('nudge', LENGTH_NUDGE) a truncated reply gets one retry with a tighter ask
    ('no_tool_call', None)  empty stop with no prior work or after one nudge
    None                    the turn has tool calls; execute and continue
    """
    if message["tool_calls"]:
        return None
    if finish_reason == "length" and not nudged:
        return "nudge", LENGTH_NUDGE
    if isinstance(text, str) and text.strip():
        return "done", text.strip()
    if turn > 1 and not nudged:
        return "nudge", NUDGE
    return "no_tool_call", None
