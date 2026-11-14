import time

from . import job, queue, record, recread, srvwire, workers


def target(request):
    task = request.get("task")
    task = "No task." if not isinstance(task, str) or not task else task
    root = request.get("root")
    env = request.get("env") if isinstance(request.get("env"), dict) else {}
    item = queue.add(task, root, env, front=True, verify=request.get("verify"))
    return item["run_id"], False


def _known(run_id):
    if job.load_for_record(run_id) or workers.find(run_id):
        return True
    snap = queue.load()
    if (snap.get("current") or {}).get("run_id") == run_id:
        return True
    return any(item.get("run_id") == run_id for item in snap.get("items") or [])


def stream(daemon, conn, run_id, from_seq=0):
    seq = int(from_seq or 0)
    missing_since = None
    while not daemon.stop_event.is_set():
        try:
            rec = recread.read(run_id)
        except record.Missing:
            rec = None
        except record.Corrupt as e:
            srvwire.send_line(conn, {"k": "error", "code": 2, "text": str(e)[:300]})
            return
        events = [] if rec is None else rec["events"]
        for event in events:
            if event["seq"] <= seq:
                continue
            srvwire.send_line(conn, event)
            seq = event["seq"]
        if events and events[-1]["type"] in ("end", "interrupted"):
            return
        if rec is None:
            if _known(run_id):
                missing_since = None
            elif missing_since is None:
                missing_since = time.time()
            elif time.time() - missing_since > 3.0:
                srvwire.send_line(conn, {"k": "error", "code": 2,
                                         "text": f"no such run {run_id!r}"})
                return
        time.sleep(0.08)
