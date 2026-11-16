import http.client
import json
import os
import unittest
from unittest import mock

from harness import mobile, mobserve, mobtoken, queue
from tests.support import RUN_ID, minimal_events, sandbox, write_record

TOKEN = "test-token-0123456789"


class FakeDaemon:
    tree = "/tmp/loop-test-tree"
    pid = 321

    def snapshot_dict(self):
        return {"k": "snapshot", "current": None, "last": None, "done": [],
                "queue": [], "costs": {"total": 0}, "version": 7}


def dirs(root, *names):
    path = root
    for name in names:
        path = os.path.join(path, name)
        os.makedirs(path, exist_ok=True)
    return path


class HttpTest(unittest.TestCase):
    def setUp(self):
        self.sandbox = sandbox()
        self.tmp = self.sandbox.__enter__()
        self.root = dirs(self.tmp, "root")
        self.child = dirs(self.root, "src")
        self.server = mobserve.MobileServer(FakeDaemon(), "127.0.0.1", 0,
                                            TOKEN, [self.root])
        self.server.start()

    def tearDown(self):
        self.server.stop()
        self.sandbox.__exit__(None, None, None)

    def call(self, method, path, body=None, token=TOKEN, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=5)
        head = {"Authorization": f"Bearer {token}"} if token else {}
        head.update(headers or {})
        raw = body if isinstance(body, str) else (
            json.dumps(body) if body is not None else None)
        if raw is not None:
            head["Content-Type"] = "application/json"
        conn.request(method, path, body=raw, headers=head)
        reply = conn.getresponse()
        data = json.loads(reply.read().decode())
        conn.close()
        return reply.status, data

    def test_requires_the_bearer_token(self):
        status, data = self.call("GET", "/v1/health", token=None)
        self.assertEqual(status, 401)
        self.assertFalse(data["ok"])
        status, _ = self.call("GET", "/v1/health", token="wrong")
        self.assertEqual(status, 401)
        status, data = self.call("GET", "/v1/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["tree"], FakeDaemon.tree)

    def test_lists_roots_and_children(self):
        status, data = self.call("GET", "/v1/dirs")
        self.assertEqual(status, 200)
        self.assertEqual(data["roots"][0]["path"], os.path.realpath(self.root))
        status, data = self.call("GET", "/v1/dirs?path=" + self.root)
        self.assertEqual(status, 200)
        self.assertEqual([row["path"] for row in data["dirs"]],
                         [os.path.realpath(self.child)])

    def test_queues_a_task_through_the_existing_queue(self):
        status, data = self.call("POST", "/v1/tasks",
                                 {"task": "check", "root": self.root})
        self.assertEqual(status, 200)
        self.assertEqual(data["k"], "queued")
        self.assertEqual(queue.snapshot()["items"][0]["task"], "check")

    def test_returns_snapshot_and_run_log(self):
        status, data = self.call("GET", "/v1/snapshot")
        self.assertEqual(status, 200)
        self.assertEqual(data["version"], 7)
        write_record(RUN_ID, minimal_events())
        status, data = self.call("GET", f"/v1/runs/{RUN_ID}")
        self.assertEqual(status, 200)
        self.assertEqual(data["entries"][-1]["result"], "ok")

    def test_rejects_non_local_hosts_and_short_tokens(self):
        for bad in ("0.0.0.0", "8.8.8.8", "example.com", "100.128.0.1"):
            with self.assertRaises(ValueError):
                mobserve.validate_host(bad)
        self.assertEqual(mobserve.validate_host("127.0.0.1"), "127.0.0.1")
        self.assertEqual(mobserve.validate_host("192.168.1.2"), "192.168.1.2")
        self.assertEqual(mobserve.validate_host("100.83.10.68"), "100.83.10.68")
        self.assertEqual(mobserve.validate_host("100.64.0.1"), "100.64.0.1")
        with self.assertRaises(ValueError):
            mobserve.MobileServer(FakeDaemon(), "127.0.0.1", 0, "short", [self.root])
        with self.assertRaises(ValueError):
            mobserve.MobileServer(FakeDaemon(), "127.0.0.1", 0, TOKEN, [])

    def test_private_peer_filter(self):
        self.assertTrue(mobserve._private_peer("127.0.0.1"))
        self.assertTrue(mobserve._private_peer("192.168.1.4"))
        self.assertTrue(mobserve._private_peer("100.80.54.61"))
        self.assertTrue(mobserve._private_peer("::1"))
        self.assertFalse(mobserve._private_peer("8.8.8.8"))
        self.assertFalse(mobserve._private_peer("100.128.0.1"))

    def test_token_is_persisted_with_owner_only_mode(self):
        token = mobtoken.load()
        path = mobtoken.path()
        self.assertTrue(token)
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertEqual(mobtoken.load(), token)

    def test_private_host_prefers_the_tailnet_address(self):
        reply = mock.Mock(returncode=0, stdout="100.80.54.61\n")
        with mock.patch("harness.mobile.subprocess.run", return_value=reply):
            self.assertEqual(mobile.tailscale_host(), "100.80.54.61")
            self.assertEqual(mobile.private_host(), "100.80.54.61")
        with mock.patch("harness.mobile.subprocess.run",
                        side_effect=OSError("missing")):
            self.assertIsNone(mobile.tailscale_host())
        reply = mock.Mock(returncode=0, stdout="192.168.1.4\nnot-an-ip\n")
        with mock.patch("harness.mobile.subprocess.run", return_value=reply):
            self.assertIsNone(mobile.tailscale_host())
        reply = mock.Mock(returncode=1, stdout="100.80.54.61\n")
        with mock.patch("harness.mobile.subprocess.run", return_value=reply):
            self.assertIsNone(mobile.tailscale_host())

    def test_bad_route_and_bad_json_are_errors(self):
        status, data = self.call("GET", "/v1/nope")
        self.assertEqual(status, 404)
        self.assertFalse(data["ok"])
        status, data = self.call("POST", "/v1/tasks", "{")
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])


if __name__ == "__main__":
    unittest.main()
