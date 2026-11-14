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

    def test_prompt_box_edges(self):
        from tui import render

        class Screen:
            def __init__(self):
                self.calls = []

            def addstr(self, y, x, text, at=0):
                self.calls.append((y, x, text, at))

        prompt = Prompt()
        prompt.set("hello")
        screen = Screen()
        render.prompt_block(screen, prompt, 0, 20, 10, "prompt", 20, 5)
        top, bottom = screen.calls[0], screen.calls[-1]
        self.assertIn("\u2500", top[2])
        self.assertTrue(top[2].startswith(" prompt "))
        self.assertEqual(bottom[2], "\u2500" * 20)
        self.assertEqual(bottom[0], top[0] + 2)

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


class TuiThemeTest(unittest.TestCase):
    def test_palette_is_complete_and_muted(self):
        from tui import theme
        self.assertEqual(set(theme.SCHEME), set(theme.PAIR))
        self.assertEqual(set(theme.BASE), set(theme.PAIR))
        self.assertEqual(len(set(theme.PAIR.values())), len(theme.PAIR))
        self.assertTrue(all(0 <= value <= 255 for value in theme.SCHEME.values()))
        self.assertNotEqual(theme.SCHEME["muted"], theme.SCHEME["strong"])
        for role in ("muted", "strong"):
            self.assertNotEqual(theme.SCHEME[role], theme.SCHEME["accent"])

    def test_prompt_box_is_grey(self):
        from tui import theme
        self.assertEqual(theme.PROMPT_IDLE, "muted")
        self.assertEqual(theme.PROMPT_FOCUS, "strong")
        self.assertNotIn(theme.PROMPT_IDLE, theme.STATE.values())
        self.assertNotIn(theme.PROMPT_FOCUS, theme.STATE.values())

    def test_prompt_block_applies_grey_roles(self):
        from unittest import mock
        from tui import render, theme

        class Screen:
            def __init__(self):
                self.calls = []

            def addstr(self, y, x, text, at=0):
                self.calls.append((y, x, text, at))

        prompt = Prompt()
        prompt.set("hello")
        for focus, role in (("prompt", "strong"), ("task", "muted")):
            screen = Screen()
            with mock.patch.object(theme, "attr", side_effect=lambda name: f"<{name}>"):
                render.prompt_block(screen, prompt, 0, 20, 10, focus, 20, 5)
            self.assertEqual(screen.calls[0][3], f"<{role}>")
            self.assertEqual(screen.calls[1][3], f"<{role}>")

    def test_state_roles(self):
        from tui import theme
        self.assertEqual(theme.state_role("running"), "accent")
        self.assertEqual(theme.state_role("complete"), "ok")
        self.assertEqual(theme.state_role("corrupt"), "err")
        self.assertEqual(theme.state_role("queued"), "muted")
        self.assertEqual(theme.status_role({"daemon": {"state": "running"}}), "muted")
        self.assertEqual(theme.status_role({"daemon": {"state": "stopped"}}), "err")

    def test_attr_is_safe_before_init(self):
        from tui import theme
        self.assertEqual(theme.attr("missing"), 0)
        self.assertIsInstance(theme.attr("muted"), int)


if __name__ == "__main__":
    unittest.main()
