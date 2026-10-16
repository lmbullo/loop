# AGENTS.md

Read this file before changing the tree. It is the operating contract for
agents. `manifest.json` is the machine-readable contract; if the two disagree,
change both in the same commit.

## What this tree is

A research harness for a tool-calling agent loop. The loop is append-only:
each turn appends one assistant message and one tool message per call. The
durable output is one JSONL record per run. `view` and `resume` are pure
functions over those bytes.

There is no text channel. Assistant text is not recorded and not re-sent.
Only tool calls and their observations survive. A turn with no tool call ends
the run with `finish=no_tool_call`.

## Non-negotiable invariants

- `run.py` is the only entry point. Modules are import-only.
- The message list is append-only; never edit, reorder or re-send old entries.
- The record is append-only; one event per fsynced line; `end` is the only
  completion marker. A missing `end` is the interrupted marker.
- Observations are verbatim except for the bounding rule in `harness/observe.py`.
- Output is metered and reported, never gated.
- Fixtures and `records/` are read-only. Every run mounts a fresh fixture copy
  under `.logs/`.
- No absolute paths in tracked files; roots come from `__file__` or env.
- The control plane never executes a run; workers survive daemon restart.
- The TUI never owns a run or authoritative state; server code never imports
  `tui/`.
- One run per tree, enforced by the tree lock; a second `api` attaches.
- `exec` argv is literal: no shell, globs, pipes or redirects unless the caller
  passes `sh -c` explicitly.
- Source modules stay under 200 lines. Split, do not grow.

## Commands

```sh
python3 run.py                      # usage and the manifest entry point list
python3 run.py check lines          # 200-line source audit
python3 run.py check tui            # resize/truncation contract
python3 run.py view --list          # read records without executing anything
python3 run.py view RUN_ID          # compact text form
python3 run.py view RUN_ID --json   # canonical loop-view/1
python3 run.py sim1 task            # offline exec-only sim
python3 run.py sim2 task2           # offline shape-aware sim
python3 run.py server status        # this tree's control plane
python3 run.py api "task"           # real model call; costs money and network
make check                          # compile + line + tui checks
make test                           # stdlib unittest suite
make verify                         # manifest-driven offline checks
python3 scripts/check_manifest.py   # contract integrity
python3 scripts/doctor.py           # local environment health
python3 scripts/repo_map.py         # file/entrypoint map for agents
```

Never run `api` or `resume` in an offline verification. They require
credentials and a network. Use `scripts/verify.py --skip-server` when the
control plane is unavailable.

## Layout

- `run.py` - dispatcher; reads `manifest.json`.
- `harness/` - loop, record, control plane, sims, offline checks.
- `tui/` - thin polling renderer over daemon snapshots.
- `scenarios/` - offline sim transcripts.
- `fixtures/` - read-only sandbox trees, copied per run.
- `records/` - frozen historical artifacts; never written.
- `tests/` - stdlib `unittest`; no third-party deps.
- `scripts/` - agent verification and inventory tools.
- `docs/` - design and runbook references.
- `.logs/` - generated runtime state; git-ignored.

## Change protocol

1. Find the affected file in `manifest.files[]` and read its `role`.
2. Make the smallest change that preserves the invariants above.
3. Keep every module under 200 lines. New behavior goes in a new module if
   needed, not as an append to a near-limit file.
4. Add a focused test under `tests/` for any logic change. Pure functions are
   preferred; tests must not use the network or the real `.logs/`.
5. Register every new tracked file in `manifest.files[]` with a `kind` and a
   `role`. Audited kinds are `module`, `entry`, `test`, `tool`.
6. Update `manifest.checks[]` if you add a new verification command.
7. Run `make verify` (or `scripts/verify.py --skip-server`) before committing.

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
lines. Never commit `.logs/`, `__pycache__/`, credentials, or generated blobs.

## Definition of done

- `python3 -m compileall -q harness tui run.py` exits 0.
- `python3 run.py check lines` and `check tui` exit 0.
- `python3 -m unittest discover -s tests -t .` exits 0.
- `python3 scripts/check_manifest.py` exits 0.
- `git status --short` is empty except for intended files.
- The relevant `manifest.checks[]` command passes offline.

## Traps

- `.logs/` is shared by the queue, worker registry, records and server. Stop
  the daemon before deleting it; deleting it under a live worker corrupts the
  run.
- `record.jsonl` is a durable log, not a cache. Never rewrite complete lines.
- `view` must not read the clock, cwd, network or server.
- `server restart` replaces the control plane only. Do not assume workers die.
- `write` replaces a file by default; pass `append=true` to append.
- `edit` requires exactly one match; fix the caller, not the matcher.
