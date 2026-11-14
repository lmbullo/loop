# Change, test and verification workflows

**Read when:** modifying code, adding a test/scenario/check/doc, or preparing a
commit.
**Source of truth:** `AGENTS.md`, `manifest.files[]`, `manifest.checks[]`,
`Makefile`, `.github/workflows/ci.yml`.
**Verify:** `make verify`, `python3 scripts/check_manifest.py`,
`python3 scripts/commit_check.py --range HEAD~1..HEAD`.

## Verification ladder

Run from the tree root. Stop at the first failure.

| Step | Command | Catches |
| --- | --- | --- |
| 1 | `python3 -m compileall -q harness tui run.py` | syntax/import block |
| 2 | `python3 run.py check lines` | code source over 200 lines or missing |
| 3 | `python3 run.py check tui` | fit, one-line task rows, prompt reflow, status width |
| 4 | `python3 -m unittest discover -s tests -t .` | logic and CLI contracts |
| 5 | `python3 scripts/check_manifest.py` | unregistered files, bad entries/record/checks/scenarios |
| 6 | `python3 scripts/verify.py --skip-server` | all offline manifest checks |
| 7 | `python3 run.py server status` | only when a control plane is expected |
| 8 | `git status --short` | unintended files |

Shortcuts:

```sh
make check        # compile + line + tui
make test         # stdlib unittest, verbose
make lint         # ruff E4/E7/E9/F when installed; skips otherwise
make verify       # scripts/verify.py --skip-server
make sim          # sim1 task + sim2 task2
make clean        # bytecode and tool caches; never .logs

python3 scripts/verify.py --list
python3 scripts/verify.py --only sim1-task
python3 scripts/verify.py --json
```

`scripts/verify.py` never selects `network: true` checks. `--skip-server` also
skips any check whose argv has an element exactly equal to `server` or `api`,
which includes `server-start`, `server-status`, `server-runs` and
`api-auth-guard`.

`api` and `resume` are deliberately absent from the offline ladder. They need
credentials and a network, and they cost real tokens.

## What each test protects

| Test | Contract |
| --- | --- |
| `test_config.py` | root/run resolution, env parsing, display paths |
| `test_record.py` | run id format/order, canonical JSON, discovery, resolve errors |
| `test_recschema.py` | envelope strictness, payload fields, declared types |
| `test_recread.py` | parse, torn tail, derived state, scan rows, corruption |
| `test_recwrite.py` | append/fsync, per-run and tree locks, seal, reconcile, torn-tail repair |
| `test_view.py` | text render, derived markers, `loop-view/1` round-trip, list rows |
| `test_pricing.py` | manifest rates and the cost formula |
| `test_observe.py` | binary detection, three bounding rules, saved bytes |
| `test_spawn.py` | literal argv, cwd/stdin, timeout, OSError, empty argv |
| `test_tools.py` | write/append/edit uniqueness, exec sandbox cwd |
| `test_assets.py` | scenario load/defaults, sim ownership, fixture mounting |
| `test_queue.py` | add/promote/update/finish/drop/move, corrupt reset |
| `test_regstore.py` | atomic registry writes, locking, current-entry precedence |
| `test_workers.py` | worker registry, pid+start liveness, reap, record state |
| `test_agent_context.py` | derive, totals, context fold, response parsing, dispatch, finish |
| `test_manifest.py` | contract integrity, entry imports, record/scenario checks, CLI wiring |
| `test_checks.py` | audited kinds, line-limit failure, TUI contract |
| `test_tui_layout.py` | fit, one-line task rows, prompt reflow/editing, exact status width |

`tests/support.py` provides `sandbox()`, fixed run ids, event builders, record
writers and `run_py()`. `sandbox()` redirects `LOOP_ROOT`, `LOOP_RUNS`,
`LOOP_REGISTRY`, `LOOP_AUTH_FILE` and clears the other `LOOP_*` keys. Tests must
never write the real `.logs/` or use the network.

## Change recipes

### Change behavior in an existing module

1. Find the path in `manifest.files[]` and read its `role`.
2. Read the owning module and the nearest test.
3. Make the smallest change that preserves the invariants in `AGENTS.md`.
4. Add or update a focused test.
5. Keep the module under 200 lines; split instead of appending.
6. Run the verification ladder.
7. Update docs only if the public behavior, commands, paths or contract changed.

### Add a module

1. Create `harness/<name>.py` (or `tui/`, `scripts/`, `tests/`) under 200 lines.
2. Register it in `manifest.files[]` with a `kind` and a `role`:
   `module`, `entry`, `test`, `tool`, `doc`, etc.
3. Import it from the owner; do not add a second top-level entry point.
4. Add a focused test if it contains logic.
5. Run `python3 scripts/check_manifest.py` and `python3 run.py check lines`.

### Add or change an entry point

1. Implement `main(argv)` in a module.
2. Add an `entrypoints[]` row: `id`, `module`, `function`, `network`,
   `args_usage`, `role`, and the exit codes/writes/reads that apply.
3. `run.py` uses the row for dispatch and usage; do not hardcode a command.
4. `tests/test_manifest.py` imports every entry point; keep it importable.
5. If the command is offline and deterministic, add it to `checks[]`.
6. If it is networked or expensive, set `network: true` and keep it out of the
   offline ladder.

### Add a test

1. Create `tests/test_<area>.py`.
2. Use `tests.support.sandbox()` and fixed ids; never touch the real `.logs/`.
3. Name the behavior: `test_newest_run_wins`, not `test_resolve_2`.
4. Prefer pure functions; use `run_py()` for CLI coverage.
5. Keep it under 200 lines and register it with `kind: "test"`.
6. Run the single test during development, then the full suite.

### Add an offline scenario

1. Choose or add a fixture under `fixtures/`.
2. Write `scenarios/<id>.json`:

```json
{
  "id": "<id>",
  "sim": "sim1",
  "label": "<id>",
  "fixture": "ws1",
  "purpose": "one line",
  "expected": "observable result",
  "steps": [
    {"tool": "exec", "argv": ["python3", "src/analyze.py", "data/app.log"]},
    {"tool": "done", "result": "repaired"}
  ]
}
```

3. `sim` is `sim1` or `sim2`; loading under the wrong sim fails.
4. `label` defaults to `id`; it names `.logs/<sim>/<label>/`.
5. `fixture` defaults to `ws1`; it is copied, never mounted in place.
6. `exec` fields: `argv` required; `cwd`, `stdin`, `timeout_ms` optional
   (default `cwd` is the run workspace, timeout 10000 ms).
7. `edit` is sim2 only: `path`, `old`, `new`; exactly one match is required.
8. Run `python3 run.py sim1 <id>` or `python3 run.py sim2 <id>` and inspect
   `.logs/<sim>/<label>/log.json` and `obs/`.
9. Register the file in `manifest.files[]` with `kind: "data"`.
10. Add `{"id","sim","fixture","steps","purpose",...}` to
    `manifest.scenarios[]`; `steps` must match the JSON length.
11. Add a `checks[]` row when it is a regression guard, with `network: false`.

Keep scenarios small. They are executable documentation; a 100-step transcript
belongs in a fixture or a test.

### Add a manifest check

1. Make the command deterministic, offline and runnable from the tree root.
2. Add to `manifest.checks[]`:
   `{"id","argv","expect_exit","network":false,"note"}`.
3. Use an exact exit code; `verify.py` treats a mismatch as failure.
4. Prefer commands that fail loudly and print one line of diagnosis.
5. Run `python3 scripts/verify.py --only <id>` and then `make verify`.
6. If the command needs the daemon, keep `server`/`api` in argv so
   `--skip-server` can exclude it.

### Change the record schema

Records are frozen artifacts. `recschema` validates exactly the fields in
`manifest.record` and rejects unknown fields. Changing an existing event's field
set without a version strategy makes old records corrupt.

1. Prefer a new event type or an explicit version bump plus a reader path.
2. Update `manifest.record.events` and `manifest.record.types`.
3. Update `tests/test_recschema.py`, `tests/test_recread.py`,
   `tests/test_recwrite.py`, `tests/test_view.py` and fixtures.
4. Keep `end` the only completion marker and `seq` contiguous.
5. Run the full ladder and `python3 run.py view --schema`.

### Change a tool or observation rule

1. Update `harness/tools.py`, `harness/observe.py`, or `harness/spawn.py`.
2. Update `tests/test_tools.py`, `tests/test_observe.py`, or
   `tests/test_spawn.py`.
3. Update `manifest.wire` shape/threshold text.
4. Update `docs/agent/WIRE.md`.
5. Exercise `python3 run.py sim1 edge` and `python3 run.py sim2 edge2`.

### Change the TUI

1. Keep it a renderer over daemon snapshots; never add queue or run authority.
2. Update `tui/panes.py`, `tui/prompt.py`, or `tui/render.py` and the matching
   tests.
3. Run `python3 run.py check tui`; it pins fit, one-line rows, prompt reflow and
   exact status width.
4. Server modules must not import `tui/`.

### Add or change docs

1. Add the file under `docs/agent/`.
2. Start it with **Read when**, **Source of truth**, **Verify**.
3. Use exact commands, paths and tables; do not duplicate values that already
   live in `manifest.json`.
4. Give it a route in `docs/agent/index.json` and the table in
   `docs/agent/README.md`.
5. Register it in `manifest.files[]` with `kind: "doc"` and a role.
6. Cross-link the owning doc; fix stale links in the same commit.
7. Run `make verify` (docs are not size-audited, but links and contract are).

## Manifest registration rules

- `manifest.json` is the contract of record. Every file in `files[]` must exist,
  be relative, have a `kind` from the allowed set and a non-empty `role`.
- Every `.py` under `harness/`, `tui/`, `tests/` or `scripts/` must be
  registered or `scripts/check_manifest.py` fails.
- Audited kinds for the 200-line limit: `module`, `entry`, `test`, `tool`, and
  only `.py` files. Docs, data, fixtures, records, configs and CI are not
  audited.
- A new scenario needs both a `data` file entry and a `scenarios[]` row.
- A new check needs an `argv`, an integer `expect_exit` and a `network` bool.
- A new entry point needs a callable `module.function` and `network` bool.
- No absolute paths in tracked files; use `__file__`, `LOOP_ROOT`, `LOOP_RUNS`
  or `LOOP_REGISTRY`.

## Commit protocol

Commits are agent-facing. Use a conventional subject and a machine-parseable
body:

```
type(scope): imperative summary

why: the invariant or failure this changes
check: the exact command that proves it
agent: the rule a future agent must follow
```

- Subject: `feat|fix|refactor|test|docs|chore|perf|build|ci|revert`, optional
  `(scope)`, colon, at least 3 characters, at most 100.
- `scripts/commit_check.py` enforces the subject and the `why:` and `check:`
  lines. `agent:` is required by `AGENTS.md`.
- One logical change per commit. Do not mix a refactor, a feature and a
  manifest update.
- Never commit `.logs/`, `__pycache__/`, credentials, generated blobs or
  `.ruff_cache/`.

After committing, validate the commit, not just the working tree:

```sh
python3 scripts/commit_check.py --range HEAD~1..HEAD
git status --short
```

## Definition of done

- `python3 -m compileall -q harness tui run.py` exits 0.
- `python3 run.py check lines` exits 0 with `over=0`.
- `python3 run.py check tui` exits 0.
- `python3 -m unittest discover -s tests -t .` exits 0.
- `python3 scripts/check_manifest.py` exits 0.
- `python3 scripts/verify.py --skip-server` exits 0.
- `git status --short` is clean except intended files.
- The commit subject/body pass `scripts/commit_check.py`.
- Any changed public behavior is reflected in `manifest.json` and `docs/agent/`
  in the same commit.

## CI

`.github/workflows/ci.yml` runs on push/PR: compile, line and TUI audits,
`scripts/check_manifest.py`, the full unittest suite, `scripts/verify.py
--skip-server`, and a final `git status --porcelain` check. It uses Python 3.12
on Ubuntu and has a 15-minute timeout. Keep the tree clean; CI fails on untracked
or modified files left by a check.
