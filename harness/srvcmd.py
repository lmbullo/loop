import json
import os
import sys

from . import config, record, recread, reload as reloadmod, regprobe, regstore, registry, srvctl, srvlist, workers


def start():
    try:
        entry, created = srvctl.start()
    except (OSError, RuntimeError) as e:
        print(f"err server start tree={config.ROOT} detail={type(e).__name__}: {e}", file=sys.stderr)
        return 5
    print(f"server running tree={entry['tree']} pid={entry['pid']} addr={entry['address']} "
          f"started={entry['started_at']} created={'true' if created else 'false'} log={entry['log']}")
    return 0


def _names(live):
    return ",".join(str(w.get("run_id")) for w in live) or "-"


def _detail(live):
    return "; ".join(f"run={w.get('run_id')} worker_pid={w.get('pid')} "
                     f"task={(w.get('task') or '')[:100]}" for w in live)


def stop(rest):
    force = "--force" in rest
    live = workers.live_entries()
    if live and not force:
        print(f"err server stop refused tree={registry.tree()} reason=run_in_flight "
              f"{_detail(live)} hint='server stop --force'", file=sys.stderr)
        return 5
    for worker in live:
        print(f"force stop interrupting run={worker.get('run_id')} worker_pid={worker.get('pid')} "
              f"task={(worker.get('task') or '')[:120]}")
    try:
        was_running = srvctl.stop(force=force)
    except (OSError, RuntimeError) as e:
        print(f"err server stop tree={config.ROOT} detail={type(e).__name__}: {e}", file=sys.stderr)
        return 5
    print(f"server stopped tree={registry.tree()} was_running={'true' if was_running else 'false'} "
          f"interrupted={_names(live)}")
    return 0


def restart(rest):
    if "--all" in rest:
        return srvlist.restart_all(rest)
    force = "--force" in rest
    live = workers.live_entries()
    if live and not force:
        print(f"err server restart refused tree={registry.tree()} reason=run_in_flight "
              f"{_detail(live)} hint='server restart --force'", file=sys.stderr)
        return 5
    for worker in live:
        print(f"force restart interrupting control-plane attachment run={worker.get('run_id')} "
              f"worker_pid={worker.get('pid')} task={(worker.get('task') or '')[:120]} "
              f"worker_survives=true")
    try:
        was_running = srvctl.stop(shutdown=True)
    except (OSError, RuntimeError) as e:
        print(f"err server restart tree={config.ROOT} detail={type(e).__name__}: {e}", file=sys.stderr)
        return 5
    try:
        entry, created = srvctl.start()
    except (OSError, RuntimeError) as e:
        print(f"err server restart tree={config.ROOT} detail={type(e).__name__}: {e}", file=sys.stderr)
        return 5
    live_now = workers.live_entries()
    print(f"server running tree={entry['tree']} pid={entry['pid']} addr={entry['address']} "
          f"started={entry['started_at']} created={'true' if created else 'false'} "
          f"was_running={'true' if was_running else 'false'} live_workers={_names(live_now)} "
          f"log={entry['log']}")
    return 0


def reload(rest):
    data = reloadmod.bump("server")
    live = workers.live_entries()
    print(f"server reloaded tree={registry.tree()} generation={data['generation']} "
          f"in_flight={_names(live)} applied=next_turn_boundary process_restart=false")
    return 0


def status():
    entry = regstore.current()
    rows = recread.scan()
    live = workers.live_entries()
    running = bool(entry and regprobe.probe(entry)[0] == "running")
    reply = {}
    if running:
        try:
            reply = regprobe.call(entry["address"], {"cmd": "status"}, timeout=5.0) or {}
        except (OSError, ValueError):
            reply = {}
            running = False
    interrupted = sum(1 for r in rows if r["state"] in ("interrupted", "running"))
    run = reply.get("run") if isinstance(reply.get("run"), dict) else None
    run_id = (live[0].get("run_id") if live else None) or "-"
    run_state = "running" if live else ("complete" if run and run.get("state") == "complete" else "-")
    disk = (f"runs_on_disk={len(rows)} runs_interrupted={interrupted} "
            f"latest_run={rows[-1]['run_id'] if rows else '-'}")
    if not entry or not running:
        print(f"tree={registry.tree()} state=down pid=0 addr=- started=- "
              f"log={config.display(registry.log_path())} {disk} queue_waiting=0 "
              f"workers_live={len(live)} in_flight={run_id} run_state={run_state}")
        return 1
    print(regprobe.describe(entry, "running")
          + f" detail=ok {disk} queue_waiting={reply.get('queue_waiting', 0)} "
            f"workers_live={len(live)} in_flight={run_id} run_state={run_state} "
            f"reconciled={len(reply.get('reconciled') or [])}")
    return 0


def list_servers(rest):
    rows = [srvlist.view(e) for e in regstore.snapshot()]
    if "--json" in rest:
        print(json.dumps({"schema": registry.SCHEMA, "registry": registry.global_path(),
                          "servers": rows}, indent=1, sort_keys=True))
    elif not rows:
        print(f"no servers registry={registry.global_path()}")
    else:
        for row in rows:
            print(regprobe.describe(row, row["state"]) + f" detail={row['detail']}")
    if "--prune" in rest:
        srvlist.prune()
    return 0


def runs(rest):
    from . import view as viewmod
    entry = regstore.current()
    rows, source = None, "disk"
    if entry and regprobe.probe(entry)[0] == "running":
        try:
            reply = regprobe.call(entry["address"], {"cmd": "runs"}, timeout=5.0) or {}
            if isinstance(reply.get("runs"), list):
                rows, source = reply["runs"], "daemon"
        except (OSError, ValueError):
            rows = None
    if rows is None:
        rows = recread.scan()
    if "--json" in rest:
        print(record.canonical({"schema": "loop-runs/1", "source": source, "runs": rows}))
    elif not rows:
        print(f"no runs under {config.display(record.runs_dir())}")
    else:
        for line in viewmod.list_rows(rows):
            print(line)
    return 0 if all(r["state"] != "corrupt" for r in rows) else 1


def logs(rest):
    lines, follow = 40, False
    idx = 0
    while idx < len(rest):
        arg = rest[idx]
        if arg in ("-f", "--follow"):
            follow = True
            idx += 1
        elif arg in ("-n", "--lines") and idx + 1 < len(rest):
            try:
                lines = int(rest[idx + 1])
            except ValueError:
                lines = 40
            idx += 2
        else:
            try:
                lines = int(arg)
            except ValueError:
                pass
            idx += 1
    text = srvctl.log_tail(lines)
    if text:
        print(text)
    path = registry.log_path()
    if not follow:
        return 0
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            for line in iter(f.readline, b""):
                sys.stdout.write(line.decode("utf-8", "replace"))
                sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    except OSError as e:
        print(f"err logs {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


def stale():
    print("\n".join(srvctl.clean_stale()) or "clean")
    return 0
