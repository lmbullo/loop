import os
import sys
import tempfile
import unittest

from harness import api, ledger, tools


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
        self.assertIn("match=2 expected=1 a.txt",
                      tools.do_edit({"path": "a.txt", "old": "x", "new": "y"}, self.root))
        self.assertIn("match=0 expected=1 a.txt",
                      tools.do_edit({"path": "a.txt", "old": "z", "new": "y"}, self.root))

    def test_edit_bad_args(self):
        out = tools.do_edit({"path": "a.txt", "old": "x"}, self.root)
        self.assertIn("err bad_args", out)

    def test_edit_failure_reports_lines(self):
        tools.do_write({"path": "a.txt", "data": "x\nx\n"}, self.root)
        out = tools.do_edit({"path": "a.txt", "old": "x", "new": "y"}, self.root)
        self.assertIn("match=2 expected=1 a.txt lines=1,2", out)

    def test_edit_zero_match_hints_whitespace_and_crlf(self):
        tools.do_write({"path": "a.txt", "data": "    foo\n    bar\n"}, self.root)
        out = tools.do_edit({"path": "a.txt", "old": "  foo\n  bar\n", "new": "z"}, self.root)
        self.assertIn("near=1", out)
        tools.do_write({"path": "b.txt", "data": "foo\r\nbar\r\n"}, self.root)
        out = tools.do_edit({"path": "b.txt", "old": "foo\nbar\n", "new": "z"}, self.root)
        self.assertIn("CRLF", out)

    def test_exec_string_argv_runs_through_sh(self):
        out = tools.do_exec({"argv": "printf hi"}, self.obs, "o1", sandbox=self.root)
        self.assertIn("hi", out)
        out = tools.do_exec({"cmd": "printf bye"}, self.obs, "o2", sandbox=self.root)
        self.assertIn("bye", out)

    def test_exec_rejects_shell_syntax(self):
        for argv in (["echo", "hi", "|", "cat"],
                     ["sh", "-c", "echo", "&&", "cat"],
                     ["for", "x", "in", "a"]):
            out = tools.do_exec({"argv": argv}, self.obs, "o1", sandbox=self.root)
            self.assertIn("err shell_syntax", out)
            self.assertIn('cmd:"..."', out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "a")))

    def test_exec_allows_quoted_operators_and_real_sh(self):
        out = tools.do_exec({"argv": [sys.executable, "-c", "print('a|b')"]},
                            self.obs, "o1", sandbox=self.root)
        self.assertTrue(out.startswith("exit=0 ms="))
        self.assertIn("a|b", out)
        out = tools.do_exec({"argv": ["sh", "-c", "printf hi | cat"]},
                            self.obs, "o2", sandbox=self.root)
        self.assertTrue(out.startswith("exit=0 ms="))
        self.assertIn("hi", out)

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

    def test_dispatch_unknown_tool(self):
        out = tools.dispatch("bogus", {}, self.obs, "o1", self.root)
        self.assertIn("err unknown_tool bogus", out)
        self.assertIn("exec, read, write, edit, done", out)
        self.assertIn("read(path, start?", out)

    def test_wire_schema_matches_signatures(self):
        names = [t["function"]["name"] for t in api.TOOLS]
        self.assertEqual(names, ["exec", "read", "write", "edit", "done"])
        self.assertEqual(set(names), set(tools.SIGNATURES))
        for tool in api.TOOLS:
            fn = tool["function"]
            self.assertTrue(fn["description"])
            self.assertIn("parameters", fn)
            for required in fn["parameters"].get("required") or []:
                self.assertIn(required, fn["parameters"]["properties"])
            self.assertIn(fn["name"] + "(", tools.SIGNATURES[fn["name"]])
        text = api.header()
        for name in names:
            self.assertIn(tools.SIGNATURES[name], text)
        self.assertEqual(api.WIRE_SCHEMA, "loop-wire/2")

    def test_read_repeat_becomes_same_reference(self):
        tools.do_write({"path": "s.txt", "data": "a\nb\n"}, self.root)
        led = ledger.Ledger()
        first = tools.dispatch("read", {"path": "s.txt"}, self.obs, "obs-1", self.root,
                               ledger=led, obs_id="obs-1")
        again = tools.dispatch("read", {"path": "s.txt"}, self.obs, "obs-2", self.root,
                               ledger=led, obs_id="obs-2")
        self.assertIn("1| a", first)
        self.assertTrue(again.startswith("same=obs-1 bytes="), again)

    def test_dispatch_read_routes_to_numbered_read(self):
        tools.do_write({"path": "r.txt", "data": "a\nb\n"}, self.root)
        out = tools.dispatch("read", {"path": "r.txt"}, self.obs, "o1", self.root)
        self.assertIn("obs r.txt lines=2", out)
        self.assertIn("1| a", out)


if __name__ == "__main__":
    unittest.main()
