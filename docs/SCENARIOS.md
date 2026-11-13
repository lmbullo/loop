# Scenarios

Scenarios are JSON transcripts for the offline sims. They are data, not code:
no model, no network, deterministic subprocess calls over a freshly mounted
fixture.

## Schema

```json
{
  "sim": "sim1",
  "label": "task",
  "fixture": "ws1",
  "steps": [
    {"tool": "exec", "argv": ["python3", "src/analyze.py", "data/app.log"]},
    {"tool": "edit", "path": "src/analyze.py", "old": "...", "new": "..."},
    {"tool": "done", "result": "repaired"}
  ]
}
```

- `sim` is `sim1` or `sim2`; loading a scenario under the wrong sim fails.
- `label` defaults to `id`; it names `.logs/<sim>/<label>/`.
- `fixture` defaults to `ws1`; it is copied, never mounted in place.
- `exec` fields: `argv` (required), `cwd` (relative to the workspace),
  `stdin`, `timeout_ms` (default 10000).
- `edit` is sim2 only: `path`, `old`, `new`; exactly one match is required.
- `done` ends the transcript and records `result`.

## Current scenarios

| id | sim | fixture | purpose |
| --- | --- | --- | --- |
| `task` | sim1 | ws1 | repair the buggy analyzer through `exec` |
| `edge` | sim1 | ws1 | bounded-wire edge cases: binary, ANSI, large output, timeout |
| `task2` | sim2 | ws1 | the same repair through structured `edit` |
| `edge2` | sim2 | ws1 | shape-aware wire and edit failures |

## Fixtures

`fixtures/ws1` is the main sandbox: a deliberately buggy log analyzer and a
sample log. The baseline raises `IndexError` on the trailing blank line; the
fixed behavior prints `<code> <count>` sorted by count descending and exits 0.
`fixtures/ws2` is a standalone arithmetic evaluator, useful as an untouched
sandbox target.

Fixtures are read-only. Every run copies them to `.logs/<sim>/<label>/ws/`, so a
transcript can be replayed without reset code.

## Running

```sh
python3 run.py sim1 task
python3 run.py sim1 edge
python3 run.py sim2 task2
python3 run.py sim2 edge2
```

Each run prints per-step wire output, a cache/cost projection and a final
`summary: {json}` line. The transcript is written to
`.logs/<sim>/<label>/log.json`; saved observation bytes are under `obs/`.

## Adding a scenario

1. Pick an existing fixture or add one under `fixtures/`.
2. Write `scenarios/<id>.json`; include `sim`, `fixture` and `steps`.
3. Run it and inspect the generated workspace and log.
4. Register the file in `manifest.files[]` with `kind: "data"` and a role.
5. Add the scenario id to `manifest.scenarios[]` and, when it is a regression
   guard, to `manifest.checks[]` with `network: false`.

Keep scenarios small. They are executable documentation; a 100-step transcript
is a program that should live in fixtures instead.
