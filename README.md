# loop

audience: agents. Every tracked text is machine input.

- contract of record: `manifest.json`
- operating rules: `AGENTS.md`
- task routes: `docs/agent/index.yaml`
- bootstrap: `python3 run.py --json` -> one compact `loop-index/1` line
  (entrypoints, checks, scenarios, docs, invariants, env, layout, record, wire;
  derived from the manifest only, no tree walk, no absolute paths)

If code and docs disagree, code wins: fix the doc and, when the contract is
affected, `manifest.json` in the same commit. Do not add human-facing prose.

## Invariants

- `run.py` is the only entry point; modules are import-only.
- The message list is append-only: never edit, reorder or re-send an entry.
- The record is append-only: one fsynced JSONL line per event, `end` is the only
  completion marker; a missing `end` is the interrupted marker.
- Observations are verbatim except the bounding rule in `harness/observe.py`.
- Output is metered and reported, never gated.
- `LOOP_ROOT` is the workspace identity (root, sandbox, daemon, queue,
  registry); `LOOP_RUNS` selects the state directory.
- One run per tree, enforced by `.logs/run.lock`.
- The control plane never executes a run; detached workers survive daemon
  restart.
- TUI code is a renderer only; server code never imports `tui/`.
- `fixtures/` and `records/` are read-only; every run mounts a fresh fixture
  copy under `.logs/`.
- No absolute paths in tracked files; roots come from `__file__` or env.
- Source modules stay under 200 lines.

## Commands

Offline, deterministic, no credentials:

| argv | effect |
| --- | --- |
| `python3 run.py --json` / `make index` | agent index (`loop-index/1`) |
| `python3 run.py` | usage and manifest entry points (exit 2) |
| `python3 run.py check lines` | 200-line source audit |
| `python3 run.py check tui` | resize/truncation contract |
| `python3 run.py view --list` | records on disk, no execution |
| `python3 run.py view RUN_ID` | compact text form |
| `python3 run.py view RUN_ID --json` | canonical `loop-view/1` |
| `python3 run.py sim1 task` | offline exec-only sim |
| `python3 run.py sim2 task2` | offline shape-aware sim |
| `python3 run.py probe` | headless TUI render |
| `python3 run.py server status` | this tree's control plane |
| `make check` | compile + line + tui audits |
| `make test` | stdlib unittest suite |
| `make verify` | manifest-driven offline checks |
| `python3 scripts/check_manifest.py` | contract integrity |
| `python3 scripts/doctor.py` | local environment health |
| `python3 scripts/repo_map.py` | manifest-derived file map |

Network and real tokens only:

| argv | effect |
| --- | --- |
| `python3 run.py api TASK` | production loop through the daemon |
| `python3 run.py api --verify CMD TASK` | same, then run `CMD` at the run root and record `verify` before `end` |
| `python3 run.py resume RUN_ID` | continue an interrupted record |

`api` and `resume` are the only expensive, networked paths. Never select them
in offline verification; `scripts/verify.py` skips any argv containing an
element exactly equal to `server` or `api`.

## Routes

| Need | Read |
| --- | --- |
| Rules, change/commit protocol, definition of done | `AGENTS.md` |
| Fast facts, routes, commands, paths, exit codes, traps | `docs/agent/index.yaml` |
| Owning module, entry points, write ownership, imports | `docs/agent/MAP.yaml` |
| Record events, fold, view, resume | `docs/agent/RECORD.yaml` |
| Tools, observations, verify, cost | `docs/agent/WIRE.yaml` |
| Daemon, queue, workers, locks | `docs/agent/SERVER.yaml` |
| Change/test/verify/commit recipes | `docs/agent/WORKFLOWS.yaml` |
| Symptom matrix and recovery order | `docs/agent/DEBUG.yaml` |

## Layout

`run.py` dispatcher; `harness/` loop and control plane; `tui/` thin renderer;
`scenarios/` transcripts; `fixtures/` sandboxes; `records/` frozen artifacts;
`tests/`, `scripts/`, `docs/agent/`. Runtime state is generated under `.logs/`
and git-ignored.
