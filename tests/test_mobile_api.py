import os
import unittest

from harness import mobapi, queue, workers
from tests.support import RUN_ID, TURN, event, minimal_events, sandbox, write_record


class FakeDaemon:
    tree = "/tmp/loop-test-tree"
    pid = 321

    def snapshot_dict(self):
        return {"k": "snapshot", "current": None, "last": None, "done": [],
                "queue": [], "costs": {"total": 0}, "version": 1}


def dirs(root, *names):
    path = root
    for name in names:
        path = os.path.join(path, name)
        os.makedirs(path, exist_ok=True)
    return path


class ApiTest(unittest.TestCase):
    def test_roots_are_real_directories_and_deduplicated(self):
        with sandbox() as tmp:
            root = dirs(tmp, "root")
            missing = os.path.join(tmp, "missing")
            roots = mobapi.normalize_roots([root, root + "/", missing])
            self.assertEqual(roots, [os.path.realpath(root)])
            self.assertEqual(mobapi.select_root(root, roots), os.path.realpath(root))

    def test_listing_stays_inside_the_allowlist(self):
        with sandbox() as tmp:
            root = dirs(tmp, "root")
            child = dirs(root, "src")
            outside = dirs(tmp, "outside")
            os.makedirs(os.path.join(root, ".hidden"), exist_ok=True)
            os.makedirs(os.path.join(root, "node_modules"), exist_ok=True)
            os.symlink(outside, os.path.join(root, "escape"))
            roots = mobapi.normalize_roots([root])
            first = mobapi.list_dirs(roots)
            self.assertEqual(first["roots"], [{"name": "root", "path": roots[0]}])
            listing = mobapi.list_dirs(roots, root)
            self.assertEqual([row["path"] for row in listing["dirs"]],
                             [os.path.realpath(child)])
            self.assertIsNone(listing["parent"])
            with self.assertRaises(mobapi.ApiError) as caught:
                mobapi.list_dirs(roots, outside)
            self.assertEqual(caught.exception.status, 403)
            with self.assertRaises(mobapi.ApiError):
                mobapi.list_dirs(roots, os.path.join(root, "..", "outside"))
            with self.assertRaises(mobapi.ApiError):
                mobapi.select_root("/", roots)

    def test_parent_is_only_reported_inside_the_allowlist(self):
        with sandbox() as tmp:
            root = dirs(tmp, "root")
            child = dirs(root, "a", "b")
            listing = mobapi.list_dirs(mobapi.normalize_roots([root]), child)
            self.assertEqual(listing["parent"], os.path.realpath(os.path.dirname(child)))
            nested = mobapi.list_dirs(mobapi.normalize_roots([root]), root)
            self.assertIsNone(nested["parent"])

    def test_enqueue_uses_the_queue_and_validates_root(self):
        with sandbox() as tmp:
            root = dirs(tmp, "root")
            outside = dirs(tmp, "outside")
            roots = mobapi.normalize_roots([root])
            reply = mobapi.enqueue({"task": "  fix it  ", "root": root}, roots)
            self.assertEqual(reply["k"], "queued")
            self.assertEqual(reply["item"]["task"], "fix it")
            self.assertEqual(reply["item"]["root"], roots[0])
            self.assertEqual([x["task"] for x in queue.snapshot()["items"]], ["fix it"])
            with self.assertRaises(mobapi.ApiError) as caught:
                mobapi.enqueue({"task": "x", "root": outside}, roots)
            self.assertEqual(caught.exception.status, 403)
            with self.assertRaises(mobapi.ApiError):
                mobapi.enqueue({"task": " ", "root": root}, roots)
            with self.assertRaises(mobapi.ApiError) as caught:
                mobapi.enqueue({"task": "x" * (mobapi.TASK_LIMIT + 1), "root": root}, roots)
            self.assertEqual(caught.exception.status, 413)

    def test_run_log_rejects_bad_and_missing_ids(self):
        with sandbox():
            write_record(RUN_ID, minimal_events())
            data = mobapi.run_log(RUN_ID)
            self.assertEqual(data["state"], "complete")
            self.assertEqual(data["entries"][-1]["kind"], "result")
            self.assertEqual(data["entries"][-1]["result"], "ok")
            with self.assertRaises(mobapi.ApiError) as caught:
                mobapi.run_log("../escape")
            self.assertEqual(caught.exception.status, 400)
            with self.assertRaises(mobapi.ApiError) as caught:
                mobapi.run_log("20240101T000000000Z-deadbeef")
            self.assertEqual(caught.exception.status, 404)

    def test_run_log_reports_a_live_worker_as_running(self):
        with sandbox():
            write_record(RUN_ID, [
                event(RUN_ID, 1, "run_start", {"task": "x", "root": "/tmp",
                                                "entrypoint": "api", "model": "m",
                                                "tools": ["exec"], "max_inline": 1,
                                                "record_source": "live"}),
                event(RUN_ID, 2, "turn", dict(TURN)),
            ])
            workers.write({"run_id": RUN_ID, "state": "running", "pid": os.getpid()})
            data = mobapi.run_log(RUN_ID)
            self.assertEqual(data["state"], "running")
            self.assertFalse(data["terminal"])

    def test_dispatch_routes_and_rejects_unknown(self):
        with sandbox() as tmp:
            root = dirs(tmp, "root")
            roots = [os.path.realpath(root)]
            daemon = FakeDaemon()
            health = mobapi.dispatch(daemon, "GET", ["health"], {}, None, roots)
            self.assertTrue(health["ok"])
            snap = mobapi.dispatch(daemon, "GET", ["snapshot"], {}, None, roots)
            self.assertEqual(snap["mobile"]["roots"], roots)
            self.assertEqual(mobapi.dispatch(daemon, "GET", ["runs"], {}, None, roots)["runs"], [])
            with self.assertRaises(mobapi.ApiError):
                mobapi.dispatch(daemon, "DELETE", ["health"], {}, None, roots)


if __name__ == "__main__":
    unittest.main()
