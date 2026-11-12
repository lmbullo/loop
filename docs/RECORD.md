# Record

The record is the only durable truth. Everything else is a cache, a view or a
lock.

## Location

```
.logs/runs/<run_id>/record.jsonl
.logs/runs/<run_id>/record.lock
.logs/runs/<run_id>/obs/
.logs/run.lock
```

`run_id` is `YYYYMMDDTHHMMSSmmmZ-<8 hex>`; lexicographic order is chronological
order. The newest run is `max(run_id)`.

## Line format

One JSON object per line, UTF-8, LF terminated, no embedded newline:

```json
{"schema":"loop-record/1","v":1,"run_id":"...","seq":1,"ts":"...","type":"run_start","data":{...}}
```

- `seq` is contiguous from 1 and is never reused.
- Unknown envelope fields or payload fields are corruption, not extensions.
- A final line without LF is a torn write. The next writer truncates it.
- Complete lines are never modified.

## Events

| type | terminal | payload |
| --- | --- | --- |
| `run_start` | no | task, root, entrypoint, model, tools, max_inline, record_source |
| `turn` | no | turn, finish_reason, usage, message, calls, done |
| `resume` | no | from_seq, turn, messages, root, by |
| `error` | no | code, text, finish |
| `interrupted` | yes | reason, last_seq, by |
| `end` | yes | exit, finish, result, turns, hit, miss, out, reasoning_c, cost |

`end` is the only completion marker. A record whose last event is not `end` is
interrupted, even if no `interrupted` event exists.

## Derived state

```
empty        no events
interrupted  last event is not end
complete     last event is end
```

`recread.state()` implements exactly this. `view.render()` adds a derived
`[interrupted] reason=no_terminal_event` line when the state is interrupted and
the last event is not an explicit `interrupted` marker.

## Folding

The message list is a pure fold over the events:

1. system header using `run_start.max_inline`
2. user `run_start.task`
3. for each `turn`: the assistant `message`
4. for each call in that turn: one `tool` message keyed by `call.id`

`resume` rebuilds this list, then continues. It does not replay tools.

## Reading and viewing

```sh
python3 run.py view --list
python3 run.py view RUN_ID
python3 run.py view RUN_ID --json
python3 run.py view --json RUN_ID | python3 run.py view -
```

`view` is a pure function of record bytes: no server, no network, no clock and
no cwd. `--json` emits the canonical `loop-view/1` document and `view -` reads
it back.

## Writing

Only `recwrite.Writer` appends. It:

1. validates the run id;
2. takes the per-run flock (non-blocking) and raises `Busy` if held;
3. reads existing events and truncates a torn tail;
4. writes one canonical line with `O_APPEND`, then `fsync`s;
5. seals on `end`; appends after sealing raise `Sealed`.

Crash safety: a kill loses at most the in-flight turn. `end` is never inferred;
the daemon's reconcile appends an `interrupted` marker only to unlocked records.
