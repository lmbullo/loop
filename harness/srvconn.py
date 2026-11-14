import os
import signal
import time

from . import queue, recread, reload, srvrun, srvwire, workers


def _text(live):
    return ", ".join(f"run={w.get('run_id')} pid={w.get('pid')} task={(w.get('task') or '')[:80]}"
                     for w in live)


def _run_for_item(ident):
    """Resolve a queue item id to its run id, even after promotion."""
    if not ident:
        return None
    snap = queue.load()
    current = snap.get("current")
    if isinstance(current, dict) and current.get("id") == ident:
        return current.get("run_id")
    for item in snap.get("items") or []:
        if item.get("id") == ident:
            return item.get("run_id")
    return None


def _cancel(request):
    """Cancel one task: drop a waiting item, else signal the live run."""
    ident = request.get("id")
    run_id = request.get("run_id") or _run_for_item(ident) or ident
    if ident and queue.drop(ident):
        return {"k": "cancelled", "kind": "queued", "id": ident, "changed": True}
    live = [w for w in workers.live_entries()
            if run_id and w.get("run_id") == run_id]
    if live:
        _interrupt(live)
        return {"k": "cancelled", "kind": "running", "run_id": run_id,
                "pid": live[0].get("pid"), "changed": True}
    return {"k": "cancelled", "kind": None, "id": ident, "run_id": run_id,
            "changed": False}


def _interrupt(live):
    for worker in live:
        pid = worker.get("pid")
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + 3.0
    while time.time() < deadline:
        if not any(workers.live(workers.read(w.get("run_id"))) for w in live):
            return
        time.sleep(0.05)
    for worker in live:
        try:
            os.kill(worker.get("pid"), signal.SIGKILL)
        except OSError:
            pass


def handle(daemon, conn):
    try:
        conn.settimeout(30.0)
        try:
            request = srvwire.recv_line(conn)
        except (OSError, ValueError) as e:
            srvwire.send_line(conn, {"k": "error", "code": 5,
                                     "text": f"bad request: {type(e).__name__}"})
            return
        if not isinstance(request, dict):
            srvwire.send_line(conn, {"k": "error", "code": 5, "text": "bad request"})
            return
        cmd = request.get("cmd")
        if cmd == "ping":
            srvwire.send_line(conn, daemon.hello())
        elif cmd == "status":
            srvwire.send_line(conn, daemon.status_dict())
        elif cmd == "snapshot":
            srvwire.send_line(conn, daemon.snapshot_dict())
        elif cmd == "runs":
            srvwire.send_line(conn, {"k": "runs", "runs": recread.scan()})
        elif cmd == "enqueue":
            task = request.get("task")
            task = "No task." if not isinstance(task, str) or not task else task
            root = request.get("root")
            env = request.get("env") if isinstance(request.get("env"), dict) else {}
            item = queue.add(task, root, env, front=bool(request.get("front")),
                             verify=request.get("verify"))
            srvwire.send_line(conn, {"k": "queued", "item": item})
        elif cmd == "drop":
            ok = queue.drop(request.get("id"))
            srvwire.send_line(conn, {"k": "ok", "changed": ok})
        elif cmd == "move":
            ok = queue.move(request.get("id"), int(request.get("delta") or 0))
            srvwire.send_line(conn, {"k": "ok", "changed": ok})
        elif cmd == "cancel":
            srvwire.send_line(conn, _cancel(request))
        elif cmd == "reload":
            data = reload.bump("server")
            live = workers.live_entries()
            srvwire.send_line(conn, {"k": "reloaded", "generation": data["generation"],
                                     "at": data.get("at"),
                                     "in_flight": [w.get("run_id") for w in live]})
        elif cmd == "stop":
            live = workers.live_entries()
            if live and not request.get("force"):
                srvwire.send_line(conn, {"k": "error", "code": 5,
                                         "text": "run in flight: " + _text(live)
                                                 + "; use server stop --force"})
                return
            srvwire.send_line(conn, {"k": "ok", "pid": daemon.pid, "bye": True,
                                     "interrupted": [w.get("run_id") for w in live]})
            if live:
                _interrupt(live)
            daemon.stop_event.set()
            try:
                daemon.wake.send(b"x")
            except OSError:
                pass
        elif cmd == "shutdown":
            srvwire.send_line(conn, {"k": "ok", "pid": daemon.pid, "bye": True,
                                     "workers_left": [w.get("run_id") for w in workers.live_entries()]})
            daemon.stop_event.set()
            try:
                daemon.wake.send(b"x")
            except OSError:
                pass
        elif cmd in ("run", "attach"):
            if cmd == "run":
                run_id, attached = srvrun.target(request)
            else:
                run_id = request.get("run_id")
                attached = True
            if not run_id:
                srvwire.send_line(conn, {"k": "error", "code": 2, "text": "no run id"})
                return
            srvwire.send_line(conn, daemon.hello(run_id, attached))
            srvrun.stream(daemon, conn, run_id, int(request.get("from_seq") or 0))
        else:
            srvwire.send_line(conn, {"k": "error", "code": 5,
                                     "text": f"unknown cmd {cmd!r}"})
    except OSError:
        pass
    finally:
        try:
            conn.close()
        except OSError:
            pass
