import base64
import unittest

from tui import clipboard, select


def rows(*lines, width=12):
    def read(y):
        return (lines[y] if y < len(lines) else "").ljust(width)
    return read


class SelectTest(unittest.TestCase):
    def test_range_is_ordered_across_rows_in_both_directions(self):
        self.assertEqual(select.ordered({"a": (3, 1), "b": (2, 4)}),
                         ((3, 1), (2, 4)))
        self.assertEqual(select.ordered({"a": (5, 3), "b": (1, 1)}),
                         ((1, 1), (5, 3)))

    def test_spans_cover_first_and_last_rows_and_everything_between(self):
        sel = {"a": (3, 1), "b": (4, 3)}
        self.assertEqual(select.spans(sel, 10),
                         [(1, 3, 10), (2, 0, 10), (3, 0, 5)])
        self.assertEqual(select.spans({"a": (2, 2), "b": (4, 2)}, 10),
                         [(2, 2, 5)])

    def test_text_keeps_middle_rows_and_trims_only_the_edges(self):
        sel = {"a": (1, 1), "b": (4, 2)}
        got = select.text(sel, 12, rows("zero", "one  two", "  indented"))
        self.assertEqual(got, "ne  two\n  ind")
        self.assertEqual(select.text(None, 12, rows("x")), "")

    def test_text_of_a_single_row_reads_only_its_cells(self):
        sel = {"a": (1, 0), "b": (3, 0)}
        self.assertEqual(select.text(sel, 12, rows("hello")), "ell")
        self.assertEqual(select.text({"a": (9, 0), "b": (1, 0)}, 12,
                                     rows("hello")), "ello")


class ClipboardTest(unittest.TestCase):
    def copied(self, **kw):
        written = []
        ok = clipboard.copy("hi", write=written.append, env={}, which=lambda n: None,
                            **kw)
        return ok, written

    def test_osc52_carries_base64_utf8_on_the_clipboard(self):
        text = "héllo\nworld"
        seq = clipboard.sequence(text, env={})
        self.assertEqual(seq, "\x1b]52;c;%s\x07" %
                         base64.b64encode(text.encode()).decode())
        self.assertEqual(clipboard.sequence("x", env={"TMUX": "/tmp/t"}),
                         "\x1bPtmux;\x1b\x1b]52;c;eA==\x07\x1b\\")

    def test_copy_writes_the_sequence_and_reports_success(self):
        ok, written = self.copied()
        self.assertTrue(ok)
        self.assertEqual(written, [clipboard.sequence("hi", env={}).encode()])

    def test_copy_falls_back_to_the_first_installed_helper(self):
        calls = []

        def which(name):
            return "/bin/" + name if name == "xclip" else None

        def run(cmd, **kw):
            calls.append((cmd, kw["input"]))

        wrote = []
        ok = clipboard.copy("hi", write=wrote.append, env={}, which=which, run=run)
        self.assertTrue(ok)
        self.assertEqual(calls, [(["xclip", "-selection", "clipboard"], b"hi")])

    def test_copy_skips_osc52_for_huge_text_but_still_uses_a_helper(self):
        wrote = []
        run = lambda cmd, **kw: None
        ok = clipboard.copy("x" * (clipboard.MAX + 1), write=wrote.append,
                            env={}, which=lambda n: "/bin/" + n, run=run)
        self.assertTrue(ok)
        self.assertEqual(wrote, [])

    def test_copy_reports_failure_when_no_transport_works(self):
        def bad(data):
            raise OSError("no tty")
        self.assertFalse(clipboard.copy("hi", write=bad, env={},
                                        which=lambda n: None))

    def test_an_empty_selection_is_not_copied(self):
        self.assertFalse(clipboard.copy("", write=lambda data: None,
                                        which=lambda n: None))

    def test_helper_skips_a_command_that_exits_nonzero(self):
        class Done:
            returncode = 1

        names = []
        self.assertIsNone(clipboard.helper(
            "hi", which=lambda n: "/bin/" + n,
            run=lambda cmd, **kw: names.append(cmd[0]) or Done()))
        self.assertEqual(names, ["wl-copy", "xclip", "xsel", "pbcopy"])


if __name__ == "__main__":
    unittest.main()
