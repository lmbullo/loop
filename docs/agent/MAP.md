# Tree map

**Read when:** finding the module that owns a behavior, an entry point, or a
file that is safe to write.
**Source of truth:** `manifest.entrypoints`, `manifest.files[]`, and the modules.
**Verify:** `python3 scripts/repo_map.py`, `python3 scripts/check_manifest.py`.

## Entry points

`run.py` is the only executable entry. It loads `manifest.json`, looks up
`argv[1]` in `entrypoints[]`, imports `entry.module`, and calls `entry.function`
(default `main`). Do not add a second top-level script.

| id | module | Network | Main writes |
| --- | --- | --- | --- |
| `api` | `harness.agent` | yes, expensive | daemon queue, then worker: record, lock, obs |
| `server` | `harness.server` | no | socket, pid, log, registry, queue, jobs, workers, reconcile |
| `view` | `harness.view` | no | none; pure read/render |
| `resume` | `harness.resume` | yes, expensive | the existing record, lock, obs |
| `sim1` | `harness.sim1` | no | `.logs/sim1/<label>/` |
| `sim2` | `harness.sim2` | no | `.logs/sim2/<label>/` |
| `check` | `harness.checks` | no | none; static audit |
| `tui` | `tui.app` | no | daemon queue through the socket; may start the daemon |

`api` does not execute a run in the client process. It starts or attaches to the
tree daemon, submits a task, and tails the worker's record. A detached worker
owns execution and the run lock. `resume` is the exception: it executes in the
client process and takes the tree lock itself.

## Runtime flow

```
run.py api TASK
  -> srvctl.start()                       one daemon per tree
  -> srvconn "run"                        attach if a run is in flight,
                                          else queue.add(front=True)
  -> srvwork.launch()                     job.write + detached worker
  -> worker.main(run_id)
       -> recwrite.acquire_tree()         .logs/run.lock
       -> recwrite.Writer(run_id)         .logs/runs/<run_id>/record.lock
       -> agent.run_task()
            -> fold record -> messages
            -> api.call()                 model
            -> tools.dispatch()           exec/write/edit
            -> writer.append("turn")      one fsynced JSONL line
            -> repeat until done or no tool call
       -> writer.append("end")            the only completion marker
  -> client streams record events from disk until end/interrupted
```

`view` never enters this flow. It reads record bytes and renders them.

## Subsystems

### Turn loop and wire

| Path | Owns |
| --- | --- |
| `harness/agent.py` | derive/totals, context fold, response parsing, tool calls, `end` |
| `harness/api.py` | tool schemas, system header, model id, HTTP call |
| `harness/tools.py` | `exec`, `write`, `edit` bodies and dispatch |
| `harness/observe.py` | `render_api`, `render_v1`, `render_v2` bounding rules |
| `harness/spawn.py` | one literal-argv subprocess; timeout and OSError mapping |
| `harness/pricing.py` | manifest rates, cost formula, hot reload by mtime |
| `harness/auth.py` | `LOOP_API_KEY`, else `LOOP_AUTH_FILE.deepseek.key` |
| `harness/reload.py` | reload generation and per-turn module re-import |

### Record

| Path | Owns |
| --- | --- |
| `harness/record.py` | run ids, paths, canonical JSON, UTC stamp, discovery |
| `harness/recread.py` | parse, torn tail, derived state, list rows |
| `harness/recschema.py` | manifest record schema, strict envelope/payload checks |
| `harness/recwrite.py` | append writer, per-run lock, tree lock, reconcile |
| `harness/view.py` | pure text renderer and `loop-view/1`; `--list`, `--schema` |
| `harness/resume.py` | rebuild messages from an interrupted record and continue |

### Control plane and shared state

| Path | Owns |
| --- | --- |
| `harness/server.py` | command dispatch and `_daemon` / `_worker` internals |
| `harness/srvcmd.py` | `start`, `stop`, `restart`, `reload`, `status`, `list`, `runs`, `logs` |
| `harness/srvctl.py` | daemon spawn/probe/stop/clean-stale, log tail |
| `harness/srvdaemon.py` | socket serve loop, registry entry, startup reconcile, shutdown |
| `harness/srvwork.py` | supervisor: reap, promote queue, launch one worker |
| `harness/srvconn.py` | socket command handlers; force-stop interruption |
| `harness/srvclient.py` | client attach/stream/reconnect; `api` entry |
| `harness/srvrun.py` | run targeting and record tailing to a client |
| `harness/srvsnap.py` | snapshot/status views used by TUI and `server status`; snapshot carries current, queue and a bounded done list |
| `harness/srvlist.py` | registry views, prune, `restart --all` |
| `harness/srvwire.py` | newline JSON framing, timeouts, per-run env key list |
| `harness/worker.py` | detached executor: tree lock, writer, signals, job cleanup |
| `harness/workers.py` | on-disk worker registry and pid+start liveness |
| `harness/queue.py` | daemon-owned queue: add, promote, update, finish, drop, move |
| `harness/job.py` | per-run payload under `.logs/jobs/<run_id>.json` |
| `harness/registry.py` | state paths, socket path fallback, tree identity |
| `harness/regstore.py` | locked, atomic JSON registry writes |
| `harness/regprobe.py` | pid liveness, `/proc` start fingerprint, socket ping/probe |

### Sims, checks, TUI

| Path | Owns |
| --- | --- |
| `harness/sim1.py` | offline v1 sim: exec only, head 600B + tail 400B |
| `harness/sim2.py` | offline v2 sim: shape-aware, 2000B inline, structured edit |
| `harness/assets.py` | scenario load/defaults and fresh fixture mount |
| `harness/checks.py` | `check lines` (200-line audit), `check tui` layout contract |
| `tui/app.py` | curses shell and raw input loop |
| `tui/client.py` | daemon snapshot/enqueue/drop/move client |
| `tui/{input,keys,prompt}.py` | arrow key dispatch, editing, history, wrapping |
| `tui/panes.py` | fitting/clipping, horizontal rules, one-line running/queued/done rows, muted chrome with a `›` selection marker; row content lives in `tui/rows.py` |
| `tui/rows.py` | row content: state glyphs, short run ids, middle-dot metadata separators, selected-row roles, section count headers |
| `tui/theme.py` | one palette: grey chrome roles, muted state hues, grey prompt roles, `init_colors` |
| `tui/{model,render,worker}.py` | snapshot copy, themed painting of running/queued/done sections with prompt box edge rules, polling |

### Support surface

| Path | Purpose |
| --- | --- |
| `scripts/verify.py` | run `manifest.checks[]` offline; `--skip-server`, `--only`, `--json` |
| `scripts/check_manifest.py` | registered files, importable entries, record/check/scenario integrity |
| `scripts/repo_map.py` | generated manifest map with line counts |
| `scripts/doctor.py` | local health; never starts the daemon |
| `scripts/commit_check.py` | conventional subject plus `why:` / `check:` lines |
| `tests/support.py` | sandbox env, fixed ids, event builders, CLI helper |
| `docs/agent/` | this documentation set; register new files in `manifest.files[]` |

## Write ownership

| State | Only writer |
| --- | --- |
| `.logs/runs/<run_id>/record.jsonl` | `recwrite.Writer`, held by one worker or `resume` |
| `.logs/runs/<run_id>/record.lock` | the executor's `Writer` |
| `.logs/runs/<run_id>/obs/` | the executor's `tools`/`observe` path |
| `.logs/run.lock` | `recwrite.TreeLock` in a worker or `resume` |
| `.logs/queue.json` | the daemon through `queue.py` |
| `.logs/jobs/<run_id>.json` | the daemon (`srvwork.launch`) |
| `.logs/workers/<run_id>.json` | the worker, plus daemon reconcile updates |
| `.logs/reload.json` | `server reload` or the daemon |
| `.logs/server.sock`, `.pid`, `.log`, `.lock` | the daemon |
| `$LOOP_REGISTRY`, `.logs/registry.json` | `regstore` under a file lock |
| `scenarios/`, `fixtures/`, `records/` | read-only; copy before using |

## Import direction

- `tui/client.py` is the only TUI module that imports `harness` server/state
  helpers; the rest of `tui/` stays local. Server modules must never import
  `tui/`.
- `harness/` modules may import each other; `run.py` is the only entry.
- `view`, `recread` rendering and `recschema` validation must not read the
  daemon, network or cwd. `record` owns id/time creation.
- Do not add absolute paths. Roots come from `__file__`, `LOOP_ROOT` or
  `LOOP_RUNS`.

## Where to change what

| Change | Start here | Then register or test |
| --- | --- | --- |
| Tool behavior or observation shape | `harness/tools.py`, `harness/observe.py` | `tests/test_tools.py`, `tests/test_observe.py` |
| Turn loop, stop condition, `end` payload | `harness/agent.py` | `tests/test_agent_context.py`, `tests/test_view.py` |
| Record event fields or state rules | `manifest.record`, `harness/recschema.py` | `tests/test_recschema.py`, `tests/test_recread.py` |
| Daemon command or guard | `harness/srvcmd.py`, `harness/srvconn.py` | `tests/test_manifest.py`, `scripts/verify.py --skip-server` |
| Queue or worker lifecycle | `harness/queue.py`, `harness/srvwork.py`, `harness/worker.py` | `tests/test_queue.py`, `tests/test_workers.py` |
| TUI layout, keymap or palette roles | `tui/panes.py`, `tui/theme.py`, `tui/input.py`, `tui/render.py` | `python3 run.py check tui`, `tests/test_tui_layout.py`, `tests/test_tui_input.py` |
| Offline scenario | `scenarios/` + `manifest.scenarios[]` | `python3 run.py sim1 <id>` |
| New doc | `docs/agent/` | `manifest.files[]` + `docs/agent/index.json` |
