"""Opt-in HTTP bridge for the local-network mobile client.

The bridge lives inside the daemon process, so it uses the same queue,
snapshot and record functions as the Unix socket.  It binds one explicit
private or loopback address, rejects non-private peers, and requires a bearer
token for every request.  It is not a second control plane.
"""

import hmac
import http.server
import ipaddress
import json
import os
import socket
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit

from . import mobapi, srvwire

DEFAULT_PORT = 8787
MAX_BODY = 64 * 1024
TOKEN_MIN = 16


def authority(host, port):
    return f"[{host}]:{port}" if ":" in host else f"{host}:{port}"


def validate_host(host):
    try:
        ip = ipaddress.ip_address(str(host))
    except ValueError as exc:
        raise ValueError("host must be a literal private or loopback IP") from exc
    if not (ip.is_private or ip.is_loopback):
        raise ValueError("host is not private or loopback")
    if ip.is_unspecified or ip.is_multicast:
        raise ValueError("host is not a unicast private or loopback IP")
    return str(ip)


def _private_peer(value):
    try:
        ip = ipaddress.ip_address(str(value))
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not ip.is_unspecified and (ip.is_private or ip.is_loopback)


def _decode(raw):
    try:
        return json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError) as exc:
        raise mobapi.ApiError(400, "bad json") from exc


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "loop-mobile/1"

    def log_message(self, fmt, *args):
        srvwire.log("mobile", f"{self.client_address[0]} {fmt % args}")

    def _send(self, status, payload, headers=None):
        raw = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)
        self.close_connection = True

    def _authorized(self):
        expected = self.server.token
        header = self.headers.get("Authorization") or ""
        scheme, _, supplied = header.partition(" ")
        return (bool(scheme) and scheme.lower() == "bearer" and
                hmac.compare_digest(supplied.strip(), expected))

    def _handle(self, method):
        if not _private_peer(self.client_address[0]):
            self._send(403, {"schema": mobapi.SCHEMA, "ok": False,
                             "text": "local network only"})
            return
        if not self._authorized():
            self._send(401, {"schema": mobapi.SCHEMA, "ok": False,
                             "text": "unauthorized"},
                       {"WWW-Authenticate": "Bearer"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self._send(413, {"schema": mobapi.SCHEMA, "ok": False,
                             "text": "request too large"})
            return
        raw = self.rfile.read(length) if length else b""
        url = urlsplit(self.path)
        parts = [unquote(piece) for piece in url.path.split("/") if piece]
        if not parts or parts[0] != "v1":
            self._send(404, {"schema": mobapi.SCHEMA, "ok": False,
                             "text": "unknown route"})
            return
        try:
            body = _decode(raw)
            data = mobapi.dispatch(self.server.daemon, method, parts[1:],
                                   parse_qs(url.query), body,
                                   self.server.roots)
            self._send(200, data)
        except mobapi.ApiError as exc:
            self._send(exc.status, {"schema": mobapi.SCHEMA, "ok": False,
                                    "text": exc.text})
        except Exception as exc:
            srvwire.log("mobile", f"request failed {type(exc).__name__}: {exc}")
            self._send(500, {"schema": mobapi.SCHEMA, "ok": False,
                             "text": "internal error"})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


class _HTTP(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _HTTP6(_HTTP):
    address_family = socket.AF_INET6


class MobileServer:
    def __init__(self, daemon, host, port, token, roots):
        self.daemon = daemon
        self.host = validate_host(host)
        self.roots = mobapi.normalize_roots(roots)
        self.started = time.time()
        if not self.roots:
            raise ValueError("no mobile roots are configured")
        if not isinstance(token, str) or len(token) < TOKEN_MIN:
            raise ValueError("mobile token is too short")
        self.httpd = (_HTTP6 if ":" in self.host else _HTTP)(
            (self.host, int(port)), _Handler)
        self.httpd.daemon = daemon
        self.httpd.token = token
        self.httpd.roots = self.roots
        self.port = int(self.httpd.server_address[1])
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       kwargs={"poll_interval": 0.2},
                                       name="loop-mobile", daemon=True)

    def start(self):
        self.thread.start()
        return self.info()

    def stop(self):
        try:
            self.httpd.shutdown()
        finally:
            self.httpd.server_close()
            self.thread.join(2.0)

    def info(self):
        return {"k": "mobile", "state": "running", "tree": self.daemon.tree,
                "host": self.host, "port": self.port,
                "address": f"http://{authority(self.host, self.port)}",
                "roots": list(self.roots),
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%S",
                                            time.localtime(self.started))}


def start(daemon, host, port, token, roots):
    stop(daemon)
    server = MobileServer(daemon, host, port, token, roots)
    daemon.mobile = server
    return server.start()


def stop(daemon):
    server = getattr(daemon, "mobile", None)
    daemon.mobile = None
    if server is None:
        return {"k": "mobile", "state": "stopped"}
    server.stop()
    return {"k": "mobile", "state": "stopped"}


def status(daemon):
    server = getattr(daemon, "mobile", None)
    return server.info() if server is not None else {"k": "mobile", "state": "stopped"}
