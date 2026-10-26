import sys

from . import srvcmd, srvdaemon, worker

USAGE = """\
usage: python3 run.py server <command>

  start              attach if this tree has a daemon, else spawn one (idempotent)
  stop [--force]     stop this tree's daemon; --force interrupts the named run
  restart [--all] [--force]
                     replace the control-plane process; workers survive
  reload             soft reload: per-turn settings apply at the next turn boundary
  status             this tree: pid, address, state, runs, queue, live workers
  list [--json]      every server in the machine-wide registry
  runs [--json]      every run record on disk, read without executing anything
  logs [-n N] [-f]   tail .logs/server.log
"""


def main(argv):
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    if cmd == "_daemon":
        return srvdaemon.Daemon().serve()
    if cmd == "_worker":
        return worker.main(rest)
    if cmd == "start":
        return srvcmd.start()
    if cmd == "stop":
        return srvcmd.stop(rest)
    if cmd == "restart":
        return srvcmd.restart(rest)
    if cmd == "reload":
        return srvcmd.reload(rest)
    if cmd == "status":
        return srvcmd.status()
    if cmd == "list":
        return srvcmd.list_servers(rest)
    if cmd == "runs":
        return srvcmd.runs(rest)
    if cmd == "logs":
        return srvcmd.logs(rest)
    if cmd == "_stale":
        return srvcmd.stale()
    print(f"err unknown server command {cmd!r}\n{USAGE}", file=sys.stderr)
    return 2
