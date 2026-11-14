# Debugging and recovery

**Read when:** a command is blocked, a run is interrupted or stuck, a record is
corrupt, or verification fails.
**Source of truth:** the symptom owner in `MAP.md`; record rules in `RECORD.md`;
control-plane rules in `SERVER.md`.
**Verify:** the command in the symptom row; then `make verify`.

## First probes

Start read-only. Do not delete state or kill a worker before you know which run
owns it.

```sh
git status --short
python3 scripts/doctor.py
python3 run.py server status          # exits 1 when the daemon is down
python3 run.py view --list | tail -10
python3 run.py server logs -n 80
python3 run.py server runs --json
```

`server status` is read-only even when it exits 1. `view` and `server runs` work
with the daemon stopped because they read record bytes from disk.

## Symptom matrix

| Symptom | Inspect | Action |
| --- | --- | --- |
| `Busy: tree lock held by pid=N; one run per tree` | `server status`; `.logs/run.lock` | Wait for the live worker. If it is dead, the daemon reconciles on the next start/tick. Do not delete the lock file. |
| `run ... is held by a live executor` | `server status`; `.logs/runs/<id>/record.lock` | The record has an executor. Wait or `resume` later; never append by hand. |
| Run has no `end` | `python3 run.py view RUN_ID` | It is interrupted. Use `python3 run.py resume RUN_ID` if you want to continue; `view` is enough to inspect. |
| `server status` exits 1 | `server logs -n 80`; registry | `python3 run.py server start`. The daemon can be down while records are healthy. |
| Daemon will not start | `server logs -n 40`; `server _stale` | Run `_stale`, then `start`. A too-long socket path falls back to `$TMPDIR/loop-<hash>.sock`; read the registry, do not guess. |
| `server stop`/`restart` refused | `server status`; live worker entry | A worker is live. Let it finish, or use `--force` knowing it names and interrupts/detaches the run. |
| A second `api` ignores my new task | `server status`; `queue.json` | `api` attaches to the current/live run instead of enqueueing. Use the TUI or the daemon `enqueue` command for a second task. |
| Queue stuck on `current` | `server status`; `.logs/queue.json`; `.logs/workers/` | The supervisor promotes after a lost worker (about 6s tolerance). Do not hand-edit `queue.json` while the daemon runs. |
| Worker died | `workers/<run_id>.json`; record state | The daemon reconciles an unlocked record to `interrupted`; then decide whether to `resume`. |
| `api` exits 3 | record `error` event; `LOOP_API_KEY`/auth file | Missing credentials. Fix `LOOP_API_KEY` or `LOOP_AUTH_FILE`; the failed run still has an inspectable record. |
| `api` exits 4 | record `error` event; `server logs` | HTTP/model error. Do not retry blindly; read the recorded body and the model/env settings. |
| `api` exits 5 | `server logs`; `server status` | The control plane is unavailable. Fix the daemon, then retry; do not assume the task ran. |
| `resume` exits 5 | `server status`; lock holders | A tree run or the record is held. Wait for it to finish; do not force. |
| `resume` exits 2 | `view --list`; record state | The run is complete, corrupt, or the id is wrong. Nothing to resume. |
| Record is corrupt | `view RUN_ID`; raw lines | Never rewrite complete lines. Preserve the file, find the first bad `seq`/field/JSON line, and fix the producer/test. |
| `[torn] bytes=N` in view | last line of `record.jsonl` | A partial trailing line. The next writer truncates it; `resume` reports it. Do not edit earlier lines. |
| Large observation is a summary | `call.saved`; `obs/` | Read the saved file in ranges. Binary observations are a digest only; the raw bytes are not recoverable from the record. |
| Tests wrote real `.logs/` | test code and env | Use `tests.support.sandbox()`; it redirects `LOOP_*`. Do not delete the repo `.logs/` to clean up a test. |
| `check lines` fails | `python3 run.py check lines` | Split the module or move behavior to a new module. Do not raise the 200-line limit for a source file. |
| `check_manifest.py`: unregistered source | `manifest.files[]` | Add the file with a `kind` and `role`; every `.py` under `harness/`, `tui/`, `tests/`, `scripts/` is checked. |
| `check_manifest.py`: bad scenario/check/record | the manifest row | Make `argv`/`expect_exit`/`network`, `scenarios[]` steps, or record types match the tree. |
| `check tui` fails | `tui/panes.py`, `tui/prompt.py`, `tui/render.py` | Fix fit/reflow/width. Do not weaken the audit. |
| Sim fails | `.logs/<sim>/<label>/log.json`; `obs/`; scenario JSON | Check the `sim` field, fixture, step schema, exit behavior and mounted workspace. |
| Docs look stale | `manifest.json`, owning module, tests | Code wins. Update the doc and, if the contract changed, the manifest in the same commit. |

## Safe and unsafe commands

Read-only or isolated:

```sh
python3 run.py                              # usage
python3 run.py view --list
python3 run.py view RUN_ID [--json]
python3 run.py view --schema
python3 run.py server status                # exits 1 when down
python3 run.py server runs [--json]
python3 run.py server logs -n 80
python3 run.py check lines
python3 run.py check tui
python3 scripts/check_manifest.py
python3 scripts/repo_map.py
python3 scripts/doctor.py
python3 run.py sim1 task                    # writes only .logs/sim1/
python3 run.py sim2 task2                   # writes only .logs/sim2/
```

Mutating or expensive:

- `run.py api` / `run.py resume`: network, tokens, record writes.
- `server start|stop|restart|reload`: process/queue/registry changes.
- `server list --prune`: removes dead registry entries.
- `sim1`/`sim2`: rewrite `.logs/<sim>/<label>/`.
- `make clean`: removes bytecode/caches, never `.logs`.
- `scripts/verify.py`: its `clean` check deletes `__pycache__`; offline checks
  may spawn sims and write `.logs/sim*`.

Never:

- run `api` or `resume` in offline verification;
- delete `.logs/` while a worker is live;
- hand-edit a complete record line;
- rewrite `fixtures/`, `scenarios/` or `records/` in place during a run;
- kill a worker pid from a stale registry entry without checking its start
  fingerprint and the live record lock;
- commit `.logs/`, `__pycache__/`, credentials or generated blobs;
- hide a failed tool call instead of recording it as an observation.

## Recovery order

1. Identify the state: `server status`, `view --list`, worker registry.
2. Identify the owner: tree lock, record lock, live pid + proc_start.
3. Prefer waiting for a live worker over force-stopping it.
4. Prefer `view` or `resume` over rewriting a record.
5. Prefer daemon reconcile over hand-editing queue/worker files.
6. After recovery, run the relevant verification and record the exact command
   in the commit `check:` line.

## Escalation map

| Layer | Read | Change |
| --- | --- | --- |
| Record bytes | `RECORD.md` | `recwrite.py` only through `Writer` |
| Turn loop | `WIRE.md` | `agent.py` + tests |
| Tools/observations | `WIRE.md` | `tools.py`, `observe.py` + tests |
| Daemon/workers | `SERVER.md` | `srv*.py`, `worker.py`, `queue.py` + tests |
| Contract | `manifest.json` | `scripts/check_manifest.py` must pass |
| Docs | this folder | `manifest.files[]` + `index.json` |
