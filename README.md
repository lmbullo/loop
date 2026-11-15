# loop

[![ci](https://github.com/lmbullo/loop/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/lmbullo/loop/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python: 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](pyproject.toml)

**An agent-first research harness for a tool-calling coding loop.**

`loop` drives a model through exactly four tools — `exec`, `write`, `edit`,
`done` — against a workspace, and writes every event to an append-only JSONL
record. State is derived from those bytes, never stored beside them. The point
is to measure tool and observation designs by token cost and correctness.

The repository is intentionally agent-first: source, contracts and most docs are
optimized for machine readers. This README, [`LICENSE`](LICENSE),
[`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md),
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) and the GitHub issue/PR templates are
the human-facing layer.

## Design

- **One exec waist.** Instead of a large tool menu, the model gets one way to
  act on the world. Editing a file means writing a program that edits it. This
  keeps the wire small and makes every action reproducible.
- **Bounded observations.** Small results stay inline. Text over the run's
  bound becomes a budget-filling head/tail/stderr index with a byte-sized `next:`
  slice and the raw bytes saved under the run's `obs/` directory; binary output becomes a digest, and an exact repeat
  becomes a one-line `same=obs-N` reference. Context growth is predictable.
- **Cache-aware accounting.** The system header, tool schema, model and thinking
  settings are snapshotted at run start and the message list is append-only, so
  the unchanged prefix is a cache hit and only the appended suffix is a miss.
  Every turn reports hit/miss/output cost.
- **Durable by construction.** One record per run, one fsynced JSONL line per
  event, and `end` as the only completion marker. `view` is a pure function over
  record bytes; `resume` rebuilds state from the same bytes and continues.
- **Detached execution.** A per-tree control plane owns the queue and worker
  registry. Each run executes in a detached worker, so a daemon restart does not
  interrupt work.
- **Evidence, not gates.** A `--verify` command is declared before the first
  turn, run after the terminal turn, and recorded before `end`. Its exit code is
  stored; absence is not a pass.

## Quick start (offline, no API key)

Requirements: Python 3.8+ (standard library only), `git`, and optionally `make`.
There are no Python dependencies to install.

```sh
git clone https://github.com/lmbullo/loop.git
cd loop

python3 run.py --version    # release declared in manifest.json
python3 run.py --json        # one compact loop-index/1 contract line
python3 run.py sim1 task     # deterministic exec-only simulation
python3 run.py sim2 task2    # deterministic shape-aware simulation
python3 run.py probe         # headless TUI frame
python3 run.py tui           # interactive TUI over local records

make test                    # stdlib unittest suite
make verify                  # every offline check declared in manifest.json
make audit                   # offline cache audit for the newest record
```

Install the `loop` launcher on `PATH` if you want to run it from anywhere:

```sh
sh install.sh                # ~/.local/bin/loop
sh install.sh --system       # /usr/local/bin/loop (sudo when needed)
```

## Run a real task

`api` and `resume` are the only expensive paths: they call a model. The
defaults target a DeepSeek-compatible chat-completions endpoint.

```sh
export LOOP_API_KEY=...      # or use LOOP_AUTH_FILE
python3 run.py api "find the failing test and fix it"
```

Credentials resolve in this order:

1. `LOOP_API_KEY`
2. `LOOP_AUTH_FILE`, default `~/.pi/agent/auth.json`, with the shape
   `{"deepseek": {"key": "..."}}`

Useful overrides: `LOOP_URL` (chat-completions endpoint), `LOOP_MODEL`
(default `deepseek-flash`), `LOOP_MAX_TOKENS`, `LOOP_MAX_INLINE`,
`LOOP_HTTP_TIMEOUT_S`. The full environment contract is in
[`docs/agent/index.yaml`](docs/agent/index.yaml).

The daemon starts on demand. To operate it explicitly:

```sh
python3 run.py server start
python3 run.py server status
python3 run.py server runs --json
python3 run.py server logs -n 80
```

One run per tree is enforced by `.logs/run.lock`. A second `api` queues behind
the live run. An interrupted run can be continued with
`python3 run.py resume RUN_ID`.

## What a run looks like

```text
$ python3 run.py sim1 task

=== task ===
[turn 1] find . -type f
  $ code=0 out=44B dur=1ms
  ./src/u.txt
  ./src/analyze.py
  ./data/app.log

  <cache prefix=103t miss=103t hit=0% cost=$0.0310/call>
[turn 2] cat src/analyze.py
  $ code=0 out=247B dur=0ms
  ...
```

Inspect any run without executing anything:

```sh
python3 run.py view --list
python3 run.py view RUN_ID
python3 run.py view RUN_ID --json
python3 run.py view --schema
```

`python3 scripts/cache_audit.py RUN_ID` (or `make audit RUN=RUN_ID`) replays
one record offline: it rebuilds each request prefix, confirms the prefix only
grows, and reports the hit/miss/out cost split, reuse references, peak context
and any turn whose cache miss dwarfs the bytes it appended. It never calls the
model.

Records live under `.logs/runs/<run_id>/record.jsonl`. The `records/` directory
holds frozen sample and historical records and is never written. `view` never
reads the clock, cwd, network or server; it is a pure function over record
bytes.

## Tools

| tool | contract |
| --- | --- |
| `exec` | spawn literal `argv`; no shell unless the caller passes `sh -c`; returns exit code, stdout, stderr |
| `write` | UTF-8 write, creates parent directories, optional append |
| `edit` | replace exactly one occurrence of `old` with `new` |
| `done` | finish the run with a result string |

Independent tool calls are issued together and run in order. Repeated probes
should be scripted once rather than re-run one step at a time.

## Architecture

```text
run.py            dispatcher; reads manifest.json, imports one entry point
harness/          loop, record, control plane, sims, offline checks
tui/              thin polling renderer; never owns a run or authoritative state
mobile/           Android-first Flutter client for the opt-in local bridge
scenarios/        deterministic sim transcripts
fixtures/         read-only sandbox trees, copied per sim run
records/          frozen historical artifacts, never written
docs/agent/       machine-optimized YAML docs and route tables
tests/            stdlib unittest suite
scripts/          verification, manifest and inventory tools
manifest.json     the machine contract of record
```

`run.py` is the only top-level entry point; modules are import-only. Runtime
state goes to `.logs/` and is git-ignored.

## TUI

`python3 run.py tui` opens a terminal renderer over the local daemon and
records: one scrollable task list, a prompt dock, per-run tool calls and a full
final summary. It never executes a model call itself. `python3 run.py probe`
renders one frame without a terminal.

## Android client

`mobile/` is a Gruvbox-styled, Android-first Flutter client for the same tree.
It uses a floating composer, a floating tasks/activity/workspace nav rail and
rounded state cards. The bridge is opt-in, binds only a literal private or
loopback address, and requires a bearer token on every `/v1` request.

```sh
python3 run.py server mobile start --host 192.168.1.10 --root ~/project
cd mobile
flutter pub get
flutter analyze --no-pub
flutter test --no-pub
flutter build apk --release --target-platform android-arm64 --split-per-abi
```

See [`mobile/README.md`](mobile/README.md) for the protocol, allowlist, saved
connection and build details.

## Project status

`loop` is a pre-1.0 research harness, not a hosted product or a general-purpose
agent framework. The wire and record formats are versioned (`loop-index/1`,
`loop-record/1`, `loop-wire/1`, `loop-view/1`); other interfaces may change.
The offline suite and CI are the compatibility gate.

The repository is one tree, one run at a time. There is no multi-user
authentication, no filesystem confinement, and no public-internet mode for the
mobile bridge. The workspace root is the default cwd and the base for relative
tool paths, not an OS sandbox.

## Security

`api` runs model-chosen commands in the workspace. Read
[`SECURITY.md`](SECURITY.md) before pointing it at anything important. Report
vulnerabilities privately through GitHub Security Advisories; do not open a
public issue for a live secret or an exploitable bug.

## Contributing

Contributions are welcome, especially reductions in tool surface, observation
size and cost. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) and
[`AGENTS.md`](AGENTS.md) first. The short version: one logical change, register
new tracked files in `manifest.json`, run the offline ladder, and never commit
credentials, `.logs/` or generated artifacts.

Usage questions and design discussion belong in
[GitHub Discussions](https://github.com/lmbullo/loop/discussions); bugs and
concrete proposals belong in issues.

## License

MIT. See [`LICENSE`](LICENSE).

## Machine entry (for agents)

audience: agents. The agent contract starts here and in `AGENTS.md`.

- bootstrap: `python3 run.py --json` -> one compact `loop-index/1` line
- contract of record: `manifest.json`
- rules: `AGENTS.md`
- routes: `docs/agent/index.yaml`
- tree map: `docs/agent/MAP.yaml`
- record: `docs/agent/RECORD.yaml`
- wire: `docs/agent/WIRE.yaml`
- control plane: `docs/agent/SERVER.yaml`
- workflows: `docs/agent/WORKFLOWS.yaml`
- debugging: `docs/agent/DEBUG.yaml`

If code and docs disagree, code wins: fix the doc and, when the contract is
affected, `manifest.json` in the same commit. Keep machine text machine-first;
human-facing prose belongs only in the human layer named at the top of this
file.
