import unittest
from unittest import mock

from tui import render
from tui.prompt import Prompt


class Screen:
    def __init__(self):
        self.rows = {}

    def erase(self):
        self.rows = {}

    def addstr(self, y, x, text, at=0):
        self.rows[y] = self.rows.get(y, "") + text

    def move(self, y, x):
        self.cursor = (y, x)

    def noutrefresh(self):
        pass


def snap():
    return {"daemon": {"state": "running", "detail": "", "pid": 1},
            "notice": "", "notice_at": 0, "current": None, "queue": [],
            "done": []}


def log():
    return {"id": "run", "data": {"id": "run", "state": "complete",
                                  "entries": [{"kind": "result",
                                               "result": "ok",
                                               "finish": "done"}]},
            "sel": 0, "scroll": 0, "follow": True}


def draw(prompt, focus, opened=None):
    screen = Screen()
    with mock.patch.object(render.curses, "doupdate", lambda: None), \
         mock.patch.object(render.curses, "curs_set", lambda n: None):
        lay = render.draw(screen, snap(), prompt, 60, 10, focus, 0, 0, 0,
                          opened)
    return screen, lay


class PromptOverlayTest(unittest.TestCase):
    def test_prompt_draws_over_an_open_log(self):
        prompt = Prompt()
        prompt.set("hello")
        screen, lay = draw(prompt, "prompt", log())
        text = "\n".join(screen.rows[y] for y in sorted(screen.rows))
        self.assertIn("logs:", text)
        self.assertIn("hello", text)
        self.assertIn("prompt", text)
        self.assertTrue(lay["prompt_open"])
        self.assertLess(lay["prompt_top"], 10)

    def test_task_view_has_no_log_header(self):
        screen, lay = draw(Prompt(), "task")
        text = "\n".join(screen.rows[y] for y in sorted(screen.rows))
        self.assertNotIn("logs:", text)
        self.assertIn("running:", text)
        self.assertNotIn("log", lay)

    def test_log_uses_the_body_above_the_prompt(self):
        screen, lay = draw(Prompt(), "prompt", log())
        self.assertEqual(lay["log"]["n"], 1)
        self.assertLess(lay["log"]["vis"], 9)
        self.assertGreater(lay["prompt_top"], 1)


if __name__ == "__main__":
    unittest.main()
