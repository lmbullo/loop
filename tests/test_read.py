import os
import tempfile
import unittest

from harness import read


def write(root, name, text):
    path = os.path.join(root, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def field(out, key):
    for line in out.split("\n"):
        if line.startswith(key + " "):
            return line[len(key) + 1:]
    return None


def next_call(out):
    for line in out.split("\n"):
        if line.startswith("next: "):
            return line[6:]
    return None


class ReadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.path = write(self.root, "m.txt",
                          "\n".join(f"line-{i:03d}" for i in range(1, 61)) + "\n")

    def test_range_is_numbered_and_paged(self):
        out = read.do_read({"path": self.path, "start": 10, "end": 12}, None, 2048)
        self.assertIn("lines=60", out)
        self.assertIn("shown 10-12 of 60", out)
        self.assertIn("10| line-010", out)
        self.assertIn("12| line-012", out)
        self.assertNotIn("line-013", out)

    def test_end_past_eof_is_clamped(self):
        out = read.do_read({"path": self.path, "start": 58, "end": 999}, None, 2048)
        self.assertIn("shown 58-60 of 60", out)
        self.assertIsNone(next_call(out))

    def test_small_budget_prints_one_executable_next(self):
        out = read.do_read({"path": self.path}, None, 400)
        call = next_call(out)
        taken = int(field(out, "shown").split(" of ")[0].rsplit("-", 1)[1])
        self.assertEqual(call, f"read(path={self.path}, start={taken + 1})")
        self.assertTrue(field(out, "shown").startswith("1-"), out)
        self.assertNotIn(f"line-{taken + 1:03d}", out)
        self.assertLessEqual(len(out.split("\nnext: ")[0].encode()), 400)

    def test_next_call_resumes_the_same_slice(self):
        first = read.do_read({"path": self.path}, None, 400)
        start = int(next_call(first).rsplit("start=", 1)[1].rstrip(")"))
        second = read.do_read({"path": self.path, "start": start}, None, 400)
        shown = field(second, "shown")
        self.assertTrue(shown.startswith(f"{start}-"), shown)
        self.assertIn(f"{start}| line-{start:03d}", second)
        self.assertNotIn(f"{start - 1}| line-{start - 1:03d}", second)

    def test_find_with_context(self):
        out = read.do_read({"path": self.path, "find": r"line-0(0[5]|1[0])", "ctx": 1},
                           None, 2048)
        self.assertIn("matches=2", out)
        self.assertIn("shown 4-6,9-11 of 60", out)
        self.assertIn(" 5| line-005", out)

    def test_find_without_match_hints_the_fix(self):
        out = read.do_read({"path": self.path, "find": "nope"}, None, 2048)
        self.assertIn("matches=0", out)
        self.assertIn("hint=", out)

    def test_offset_pages_one_long_line(self):
        long_path = write(self.root, "long.txt", "x" * 400)
        out = read.do_read({"path": long_path, "offset": 0}, None, 200)
        call = next_call(out)
        self.assertIsNotNone(call)
        at = int(call.rsplit("offset=", 1)[1].rstrip(")"))
        self.assertGreater(at, 0)
        out2 = read.do_read({"path": long_path, "offset": at}, None, 200)
        self.assertIn(f"offset={at}", out2)
        self.assertNotIn("offset=0 ", out2)

    def test_empty_binary_and_dir(self):
        empty = write(self.root, "e.txt", "")
        self.assertIn("lines=0", read.do_read({"path": empty}, None, 2048))
        binp = os.path.join(self.root, "b.bin")
        with open(binp, "wb") as f:
            f.write(b"\x00\x01\x02binary")
        self.assertIn("kind=binary", read.do_read({"path": binp}, None, 2048))
        self.assertIn("kind=dir", read.do_read({"path": self.root}, None, 2048))

    def test_missing_path_and_bad_args(self):
        self.assertIn("err read", read.do_read({"path": os.path.join(self.root, "no")}))
        self.assertIn("err bad_args read", read.do_read({}))

    def test_spaced_path_is_quoted_in_next(self):
        spaced = write(self.root, "a b.txt", "y\n" * 80)
        out = read.do_read({"path": spaced}, None, 300)
        self.assertIn(f'read(path="{spaced}", start=', next_call(out))


if __name__ == "__main__":
    unittest.main()
