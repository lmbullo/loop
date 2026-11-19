import re
import tempfile
import unittest

from harness import bound, observe, tools


class ReadShapeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.obs = self.tmp.name + "/obs"

    def render(self, raw, cap=2048, mode="mixed"):
        saved = []
        out = observe.render_api(raw, self.obs, "o1", max_inline=cap,
                                 saved=saved, rel_base=self.tmp.name, mode=mode)
        return out, saved

    def test_read_mode_is_contiguous(self):
        raw = b"\n".join(b"row-%03d" % i for i in range(300))
        out, saved = self.render(raw, mode="read")
        self.assertIn("head:", out)
        self.assertNotIn("tail:", out)
        self.assertIn("row-000", out)
        self.assertIn("row-029", out)
        match = re.search(r"next: sed -n (\d+),(\d+)p", out)
        self.assertIsNotNone(match, out)
        self.assertGreater(int(match.group(1)), 20)
        self.assertEqual(saved, ["obs/o1.txt"])
        self.assertLessEqual(len(out.encode()), 2048)

    def test_stderr_tail_is_kept_for_failures(self):
        out, _ = self.render(b"banner\n" + b"x\n" * 2000 + b"tail\n" +
                             bound.STDERR_SEP + b"Traceback\nboom: failed\n", cap=1024)
        self.assertIn("head:", out)
        self.assertIn("tail:", out)
        self.assertIn("stderr_tail:", out)
        self.assertIn("boom: failed", out)
        self.assertLessEqual(len(out.encode()), 1024)

    def test_read_like_classification(self):
        self.assertTrue(tools.read_like(["sed", "-n", "1,5p", "x"]))
        self.assertTrue(tools.read_like(["git", "diff"]))
        self.assertTrue(tools.read_like(["sh", "-c", "grep -n x | head"]))
        self.assertFalse(tools.read_like(["python3", "-m", "unittest"]))
        self.assertFalse(tools.read_like(["sh", "-c", "pytest -q"]))


if __name__ == "__main__":
    unittest.main()
