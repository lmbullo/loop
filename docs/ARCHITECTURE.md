# Architecture

## Layers

```
run.py                     dispatcher over manifest.entrypoints[]
manifest.json              contract: files, entrypoints, record, checks, cost
harness/                   loop, record, control plane, sims, audits
tui/                       polling renderer over daemon snapshots
scenarios/ + fixtures/     offline transcripts and sandboxes
records/                   frozen artifacts, never written
tests/ + scripts/ + docs/  agent support surface
```

## The loop

```
run_start
  -> messages = [system(header), user(task)]
  -> model call
  -> turn event: usage, assistant message, tool calls, observations
  -> append tool messages
  -> repeat until done or no tool call
end
```

The message list is rebuilt by folding the record:

```
msgs = [system(header at run_start.max_inline), user(task)]
for turn in turns:
    msgs.append(turn.message)
    msgs.extend(tool(call.id, call.observation) for call in turn.calls)
```

`agent.context()` is that fold. `resume` and a fresh run share the same code
path; a resume only appends a marker first.

## Record and locks

- `.logs/runs/<run_id>/record.jsonl` - append-only, one fsynced line per event.
- `.logs/runs/<run_id>/record.lock` - flock held by the live executor.
- `.logs/run.lock` - tree-wide lock; one run per tree.
- `.logs/runs/<run_id>/obs/` - raw bytes for bounded observations.

The lock is the liveness signal. A record without `end` and with a free lock is
interrupted and resumable. A record with a locked executor is left alone.

## Control plane

The daemon owns the queue and the on-disk worker registry. It never executes a
model turn.

- `server start` attaches or spawns one daemon per tree, then returns.
- `api` enqueues, then attaches to the run record through the daemon.
- The daemon promotes one waiting item and spawns a detached worker.
- The worker holds the tree lock, writes the record, and survives daemon loss.
- `server restart` replaces the daemon only; workers keep running and the new
  daemon reattaches from `.logs/queue.json` and `.logs/workers/`.
- `server reload` bumps a generation file; workers re-import per-turn modules
  and refresh the system header at their next turn boundary.

Every reply that matters is answered from disk, not daemon memory.

## Bounded observations

Two independent bounding rules exist because the two wires ask different
questions:

- `observe.render_api` (production): binary digest, verbatim when small,
  `kind=text` shape + saved file when large.
- `observe.render_v1` / `render_v2` (offline sims): fixed head/tail and
  shape-aware variants. These are experiments, not the production wire.

The invariant is identical: observations are verbatim except for the bounding
rule, and the full bytes are recoverable from the saved file.

## Failure model

- Process kill: at most the in-flight turn is lost; completed lines are fsynced.
- Torn tail: the next writer truncates the incomplete line before appending.
- Daemon kill: workers survive; a replacement reconciles from disk.
- Worker kill: the free record lock leaves the run interrupted and resumable.
- Corrupt record: never rewritten by the daemon; `view` reports corruption.

## Why the TUI is separate

The TUI imports only its own client and model code. It sends enqueue/drop/move
requests and renders a snapshot. It cannot own a run, hold a lock, or become a
second source of truth. Server modules never import `tui/`.
