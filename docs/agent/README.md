# Agent docs

**Read when:** first visit, or when you need the route for a task.
**Source of truth:** `AGENTS.md` for rules, `manifest.json` for the contract,
the owning modules for behavior.
**Verify:** `python3 scripts/check_manifest.py`, `make verify`.

Read `AGENTS.md` first: it holds the non-negotiable rules and the commit protocol.
This folder is the task-oriented reference for changing or operating the tree.
`manifest.json` is the machine-readable contract; code is the final truth.

If a doc and the code disagree, fix the doc and, when the contract is affected,
fix `manifest.json` in the same commit. `manifest.behavior_changes[]` is a
historical migration log: later entries supersede earlier ones. Use
`manifest.entrypoints`, `manifest.files`, `manifest.record`, `manifest.server`,
`manifest.wire`, and `manifest.checks` for current facts.

## Route by task

| I need to... | Read | Prove with |
| --- | --- | --- |
| Find the module that owns a behavior | `MAP.md` | `python3 scripts/repo_map.py` |
| Inspect or resume a run | `RECORD.md` | `python3 run.py view --list` |
| Understand tools, observations, cost | `WIRE.md` | `python3 run.py view RUN_ID` |
| Operate the daemon, queue or workers | `SERVER.md` | `python3 run.py server status` |
| Change code, tests, scenarios or checks | `WORKFLOWS.md` | `make verify` |
| Diagnose a failure or blocked run | `DEBUG.md` | the command in the symptom row |
| Commit a change | `AGENTS.md` + `WORKFLOWS.md` | `python3 scripts/commit_check.py` |
| Scroll a run log or open the prompt | `MAP.md` | `python3 run.py tui` |
| Cancel the selected task | `MAP.md`, `SERVER.md` | `python3 run.py tui` |
| Get a machine-readable route list | `index.json` | `json.tool` or `grep` |

## Fast facts

| Fact | Value |
| --- | --- |
| Runtime | Python >=3.8, standard library only, tested on 3.12 |
| Entry point | `python3 run.py <command>`; modules are import-only |
| Sandbox root | dirname of `run.py`, overridable with `LOOP_ROOT` |
| Runtime state | `<repo>/.logs`, overridable with `LOOP_RUNS` |
| Durable truth | `.logs/runs/<run_id>/record.jsonl`; `end` is the only completion marker |
| One run per tree | `.logs/run.lock`, a flock; a second `api` attaches, it does not start a run |
| Network commands | `api`, `resume` only; both cost real tokens |
| Offline commands | everything else, including `view`, `server status`, sims and checks |
| Tools | `exec`, `write`, `edit`, `done` |
| Inline observation limit | `LOOP_MAX_INLINE`, default 32768 bytes; larger text is summarized and saved |
| Binary observations | `kind=binary ...` digest; raw bytes are not saved |
| Record schema | `loop-record/1`; view schema `loop-view/1` |

## 60-second map

```
run.py                         dispatcher over manifest.entrypoints[]
manifest.json                  contract: files, entries, record, wire, checks
harness/agent.py               turn loop; folds the record into messages
harness/{api,tools,observe,spawn}
                               model call, four tools, bounding, subprocess
harness/{record,recread,recschema,recwrite,view,resume}
                               append-only record, reader, schema, writer, renderer
harness/{server,srv*,worker,queue,workers,job,registry,regstore,regprobe,reload}
                               daemon, workers, queue, registries, soft reload
harness/{sim1,sim2,assets}     offline scenario sims and fixture mounting
harness/checks.py              200-line and TUI layout audits
tui/                           thin polling renderer; no run or queue authority
scenarios/ fixtures/ records/  inputs and frozen history; read-only
tests/ scripts/ docs/agent/    agent support surface
.logs/                         generated runtime state; never commit
```

## Offline first

```sh
python3 run.py                          # usage + manifest entrypoint list
python3 run.py check lines              # 200-line source audit
python3 run.py check tui                # resize/truncation contract
python3 run.py view --list              # records without executing anything
python3 run.py view RUN_ID              # compact text render
python3 run.py view RUN_ID --json       # canonical loop-view/1
python3 run.py sim1 task                # offline exec-only sim
python3 run.py sim2 task2               # offline shape-aware sim
make test                               # stdlib unittest suite
make verify                             # offline manifest checks
python3 scripts/check_manifest.py       # tree/contract integrity
python3 scripts/doctor.py               # local environment health
python3 scripts/repo_map.py             # generated file/entry/check map
```

`make verify` runs `scripts/verify.py --skip-server`, so checks whose argv has
an element exactly equal to `server` or `api` are skipped. Never run `api` or
`resume` as part of offline verification: they require credentials and a
network.

## Doc conventions

Each reference doc (except this router and `index.json`) starts with three
facts: **Read when**, **Source of truth**, **Verify**.
Keep them dense, command-first and free of duplicated contract values. When you
add or rename a doc:

1. Add it under `docs/agent/`.
2. Register it in `manifest.files[]` with `kind: "doc"` and a `role`.
3. Add its route to `docs/agent/index.json`.
4. Update this table and any cross-links.
5. Run `make verify` and `python3 scripts/commit_check.py`.
