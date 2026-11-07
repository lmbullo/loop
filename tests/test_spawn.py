import os
import sys
import tempfile
import unittest

from harness import spawn


class SpawnTest(unittest.TestCase):
    def test_stdout_and_code(self):
        code, out, err, dur = spawn.spawn([sys.executable, "-c", "print('ok')"])
        self.assertEqual((code, out, err), (0, b"ok\n", b""))
        self.assertGreaterEqual(dur, 0)

    def test_nonzero_and_stderr(self):
        code, out, err, _ = spawn.spawn(
            [sys.executable, "-c", "import sys; print('x'); print('bad', file=sys.stderr); sys.exit(3)"])
        self.assertEqual(code, 3)
        self.assertEqual(out, b"x\n")
        self.assertEqual(err, b"bad\n")

    def test_stdin_is_passed(self):
        code, out, _, _ = spawn.spawn(
            [sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"], stdin="abc")
        self.assertEqual((code, out), (0, b"ABC\n"))

    def test_cwd_is_honored(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _, _ = spawn.spawn(
                [sys.executable, "-c", "import os; print(os.getcwd())"], cwd=tmp)
            self.assertEqual(code, 0)
            self.assertEqual(os.path.realpath(out.decode().strip()), os.path.realpath(tmp))

    def test_argv_is_literal(self):
        code, out, _, _ = spawn.spawn(
            [sys.executable, "-c", "import sys; print(sys.argv[1])", "$HOME"])
        self.assertEqual(code, 0)
        self.assertEqual(out, b"$HOME\n")

    def test_timeout(self):
        code, out, _, _ = spawn.spawn(
            [sys.executable, "-c", "import time; time.sleep(1)"], timeout_ms=50)
        self.assertEqual(code, "TIMEOUT")

    def test_timeout_kill_group(self):
        code, _, _, _ = spawn.spawn(
            [sys.executable, "-c", "import time; time.sleep(1)"], timeout_ms=50, kill_group=True)
        self.assertEqual(code, "TIMEOUT")

    def test_missing_program(self):
        code, out, err, _ = spawn.spawn(["/definitely/not/a/program"])
        self.assertEqual(code, 127)
        self.assertEqual(out, b"")
        self.assertIn(b"FileNotFoundError", err)

    def test_empty_argv(self):
        code, out, err, _ = spawn.spawn([])
        self.assertEqual(code, 127)
        self.assertIn(b"ValueError", err)


if __name__ == "__main__":
    unittest.main()
