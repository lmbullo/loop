import os
import subprocess
import sys
import time

from . import config, job, queue, record, recwrite, registry, srvwire, workers


def supervise(daemon):
    while not daemon.stop_event.is_set():
        try:
            tick(daemon)
        except Exception as e:
            srvwire.log("daemon", f"supervise {type(e).__name__}: {e}")
        daemon.stop_event.wait(0.25)


def reap(daemon):
    for proc in list(daemon.children):
        if proc.poll() is not None:
            try:
                daemon.children.remove(proc)
            except ValueError:
                pass


def tick(daemon):
    reap(daemon)
    live = {w.get("run_id"): w for w in workers.live_entries()}
    snap = queue.snapshot()
    current = snap.get("current")
    if current:
        run_id = current["run_id"]
        worker = live.get(run_id)
        if worker:
            if current.get("worker_pid") != worker.get("pid"):
                queue.update(current["id"], worker_pid=worker.get("pid"), state="running")
            return
        launched = float(current.get("launched_ts") or 0.0)
        state = workers.record_state(run_id)
        if not launched and current.get("state") == "queued":
            launch(daemon, current)
            return
        if time.time() - launched < 6.0 and state in ("missing", "running"):
            return
        if state == "missing":
            queue.finish("failed", detail="worker produced no record")
            return
        if state != "complete":
            recwrite.reconcile("worker_lost", "server", run_id=run_id)
            state = workers.record_state(run_id)
            if state == "interrupted":
                workers.update(run_id, state="interrupted", ended_at=record.utc())
        if state in ("complete", "interrupted"):
            queue.finish(state)
        return
    if queue.waiting():
        item = queue.promote()
        if item:
            launch(daemon, item)


def launch(daemon, item):
    run_id = item["run_id"]
    job.write(run_id, {"item_id": item["id"], "task": item["task"],
                       "root": item.get("root"), "env": item.get("env") or {}})
    queue.update(item["id"], state="running", launched_ts=time.time())
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    with open(registry.log_path(), "ab", buffering=0) as out:
        proc = subprocess.Popen(
            [sys.executable, os.path.join(config.ROOT, "run.py"), "server", "_worker", run_id],
            cwd=config.ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=out,
            start_new_session=True, close_fds=True, env=env)
    daemon.children.append(proc)
    queue.update(item["id"], worker_pid=proc.pid)
    srvwire.log("daemon", f"worker spawn run={run_id} pid={proc.pid} item={item['id']}")
