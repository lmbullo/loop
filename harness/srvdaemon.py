import os
import select
import signal
import socket
import threading
import time

from . import config, queue, record, recwrite, regprobe, regstore, registry, srvconn, srvsnap, srvwire, srvwork, workers


class Daemon:
    def __init__(self):
        self.tree = registry.tree()
        self.pid = os.getpid()
        self.started = time.time()
        self.reconciled = []
        self.srv = None
        self.stop_event = threading.Event()
        self.wake = None
        self.children = []
        self.mobile = None

    def entry(self):
        return {
            "tree": self.tree, "pid": self.pid,
            "address": "unix:" + registry.sock_path(), "state": "running",
            "started_at": registry.iso(self.started), "started_ts": int(self.started),
            "proc_start": regprobe.fingerprint(self.pid),
            "log": config.display(registry.log_path()),
            "sock": config.display(registry.sock_path()),
            "runs": registry.state_dir(), "runner": "harness.server",
        }

    def register(self):
        entry = self.entry()
        regstore.upsert(entry)
        regstore.write_local(entry)
        return entry

    def hello(self, run_id=None, attached=False):
        snap = queue.snapshot()
        return {"k": "hello", "pid": self.pid, "tree": self.tree,
                "address": "unix:" + registry.sock_path(), "state": "running",
                "started_at": registry.iso(self.started), "run": run_id,
                "attached": attached, "runs": len(record.ids()),
                "waiting": len(snap["items"]),
                "reconciled": list(self.reconciled)}

    def workers(self):
        return workers.live_entries()

    def snapshot_dict(self):
        return srvsnap.snapshot(queue.snapshot(), self.workers(), self.reconciled)

    def status_dict(self):
        return srvsnap.status(self, self.workers())

    def serve(self):
        os.makedirs(registry.state_dir(), exist_ok=True)
        path = registry.sock_path()
        try:
            os.unlink(path)
        except OSError:
            pass
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(path)
        os.chmod(path, 0o600)
        srv.listen(64)
        srv.setblocking(False)
        self.srv = srv
        with open(registry.pid_path(), "w", encoding="utf-8") as f:
            f.write(f"{self.pid}\n")
        entry = self.register()
        wake_r, wake_w = socket.socketpair()
        wake_r.setblocking(False)
        wake_w.setblocking(False)
        self.wake = wake_w

        def begin_stop(signum, frame):
            self.stop_event.set()
            try:
                wake_w.send(b"x")
            except OSError:
                pass

        signal.signal(signal.SIGTERM, begin_stop)
        signal.signal(signal.SIGINT, begin_stop)
        self.reconcile()
        threading.Thread(target=srvwork.supervise, args=(self,), daemon=True).start()
        srvwire.log("daemon", f"started pid={self.pid} tree={self.tree} "
                              f"addr={entry['address']} queue={registry.state_dir()}")
        try:
            while not self.stop_event.is_set():
                try:
                    ready, _, _ = select.select([srv, wake_r], [], [], 1.0)
                except (OSError, ValueError):
                    break
                if wake_r in ready:
                    try:
                        wake_r.recv(64)
                    except OSError:
                        pass
                if srv in ready:
                    try:
                        conn, _ = srv.accept()
                    except (BlockingIOError, InterruptedError):
                        continue
                    except OSError:
                        break
                    threading.Thread(target=srvconn.handle, args=(self, conn), daemon=True).start()
        finally:
            self.shutdown()
        return 0

    def reconcile(self):
        try:
            marked = recwrite.reconcile("server_start", "server")
        except OSError as e:
            srvwire.log("daemon", f"reconcile failed {type(e).__name__}: {e}")
            marked = []
        live = {w.get("run_id") for w in self.workers()}
        self.reconciled = [r for r in marked if r not in live]
        srvwire.log("daemon", f"reconcile scanned={len(record.ids())} marked={len(marked)} "
                              f"live_workers={len(live)}")

    def shutdown(self):
        self.stop_event.set()
        if self.mobile is not None:
            self.mobile.stop()
            self.mobile = None
        try:
            self.srv.close()
        except (OSError, AttributeError):
            pass
        for path in (registry.sock_path(), registry.pid_path()):
            try:
                os.unlink(path)
            except OSError:
                pass
        try:
            regstore.remove(self.tree)
        except OSError:
            pass
        try:
            regstore.write_local({**self.entry(), "state": "stopped", "pid": 0})
        except OSError:
            pass
        srvwire.log("daemon", "stopped; workers left running")
