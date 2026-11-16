# Security policy

## Supported versions

`loop` is pre-1.0. Security fixes land on the `main` branch; there are no
maintained release branches yet. Run the latest `main`.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting:

<https://github.com/lmbullo/loop/security/advisories/new>

Do not open a public issue for a live secret, an exploitable bug or anything
that could put a running tree at risk. If private reporting is unavailable,
open a minimal issue that asks for a private contact channel and contains no
exploit details.

Please include:

- the affected commit or version
- the smallest reproduction you can make
- the observed impact
- whether a credential, record or workspace was exposed

This is a volunteer research project. Reports are handled on a best-effort
basis; there is no SLA.

## Scope

In scope:

- `run.py`, `harness/`, `tui/`, `scripts/` and the installer
- the record format, record locking and resume behavior
- the control plane: daemon socket, registry, queue, worker lifecycle
- the mobile bridge: bind checks, bearer-token handling and directory allowlist
- the Android client's handling of saved connections and run data

Out of scope by design:

- A model choosing to run a destructive command inside the workspace. `api`
  executes model-chosen commands with the permissions of the user running it.
  Point it at a disposable workspace and review what it runs.
- A local user who can already read `.logs/` reading record contents or the
  mobile token. The token file is created with mode `0600`, but it is not a
  defense against the same user account.
- Exposing the mobile bridge to a public network. It is private-network only:
  loopback, LAN or Tailscale. It refuses public addresses. Do not port-forward
  it, expose it with Tailscale Funnel or place it behind a public reverse proxy.
- Denial of service from a deliberately huge task, tool output or model
  response beyond the documented bounds.

## Operational guidance

- Never commit API keys. Use `LOOP_API_KEY` or a `0600` auth file outside the
  tree (`LOOP_AUTH_FILE`).
- `.logs/` contains full run records, observations and the mobile bearer token.
  Treat it as sensitive; it is git-ignored.
- The mobile bridge requires a bearer token on every `/v1` request and binds
  one literal private, loopback or Tailscale address. Start it only on a network you trust.
- `api` has the same filesystem permissions as your shell. Use a dedicated
  workspace, a container or an unprivileged account when running untrusted
  tasks.

## Secret scanning

The repository enables GitHub secret scanning and push protection. CI also
scans tracked files for common key formats. If a secret does reach history,
rotate it first; deleting the commit is not enough.
