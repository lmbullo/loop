import os
import unittest
from unittest import mock

from harness import config


class ConfigTest(unittest.TestCase):
    def test_asset_is_under_root(self):
        self.assertTrue(config.asset("manifest.json").endswith(os.path.join("loop", "manifest.json")) or
                        config.asset("manifest.json").endswith("manifest.json"))

    def test_root_env_override(self):
        with mock.patch.dict(os.environ, {"LOOP_ROOT": "/tmp/sandbox"}, clear=False):
            self.assertEqual(config.root(), "/tmp/sandbox")

    def test_root_defaults_to_repo(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config.root(), config.ROOT)

    def test_runs_env_override(self):
        with mock.patch.dict(os.environ, {"LOOP_RUNS": "/tmp/runs"}, clear=False):
            self.assertEqual(config.runs(), "/tmp/runs")

    def test_runs_defaults_to_logs(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config.runs(), os.path.join(config.ROOT, ".logs"))

    def test_resolve_relative_and_absolute(self):
        self.assertEqual(config.resolve("a/b", "/base"), "/base/a/b")
        self.assertEqual(config.resolve("/abs", "/base"), "/abs")
        self.assertIsNone(config.resolve(None))
        self.assertEqual(config.resolve(""), "")

    def test_env_and_env_int(self):
        with mock.patch.dict(os.environ, {"X": "7", "Y": ""}, clear=True):
            self.assertEqual(config.env("X", 1), "7")
            self.assertEqual(config.env("Y", 1), 1)
            self.assertEqual(config.env("Z", 1), 1)
            self.assertEqual(config.env_int("X", 1), 7)
            self.assertEqual(config.env_int("Y", 1), 1)
            self.assertEqual(config.env_int("NOPE", 9), 9)

    def test_max_inline(self):
        self.assertEqual(config.DEFAULT_MAX_INLINE, 2048)
        with mock.patch.dict(os.environ, {"LOOP_MAX_INLINE": "12"}, clear=False):
            self.assertEqual(config.max_inline(), 12)
        with mock.patch.dict(os.environ, {"LOOP_MAX_INLINE": "bad"}, clear=True):
            self.assertEqual(config.max_inline(), config.DEFAULT_MAX_INLINE)

    def test_max_tokens(self):
        self.assertEqual(config.max_tokens(), config.MAX_TOKENS)
        with mock.patch.dict(os.environ, {"LOOP_MAX_TOKENS": "17"}, clear=False):
            self.assertEqual(config.max_tokens(), 17)
        with mock.patch.dict(os.environ, {"LOOP_MAX_TOKENS": "bad"}, clear=True):
            self.assertEqual(config.max_tokens(), config.MAX_TOKENS)

    def test_think_budget(self):
        self.assertEqual(config.think_budget(), config.THINK_BUDGET)
        with mock.patch.dict(os.environ, {"LOOP_THINK_BUDGET": "17"}, clear=False):
            self.assertEqual(config.think_budget(), 17)

    def test_defaults_do_not_starve_the_loop(self):
        self.assertGreaterEqual(config.MAX_TOKENS, 65536)
        self.assertGreaterEqual(config.THINK_BUDGET, 32768)
        self.assertGreaterEqual(config.exec_timeout_ms(), 600000)
        with mock.patch.dict(os.environ, {"LOOP_EXEC_TIMEOUT_MS": "0"}, clear=False):
            self.assertEqual(config.exec_timeout_ms(), 0)

    def test_display_relative_and_outside(self):
        inside = os.path.join(config.ROOT, "harness", "config.py")
        self.assertEqual(config.display(inside), os.path.join("harness", "config.py"))
        self.assertEqual(config.display("/definitely/outside"), "/definitely/outside")


if __name__ == "__main__":
    unittest.main()
