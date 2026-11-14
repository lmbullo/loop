# Agent wire: tools, observations, cost

**Read when:** changing a tool, bounding rule, observation format, stop
condition, or cost accounting; or reasoning about what the model sees.
**Source of truth:** `harness/api.py`, `harness/agent.py`, `harness/tools.py`,
`harness/observe.py`, `harness/spawn.py`, `harness/pricing.py`,
`manifest.wire`, `manifest.cost_model` and `manifest.env`.
**Verify:** `python3 -m unittest tests.test_agent_context tests.test_observe
tests.test_tools tests.test_spawn tests.test_pricing`,
`python3 run.py sim1 edge`, `python3 run.py sim2 edge2`.

## Message list

The model sees a strict append-only list:

```
system   api.header()            rebuilt at each fold from current config
user     run_start.task
for each turn event:
  assistant  turn.message         content is null; tool_calls carry the calls
  tool       one per call         keyed by call.id, content is call.observation
```

- Reasoning is never re-sent. `turn.usage.reasoning_c` counts characters of
  returned `reasoning_content`, not tokens.
- Assistant text is not recorded and not re-sent. There is no text channel.
- A turn with no tool call ends the run with `finish=no_tool_call`.
- `done` ends the run; it is recorded in `turn.done` and `end`, not as a tool
  observation.
- The whole list is re-sent each turn. Only the appended suffix is a cache miss.

## Tools

The production tool schema is `harness/api.py:TOOLS`. `run_start.tools` records
the four names in order.

| Tool | Signature | Behavior |
| --- | --- | --- |
| `exec` | `exec(argv: [str], cwd?: str, stdin?: str, timeout_ms?: int)` | Spawn argv literally; return exit, duration, stdout and stderr. |
| `write` | `write(path: str, data: str, append?: bool)` | Write UTF-8 at path; replace unless `append is true`; create parents. |
| `edit` | `edit(path: str, old: str, new: str)` | Replace exactly one byte occurrence; return a 40-byte context window. |
| `done` | `done(result: str)` | End the run; result goes to `turn.done.result` and `end.result`. |

`exec` details:

- No shell, globs, pipes, redirects or expansion. Use `["sh","-c","..."]` only
  when a shell is actually required.
- `cwd` resolves against the sandbox root (`LOOP_ROOT`) when relative. Default
  `cwd` is `.`. Default timeout is 120000 ms in production; sims default to
  10000 ms.
- A timeout kills the process group and reports `code=TIMEOUT`. A spawn failure
  reports `code=127` and `TypeName: message` on stderr.
- `stdin` is encoded UTF-8; the subprocess runner starts a new session so the
  timeout can kill the whole group.
- Output is always `exit=<code> ms=<dur>\n` followed by the bounded payload.

`write` details:

- `data` must be `str`; missing or non-str returns
  `err bad_args write requires data:str, got NoneType` (or the actual type).
- Success is `ok wrote <n>B <path>` plus ` replaced=<prior>B` or
  ` appended_to=<prior>B` when the file already existed.
- `append` is true only when the JSON value is exactly `true`; any other value
  replaces.

`edit` details:

- `old` and `new` must be `str`.
- Exactly one match is required. Zero or multiple matches returns
  `err match=<n> expected=1`; the file is not changed.
- Success is `ok -<old bytes> +<new bytes> <path>` and a context window from 40
  bytes before to 40 bytes after the replacement.
- Use `edit` for a surgical change; use `write` for a full rewrite.

`done` is not dispatched. `agent.run_calls()` sets `turn.done` and breaks out of
the call list. Any other tool name falls through to the edit implementation and
normally fails with `err bad_args edit ...`.

## Observation formats

Production (`observe.render_api`) receives `stdout + "\n--stderr--\n" + stderr`
when stderr is non-empty.

| Condition | Observation |
| --- | --- |
| Binary sample | `kind=binary bytes=<n> sha256=<16 hex> head_hex=<24 bytes>` |
| `len(raw) <= LOOP_MAX_INLINE` | raw UTF-8 text, verbatim |
| Larger text | `kind=text bytes=<n> lines=<n> saved=<run-relative path>` then `first15:` and `last5:` |
| No output | empty string |

Bounding details:

- Binary means more than 20% of the first 4096 bytes are non-printable
  (`<9`, `14..31`, or `>126`).
- Binary output is not saved. The digest is the only recoverable description.
- Large text is saved under `.logs/runs/<run_id>/obs/obs-<k>.txt`, where `k`
  counts dispatched tool observations over the run (`done` and malformed-argument
  calls do not consume a name). Saved paths in the wire are run-relative
  (`obs/obs-<k>.txt`) so a record renders the same from any cwd.
- `first15` and `last5` show at most 15 and 5 source lines, each cut to 160
  characters. The full bytes are in the saved file.
- Read the saved file in ranges; do not dump it back into the message list.
- `call.bytes` is the byte length of the rendered observation, not the raw
  subprocess payload. `call.saved` is set only when a large text file was saved.

## Failure responses

Tool errors are observations, not harness crashes. The model decides whether to
retry.

| Trigger | Observation |
| --- | --- |
| `arguments` is not valid JSON or not an object | `err malformed_arguments <detail>` |
| `write` missing/non-str `data` | `err bad_args write requires data:str, got <Type>` |
| `edit` missing/non-str `old` or `new` | `err bad_args edit requires old:str and new:str; <key> incorrect` |
| `edit` match count is not 1 | `err match=<n> expected=1` |
| Tool body raises | `err harness <TypeName>: <detail>; exec argv, write path+data, edit path+old+new` |
| File open/write fails | `err <TypeName>: <detail>` |

Malformed arguments and harness errors are appended as call observations; the
turn continues.

## Cost

Rates live in `manifest.cost_model.pricing_per_1M` and are re-read when the
manifest mtime/size changes:

```
cost = (hit * cache_hit + miss * cache_miss + out * completion) / 1e6
defaults: cache_hit=0.006, cache_miss=0.30, completion=1.20
```

- `hit`, `miss`, `out` come from the API usage fields
  `prompt_cache_hit_tokens`, `prompt_cache_miss_tokens`, `completion_tokens`.
- `reasoning_c` is `len(reasoning_content)`; it is informational and is not in
  the cost formula.
- Each `turn.usage.cost` is rounded to 6 decimals. `end` sums `hit`, `miss`,
  `out`, `reasoning_c` and computes the run cost once.
- The unchanged prefix is a cache hit; only the appended suffix is a miss.
  Output bills highest. The sim projection uses `bytes / 4` as tokens.

## System header

`api.header()` is a fixed text block formatted with the current inline limit.
It states: append-only messages, one JSONL event per fsynced record line, `end`
as the only completion marker, one run per tree, literal argv, the cost model,
the absence of a text channel, the inline observation limit, and the four tool
signatures. The header is refreshed at a soft reload boundary.

## Offline sim wires

Sims are experiments, not the production wire.

| Sim | Inline rule | Saved name | Notes |
| --- | --- | --- | --- |
| `sim1` | payload <=1000B inline; else head 600B + tail 400B | `<label>-<n>.txt` | exec only; no binary detection; output shape `$ code=<code> out=<n>B dur=<ms>ms` |
| `sim2` | ANSI stripped; empty -> `""`; binary digest; >2000B -> shape + saved file | `o<n>.txt` | exec + structured `edit`; blank runs collapsed; output shape `$ code=<code> out=<n>B <body>` |

`sim2` saves the full payload when it exceeds 2000 bytes and inlines the first
2000 bytes only when the payload has at most 40 newlines. Its binary digest does
not include `bytes=` or a saved file. See `docs/agent/WORKFLOWS.md` for scenario
commands and the fixture contract.
