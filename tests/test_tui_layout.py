import unittest

from tui.panes import fit, marked, task_rows
from tui.prompt import Prompt, display, swidth, wrap
from tui.render import status_line


class TuiLayoutTest(unittest.TestCase):
    def test_fit_fits_and_marks(self):
        self.assertEqual(fit("hello", 5), "hello")
        self.assertEqual(fit("hello", 4), "hel\u2026")
        self.assertEqual(fit("hello", 1), "\u2026")
        self.assertEqual(fit("hello", 0), "")
        self.assertLessEqual(swidth(fit("hello world", 7)), 7)

    def test_swidth_wide_characters(self):
        self.assertEqual(swidth("abc"), 3)
        self.assertEqual(swidth("\u4f60\u597d"), 4)
        self.assertLessEqual(swidth(fit("\u4f60\u597d\u4e16\u754c", 5)), 5)

    def test_task_rows_are_one_line_and_fitted(self):
        snap = {"current": {"id": "r", "state": "running", "turns": 3, "cost": 0.5,
                            "detail": "bad\nnews", "text": ("task " * 40) + "\nmore"}}
        for width in (1, 7, 24, 80, 200):
            rows = task_rows(snap, width)
            self.assertEqual(len(rows), 3)
            for text, _ in rows:
                self.assertNotIn("\n", text)
                self.assertLessEqual(swidth(text), width)

    def test_task_rows_idle(self):
        rows = task_rows({"current": None}, 80)
        self.assertEqual(len(rows), 1)
        self.assertIn("idle", rows[0][0])

    def test_prompt_reflows(self):
        prompt = Prompt()
        prompt.set(" ".join("word%d" % i for i in range(50)))
        narrow = prompt.layout(40)["height"]
        wide = prompt.layout(200)["height"]
        self.assertLess(wide, narrow)
        for width in (39, 40, 119, 199):
            for row in prompt.layout(width)["rows"]:
                self.assertFalse(row["text"].startswith(" "))

    def test_prompt_editing(self):
        prompt = Prompt()
        prompt.set("hello world")
        prompt.word_left()
        self.assertEqual(prompt.cursor, 6)
        prompt.word_right()
        self.assertEqual(prompt.cursor, 11)
        prompt.backspace()
        self.assertEqual(prompt.text, "hello worl")
        prompt.kill_start()
        self.assertEqual((prompt.text, prompt.cursor), ("", 0))
        prompt.set("abc")
        prompt.cursor = 1
        prompt.kill_end()
        self.assertEqual(prompt.text, "a")

    def test_wrap_and_display(self):
        rows = wrap("a b c", 3)
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(display("a\tb\nc"), "a    b c")
        self.assertNotIn("\n", display("a\nb"))

    def test_status_line_width_is_exact(self):
        for width in (1, 5, 20, 80):
            snap = {"daemon": {"state": "running", "detail": "", "pid": 7},
                    "notice": "", "notice_at": 0}
            self.assertEqual(swidth(status_line(snap, width, "prompt")), width)


    def test_selection_marker_fits(self):
        self.assertEqual(marked("task", 6, "> "), "> task")
        self.assertEqual(marked("task", 8), "task")
        self.assertLessEqual(swidth(marked("long task", 5, "> ")), 5)
        self.assertLessEqual(swidth(marked("long task", 3, "> ")), 3)


class TuiMinimalTest(unittest.TestCase):
    def test_no_color_or_bold_surface(self):
        from tui import panes
        self.assertFalse(hasattr(panes, "init_colors"))
        self.assertFalse(hasattr(panes, "PAIR"))
        self.assertFalse(hasattr(panes, "GRUVBOX"))


if __name__ == "__main__":
    unittest.main()
