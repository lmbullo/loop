import json

from . import record, registry

BACKLOG = 2000
READY_TIMEOUT = 20.0
STOP_TIMEOUT = 10.0
ENV_KEYS = ("LOOP_API_KEY", "LOOP_AUTH_FILE", "LOOP_MODEL", "LOOP_URL", "LOOP_MAX_TOKENS",
            "LOOP_MAX_INLINE", "LOOP_HTTP_TIMEOUT_S", "LOOP_ROOT")


def line(obj):
    return (record.canonical(obj) + "\n").encode()


def recv_line(sock, limit=1 << 22):
    buf = b""
    while b"\n" not in buf:
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf += chunk
        if len(buf) > limit:
            raise OSError("request too large")
    return json.loads(buf.decode()) if buf.strip() else None


def send_line(sock, obj):
    sock.sendall(line(obj))


def log(scope, text):
    print(f"[{registry.iso()}] {scope} {text}".rstrip(), flush=True)
