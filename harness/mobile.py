"""Manage the opt-in mobile HTTP bridge on this tree's daemon.

    python3 run.py server mobile start [--host IP] [--port N] [--root DIR ...]
    python3 run.py server mobile status [--json]
    python3 run.py server mobile stop

The bridge binds a private, loopback or Tailscale address and needs the token
in .logs/mobile.token.  With Tailscale up the default is this node's 100.x.y.z
tailnet address, so the phone can connect from any network.  A daemon restart
closes the listener; no worker is interrupted.
"""

import ipaddress
import json
import os
import socket
import subprocess
import sys

from . import config, mobapi, mobserve, mobtoken, regprobe, regstore, registry, srvctl

USAGE = """\
usage: python3 run.py server mobile <start|status|stop> [options]

  start [--host IP] [--port N] [--root DIR ...]
                     start the bridge; roots default to LOOP_MOBILE_ROOTS
                     (os.pathsep separated) or LOOP_ROOT
  status [--json]    bridge address, private/tailnet host, roots, token file
  stop               close the bridge; the daemon and workers stay up
"""


def tailscale_host():
    """Return this node's Tailscale IPv4 address, or None when unavailable."""
    try:
        result = subprocess.run(["tailscale", "ip", "-4"], capture_output=True,
                                check=False, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        value = line.strip()
        try:
            ip = ipaddress.ip_address(value)
        except ValueError:
            continue
        if mobserve.is_tailnet(ip):
            return value
    return None


def private_host():
    tailnet = tailscale_host()
    if tailnet:
        return tailnet
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return "127.0.0.1"
    for info in infos:
        value = info[4][0]
        try:
            ip = ipaddress.ip_address(value)
        except ValueError:
            continue
        if ip.is_private and not ip.is_loopback:
            return value
    return "127.0.0.1"


def _flags(args):
    host, port, roots = None, mobserve.DEFAULT_PORT, []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in ("-h", "--help"):
            print(USAGE.rstrip())
            return None
        if arg not in ("--host", "--port", "--root"):
            raise ValueError(f"unknown argument {arg!r}")
        if index + 1 >= len(args):
            raise ValueError(f"{arg} needs a value")
        value = args[index + 1]
        if arg == "--host":
            host = value
        elif arg == "--port":
            port = int(value)
        else:
            roots.append(value)
        index += 2
    if port < 0 or port > 65535:
        raise ValueError("port must be 0..65535")
    if not roots:
        configured = config.env("LOOP_MOBILE_ROOTS")
        roots = configured.split(os.pathsep) if configured else [config.root()]
    return host or private_host(), port, roots


def _call(entry, request):
    try:
        return regprobe.call(entry["address"], request, timeout=10.0)
    except (OSError, ValueError) as exc:
        return {"k": "error", "text": f"{type(exc).__name__}: {exc}"}


def start(args):
    try:
        parsed = _flags(args)
    except ValueError as exc:
        print(f"err {exc}\n{USAGE}", file=sys.stderr)
        return 2
    if parsed is None:
        return 0
    host, port, roots = parsed
    try:
        roots = mobapi.normalize_roots(roots)
        mobserve.validate_host(host)
    except (ValueError, OSError) as exc:
        print(f"err mobile start {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    try:
        entry, created = srvctl.start()
    except (OSError, RuntimeError) as exc:
        print(f"err mobile start daemon {type(exc).__name__}: {exc}", file=sys.stderr)
        return 5
    token = mobtoken.load()
    reply = _call(entry, {"cmd": "mobile_start", "host": host, "port": port,
                          "token": token, "roots": roots})
    if not isinstance(reply, dict) or reply.get("k") == "error":
        print(f"err mobile start {(reply or {}).get('text') or 'no reply'}",
              file=sys.stderr)
        return 5
    print(f"mobile running tree={reply['tree']} addr={reply['address']} "
          f"host={reply['host']} port={reply['port']} roots={','.join(reply['roots'])} "
          f"token={token} token_file={config.display(mobtoken.path())} "
          f"daemon_created={'true' if created else 'false'}")
    if host == "127.0.0.1":
        print("note loopback-only; pass --host <lan-ip> or a Tailscale IP",
              file=sys.stderr)
    elif mobserve.is_tailnet(ipaddress.ip_address(host)):
        print("note tailnet-only; reachable through Tailscale", file=sys.stderr)
    return 0


def stop(args):
    if args:
        print(f"err mobile stop takes no arguments\n{USAGE}", file=sys.stderr)
        return 2
    entry = regstore.current()
    if not entry or regprobe.probe(entry)[0] != "running":
        print(f"mobile stopped tree={registry.tree()} daemon=down")
        return 0
    reply = _call(entry, {"cmd": "mobile_stop"})
    if not isinstance(reply, dict) or reply.get("k") == "error":
        print(f"err mobile stop {(reply or {}).get('text') or 'no reply'}",
              file=sys.stderr)
        return 5
    print(f"mobile stopped tree={registry.tree()} daemon=running")
    return 0


def status(args):
    as_json = "--json" in args
    if [a for a in args if a != "--json"]:
        print(f"err mobile status: unknown argument\n{USAGE}", file=sys.stderr)
        return 2
    entry = regstore.current()
    if not entry or regprobe.probe(entry)[0] != "running":
        if as_json:
            print(json.dumps({"k": "mobile", "state": "down", "tree": registry.tree()}))
        else:
            print(f"mobile down tree={registry.tree()} daemon=down")
        return 1
    reply = _call(entry, {"cmd": "mobile_status"})
    if not isinstance(reply, dict) or reply.get("k") == "error":
        print(f"err mobile status {(reply or {}).get('text') or 'no reply'}",
              file=sys.stderr)
        return 5
    if as_json:
        print(json.dumps(reply, sort_keys=True))
    elif reply.get("state") == "running":
        print(f"mobile running tree={reply['tree']} addr={reply['address']} "
              f"roots={','.join(reply['roots'])} token_file={config.display(mobtoken.path())}")
    else:
        print(f"mobile stopped tree={reply.get('tree')} daemon=running")
    return 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE.rstrip())
        return 0 if argv else 2
    command, rest = argv[0], argv[1:]
    commands = {"start": start, "stop": stop, "status": status}
    if command in commands:
        return commands[command](rest)
    print(f"err unknown mobile command {command!r}\n{USAGE}", file=sys.stderr)
    return 2
