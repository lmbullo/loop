import fcntl
import os
import threading

from . import config, record, recread, recschema


def sync_dir(path):
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


class Writer:
    def __init__(self, run_id):
        if not record.ID_RE.match(run_id or ""):
            raise ValueError(f"bad run id {run_id!r}")
        self.run_id = run_id
        self.dir = record.run_dir(run_id)
        os.makedirs(self.dir, exist_ok=True)
        self.mu = threading.RLock()
        self.sealed = False
        self.lock_fd = os.open(record.lock_path(run_id), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self.lock_fd)
            raise record.Busy(f"run {run_id} is held by a live executor")
        self.path = record.record_path(run_id)
        fresh = not os.path.exists(self.path)
        events, torn = recread.read_raw(self.path, run_id)
        self.fd = os.open(self.path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
        if torn:
            size = os.fstat(self.fd).st_size
            os.ftruncate(self.fd, size - torn)
            os.fsync(self.fd)
        if fresh:
            sync_dir(self.dir)
        self.seq = events[-1]["seq"] if events else 0
        self.last_type = events[-1]["type"] if events else None

    def append(self, kind, data, ts=None):
        with self.mu:
            if self.sealed:
                raise record.Sealed(f"run={self.run_id} record is sealed")
            ev = recschema.event(self.run_id, self.seq + 1, kind, data, ts)
            raw = (record.canonical(ev) + "\n").encode()
            sent = 0
            while sent < len(raw):
                sent += os.write(self.fd, raw[sent:])
            os.fsync(self.fd)
            self.seq += 1
            self.last_type = kind
            return ev

    def interrupt(self, reason, by):
        with self.mu:
            if self.sealed or self.last_type in ("end", "interrupted"):
                return None
            return self.append("interrupted", {"reason": reason, "last_seq": self.seq, "by": by})

    def seal(self):
        with self.mu:
            if self.sealed:
                return
            self.sealed = True
            try:
                os.fsync(self.fd)
            except OSError:
                pass

    def close(self):
        with self.mu:
            try:
                self.seal()
            except OSError:
                pass
            for fd in (self.fd, self.lock_fd):
                try:
                    os.close(fd)
                except OSError:
                    pass
            self.fd = self.lock_fd = -1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class TreeLock:
    def __init__(self):
        self.path = os.path.join(config.runs(), "run.lock")
        self.fd = None

    def acquire(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            try:
                owner = os.pread(fd, 64, 0).decode("ascii", "replace").strip() or "?"
            except OSError:
                owner = "?"
            os.close(fd)
            raise record.Busy(f"tree lock held by pid={owner}; one run per tree")
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())
        os.fsync(fd)
        self.fd = fd
        return self

    def release(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
        return False


def acquire_tree():
    return TreeLock().acquire()


def reconcile(reason="server_start", by="server", run_id=None):
    marked = []
    targets = [run_id] if run_id else record.ids()
    for rid in targets:
        try:
            rec = recread.read(rid)
        except record.Corrupt:
            continue
        if rec["state"] in ("complete", "empty"):
            continue
        try:
            writer = Writer(rid)
        except record.Busy:
            continue
        try:
            ev = writer.interrupt(reason, by)
            if ev is not None:
                marked.append(rid)
        finally:
            writer.close()
    return marked
