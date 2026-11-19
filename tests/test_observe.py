import os
import re
import tempfile
import unittest

from harness import ledger, observe


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

    def test_is_binary_keeps_utf8_text(self):
        self.assertFalse(observe.is_binary("第一行\n".encode()))
        self.assertFalse(observe.is_binary("résumé café\n".encode()))
        self.assertFalse(observe.is_binary(("第一行\n" * 300).encode()))
        self.assertFalse(observe.is_binary("done ✅\n".encode()))

    def test_is_binary_at_sample_boundary(self):
        raw = b"a" * 4095 + "你".encode()[:2]
        self.assertEqual(len(raw), 4097)
        self.assertFalse(observe.is_binary(raw))
        self.assertTrue(observe.is_binary(b"abc\xff"))

    def test_digest(self):
        text = observe.digest(b"\x00\x01")
        self.assertIn("kind=binary", text)
        self.assertIn("bytes=2", text)
        self.assertIn("sha256=", text)
        self.assertIn("head_hex=0001", text)

    def test_render_api_small_is_verbatim(self):
        self.assertEqual(observe.render_api(b"hello", self.obs, "o1"), "hello")
        self.assertFalse(os.path.exists(self.obs))

    def test_default_bound_summarizes_and_preserves_bytes(self):
        bound = observe.config.DEFAULT_MAX_INLINE
        raw = b"x" * (bound + 1)
        saved = []
        out = observe.render_api(raw, self.obs, "o1", max_inline=bound,
                                 saved=saved, rel_base=self.tmp.name)
        self.assertIn("obs bytes=", out)
        self.assertIn("saved=", out)
        self.assertIn("sha=", out)
        self.assertLessEqual(len(out.encode()), bound)
        self.assertIn("next: tail -c +", out)
        self.assertEqual(saved, ["obs/o1.txt"])
        with open(os.path.join(self.obs, "o1.txt"), "rb") as f:
            self.assertEqual(f.read(), raw)

    def test_bound_is_inclusive(self):
        bound = observe.config.DEFAULT_MAX_INLINE
        raw = b"x" * bound
        self.assertEqual(observe.render_api(raw, self.obs, "o1", max_inline=bound),
                         raw.decode())

    def test_render_api_binary_is_digest(self):
        out = observe.render_api(b"\x00\x01", self.obs, "o1")
        self.assertTrue(out.startswith("kind=binary"))

    def test_render_api_unicode_is_text_and_saved(self):
        raw = ("第一行内容\n" * 300).encode()
        saved = []
        out = observe.render_api(raw, self.obs, "o1", max_inline=2048,
                                 saved=saved, rel_base=self.tmp.name)
        self.assertIn("obs bytes=", out)
        self.assertNotIn("kind=binary", out)
        self.assertIn("第一行内容", out)
        self.assertEqual(saved, ["obs/o1.txt"])
        with open(os.path.join(self.obs, "o1.txt"), "rb") as f:
            self.assertEqual(f.read(), raw)

    def test_render_api_large_saves_and_shapes(self):
        raw = b"\n".join([b"line-%02d" % i for i in range(100)])
        saved = []
        out = observe.render_api(raw, self.obs, "o1", max_inline=100,
                                 saved=saved, rel_base=self.tmp.name)
        self.assertIn("obs bytes=", out)
        self.assertIn("head:", out)
        self.assertIn("tail:", out)
        self.assertEqual(saved, ["obs/o1.txt"])
        with open(os.path.join(self.obs, "o1.txt"), "rb") as f:
            self.assertEqual(f.read(), raw)

    def test_summary_fills_bound_and_repeat_keeps_next(self):
        raw = b"\n".join([b"row-%03d unique" % i for i in range(200)])
        led, saved = ledger.Ledger(), []
        out = observe.render_api(raw, self.obs, "o1", max_inline=2048,
                                 saved=saved, rel_base=self.tmp.name,
                                 ledger=led, obs_id="obs-1")
        self.assertLessEqual(len(out.encode()), 2048)
        m = re.search(r"next: sed -n (\d+),(\d+)p (\S+)", out)
        lines = raw.split(b"\n")
        part = b"\n".join(lines[int(m.group(1)) - 1:int(m.group(2))])
        self.assertEqual(observe.render_api(part, self.obs, "o2",
                                           max_inline=2048), part.decode())
        again = observe.render_api(raw, self.obs, "o3", max_inline=2048,
                                   ledger=led, obs_id="obs-2", rel_base=self.tmp.name)
        self.assertTrue(again.startswith("same=obs-1 bytes="))
        self.assertIn("next: sed -n", again)

    def test_render_api_head_tail_do_not_repeat_lines(self):
        raw = b"\n".join([b"unique-%02d" % i for i in range(20)])
        out = observe.render_api(raw, self.obs, "o1", max_inline=50)
        for i in range(6):
            self.assertEqual(out.count("unique-%02d" % i), 1)
        for i in range(17, 20):
            self.assertEqual(out.count("unique-%02d" % i), 1)
        self.assertNotIn("unique-10", out)

    def test_render_api_short_output_shows_all_lines_once(self):
        raw = b"\n".join([b"row-%02d" % i for i in range(10)])
        out = observe.render_api(raw, self.obs, "o1", max_inline=20)
        self.assertIn("head:", out)
        for i in range(10):
            self.assertEqual(out.count("row-%02d" % i), 1)

    def test_render_api_keeps_stderr_tail(self):
        raw = b"out\n" + observe.STDERR_SEP + b"\n".join(
            [b"warn-%d" % i for i in range(20)])
        out = observe.render_api(raw, self.obs, "o1", max_inline=20)
        self.assertIn("stderr_tail:", out)
        self.assertIn("warn-19", out)

    def test_ledger_turns_an_exact_repeat_into_a_reference(self):
        raw = b"same payload\n" * 20
        led = ledger.Ledger()
        first = observe.render_api(raw, self.obs, "o1", max_inline=50,
                                   ledger=led, obs_id="obs-1",
                                   rel_base=self.tmp.name)
        second = observe.render_api(raw, self.obs, "o2", max_inline=50,
                                    ledger=led, obs_id="obs-2",
                                    rel_base=self.tmp.name)
        self.assertIn("obs bytes=", first)
        self.assertEqual(second, "same=obs-1 bytes=260")
        self.assertFalse(os.path.exists(os.path.join(self.obs, "o2.txt")))

    def test_ledger_from_events_recovers_exec_payload(self):
        events = [{"type": "turn", "data": {"calls": [{
            "name": "exec", "observation": "exit=0 ms=1\nsame payload",
            "saved": None}]}}]
        led = ledger.Ledger.from_events(events)
        self.assertIsNotNone(led.get(b"same payload"))

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
