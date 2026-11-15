# loop

audience: agents. Every tracked text is machine input.

- contract of record: `manifest.json`
- operating rules: `AGENTS.md`
- task routes: `docs/agent/index.yaml`
- bootstrap: `python3 run.py --json` -> one compact `loop-index/1` line
  (purpose, runtime, entrypoints, checks, scenarios, docs, invariants, env,
  layout, record, wire; derived from the manifest only, no tree walk, no
  absolute paths)

If code and docs disagree, code wins: fix the doc and, when the contract is
affected, `manifest.json` in the same commit. Do not add human-facing prose.

## Invariants

- `run.py` is the only entry point; modules are import-only.
- The message list is append-only: never edit, reorder or re-send an entry.
- The record is append-only: one fsynced JSONL line per event, `end` is the only
  completion marker; a missing `end` is the interrupted marker.
- Observations are verbatim except the bounding rule in `harness/observe.py`;
  text over the run's bound (default 8 KiB) is summarized and its raw bytes are
  saved; binary output is a digest only.
- The system header is constant across runs; task and run-specific values enter
  after it, so the prefix is cacheable.
- A terminal turn with no tool call and no text is not final on its own: after
  turn 1 one `nudge` user message is recorded and retried; a second silent stop
  ends `finish=no_tool_call`.
- A `verify` event is evidence, not a gate: it stores the exit code and `view`
  derives `ok=1`/`ok=0`; a command that was never declared leaves no event.
- Output is metered and reported, never gated.
- `LOOP_ROOT` is the workspace identity (root, sandbox, daemon, queue,
  registry); `LOOP_RUNS` selects the state directory.
- One run per tree, enforced by `.logs/run.lock`.
- The control plane never executes a run; detached workers survive daemon
  restart.
- TUI code is a renderer only; server code never imports `tui/`.
- `fixtures/` and `records/` are read-only; each sim run copies its fixture to
  `.logs/<sim>/<label>/ws/`.
- No absolute paths in tracked files; roots come from `__file__` or env.
- Source modules stay under 200 lines.

## Commands

Offline, deterministic, no credentials:

| argv | effect |
| --- | --- |
| `sh install.sh` / `sudo sh install.sh --system` | install `loop` on PATH for the current user (`~/.local/bin`) or all users (`/usr/local/bin`) |
| `python3 run.py --json` / `make index` | agent index (`loop-index/1`) |
| `python3 run.py` | usage and manifest entry points (exit 2) |
| `python3 run.py check lines` | 200-line source audit |
| `python3 run.py check tui` | resize/truncation contract |
| `python3 run.py view --list` | records on disk, no execution |
| `python3 run.py view --list --json` | canonical `loop-view/1` list document |
| `python3 run.py view RUN_ID` | compact text form |
| `python3 run.py view RUN_ID --json` | canonical `loop-view/1` |
| `python3 run.py view --schema` | record schema for renderers |
| `python3 run.py sim1 task` | offline exec-only sim |
| `python3 run.py sim2 task2` | offline shape-aware sim |
| `python3 run.py probe` | headless TUI render |
| `python3 run.py tui` | interactive renderer; no model calls |
| `python3 run.py server start` / `python3 run.py server stop` / `python3 run.py server restart` / `python3 run.py server reload` | control-plane lifecycle; workers survive restart |
| `python3 run.py server status` | this tree's control plane |
| `python3 run.py server runs --json` | every record on disk, daemon if available |
| `python3 run.py server list --json` / `python3 run.py server logs -n 80` | machine registry / daemon log tail |
| `python3 run.py server mobile start` / `python3 run.py server mobile status` / `python3 run.py server mobile stop` | opt-in private-network bridge for the Android app; no model call |
| `make check` | compile + line + tui audits |
| `make test` | stdlib unittest suite |
| `make lint` / `make sim` / `make clean` | optional ruff, both sims, generated caches |
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

`api` and `resume RUN_ID` are the only expensive, networked paths. Never select
them in offline verification; `scripts/verify.py` skips any argv token,
including one inside `sh -c`, exactly equal to `server` or `api`. The
`resume-usage` check exercises only the offline usage path.

## Routes

| Need | Read |
| --- | --- |
| Rules, change/commit protocol, definition of done | `AGENTS.md` |
| Fast facts, routes, commands, paths, exit codes, traps | `docs/agent/index.yaml` |
| Owning module, entry points, runtime flow, write ownership, imports | `docs/agent/MAP.yaml` |
| Record events, nudge, fold, view, resume | `docs/agent/RECORD.yaml` |
| Tools, observations, stop/nudge, verify, request, cost | `docs/agent/WIRE.yaml` |
| Daemon, queue, workers, locks | `docs/agent/SERVER.yaml` |
| Android app build, local-network bridge, directory allowlist | `mobile/README.md`, `docs/agent/SERVER.yaml` |
| Change/test/verify/commit recipes | `docs/agent/WORKFLOWS.yaml` |
| Symptom matrix and recovery order | `docs/agent/DEBUG.yaml` |

## Layout

`run.py` dispatcher; `install.sh` user/global launcher installer; `harness/`
loop (`agent`, `turn`, `fold`), record, control plane, sims and checks; `tui/`
thin renderer; `mobile/` Android-first Flutter client; `scenarios/` transcripts; `fixtures/` sandboxes; `records/`
frozen artifacts; `tests/`, `scripts/`, `docs/agent/`. Runtime state is generated
under `.logs/` and git-ignored.
