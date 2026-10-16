# loop

Research harness for a tool-calling agent loop. It compares tool and
observation designs by token cost and correctness, using an append-only record
as the only source of truth.

- One exec waist: `exec`, `write`, `edit`, `done`.
- Bounded observations: inline while small, shape summary plus saved bytes
  when large.
- Cache-aware accounting: the unchanged prefix is a cache hit, only the
  appended suffix is a miss.
- Durable runs: one JSONL record per run; `view` and `resume` are pure
  functions over the bytes.
- Detached execution: a per-tree control plane owns the queue, a worker owns
  the run, and the daemon can restart without interrupting work.

## Quick start

```sh
python3 run.py                         # entry points
python3 run.py sim1 task               # offline, no model
python3 run.py sim2 task2              # offline, shape-aware wire
python3 run.py server start            # control plane for this checkout
python3 run.py view --list             # every record on disk
make test                              # stdlib unittest suite
make verify                            # manifest-driven offline checks
```

A real run needs credentials:

```sh
export LOOP_API_KEY=...
python3 run.py api "repair fixtures/ws1/src/analyze.py"
```

`api` and `resume` are the only expensive, networked paths. Everything else is
offline and deterministic.

## Contract

`manifest.json` is the contract of record: file roles, entry points, record
schema, cost model, checks, environment and artifact paths. `AGENTS.md` is the
operating guide for agents. When code and contract disagree, fix both.

## Layout

`harness/` loop and control plane, `tui/` thin renderer, `scenarios/`
transcripts, `fixtures/` sandboxes, `records/` frozen history, `tests/`,
`scripts/`, `docs/`. Runtime state is generated under `.logs/` and is ignored
by git.

## Status

Python 3.8+, standard library only. The offline suite and the recorded sims
run without credentials, a server, or network access.
