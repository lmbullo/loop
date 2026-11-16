# AGENTS.md

audience: agents. Read before changing the tree.

`manifest.json` is the machine contract. `docs/agent/index.yaml` is the route
table. Code wins over docs: fix the doc and, when the contract is affected,
`manifest.json` in the same commit. Keep machine text machine-first: human-facing
prose belongs only in `README.md`, `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`,
`CODE_OF_CONDUCT.md` and the GitHub issue/PR templates.

Bootstrap: `python3 run.py --json` prints one compact `loop-index/1` line
(purpose, runtime, entrypoints, checks, scenarios, docs, invariants, env, layout,
record, wire). It reads `manifest.json` only: no tree walk, no module import, no
absolute paths.

## What this tree is

A research harness for a tool-calling agent loop. It compares tool and
observation designs by token cost and correctness, using an append-only record
as the only source of truth.

- One exec waist: `exec`, `write`, `edit`, `done`.
- Bounded observations: inline while small; larger text becomes a budget-filling
  head/tail/stderr shape with a byte-sized `next:` slice and saved raw bytes;
  binary output is a digest.
- Cache-aware accounting: the unchanged prefix is a cache hit, only the appended
  suffix is a miss.
- Durable runs: one JSONL record per run; `view` is a pure function over bytes;
  `resume` rebuilds state from the same bytes and continues.
- Detached execution: a per-tree control plane owns queue and worker registry; a
  detached worker owns the run; the daemon can restart without interrupting work.
- Optional verification: `--verify CMD` is declared before the first turn, run
  at the run root after the terminal turn, and recorded before `end`; absence is
  not a pass.

## Read order

| Need | Read |
| --- | --- |
| Rules and protocol | this file |
| Route by task, fast facts, machine routes | `docs/agent/index.yaml` |
| Find the owning module | `docs/agent/MAP.yaml` |
| Inspect, resume, change records | `docs/agent/RECORD.yaml` |
| Tools, observations, verify, cost | `docs/agent/WIRE.yaml` |
| Daemon, queue, workers | `docs/agent/SERVER.yaml` |
| Change/test/verify/commit | `docs/agent/WORKFLOWS.yaml` |
| Diagnose a failure | `docs/agent/DEBUG.yaml` |

## Non-negotiable invariants

- `run.py` is the only entry point. Modules are import-only.
- The message list is append-only; never edit, reorder or re-send old entries.
- The record is append-only; one event per fsynced line; `end` is the only
  completion marker. A missing `end` is the interrupted marker.
- Observations are verbatim except for the bounding rule in `harness/observe.py` and `harness/bound.py`;
  text over the run's bound is summarized and its raw bytes are saved.
- The system header, tool schema, model, `max_tokens`, thinking budget and
  renderer are constant per run and snapshotted in the `wire` event at run
  start; task and observations enter after that static prefix, so a soft reload
  cannot break the cache. `reasoning_content` is replayed because thinking mode
  requires it.
- Output is metered and reported, never gated.
- A terminal turn with no tool call and no text is not final on its own: after
  turn 1 the loop records one `nudge` user message and retries; a second silent
  stop ends with `finish=no_tool_call`.
- `LOOP_ROOT` is the workspace identity: root, sandbox, daemon, socket, queue
  and registry all follow it; `LOOP_RUNS` selects the state directory.
- One run per tree, enforced by `.logs/run.lock`; a second `api` queues a front
  item and waits for the live run.
- The control plane never executes a run; workers survive daemon restart.
- The TUI never owns a run or authoritative state; server code never imports
  `tui/`.
- Fixtures and `records/` are read-only. Each sim run copies its fixture to
  `.logs/<sim>/<label>/ws/`.
- No absolute paths in code or config; roots come from `__file__` or env. Frozen
  `records/` artifacts may carry historical `/home/...` strings as data; they are
  never inputs.
- `exec` argv is literal: no shell, globs, pipes or redirects unless the caller
  passes `sh -c` explicitly.
- Source modules stay under 200 lines. Split, do not grow.
- A `verify` event is evidence, not a gate: it stores `exit`; view renders
  `ok=1` when exit is 0 and `ok=0` otherwise; no command -> no event.

## Commands

```sh
sh install.sh                       # install loop on PATH for this user (~/.local/bin)
sh install.sh --system              # system-wide (/usr/local/bin); run with sudo if needed
python3 run.py --json               # agent index, loop-index/1
python3 run.py                      # usage and the manifest entry point list
python3 run.py check lines          # 200-line source audit
python3 run.py check tui            # resize/truncation contract
python3 run.py view --list          # read records without executing anything
python3 run.py view --list --json   # canonical loop-view/1 list
python3 run.py view RUN_ID          # compact text form
python3 run.py view RUN_ID --json   # canonical loop-view/1
python3 run.py view --schema        # record schema for renderers
python3 run.py sim1 task            # offline exec-only sim
python3 run.py sim2 task2           # offline shape-aware sim
python3 run.py probe                # headless TUI render of a snapshot
python3 run.py tui                  # interactive renderer; no model calls
python3 run.py server start         # start this tree's control plane (stop/restart/reload too)
python3 run.py server status        # this tree's control plane
python3 run.py server runs --json   # every record on disk, daemon if available
python3 run.py server list --json   # machine-wide registry
python3 run.py server logs -n 80    # daemon log tail
python3 run.py server mobile start  # opt-in private-network bridge for mobile/ (stop/status too)
python3 run.py api "task"           # real model call; costs money and network
python3 run.py api --verify CMD "task"  # same, then record verify evidence
make index                          # alias for python3 run.py --json
make check                          # compile + line + tui checks
make test                           # stdlib unittest suite
make lint                           # ruff E4/E9/F when installed, otherwise skipped
make verify                         # manifest-driven offline checks
make audit                          # offline cache audit for RUN (newest by default)
make sim                            # sim1 task + sim2 task2
python3 scripts/check_manifest.py   # contract integrity
python3 scripts/doctor.py           # local environment health
python3 scripts/repo_map.py         # file/entrypoint map for agents
python3 scripts/cache_audit.py RUN_ID  # prefix growth, hit/miss/out/cost, suspected breaks
```

Never run a real `api` call or `resume RUN_ID` in an offline verification. They
require credentials and a network. `scripts/verify.py --skip-server` skips any
argv token, including tokens inside `sh -c`, exactly equal to `server` or `api`;
the `resume-usage` check exercises only the offline usage path.

## Layout

- `run.py` - dispatcher, `--json` index and `--version`; reads `manifest.json`.
- `install.sh` - user/global launcher installer; `--prefix`, `--bindir`, `--system`, `--uninstall`, `--force`, `--dry-run`.
- `harness/` - loop (`agent`, `turn`, `fold`), record, control plane, sims, offline checks.
- `tui/` - thin polling renderer over daemon snapshots.
- `mobile/` - Android-first Flutter client for the opt-in private-network bridge (LAN or Tailscale): one scrollable task list, one fixed bottom prompt and one hairline surface system.
- `scenarios/` - offline sim transcripts.
- `fixtures/` - read-only sandbox trees, copied per sim run.
- `records/` - frozen historical artifacts; never written.
- `tests/` - stdlib `unittest`; no third-party deps.
- `scripts/` - agent verification and inventory tools.
- `docs/agent/` - agent-optimized YAML docs; this file is the rules entry.
- `.logs/` - generated runtime state; git-ignored and never committed.

## Change protocol

1. Run `python3 run.py --json`; find the affected file in `files[]` and read its
   `role`.
2. Make the smallest change that preserves the invariants above.
3. Keep every source module under 200 lines. New behavior goes in a new module
   if needed, not as an append to a near-limit file.
4. Add a focused test under `tests/` for any logic change. Pure functions are
   preferred; tests must not use the network or the real `.logs/`.
5. Register every new tracked file in `manifest.files[]` with a `kind` and a
   `role`. Audited kinds are `module`, `entry`, `test`, `tool`.
6. Update `manifest.checks[]` if you add a verification command, and
   `manifest.scenarios[]` if you add a scenario.
7. Update `docs/agent/*.yaml` and `docs/agent/index.yaml` when public behavior,
   commands, paths or the contract changes.
8. Run `make verify` (or `scripts/verify.py --skip-server`) before committing.
   When the wire prefix, observation rendering or record schema changes, also
   run `make audit RUN_ID` and require `prefix_ok=True` with no suspected
   cache breaks.

## Commit protocol

Commits are for agents, not humans. Use a conventional subject and a short
machine-parseable body:

```
feat(scope): imperative summary

why: the invariant or failure this changes
check: the exact command that proves it
agent: the rule a future agent must follow
```

One logical change per commit. Do not mix a refactor, a feature and a manifest
update. `scripts/commit_check.py` enforces the subject and the `why:`/`check:`
lines; `agent:` is required by this file. Never commit `.logs/`,
`__pycache__/`, credentials, or generated blobs.

## Definition of done

- `python3 run.py --json` exits 0 and parses as `loop-index/1`.
- `python3 -m compileall -q harness tui run.py` exits 0.
- `python3 run.py check lines` exits 0 with `over=0`.
- `python3 run.py check tui` exits 0.
- `python3 -m unittest discover -s tests -t .` exits 0.
- `python3 scripts/check_manifest.py` exits 0.
- `python3 scripts/verify.py --skip-server` exits 0.
- Prefix or observation changes: `make audit RUN_ID` reports `prefix_ok=True`
  and no suspected cache breaks.
- `git status --short` is empty except for intended files.
- The commit subject/body pass `scripts/commit_check.py`.
- Any changed public behavior is reflected in `manifest.json` and `docs/agent/`
  in the same commit.

## Traps

- `.logs/` is shared by the queue, worker registry, records and server. Stop the
  daemon before deleting it; deleting it under a live worker corrupts the run.
- `record.jsonl` is a durable log, not a cache. Never rewrite complete lines.
- `view` must not read the clock, cwd, network or server.
- `server restart` replaces the control plane only. Do not assume workers die.
- A second `api` queues a front item and streams that run; it does not attach to
  the in-flight run. The tree lock makes it wait.
- `write` replaces a file by default; pass `append: true` to append.
- `edit` requires exactly one match; fix the caller, not the matcher.
- Binary observations are a digest only; raw bytes are not saved. Large text
  bytes are saved under the run's `obs/`.
- A declared verify command with `ran: false` is pending; a `ran: true` result is
  final and is never rerun on resume.
- See `docs/agent/DEBUG.yaml` for the full symptom matrix and recovery order.
