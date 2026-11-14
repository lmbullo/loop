import os
import tempfile
import unittest

from harness import observe


class ObserveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.obs = os.path.join(self.tmp.name, "obs")

    def test_is_binary(self):
        self.assertFalse(observe.is_binary(b"plain text\n"))
        self.assertTrue(observe.is_binary(b"\x00\x01\x02"))
        self.assertFalse(observe.is_binary(b""))
        self.assertTrue(observe.is_binary(bytes(range(32)) * 10))

    def test_digest(self):
        text = observe.digest(b"\x00\x01")
        self.assertIn("kind=binary", text)
        self.assertIn("bytes=2", text)
        self.assertIn("sha256=", text)
        self.assertIn("head_hex=0001", text)

    def test_render_api_small_is_verbatim(self):
        self.assertEqual(observe.render_api(b"hello", self.obs, "o1"), "hello")
        self.assertFalse(os.path.exists(self.obs))

    def test_render_api_binary_is_digest(self):
        out = observe.render_api(b"\x00\x01", self.obs, "o1")
        self.assertTrue(out.startswith("kind=binary"))

    def test_render_api_large_saves_and_shapes(self):
        raw = b"\n".join([b"line-%02d" % i for i in range(100)])
        saved = []
        out = observe.render_api(raw, self.obs, "o1", max_inline=100,
                                 saved=saved, rel_base=self.tmp.name)
        self.assertIn("kind=text", out)
        self.assertIn("first15:", out)
        self.assertIn("last5:", out)
        self.assertEqual(saved, ["obs/o1.txt"])
        with open(os.path.join(self.obs, "o1.txt"), "rb") as f:
            self.assertEqual(f.read(), raw)

    def test_render_api_head_tail_do_not_repeat_lines(self):
        raw = b"\n".join([b"unique-%02d" % i for i in range(20)])
        out = observe.render_api(raw, self.obs, "o1", max_inline=50)
        self.assertIn("first15:", out)
        self.assertIn("last5:", out)
        for i in range(20):
            self.assertEqual(out.count("unique-%02d" % i), 1)

    def test_render_api_omits_tail_when_all_lines_are_in_head(self):
        raw = b"\n".join([b"row-%02d" % i for i in range(10)])
        out = observe.render_api(raw, self.obs, "o1", max_inline=20)
        self.assertIn("first15:", out)
        self.assertNotIn("last5:", out)
        for i in range(10):
            self.assertEqual(out.count("row-%02d" % i), 1)

    def test_save_rel_base_outside_base_falls_back(self):
        elsewhere = os.path.join(self.tmp.name, "other")
        os.makedirs(elsewhere)
        path = observe.save(b"data", self.obs, "o2.txt", rel_base=elsewhere)
        self.assertTrue(os.path.isabs(path))
        self.assertTrue(os.path.isfile(path))

    def test_render_v1_small_and_large(self):
        body, nbytes, trunc = observe.render_v1(b"hello", self.obs, "v1")
        self.assertEqual((body, nbytes, trunc), ("hello", 5, False))
        raw = b"x" * 2000
        body, nbytes, trunc = observe.render_v1(raw, self.obs, "v1")
        self.assertTrue(trunc)
        self.assertIn("truncated", body)
        self.assertEqual(nbytes, 2000)
        self.assertTrue(os.path.isfile(os.path.join(self.obs, "v1.txt")))

    def test_render_v2_empty_ansi_and_blanks(self):
        self.assertEqual(observe.render_v2(b"", b"", self.obs, "o1"), ("", 0))
        out, nbytes = observe.render_v2(b"\x1b[31mred\x1b[0m\n", b"err", self.obs, "o1")
        self.assertEqual(out, "red\n\n--stderr--\nerr")
        self.assertEqual(nbytes, len(b"red\n\n--stderr--\nerr"))
        out, _ = observe.render_v2(b"a\n\n\n\nb", b"", self.obs, "o1")
        self.assertEqual(out, "a\n\nb")

    def test_render_v2_binary_and_large_text(self):
        out, nbytes = observe.render_v2(b"\x00\x01", b"", self.obs, "o1")
        self.assertTrue(out.startswith("kind=binary"))
        self.assertEqual(nbytes, 2)
        raw = b"\n".join([b"row %03d" % i for i in range(300)])
        out, nbytes = observe.render_v2(raw, b"", self.obs, "o1")
        self.assertIn("kind=text", out)
        self.assertIn("saved=", out)
        self.assertEqual(nbytes, len(raw))
        self.assertTrue(os.path.isfile(os.path.join(self.obs, "o1.txt")))

    def test_shape(self):
        text = observe.shape(b"a\nb\nc\n")
        self.assertIn("lines=3", text)
        self.assertIn("first=b'a'", text)


if __name__ == "__main__":
    unittest.main()
