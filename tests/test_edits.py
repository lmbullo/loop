import os
import tempfile
import unittest

from harness import edits


def text(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


class EditsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def put(self, name, data):
        path = os.path.join(self.root, name)
        with open(path, "wb") as f:
            f.write(data.encode())
        return path

    def test_multi_hunk_applies_in_order(self):
        path = self.put("m.txt", "alpha\nbeta\ngamma\n")
        out = edits.apply({"path": "m.txt", "edits": [
            {"old": "alpha", "new": "A"}, {"old": "gamma", "new": "G"}]}, self.root)
        self.assertTrue(out.startswith("ok edits=2 -10 +2 m.txt"), out)
        self.assertEqual(text(path), "A\nbeta\nG\n")
        self.assertIn("\n1: A", out)

    def test_failure_is_all_or_nothing_and_names_the_hunk(self):
        path = self.put("m.txt", "one\ntwo\n")
        out = edits.apply({"path": "m.txt", "edits": [
            {"old": "one", "new": "1"}, {"old": "missing", "new": "x"}]}, self.root)
        self.assertTrue(out.startswith("hunk=2/2 err match=0 expected=1 m.txt"), out)
        self.assertIn("hint=", out)
        self.assertEqual(text(path), "one\ntwo\n")

    def test_replace_all_is_opt_in(self):
        path = self.put("m.txt", "x x x\n")
        out = edits.apply({"path": "m.txt", "old": "x", "new": "y"}, self.root)
        self.assertIn("match=3 expected=1 m.txt", out)
        self.assertIn("replace_all=true", out)
        self.assertEqual(text(path), "x x x\n")
        out = edits.apply({"path": "m.txt", "old": "x", "new": "y",
                           "replace_all": True}, self.root)
        self.assertIn(" all=true", out)
        self.assertEqual(text(path), "y y y\n")

    def test_crlf_hint_when_old_uses_lf(self):
        self.put("m.txt", "foo\r\nbar\r\n")
        out = edits.apply({"path": "m.txt", "old": "foo\nbar\n", "new": "z"}, self.root)
        self.assertIn("err match=0 expected=1 m.txt", out)
        self.assertIn("CRLF", out)
        self.assertIn("\\r\\n", out)

    def test_bad_args_and_missing_file(self):
        self.put("m.txt", "x\n")
        for args in ({}, {"path": "m.txt"}, {"path": "m.txt", "old": ""},
                     {"path": "m.txt", "old": "x"},
                     {"path": "m.txt", "edits": []},
                     {"path": "m.txt", "edits": [{"old": "x"}]}):
            self.assertTrue(edits.apply(args, self.root).startswith("err bad_args edit"), args)
        out = edits.apply({"path": "no.txt", "old": "x", "new": "y"}, self.root)
        self.assertIn("hint=create it with write(path=no.txt", out)


if __name__ == "__main__":
    unittest.main()
