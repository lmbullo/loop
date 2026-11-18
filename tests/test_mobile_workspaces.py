import json
import os
import unittest
from unittest import mock

from harness import mobapi, mobpaths, mobrecords, mobview, mobworkspaces, regstore, registry
from tests.support import RUN_START, TURN, END, event, sandbox


def dirs(root, *names):
    path = root
    for name in names:
        path = os.path.join(path, name)
        os.makedirs(path, exist_ok=True)
    return path


def record(workspace, run_id, task, cost):
    start = dict(RUN_START, task=task)
    turn = dict(TURN, usage=dict(TURN["usage"], cost=cost))
    end = dict(END, cost=cost, finish="done")
    path = os.path.join(workspace, ".logs", "runs", run_id, "record.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        for seq, kind, data in ((1, "run_start", start), (2, "turn", turn),
                                (3, "end", end)):
            stream.write(json.dumps(event(run_id, seq, kind, data), sort_keys=True) + "\n")


def entry(tree, pid=999999):
    return {"tree": tree, "pid": pid, "address": "unix:/tmp/missing.sock",
            "state": "running", "started_at": "2024-01-01T00:00:00",
            "log": "server.log", "runs": os.path.join(tree, ".logs")}


class FakeDaemon:
    tree = "/tmp/not-a-workspace"
    pid = 321

    def snapshot_dict(self):
        return {"k": "snapshot", "tree": self.tree, "daemon": {"state": "running"},
                "current": None, "last": None, "done": [], "queue": [],
                "costs": {"current": None, "total": 0}, "version": 1}


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.sandbox = sandbox()
        self.tmp = self.sandbox.__enter__()
        self.home = dirs(self.tmp, "home")
        self.outside = dirs(self.tmp, "outside")
        os.environ["HOME"] = self.home
        self.ws1 = dirs(self.home, "ws1")
        self.ws2 = dirs(self.home, "ws2")
        self.roots = [self.home]

    def tearDown(self):
        self.sandbox.__exit__(None, None, None)

    def test_discovers_workspaces_under_home_and_reports_stale_registry(self):
        regstore.write_json(registry.global_path(),
                            {"schema": "loop-registry/1",
                             "servers": {self.ws2: entry(self.ws2)}})
        found = mobworkspaces.discover(self.roots)
        self.assertIn(self.ws1, found)
        self.assertIn(self.ws2, found)
        self.assertNotIn(self.outside, found)
        status = mobworkspaces.daemon_state(self.ws2)
        self.assertEqual(status["state"], "offline")
        self.assertTrue(status["stale"])
        self.assertEqual(mobrecords.state_dir(self.ws2),
                         os.path.join(self.ws2, ".logs"))

    def test_selected_workspace_snapshot_and_cost_are_isolated(self):
        record(self.ws1, "20240101T000000001Z-aaaaaaaa", "one", 0.5)
        record(self.ws2, "20240101T000000002Z-bbbbbbbb", "two", 0.25)
        daemon = FakeDaemon()
        one = mobapi.snapshot(daemon, self.roots, self.ws1)
        two = mobapi.snapshot(daemon, self.roots, self.ws2)
        self.assertEqual(one["tree"], self.ws1)
        self.assertEqual(one["costs"]["total"], 0.5)
        self.assertEqual(two["costs"]["total"], 0.25)
        self.assertEqual(len(one["done"]), 1)
        self.assertEqual(one["done"][0]["task"], "one")
        self.assertEqual(one["mobile"]["scope"], "workspace")
        self.assertFalse(one["mobile"]["aggregate"])
        self.assertEqual(one["queue"], [])

    def test_overview_aggregates_each_workspace_once(self):
        record(self.ws1, "20240101T000000001Z-aaaaaaaa", "one", 0.5)
        record(self.ws2, "20240101T000000002Z-bbbbbbbb", "two", 0.25)
        data = mobapi.overview(FakeDaemon(), self.roots)
        rows = {row["path"]: row for row in data["workspaces"]}
        self.assertEqual(rows[self.ws1]["cost"], 0.5)
        self.assertEqual(rows[self.ws2]["cost"], 0.25)
        self.assertEqual(data["totals"]["cost"], 0.75)
        self.assertEqual(data["totals"]["running"], 0)
        self.assertTrue(data["aggregate"])

    def test_run_logs_are_scoped_to_the_selected_workspace(self):
        run1 = "20240101T000000001Z-aaaaaaaa"
        record(self.ws1, run1, "one", 0.5)
        data = mobview.run_log(run1, self.ws1)
        self.assertEqual(data["tree"], self.ws1)
        self.assertEqual(data["entries"][-1]["result"], "ok")
        with self.assertRaises(mobapi.ApiError) as caught:
            mobview.run_log(run1, self.ws2)
        self.assertEqual(caught.exception.status, 404)

    def test_selected_subdirectory_uses_its_workspace_tree(self):
        src = dirs(self.ws1, "src")
        record(self.ws1, "20240101T000000001Z-aaaaaaaa", "one", 0.5)
        snap = mobapi.snapshot(FakeDaemon(), self.roots, src)
        self.assertEqual(snap["tree"], self.ws1)
        self.assertEqual(snap["mobile"]["selected"], src)
        self.assertEqual(snap["costs"]["total"], 0.5)

    def test_enqueue_and_snapshot_route_to_the_workspace_daemon(self):
        running = {"state": "running", "detail": "ok", "tree": self.ws1,
                   "entry": entry(self.ws1), "stale": False}
        reply = {"k": "snapshot", "tree": self.ws1,
                 "daemon": {"state": "running"}, "current": None, "last": None,
                 "done": [], "queue": [], "costs": {"total": 0}, "version": 3}
        with mock.patch("harness.mobworkspaces.daemon_state", return_value=running), \
                mock.patch("harness.mobworkspaces.call", return_value=reply) as call:
            snap = mobapi.snapshot(FakeDaemon(), self.roots, self.ws1)
            queued = mobapi.enqueue(FakeDaemon(), self.roots,
                                    {"task": "route me", "root": self.ws1})
        self.assertEqual(snap["tree"], self.ws1)
        self.assertEqual(snap["version"], 3)
        self.assertEqual(queued["k"], "queued")
        self.assertEqual(call.call_args_list[0].args[0], self.ws1)
        self.assertEqual(call.call_args_list[1].args[1]["cmd"], "enqueue")
        self.assertEqual(call.call_args_list[1].args[1]["root"], self.ws1)

    def test_stopped_workspace_hides_queue_and_current_but_keeps_durable_cost(self):
        run1 = "20240101T000000001Z-aaaaaaaa"
        record(self.ws1, run1, "one", 0.4)
        regstore.write_json(registry.global_path(),
                            {"schema": "loop-registry/1",
                             "servers": {self.ws1: entry(self.ws1)}})
        snap = mobapi.snapshot(FakeDaemon(), self.roots, self.ws1)
        self.assertIn(snap["daemon"]["state"], ("offline", "stopped"))
        self.assertIsNone(snap["current"])
        self.assertEqual(snap["queue"], [])
        self.assertFalse(snap["queue_known"])
        self.assertEqual(snap["costs"]["total"], 0.4)
        with self.assertRaises(mobapi.ApiError) as caught:
            mobapi.enqueue(FakeDaemon(), self.roots,
                           {"task": "no daemon", "root": self.ws1})
        self.assertEqual(caught.exception.status, 409)

    def test_start_rejects_outside_home_traversal_and_escaping_symlink(self):
        link = os.path.join(self.home, "escape")
        os.symlink(self.outside, link)
        for value in (self.outside, os.path.join(self.home, "..", "outside"), link):
            with self.assertRaises(mobworkspaces.WorkspaceError) as caught:
                mobworkspaces.start(value, self.roots)
            self.assertEqual(caught.exception.status, 403)
        with self.assertRaises(mobpaths.PathError) as caught:
            mobpaths.select_root(link, self.roots)
        self.assertEqual(caught.exception.status, 403)

    def test_start_spawns_only_inside_the_permitted_root(self):
        ready = entry(self.ws1, pid=123)
        with mock.patch("harness.mobworkspaces.daemon_state",
                        return_value={"state": "stopped", "entry": None}), \
                mock.patch("harness.mobworkspaces._spawn", return_value=123) as spawn, \
                mock.patch("harness.mobworkspaces._wait", return_value=ready):
            got, created = mobworkspaces.start(self.ws1, self.roots)
        self.assertTrue(created)
        self.assertEqual(got["tree"], self.ws1)
        self.assertEqual(spawn.call_args.args[0], self.ws1)
        self.assertTrue(os.path.isdir(os.path.join(self.ws1, ".logs")))


if __name__ == "__main__":
    unittest.main()
