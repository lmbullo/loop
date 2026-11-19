import sys

from . import api, auth, fold, pricing  # noqa: F401
from .close import (api_error as _api_error, cost_of, credentials, finish,  # noqa: F401
                    settle, stopped)
from .loop import run_task  # noqa: F401
from .turn import read_turn, run_calls  # noqa: F401
from .fold import context, derive, totals_of  # noqa: F401

USAGE = "usage: python3 run.py api [--verify CMD] [--json] [--] [TASK|-]"


def main(argv):
    as_json, verify, args, i, options = False, None, [], 0, True
    while i < len(argv):
        arg = argv[i]
        if options and arg == "--":
            options = False
        elif options and arg in ("-h", "--help"):
            print(USAGE)
            return 0
        elif options and arg == "--json":
            as_json = True
        elif options and arg == "--verify":
            if i + 1 >= len(argv):
                return _api_error("--verify needs a command string")
            verify = argv[i + 1]
            i += 1
        elif options and arg.startswith("-") and arg != "-":
            hint = (" (did you mean --verify? top-level --version prints the release)"
                    if "--verify".startswith(arg) else "")
            return _api_error(f"unknown option {arg!r}{hint}")
        else:
            args.append(arg)
        i += 1
    if len(args) > 1:
        return _api_error(f"unexpected argument {args[1]!r}")
    task = args[0] if args else "No task."
    if task == "-":
        task = sys.stdin.read()
    from . import srvclient
    return srvclient.run_local(task, as_json, verify)
