# loop mobile

Android-first Flutter client for one local `loop` tree. It chooses an
allowlisted directory, queues a task through the existing daemon, reads
snapshots and polls one run's projected log. It is a renderer plus a requester:
it has no queue, run engine or authoritative state.

## Local bridge

The bridge is opt-in and lives inside the tree's daemon. It binds one literal
private, loopback or Tailscale address and requires a bearer token on every
`/v1` request. `0.0.0.0`, public addresses and peers outside RFC1918, IPv6
ULA/link-local, loopback or the Tailscale `100.64.0.0/10` range are refused.

When Tailscale is up, `server mobile start` defaults to this node's `100.x.y.z`
tailnet address, so the phone can connect from any network with Tailscale
running. Pass `--host` to bind a LAN address instead.

```sh
# this node's tailnet address (falls back to the LAN IPv4 when Tailscale is off)
tailscale ip -4

# one or more allowlisted workspace roots
python3 run.py server mobile start --port 8787 \
  --root /home/me/project-a --root /home/me/project-b

# equivalent allowlist via environment
LOOP_MOBILE_ROOTS=/home/me/project-a:/home/me/project-b \
  python3 run.py server mobile start
```

The `start` line prints `addr=`, `roots=` and `token=`. The token is also stored
in `.logs/mobile.token` with mode 0600. Use the addr host and port plus that
token in the app. `server mobile status` shows the address without the token;
`server mobile stop` closes the listener and leaves the daemon and workers
running. A daemon stop/restart also closes the listener; start it again after.
`LOOP_MOBILE_TOKEN` overrides the stored token.

The app accepts a private, loopback or Tailscale host: RFC1918 IPv4, IPv6
ULA/link-local, loopback, or a `100.64.0.0/10` address (including a MagicDNS
name that resolves into it). It uses cleartext HTTP because the traffic stays
inside the private network or the Tailscale WireGuard tunnel; do not expose the
port with Tailscale Funnel or a public port-forward. There is no public-internet
mode.

## Tailscale setup

1. Install Tailscale on this machine and on the Android device and sign both
   into the same tailnet. `tailscale status` lists both nodes.
2. Keep `tailscaled` running on this machine and the Tailscale VPN connected on
   the phone. On Android, allow Tailscale to stay in the background and disable
   battery optimization for it; an always-on VPN is optional.
3. Start the bridge (it defaults to the `100.x.y.z` tailnet address). In the app
   use that host or, when Tailscale DNS is enabled on Android, the MagicDNS
   name; port `8787` and the bearer token from `.logs/mobile.token`.
4. `tailscale ping <phone>` proves the tunnel; `curl` the bridge `/v1/health`
   with the bearer token to prove the listener.
5. Node keys expire by default. Disable key expiry for the server and phone in
   the Tailscale admin console so the connection survives past the expiry date.

The bridge is not a system service: a daemon restart closes it, so run
`python3 run.py server mobile start` again after restarting the daemon.

## Build and run

```sh
cd mobile
flutter pub get --offline
flutter analyze --no-pub
flutter test --no-pub
flutter build apk --release --target-platform android-arm64 --split-per-abi
```

The resource-conscious Gradle settings cap the build JVM at 1.5 GiB and use at
most two workers. The app pins Gradle 9.5, AGP 9.3.1 and Kotlin 2.4.20; those
are in the local Gradle cache. Flutter 3.50's own Gradle plugin resolves its
build-time Kotlin dependencies separately on the first invocation, so seed that
cache once when the build machine is offline.

The arm64 APK is written to:

```
mobile/build/app/outputs/flutter-apk/app-arm64-v8a-release.apk
```

Install and launch on the connected Android device:

```sh
adb devices                                   # copy the serial shown
DEVICE=<serial>
adb -s "$DEVICE" install -r build/app/outputs/flutter-apk/app-arm64-v8a-release.apk
adb -s "$DEVICE" shell am start -n dev.loop.loop_mobile/.MainActivity
```

Or run directly:

```sh
flutter run -d "$DEVICE" --release
```

The app stores the last successful host, port and token in Android
`shared_preferences` and auto-connects on launch. If that connection fails, the
form stays populated with the saved values so only the stale field needs
changing. A daemon restart keeps the token file, so the saved login works after
the bridge is started again. There is no generated runtime service.

## Layout

The client is a Gruvbox dark phone surface: espresso backgrounds, cream text
and one orange accent, with a warm radial bloom behind the shell. Three
floating surfaces carry the structure: a rounded composer above the keyboard,
a rounded navigation rail above the system inset, and rounded task/activity
cards on the scrollable canvas. The rail switches between `tasks`, `activity`
and `workspace` with an animated accent pill.

The tasks tab combines a workspace strip, running/queued/cost metrics and
active/queued/done cards. The activity tab is a timeline of current, queued and
recent runs with a spend summary and tappable rows. The workspace tab exposes
the active root, the allowlisted roots, bridge details, connection settings and
disconnect. The composer is hidden outside tasks; the rail hides while the
keyboard is open so the composer stays above the inset without crowding a
small phone. Long task text truncates in a card, while ids, turns, cost and
finish stay in the run log.

The connection screen is a rounded login card over the same backdrop. The
directory picker keeps a floating path bar and footer action over rounded
folder rows. Run logs use rounded call cards, a terminal summary line and one
result callout tinted by state.

## Protocol

All routes are JSON, require `Authorization: Bearer <token>`, and are served by
the tree daemon:

| route | use |
| --- | --- |
| `GET /v1/health` | tree, pid, allowlisted roots |
| `GET /v1/dirs?path=` | roots, then child directories inside the allowlist |
| `GET /v1/snapshot` | daemon/current/queue/done/costs snapshot |
| `GET /v1/runs` | record rows |
| `GET /v1/runs/<run_id>` | tool calls plus full final summary; terminal flag |
| `POST /v1/tasks` | `{task,root}` queues through `queue.add` |

Limits: task <= 20,000 chars, request body <= 64 KiB, one listing <= 500
children. Hidden directories and symlinks that escape an allowlisted root are
omitted.

## Verification scope

`python3 -m unittest tests.test_mobile_api tests.test_mobile_http` covers the
server bridge. `flutter test --no-pub` covers the client protocol, store, widget
flows, the Gruvbox palette, the floating composer and nav rail, the activity
timeline, task-card hierarchy and keyboard/inset layout with in-memory
fixtures. No test submits a real agent task or calls a model.
