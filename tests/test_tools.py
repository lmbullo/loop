import os
import sys
import tempfile
import unittest

from harness import tools


class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.obs = os.path.join(self.root, "obs")

    def test_write_create_replace_append(self):
        self.assertIn("ok wrote 3B a.txt", tools.do_write({"path": "a.txt", "data": "abc"}, self.root))
        self.assertIn("replaced=3B", tools.do_write({"path": "a.txt", "data": "x"}, self.root))
        self.assertIn("appended_to=1B", tools.do_write(
            {"path": "a.txt", "data": "y", "append": True}, self.root))
        with open(os.path.join(self.root, "a.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "xy")

    def test_write_requires_data_string(self):
        out = tools.do_write({"path": "a.txt", "data": None}, self.root)
        self.assertIn("err bad_args", out)

    def test_edit_unique(self):
        tools.do_write({"path": "a.txt", "data": "hello world"}, self.root)
        out = tools.do_edit({"path": "a.txt", "old": "world", "new": "there"}, self.root)
        self.assertIn("ok -5 +5", out)
        with open(os.path.join(self.root, "a.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "hello there")

    def test_edit_requires_unique_match(self):
        tools.do_write({"path": "a.txt", "data": "x x"}, self.root)
        self.assertIn("match=2 expected=1",
                      tools.do_edit({"path": "a.txt", "old": "x", "new": "y"}, self.root))
        self.assertIn("match=0 expected=1",
                      tools.do_edit({"path": "a.txt", "old": "z", "new": "y"}, self.root))

    def test_edit_bad_args(self):
        out = tools.do_edit({"path": "a.txt", "old": "x"}, self.root)
        self.assertIn("err bad_args", out)

    def test_exec_uses_sandbox_cwd(self):
        os.makedirs(os.path.join(self.root, "sub"))
        out = tools.do_exec({"argv": [sys.executable, "-c", "import os;print(os.getcwd())"]},
                            self.obs, "o1", sandbox=self.root)
        self.assertTrue(out.startswith("exit=0 ms="))
        self.assertIn(os.path.realpath(self.root), out)
        out = tools.do_exec(
            {"argv": [sys.executable, "-c", "import os;print(os.getcwd())"], "cwd": "sub"},
            self.obs, "o2", sandbox=self.root)
        self.assertIn(os.path.realpath(os.path.join(self.root, "sub")), out)

    def test_dispatch_routes(self):
        tools.dispatch("write", {"path": "d.txt", "data": "z"}, self.obs, "o1", self.root)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "d.txt")))
        out = tools.dispatch("edit", {"path": "d.txt", "old": "z", "new": "q"},
                             self.obs, "o2", self.root)
        self.assertIn("ok -1 +1", out)


if __name__ == "__main__":
    unittest.main()
