import json
import os
import tempfile
import unittest

from harness import assets, config


class AssetsTest(unittest.TestCase):
    def test_available(self):
        names = assets.available()
        for name in ("task", "edge", "task2", "edge2"):
            self.assertIn(name, names)

    def test_load_scenario_defaults(self):
        sc = assets.load_scenario("task", expect_sim="sim1")
        self.assertEqual(sc["id"], "task")
        self.assertEqual(sc["sim"], "sim1")
        self.assertEqual(sc["fixture"], "ws1")
        self.assertTrue(sc["steps"])

    def test_wrong_sim_is_rejected(self):
        with self.assertRaises(ValueError):
            assets.load_scenario("task", expect_sim="sim2")

    def test_unknown_scenario(self):
        with self.assertRaises(FileNotFoundError):
            assets.load_scenario("nope")

    def test_mount_is_a_fresh_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = assets.mount(tmp, "ws1")
            path = os.path.join(first, "src", "analyze.py")
            with open(path, "a", encoding="utf-8") as f:
                f.write("# mutated\n")
            source = os.path.join(config.asset("fixtures", "ws1"), "src", "analyze.py")
            with open(source, encoding="utf-8") as f:
                self.assertNotIn("# mutated", f.read())
            second = assets.mount(tmp, "ws1")
            with open(os.path.join(second, "src", "analyze.py"), encoding="utf-8") as f:
                self.assertNotIn("# mutated", f.read())

    def test_mount_missing_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                assets.mount(tmp, "missing")

    def test_write_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "deep", "x.json")
            assets.write_json(path, {"b": 1, "a": 2})
            with open(path, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"a": 2, "b": 1})
            with open(path, "rb") as f:
                self.assertTrue(f.read().endswith(b"\n"))


if __name__ == "__main__":
    unittest.main()
