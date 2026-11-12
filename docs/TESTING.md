# Testing

## Policy

- Standard library only. `unittest`, not a third-party runner, is the baseline.
- Offline by default. Tests must not call the network or the real `.logs/`.
- Every test isolates runtime state with `tests.support.sandbox()`, which
  redirects `LOOP_RUNS`, `LOOP_REGISTRY`, `LOOP_AUTH_FILE` and `LOOP_ROOT` to a
  temporary directory.
- Fixtures and `records/` are read-only inputs. Copy them; never edit them.
- Prefer pure-function tests. Use subprocesses for CLI and sim coverage.

## Commands

```sh
python3 -m unittest discover -s tests -t . -v
python3 -m pytest -q                 # optional; imports the same tests
make test
make check
make verify                          # offline manifest checks
python3 scripts/verify.py --list     # check ids and network flags
```

`make verify` runs the checks recorded in `manifest.checks[]` with
`network: false`. Use `--skip-server` when no control plane is available.

## What each test protects

| file | contract |
| --- | --- |
| `test_config.py` | root/run resolution, env parsing, display paths |
| `test_record.py` | run id format/order, canonical JSON, discovery |
| `test_recschema.py` | envelope strictness, payload fields, type checks |
| `test_recread.py` | parse, torn tail, state, scan rows |
| `test_recwrite.py` | append/fsync, locks, seal, reconcile, torn-tail repair |
| `test_view.py` | text render, derived markers, view JSON round-trip |
| `test_pricing.py` | manifest rates and cost formula |
| `test_observe.py` | binary detection, bounding, saved bytes |
| `test_spawn.py` | literal argv, cwd/stdin, timeout, OSError mapping |
| `test_tools.py` | write/append/edit uniqueness and exec cwd |
| `test_assets.py` | scenario loading, sim ownership, fixture mounting |
| `test_queue.py` | add/promote/update/finish/drop/move |
| `test_regstore.py` | atomic registry writes, locking, current entry |
| `test_workers.py` | worker liveness fingerprint and reap |
| `test_agent_context.py` | derive, totals, context fold, response parsing |
| `test_manifest.py` | contract integrity and CLI wiring |
| `test_checks.py` | audited kinds and line-limit failure |
| `test_tui_layout.py` | fit, one-line rows, prompt reflow, status width |

## Adding a test

1. Create `tests/test_<area>.py`.
2. Import support helpers; do not touch the repository `.logs/`.
3. Name the behavior, not the function: `test_newest_run_wins`, not
   `test_resolve_2`.
4. Register the file in `manifest.files[]` with `kind: "test"`.
5. Keep it under 200 lines. If it needs a fixture, build it in the test.

## Verification ladder

1. `compileall` - syntax and import block.
2. `run.py check lines` - size guard.
3. `run.py check tui` - layout contract.
4. unit tests - logic.
5. `scripts/check_manifest.py` - tree/contract consistency.
6. `scripts/verify.py --skip-server` - offline entry points and sims.
7. `run.py server status` - only when a control plane is expected.

`api` and `resume` are deliberately excluded from the offline ladder. They cost
real tokens and require credentials.
