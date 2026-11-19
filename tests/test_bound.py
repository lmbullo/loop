import os
import re
import tempfile
import unittest

from harness import bound, observe


class BoundTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.obs = os.path.join(self.tmp.name, "obs")

    def render(self, raw, max_inline=512):
        saved = []
        out = observe.render_api(raw, self.obs, "o1", max_inline=max_inline,
                                 saved=saved, rel_base=self.tmp.name)
        return out, saved

    def test_clip_does_not_split_utf8(self):
        line = "第一行".encode() + b"x" * 300
        shown, used = bound.clip(line)
        self.assertLess(used, len(line))
        self.assertEqual(line[:used].decode("utf-8"), shown)
        self.assertEqual(bound.clip(b"x" * 300)[1], bound.LINE_WIDTH)
        self.assertEqual(bound.take_bytes("第".encode(), 1), ("第", 3))

    def test_long_line_is_pageable(self):
        raw = b"0123456789" * 600
        out, saved = self.render(raw)
        m = re.search(r"next: tail -c \+(\d+) (\S+)", out)
        self.assertIsNotNone(m, out)
        start = int(m.group(1)) - 1
        self.assertGreater(start, bound.LINE_WIDTH)
        self.assertLessEqual(len(out.encode()), 512)
        self.assertEqual(saved, ["obs/o1.txt"])
        with open(os.path.join(self.tmp.name, m.group(2)), "rb") as f:
            self.assertEqual(f.read()[start:], raw[start:])

    def test_hidden_lines_keep_the_line_slice(self):
        raw = b"\n".join(b"row-%03d" % i for i in range(400))
        out, _ = self.render(raw, 2048)
        self.assertRegex(out, r"next: sed -n \d+,\d+p \S+")
        self.assertNotIn("tail -c", out)


if __name__ == "__main__":
    unittest.main()
