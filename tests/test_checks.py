import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from harness import checks


class ChecksTest(unittest.TestCase):
    def test_line_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write("a\nb\nc\n")
            with mock.patch.object(checks.config, "ROOT", tmp):
                self.assertEqual(checks.line_count("a.py"), 3)
                self.assertEqual(checks.line_count("missing.py"), -1)

    def test_sources_audits_only_code_kinds(self):
        rows = [
            {"path": "a.py", "kind": "module"},
            {"path": "b.py", "kind": "test"},
            {"path": "c.py", "kind": "tool"},
            {"path": "d.py", "kind": "entry"},
            {"path": "e.json", "kind": "data"},
            {"path": "f.json", "kind": "manifest"},
            {"path": "g.py", "kind": "record"},
            {"path": "h.md", "kind": "doc"},
        ]
        with mock.patch.object(checks, "manifest", return_value={"files": rows}):
            self.assertEqual(checks.sources(), ["a.py", "b.py", "c.py", "d.py"])

    def test_audit_flags_over_limit_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "small.py"), "w", encoding="utf-8") as f:
                f.write("x\n")
            with open(os.path.join(tmp, "big.py"), "w", encoding="utf-8") as f:
                f.write("x\n" * (checks.LIMIT + 1))
            fake = {"files": [{"path": "small.py", "kind": "module"},
                              {"path": "big.py", "kind": "test"},
                              {"path": "gone.py", "kind": "tool"}]}
            with mock.patch.object(checks, "manifest", return_value=fake), \
                    mock.patch.object(checks.config, "ROOT", tmp):
                rows, bad = checks.audit_lines()
                self.assertEqual(len(rows), 3)
                self.assertEqual([path for path, _ in bad], ["big.py", "gone.py"])
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    self.assertEqual(checks.main(["lines"]), 1)
                self.assertIn("over=2", out.getvalue())
                self.assertIn("err lines big.py", err.getvalue())
                self.assertIn("err missing gone.py", err.getvalue())

    def test_usage(self):
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(checks.main(["bogus"]), 2)
        self.assertIn("usage:", err.getvalue())

    def test_tui_contract(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(checks.main(["tui"]), 0)
        self.assertEqual(err.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
