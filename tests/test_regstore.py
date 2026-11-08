import json
import os
import unittest

from harness import regstore, registry
from tests.support import sandbox


def entry(tree="/tree", pid=1):
    return {"tree": tree, "pid": pid, "address": "unix:/tmp/x.sock",
            "state": "running", "started_at": "2024-01-01T00:00:00", "log": "log"}


class RegStoreTest(unittest.TestCase):
    def test_empty_and_load(self):
        with sandbox():
            self.assertEqual(regstore.load()["servers"], {})
            regstore.write_json(registry.global_path(), {"schema": "x", "servers": {"t": entry()}})
            self.assertIn("t", regstore.load()["servers"])

    def test_corrupt_file_is_empty(self):
        with sandbox():
            with open(registry.global_path(), "w", encoding="utf-8") as f:
                f.write("not json")
            self.assertEqual(regstore.load()["servers"], {})
            self.assertEqual(regstore.entries(), {})
            self.assertEqual(regstore.snapshot(), [])

    def test_upsert_entries_snapshot_remove(self):
        with sandbox():
            regstore.upsert(entry("/b", 2))
            regstore.upsert(entry("/a", 1))
            regstore.upsert(entry("/b", 3))
            self.assertEqual(sorted(regstore.entries()), ["/a", "/b"])
            self.assertEqual(regstore.entries()["/b"]["pid"], 3)
            self.assertEqual([e["tree"] for e in regstore.snapshot()], ["/a", "/b"])
            regstore.remove("/a")
            self.assertEqual(sorted(regstore.entries()), ["/b"])

    def test_update_returns_result(self):
        with sandbox():
            got = regstore.update(lambda reg: (reg.setdefault("x", []), 5)[1])
            self.assertEqual(got, 5)
            self.assertIn("x", regstore.load())

    def test_write_local_wins_for_current(self):
        with sandbox():
            tree = registry.tree()
            regstore.write_local(entry(tree, 7))
            current = regstore.current()
            self.assertEqual(current["pid"], 7)
            self.assertEqual(regstore.current("/not/this/tree"), None)

    def test_write_json_is_atomic_and_typed(self):
        with sandbox() as tmp:
            path = os.path.join(tmp, "deep", "x.json")
            regstore.write_json(path, {"b": 1, "a": 2})
            with open(path, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"a": 2, "b": 1})
            self.assertFalse(any(name.endswith(".tmp") for name in os.listdir(os.path.dirname(path))))
            self.assertEqual(regstore.read_json(path), {"a": 2, "b": 1})
            self.assertEqual(regstore.read_json("/missing", {"d": 1}), {"d": 1})

    def test_lock_context(self):
        with sandbox() as tmp:
            path = os.path.join(tmp, "x.lock")
            with regstore.locked(path):
                self.assertTrue(os.path.isfile(path))


if __name__ == "__main__":
    unittest.main()
