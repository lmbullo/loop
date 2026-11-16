# Contributing to loop

`loop` is maintained as an agent-first repository: most tracked text is
machine input, and the machine contract is [`manifest.json`](manifest.json).
Human contributions are welcome, but they must keep that contract intact.

Before changing code, read:

- [`AGENTS.md`](AGENTS.md) — operating rules, invariants, definition of done
- [`docs/agent/index.yaml`](docs/agent/index.yaml) — task routes and fast facts
- [`docs/agent/WORKFLOWS.yaml`](docs/agent/WORKFLOWS.yaml) — change recipes
- [`manifest.json`](manifest.json) — files, entry points, checks and schemas

If code and docs disagree, code wins. Fix the doc and, when the contract is
affected, `manifest.json` in the same change.

## Ground rules

- Keep one logical change per commit or pull request.
- Keep every source module under 200 lines. Add a module instead of growing a
  near-limit one.
- `run.py` is the only top-level entry point. Modules are import-only.
- Do not commit `.logs/`, caches, build output, credentials or generated blobs.
  `.gitignore` covers the common cases, but check `git status` yourself.
- New tracked files must be registered in `manifest.files[]` with a `kind` and
  a `role`. New checks and scenarios belong in `manifest.checks[]` and
  `manifest.scenarios[]`.
- Human-facing prose belongs in `README.md`, `LICENSE`, `CONTRIBUTING.md`,
  `SECURITY.md`, `CODE_OF_CONDUCT.md` and the GitHub issue/PR templates. Keep
  agent docs dense and factual.

## Offline verification ladder

Run from the repository root and stop at the first failure:

```sh
python3 run.py --json
python3 -m compileall -q harness tui run.py
python3 run.py check lines
python3 run.py check tui
python3 -m unittest discover -s tests -t . -v
python3 scripts/check_manifest.py
python3 scripts/verify.py --skip-server
git status --short
```

`make check`, `make test` and `make verify` wrap the same checks. `make lint`
runs Ruff when it is installed; it is optional. `make audit RUN=RUN_ID` (or
`scripts/cache_audit.py`) replays one record offline and is the check to run
after changing the wire prefix or the observation renderer.

Never run `run.py api` or `run.py resume RUN_ID` in offline verification. They
need credentials and a network, and they cost real tokens.

## Mobile changes

The Android client is a separate Flutter project:

```sh
cd mobile
flutter pub get
flutter analyze --no-pub
flutter test --no-pub
```

The mobile bridge is private-network only: loopback, LAN or Tailscale. Do not
add public-internet, Tailscale Funnel or public tunnel modes. Keep the bind
check, bearer-token requirement and directory allowlist intact. The client is
Gruvbox dark with floating composer and nav surfaces; keep state colour
semantic and the keyboard/system insets clear.

## Commit protocol

The repository uses machine-parseable conventional commits:

```text
feat(scope): imperative summary

why: the invariant or failure this changes
check: the exact command that proves it
agent: the rule a future agent must follow
```

`scripts/commit_check.py` enforces the subject and the `why:` / `check:`
lines. Before opening a pull request:

```sh
python3 scripts/commit_check.py --range <base>..HEAD
```

## Pull requests

A useful pull request includes:

- the problem and the smallest change that fixes it
- the exact commands that prove the change
- any `manifest.json` or `docs/agent/` updates made in the same change
- a note on cost, tool-surface or record-format impact

Maintainers may replay a change through the loop itself during review. Small,
self-contained patches are easiest to verify and land.

## Reporting bugs and proposing features

Use the issue templates. For usage questions and design discussion, use
[GitHub Discussions](https://github.com/lmbullo/loop/discussions). For security
issues, follow [`SECURITY.md`](SECURITY.md) instead of opening a public issue.

## License

By contributing, you agree that your contribution is licensed under the MIT
License in [`LICENSE`](LICENSE).
