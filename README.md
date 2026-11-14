# loop

Research harness for a tool-calling agent loop. It compares tool and observation
designs by token cost and correctness, using an append-only record as the only
source of truth.

- One exec waist: `exec`, `write`, `edit`, `done`.
- Bounded observations: inline while small, shape summary plus saved bytes when
  large; binary output is a digest.
- Cache-aware accounting: the unchanged prefix is a cache hit, only the appended
  suffix is a miss.
- Durable runs: one JSONL record per run; `view` is a pure function over the
  bytes, and `resume` rebuilds state from the same bytes and continues.
- Detached execution: a per-tree control plane owns the queue and worker
  registry; a detached worker owns the run, and the daemon can restart without
  interrupting work.

## Start

```sh
python3 run.py                         # usage + manifest entry points
python3 run.py sim1 task               # offline, no model
python3 run.py sim2 task2              # offline, shape-aware wire
python3 run.py view --list             # every record on disk
python3 run.py probe                   # headless TUI render of a snapshot
python3 run.py server status           # this tree's control plane
make test                              # stdlib unittest suite
make verify                            # manifest-driven offline checks
```

A real run needs credentials and network:

```sh
export LOOP_API_KEY=...
python3 run.py api "repair fixtures/ws1/src/analyze.py"
```

`api` and `resume` are the only expensive, networked paths. Everything else is
offline and deterministic.

## Agent docs

`AGENTS.md` is the operating contract. `docs/agent/` is the task-oriented YAML
reference; `docs/agent/index.yaml` is the machine-readable route list.

| Need | Read |
| --- | --- |
| Rules, commit protocol, definition of done | `AGENTS.md` |
| Fast facts, routes, doc map, exit codes | `docs/agent/index.yaml` |
| Owning module, entry points, write ownership | `docs/agent/MAP.yaml` |
| Record events, view, resume | `docs/agent/RECORD.yaml` |
| Tools, observations, cost | `docs/agent/WIRE.yaml` |
| Daemon, queue, workers | `docs/agent/SERVER.yaml` |
| Change/test/verify/commit recipes | `docs/agent/WORKFLOWS.yaml` |
| Symptom matrix and recovery | `docs/agent/DEBUG.yaml` |

## Contract

`manifest.json` is the contract of record: file roles, entry points, record
schema, cost model, checks, environment and artifact paths. When code and
contract disagree, fix both. `docs/agent/` explains the contract; it does not
override it.

## Layout

`run.py` dispatcher; `harness/` loop and control plane; `tui/` thin renderer;
`scenarios/` transcripts; `fixtures/` sandboxes; `records/` frozen history;
`tests/`, `scripts/`, `docs/agent/`. Runtime state is generated under `.logs/`
and is ignored by git.

## Status

Python 3.8+, standard library only. The offline suite and recorded sims run
without credentials, a server, or network access.
