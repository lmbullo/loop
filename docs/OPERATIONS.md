# Operations

## One tree, one daemon, one run

A tree is the real path of the checkout. The daemon is per tree; the machine
registry is shared. The tree lock allows one executing run at a time. A second
`api` invocation attaches to the in-flight run instead of starting another.

## Commands

```sh
python3 run.py server start
python3 run.py server status
python3 run.py server list [--json]
python3 run.py server runs [--json]
python3 run.py server logs [-n N] [-f]
python3 run.py server reload
python3 run.py server stop [--force]
python3 run.py server restart [--all] [--force]
```

- `start` is idempotent: probe, clean stale, spawn, wait ready.
- `stop` refuses while a worker is live unless `--force`; force names the run,
  worker pid and task before interrupting.
- `restart` replaces the control plane only. Live workers survive and the new
  daemon reattaches from disk.
- `reload` is soft: per-turn modules and the header refresh at the next turn
  boundary; the in-flight turn is never interrupted.
- `status` answers from `.logs/`, not from process memory.

Exit codes: `0` ok, `1` status down or a corrupt record, `2` usage, `5` start
failure or a guard refusal.

## Queue and workers

- `.logs/queue.json` - current item plus waiting items; daemon-owned.
- `.logs/jobs/<run_id>.json` - payload handed to the worker.
- `.logs/workers/<run_id>.json` - pid, `proc_start`, state, seq, turns, cost.
- `.logs/runs/<run_id>/record.jsonl` - the run.

The supervisor promotes one item when no worker is live, then spawns
`run.py server _worker <run_id>` detached. A live worker is identified by a
live pid plus a matching `/proc` start fingerprint, so pid reuse cannot fake
liveness.

## Reconcile rule

On start and on every supervisor tick without a live worker:

1. scan records without `end`;
2. try the record lock;
3. if free, append one `interrupted` event;
4. if held, leave the record alone.

Corrupt records are never rewritten. Records are never deleted.

## Environment

| name | default | effect |
| --- | --- | --- |
| `LOOP_ROOT` | repo root | sandbox root for relative tool paths |
| `LOOP_RUNS` | `<repo>/.logs` | artifacts, socket, pidfile, registry |
| `LOOP_REGISTRY` | XDG state | machine-wide server registry |
| `LOOP_AUTH_FILE` | `~/.pi/agent/auth.json` | file holding `deepseek.key` |
| `LOOP_API_KEY` | unset | literal key, wins over the file |
| `LOOP_MODEL` | `deepseek-flash` | model id |
| `LOOP_URL` | DeepSeek endpoint | chat completions URL |
| `LOOP_MAX_TOKENS` | 384000 | request `max_tokens` |
| `LOOP_MAX_INLINE` | 32768 | inline observation byte limit |
| `LOOP_HTTP_TIMEOUT_S` | 1800 | HTTP timeout |

Per-run env is passed from the client to the worker by the daemon; only the
keys listed in `manifest.server.env_passed_per_run` cross that boundary.

## Runbook

### A run is stuck

```sh
python3 run.py server status
python3 run.py server logs -n 80
python3 run.py view --list
```

If a worker is live, let it finish or use `server stop --force` deliberately.
If the worker is gone, the next `server start` reconciles the record.

### The daemon will not start

```sh
python3 run.py server logs -n 40
python3 run.py server _stale      # removes dead socket/pid/registry entries
python3 run.py server start
```

A too-long socket path is normal: the address falls back to a hashed path under
the temp directory and is recorded in the registry, never guessed.

### Resume an interrupted run

```sh
python3 run.py view --list                 # find a non-complete record
python3 run.py resume RUN_ID               # costs money
```

Resume refuses a complete record, a corrupt record, a tree with a live run, or
a record held by another executor (exit 5).

### Delete runtime state

Stop the daemon first. Deleting `.logs/` under a live worker destroys the run
record. Fixtures, scenarios and `records/` are read-only and never deleted.
