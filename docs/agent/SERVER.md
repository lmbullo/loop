# Server, queue and workers

**Read when:** starting/stopping the control plane, operating the queue,
diagnosing a stuck or detached run, or changing worker lifecycle.
**Source of truth:** `harness/server.py`, `harness/srvcmd.py`,
`harness/srvdaemon.py`, `harness/srvwork.py`, `harness/srvconn.py`,
`harness/srvctl.py`, `harness/worker.py`, `harness/queue.py`,
`harness/workers.py`, `manifest.server`.
**Verify:** `python3 run.py server status`, `python3 run.py server runs --json`,
`python3 -m unittest tests.test_queue tests.test_workers tests.test_regstore`.

## Process model

```
one tree  = realpath of the checkout
one daemon per tree (control plane, never executes a model turn)
one run per tree (tree lock)
one detached worker per run (executes the loop, holds the run lock)

client (run.py api) -> server.sock -> daemon -> queue/job -> worker
worker -> record.jsonl <- daemon/client read from disk
```

The daemon owns the queue and the on-disk worker registry. It does not own a
run. Killing or restarting the daemon cannot interrupt a live worker. The
worker's record is the durable truth; the daemon answers from `.logs/` when its
memory is empty.

## Commands

```sh
python3 run.py server start
python3 run.py server stop [--force]
python3 run.py server restart [--all] [--force]
python3 run.py server reload
python3 run.py server status
python3 run.py server list [--json] [--prune]
python3 run.py server runs [--json]
python3 run.py server logs [-n N] [-f]
python3 run.py server _stale
```

| Command | Effect | Exit |
| --- | --- | --- |
| `start` | Probe, clean stale, spawn one daemon, wait ready; idempotent | `0` ok, `5` start failure |
| `stop` | Stop this tree's daemon; refuse a live worker unless `--force` | `0` ok, `2` usage, `5` guard/refusal |
| `restart` | Replace the daemon; detached workers survive; `--all` walks the machine registry | `0` ok, `5` guard/refusal |
| `reload` | Bump `.logs/reload.json`; workers apply at the next turn boundary | `0` |
| `status` | Answer from `.logs/` and the live daemon; print one flat line | `0` running, `1` down or corrupt record |
| `list` | Probe every server in the machine registry | `0` |
| `runs` | Every record with derived state; daemon if available, else disk | `0` ok, `1` corrupt record |
| `logs` | Tail `.logs/server.log`; `-f` follows | `0`, `1` follow error |
| `_stale` | Remove dead socket/pid/registry entries | `0` |

`_daemon` and `_worker` are internal process entries used by `srvctl` and
`srvwork`; do not invoke them directly except when reproducing a bug.

`stop` and `restart` refuse while a worker is live unless `--force`. The force
path first prints the run id, worker pid and task. `stop --force` then uses the
daemon `stop` command, which interrupts workers (SIGTERM, then SIGKILL after 3
seconds). `restart --force` uses the daemon `shutdown` command instead: it
prints the live run but leaves the worker running while the control plane is
replaced.

## State files

| Path | Owner | Meaning |
| --- | --- | --- |
| `.logs/server.sock` | daemon | Unix socket, mode 0600 |
| `.logs/server.pid` | daemon | live daemon pid |
| `.logs/server.log` | daemon/workers | append-only operational log |
| `.logs/server.lock` | `srvctl` | serializes start/stop |
| `.logs/registry.json` | daemon | tree-local registry mirror |
| `$LOOP_REGISTRY` | daemon | machine-wide registry, keyed by realpath(tree) |
| `.logs/queue.json` | daemon | current item plus waiting items |
| `.logs/jobs/<run_id>.json` | daemon | task/root/env payload for one worker |
| `.logs/workers/<run_id>.json` | worker/daemon | pid, proc_start, state, seq, turns, cost |
| `.logs/reload.json` | `server reload` | soft-reload generation |
| `.logs/run.lock` | worker/resume | one run per tree |
| `.logs/runs/<run_id>/record.lock` | worker/resume | one executor per record |
| `.logs/runs/<run_id>/record.jsonl` | worker/resume | durable run record |
| `.logs/runs/<run_id>/obs/` | worker/resume | saved large observations |

If the socket path exceeds 100 bytes, the daemon uses
`$TMPDIR/loop-<sha256(state_dir)[:16]>.sock` and records that path in the
registry. Never guess the address; read the registry or `server status`.

`LOOP_RUNS` selects the state directory. Use one value per tree while a daemon
is live; starting a daemon with a different state directory creates a different
control plane for the same tree.

## Queue lifecycle

`.logs/queue.json` schema is `loop-queue/1`:

```json
{"schema":"loop-queue/1","seq":0,"current":null,"items":[]}
```

An item has `id` (`q000001`), `run_id`, `task`, `root`, `env`, `state`,
`created_at`, `created_ts`, `worker_pid`, `started_at`, `finished_at`.

- `queue.add()` allocates the next id and a new run id.
- `queue.promote()` moves the first waiting item to `current` and sets
  `state=running`, `started_at`.
- `queue.update()` patches `current` or a waiting item by id.
- `queue.finish(state, **fields)` closes `current` with `finished_at`.
- `queue.drop(id)` removes a waiting item.
- `queue.move(id, delta)` swaps with a clamped neighbor.
- All mutations take `.logs/queue.json.lock`.

The supervisor ticks every 0.25 s:

1. Reap finished child processes.
2. Read live worker registry entries.
3. If `current` exists and its worker is live, sync `worker_pid` and return.
4. If `current` has not launched, launch it.
5. Within 6 seconds of launch, tolerate `missing` or `running` record state.
6. If the record is still missing, finish the item as `failed`.
7. If the record is not complete, reconcile it as `worker_lost` and finish the
   item as `interrupted`.
8. If no `current`, promote one waiting item and launch it.

`launch()` writes the job payload, marks the queue item running with
`launched_ts`, spawns `run.py server _worker <run_id>` in a new session, records
the child pid and updates `worker_pid`. A daemon restart reattaches from
`queue.json` and `workers/`; no in-memory state is required.

## Worker lifecycle

`worker.main()`:

1. Load `.logs/jobs/<run_id>.json`; missing job exits 2.
2. Acquire `.logs/run.lock`; busy exits 5.
3. Open `recwrite.Writer(run_id)`; writes `workers/<run_id>.json` with pid,
   `/proc` start fingerprint, state `running`, item, task, root, seq, turns.
4. Install SIGTERM/SIGINT handlers. A stop request appends `interrupted`
   (`reason=server_stop`, `by=server`), marks the worker interrupted with exit
   130, releases locks, removes the job, and exits 130.
5. Apply only `srvwire.ENV_KEYS` from the job payload, then run
   `agent.run_task()`.
6. On normal completion, update the worker entry to `done` or `interrupted`,
   close the record, release the tree lock, remove the job.

Worker liveness is a live pid plus a matching `/proc` start fingerprint, not a
pid alone. `workers.live()` requires `state == "running"`. A dead worker whose
registry entry is still `running` is left for the supervisor to reconcile; it is
not silently deleted.

## Locks and liveness

| Lock | Held by | Consequence |
| --- | --- | --- |
| `.logs/run.lock` | worker or `resume` | second run refused; `api` attaches instead |
| `.logs/runs/<id>/record.lock` | `recwrite.Writer` | another executor cannot append |
| `.logs/server.lock` | `srvctl.start` | start serialized |
| `.logs/queue.json.lock` | queue mutation | queue reads/writes serialized |
| `.logs/workers.lock` | worker registry mutation | registry writes serialized |
| `.logs/registry.json.lock` | registry mutation | atomic registry writes |

A record without `end` and a free `record.lock` is interrupted and resumable. A
record with a held lock is considered live and left alone.

## Reconcile

On daemon start, `recwrite.reconcile("server_start", "server")` scans every
record:

- corrupt: skip; never rewrite;
- complete (`end`): skip;
- lock held: skip;
- otherwise append one `interrupted` event if the last event is not terminal.

The supervisor repeats this for a lost current worker with reason
`worker_lost`. The daemon never deletes records and never infers `end`.

## Soft reload and restart

`server reload` increments `reload.json.generation`. At the top of each turn,
`reload.maybe()` sees the new generation and re-imports
`harness.config`, `harness.api`, `harness.observe`, `harness.tools` and
`harness.pricing`. The system header is regenerated at the next fold. The
in-flight turn is not interrupted and no process restarts.

`server restart` shuts down the daemon with the `shutdown` command and starts a
new one. Workers survive. The new daemon reads `worker` entries and reports the
live run; clients reconnect with `attach` and `from_seq`.

`server stop` stops the daemon. Without `--force` it refuses while a worker is
live. `server restart` has the same guard but `--force` only detaches the
control plane; it does not kill the worker.

## Socket protocol

One JSON request line in, one or more JSON lines out.

Inbound commands: `ping`, `status`, `snapshot`, `runs`, `enqueue`, `drop`,
`move`, `reload`, `stop`, `shutdown`, `run`, `attach`.

- `run`: if a run is current or a worker is live, attach to it. Otherwise add a
  front-of-queue item and stream it. A second `api` therefore attaches to the
  in-flight run; it does not enqueue a second task.
- `attach`: stream a known `run_id` from `from_seq`.
- `stop`: refuses live workers unless `force`; with force it interrupts them and
  stops the daemon.
- `shutdown`: stops the daemon and leaves workers running.
- `enqueue`/`drop`/`move` are the TUI's queue surface.

Every reply is one or more JSON lines. `run`/`attach` first send a `hello`
line, then record events from disk. Streaming stops at `end` or `interrupted`.
The client reconnects after a daemon restart and resumes from the last seen
`seq`.

`snapshot` returns `daemon`, `current`, `last`, `done`, `queue` and `costs`.
`done` is a bounded newest-first list of terminal runs (the current run is
excluded); the TUI renders it below the queue. When the daemon is down, or an
older daemon omits `done`, the TUI calls `srvsnap.local_done()` to derive the
same list from record bytes, skipping any run still held by a live worker.
Done history therefore survives worker exit and does not require restarting
the control plane.

## Environment handed to a worker

Only these keys cross the per-run boundary:

```
LOOP_API_KEY LOOP_AUTH_FILE LOOP_MODEL LOOP_URL LOOP_MAX_TOKENS
LOOP_MAX_INLINE LOOP_HTTP_TIMEOUT_S LOOP_ROOT
```

The worker removes any of these keys not present in the job payload. `LOOP_RUNS`
and `LOOP_REGISTRY` are daemon process settings, not per-run settings.

## Status fields

`server status` prints one flat `key=value` line. When up:

```
tree pid state addr started log detail=ok
runs_on_disk runs_interrupted latest_run
queue_waiting workers_live in_flight run_state reconciled
```

When down it prints `state=down pid=0 addr=- ...` and exits 1. `run_state` is
`running` when a live worker exists, `complete` when the daemon's current run
summary is complete, otherwise `-`. `runs_interrupted` counts every record whose
state is not `complete`.

## Guards and traps

- One run per tree is enforced by `.logs/run.lock` in the worker and `resume`,
  not by the daemon.
- The daemon never executes a model turn; do not add model code to server
  modules.
- Server modules must never import `tui/`.
- Do not delete `.logs/` while a worker is live; that destroys the run record.
- A `server restart` is not a run restart. Use `resume` for an interrupted run.
- A stopped daemon does not stop workers. Check `server status` or
  `workers.live_entries()`.
- `server status` exits 1 when the daemon is down even if records are healthy;
  `view` and `server runs` still work.
