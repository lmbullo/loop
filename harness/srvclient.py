import json
import os
import socket
import sys
import time

from . import config, record, regprobe, regstore, registry, srvctl, srvwire


def _path(address):
    return address[5:] if address.startswith("unix:") else address


def _connect(address, request):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(10.0)
    try:
        sock.connect(_path(address))
        sock.sendall(srvwire.line(request))
        sock.settimeout(None)
        return sock
    except OSError:
        sock.close()
        raise


def _reconnect(deadline):
    stopped_at = None
    while time.time() < deadline:
        entry = regstore.current()
        if entry and regprobe.probe(entry)[0] == "running":
            return entry
        if entry and entry.get("state") == "stopped":
            stopped_at = stopped_at or time.time()
            if time.time() - stopped_at > 2.0:
                return None
        elif stopped_at is None:
            try:
                entry, _ = srvctl.start()
                return entry
            except (OSError, RuntimeError):
                pass
        time.sleep(0.15)
    return None


def _render(event, as_json):
    if as_json:
        print(record.canonical(event), flush=True)
        return
    from . import view
    sys.stdout.write("".join(line + "\n" for line in view.lines(event)))
    sys.stdout.flush()


def stream(address, request, as_json=False, budget=600.0):
    deadline = time.time() + budget
    run_id = request.get("run_id")
    last_seq = int(request.get("from_seq") or 0)
    attempt = request
    ended = False
    code = 5
    while time.time() < deadline:
        try:
            sock = _connect(address, attempt)
        except OSError:
            entry = _reconnect(deadline)
            if entry is None:
                break
            address = entry["address"]
            attempt = {"cmd": "attach", "run_id": run_id, "from_seq": last_seq} if run_id else request
            continue
        try:
            reader = sock.makefile("rb")
            for raw in reader:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                except ValueError:
                    continue
                if event.get("k") == "hello":
                    run_id = event.get("run") or run_id
                    continue
                if event.get("k") == "error":
                    print(f"[err] {event.get('text')}", file=sys.stderr, flush=True)
                    code = int(event.get("code") or 5)
                    continue
                seq = int(event.get("seq") or 0)
                if seq and seq <= last_seq:
                    continue
                last_seq = seq or last_seq
                _render(event, as_json)
                if event.get("type") == "end":
                    ended = True
                    code = int(event["data"]["exit"])
                    break
                if event.get("type") == "interrupted":
                    ended = True
                    code = 130
                    break
            reader.close()
        finally:
            try:
                sock.close()
            except OSError:
                pass
        if ended:
            return code
        entry = _reconnect(deadline)
        if entry is None:
            break
        address = entry["address"]
        attempt = {"cmd": "attach", "run_id": run_id, "from_seq": last_seq} if run_id else request
    if not ended:
        print(f"[err] server closed the stream without an end event addr={address} "
              f"log={config.display(registry.log_path())}", file=sys.stderr, flush=True)
        return code if code else 5
    return code


def run_local(task, as_json=False, verify=None):
    try:
        entry, created = srvctl.start()
    except (OSError, RuntimeError) as e:
        print(f"err server unavailable tree={config.ROOT} detail={type(e).__name__}: {e} "
              f"log={config.display(registry.log_path())}", file=sys.stderr)
        return 5
    if created:
        print(f"[server] started pid={entry['pid']} addr={entry['address']} log={entry['log']}",
              file=sys.stderr, flush=True)
    env = {k: os.environ[k] for k in srvwire.ENV_KEYS if k in os.environ}
    request = {"cmd": "run", "task": task, "root": config.root(), "env": env,
               "verify": verify}
    return stream(entry["address"], request, as_json)
