import os
import signal
import subprocess
import time


def spawn(argv, cwd=None, stdin="", timeout_ms=10000, kill_group=False):
    if not isinstance(argv, list) or not argv:
        return 127, b"", b"ValueError: argv must be a non-empty list", 0
    t0 = time.perf_counter()
    code = out = err = None
    try:
        limit = None if not timeout_ms or float(timeout_ms) <= 0 else float(timeout_ms) / 1000
    except (TypeError, ValueError):
        limit = 10.0
    try:
        if kill_group:
            proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True)
            try:
                out, err = proc.communicate((stdin or "").encode(), timeout=limit)
                code = proc.returncode
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                out, err = proc.communicate()
                code = "TIMEOUT"
        else:
            proc = subprocess.run(argv, cwd=cwd, input=(stdin or "").encode(),
                                  capture_output=True, timeout=limit)
            code, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        code, out, err = "TIMEOUT", e.stdout or b"", e.stderr or b""
    except OSError as e:
        code, out, err = 127, b"", f"{type(e).__name__}: {e}".encode()
    return code, out or b"", err or b"", int((time.perf_counter() - t0) * 1000)
