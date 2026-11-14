import os
import signal
import sys
import threading
import time
import traceback

from . import agent, config, job, record, recread, recwrite, regprobe, reload, srvwire, workers


class env_scope:
    def __init__(self, values):
        self.values = dict(values or {})
        self.saved = {}

    def __enter__(self):
        self.saved = {k: os.environ.get(k) for k in srvwire.ENV_KEYS}
        for key in srvwire.ENV_KEYS:
            if key in self.values:
                os.environ[key] = str(self.values[key])
            else:
                os.environ.pop(key, None)
        return self

    def __exit__(self, *exc):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return False


def log(text):
    srvwire.log("worker", text)


def main(argv):
    if len(argv) != 1:
        print("usage: python3 run.py server _worker RUN_ID", file=sys.stderr)
        return 2
    run_id = argv[0]
    spec = job.load_for_record(run_id)
    if spec is None:
        log(f"run={run_id} no job file")
        return 2
    state = {"stop": False}
    stop_event = threading.Event()
    finished = threading.Event()

    def on_signal(signum, frame):
        state["stop"] = True
        stop_event.set()

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    try:
        lock = recwrite.acquire_tree()
    except (record.Busy, OSError) as e:
        log(f"run={run_id} tree busy {type(e).__name__}: {e}")
        return 5
    writer = None
    summary = None
    try:
        writer = recwrite.Writer(run_id)
        workers.write({
            "run_id": run_id, "pid": os.getpid(), "proc_start": regprobe.fingerprint(os.getpid()),
            "state": "running", "item_id": spec.get("item_id"), "task": spec.get("task"),
            "root": spec.get("root"), "started_at": record.utc(), "started_ts": time.time(),
            "seq": writer.seq, "turns": 0, "cost": None,
        })
        reload.baseline()
        turn_count = {"n": 0}

        def monitor_stop():
            stop_event.wait()
            if finished.is_set():
                return
            try:
                writer.interrupt("server_stop", "server")
            except Exception:
                pass
            try:
                workers.update(run_id, state="interrupted", ended_at=record.utc(),
                               exit=130, seq=writer.seq)
            except Exception:
                pass
            try:
                writer.close()
                lock.release()
                job.remove(run_id)
            except Exception:
                pass
            log(f"run={run_id} interrupted by signal")
            os._exit(130)

        threading.Thread(target=monitor_stop, daemon=True).start()

        def emit(event):
            if event.get("type") == "turn":
                turn_count["n"] += 1
            fields = {"seq": event.get("seq"), "turns": turn_count["n"]}
            data = event.get("data") or {}
            if event.get("type") == "turn":
                fields["cost"] = float((data.get("usage") or {}).get("cost") or 0.0)
            workers.update(run_id, **fields)
            return event

        with env_scope(spec.get("env") or {}):
            summary = agent.run_task(writer, emit, spec.get("task") or "No task.",
                                     spec.get("root") or config.root(),
                                     should_stop=lambda: state["stop"],
                                     verify=spec.get("verify"))
        if state["stop"] and writer.last_type != "end":
            writer.interrupt("server_stop", "server")
            summary = agent.stopped(writer, recread.read(writer.run_id)["events"], turn_count["n"])
    except record.Sealed:
        log(f"run={run_id} record sealed while appending")
    except Exception as e:
        traceback.print_exc()
        try:
            if writer is not None and writer.last_type != "end":
                writer.append("error", {"code": 1, "text": f"harness {type(e).__name__}: {e}",
                                        "finish": "harness_error"})
                evs = recread.read(writer.run_id)["events"]
                summary = agent.finish(writer, lambda ev: ev, evs,
                                       sum(1 for e in evs if e["type"] == "turn"),
                                       "harness_error", None, 1)
        except record.Sealed:
            summary = None
    finally:
        finished.set()
        final = "done" if writer is not None and writer.last_type == "end" else "interrupted"
        if state["stop"] and final != "done":
            final = "interrupted"
        exit_code = (summary or {}).get("exit")
        try:
            workers.update(run_id, state=final, ended_at=record.utc(), exit=exit_code,
                           seq=writer.seq if writer is not None else 0,
                           turns=(summary or {}).get("turns"),
                           cost=(summary or {}).get("cost"))
        except OSError:
            pass
        if writer is not None:
            writer.close()
        lock.release()
        job.remove(run_id)
        log(f"run={run_id} finished state={final} exit={exit_code}")
    return int((summary or {}).get("exit") or 0)
