import unittest
from unittest import mock

from tui import indicator, input, render
from tui.prompt import Prompt


class Screen:
    def __init__(self):
        self.rows = {}

    def erase(self):
        self.rows = {}

    def addstr(self, y, x, text, at=0):
        self.rows[y] = self.rows.get(y, "") + text

    def noutrefresh(self):
        pass


def snap(done=8, queue=0):
    return {
        "daemon": {"state": "running", "detail": "", "pid": 1},
        "notice": "", "notice_at": 0, "current": None,
        "queue": [{"id": f"q{k}", "state": "queued", "text": f"q{k}"}
                  for k in range(queue)],
        "done": [{"id": f"r{k}", "state": "complete", "turns": 1,
                  "cost": 0.1, "text": f"task {k}"} for k in range(done)],
    }


def drawn(snapshot, width=50, height=8, focus="task", qsel=0, tsel=0,
          tscroll=0, qscroll=0, tfollow=True, qfollow=True):
    screen = Screen()
    with mock.patch.object(render.curses, "doupdate", lambda: None), \
         mock.patch.object(render.curses, "curs_set", lambda n: None):
        lay = render.draw(screen, snapshot, Prompt(), width, height, focus,
                          qsel, tsel, tscroll, None, qscroll, tfollow,
                          qfollow)
    return screen.rows, lay


def body(rows):
    return [rows[y] for y in sorted(rows)]


class DoneScrollRenderTest(unittest.TestCase):
    def test_overflow_keeps_only_the_scrolled_window_visible(self):
        rows, lay = drawn(snap(), tscroll=3, tfollow=False)
        self.assertEqual(lay["task"]["scroll"], 3)
        self.assertFalse(lay["task"]["follow"])
        text = "\n".join(body(rows))
        self.assertIn("done: 4\u20137/8", text)
        self.assertIn("task 3", text)
        self.assertIn("task 6", text)
        self.assertNotIn("task 0", text)
        self.assertNotIn("task 7", text)
        self.assertTrue(indicator.THUMB in text)

    def test_scroll_clamps_at_both_ends(self):
        top, _ = drawn(snap(), tscroll=-9, tfollow=False)
        bottom, lay = drawn(snap(), tscroll=99, tfollow=False)
        self.assertIn("done: 1\u20134/8", "\n".join(body(top)))
        self.assertEqual(lay["task"]["scroll"], 4)
        self.assertIn("done: 5\u20138/8", "\n".join(body(bottom)))

    def test_fitting_content_has_no_scroll_or_indicator(self):
        rows, lay = drawn(snap(done=2), height=20, tscroll=9, tfollow=False)
        self.assertEqual(lay["task"]["scroll"], 0)
        text = "\n".join(body(rows))
        self.assertNotIn(indicator.TRACK, text)
        self.assertNotIn(indicator.THUMB, text)

    def test_prompt_shrinks_the_task_window_without_overlap(self):
        rows, lay = drawn(snap(), height=10, focus="prompt", tscroll=99,
                          tfollow=False)
        self.assertGreater(lay["prompt_top"], 1)
        self.assertLessEqual(lay["task"]["scroll"], 5)
        for y, line in rows.items():
            if y >= lay["prompt_top"]:
                self.assertNotIn("id=r", line)

    def test_resize_and_content_changes_reclamp_the_offset(self):
        _, short = drawn(snap(), height=8, tscroll=99, tfollow=False)
        _, tall = drawn(snap(), height=40, tscroll=99, tfollow=False)
        _, shrunk = drawn(snap(done=2), height=8, tscroll=4, tfollow=False)
        self.assertEqual(short["task"]["scroll"], 4)
        self.assertEqual(tall["task"]["scroll"], 0)
        self.assertEqual(shrunk["task"]["scroll"], 0)


class QueueScrollRenderTest(unittest.TestCase):
    def test_overflowing_queue_scrolls_without_dropping_the_cursor(self):
        rows, lay = drawn(snap(done=0, queue=8), focus="queue", qsel=0,
                          qscroll=2, qfollow=False)
        queue = lay["task"]["queue"]
        self.assertEqual((queue["sel"], queue["scroll"], queue["follow"]),
                         (0, 2, False))
        text = "\n".join(body(rows))
        self.assertIn("queued: 3\u20136/8", text)
        self.assertIn("q2", text)
        self.assertNotIn("q0", text)


class FakeWorker:
    def move(self, item_id, delta):
        pass

    def drop(self, item_id):
        pass

    def cancel(self, item_id=None, run_id=None):
        return True


class FakeApp:
    def __init__(self, done=8, queue=0):
        self.q = [{"id": f"q{k}", "text": f"q{k}"} for k in range(queue)]
        self.d = [{"id": f"r{k}", "text": f"task {k}"} for k in range(done)]
        self.worker = FakeWorker()
        self.focus = "task"
        self.qsel = 0
        self.tsel = 0
        self.tscroll = 0
        self.qscroll = 0
        self.tfollow = True
        self.qfollow = True
        self.tview = {"n": 1 + done + queue, "vis": 4,
                      "done": {"n": done, "vis": 4}}
        self.dirty = False
        self.said = []

    def snapshot(self):
        return {"current": None, "queue": self.q, "done": self.d}

    def say(self, text):
        self.said.append(text)


class TaskWheelTest(unittest.TestCase):
    def test_wheel_scrolls_both_directions_without_moving_selection(self):
        app = FakeApp(done=8)
        input.handle(app, ("key", "scroll_down"))
        input.handle(app, ("key", "scroll_down"))
        self.assertEqual((app.tsel, app.tscroll, app.tfollow),
                         (0, 2, False))
        input.handle(app, ("key", "wheel_up"))
        self.assertEqual((app.tsel, app.tscroll), (0, 1))

    def test_shift_arrows_use_the_same_free_scroll(self):
        app = FakeApp(done=8)
        input.handle(app, ("key", "shift_down"))
        self.assertEqual((app.tsel, app.tscroll), (0, 1))
        input.handle(app, ("key", "shift_up"))
        self.assertEqual((app.tsel, app.tscroll), (0, 0))

    def test_wheel_clamps_when_all_done_rows_fit(self):
        app = FakeApp(done=2)
        app.tview["done"]["vis"] = 5
        input.handle(app, ("key", "wheel_down"))
        self.assertEqual((app.tscroll, app.tfollow), (0, False))

    def test_selection_keys_resume_following_the_viewport(self):
        app = FakeApp(done=8)
        input.handle(app, ("key", "wheel_down"))
        app.tsel = 1
        input.handle(app, ("key", "down"))
        self.assertTrue(app.tfollow)
        self.assertEqual(app.tsel, 2)

    def test_queue_wheel_scrolls_the_queue_viewport(self):
        app = FakeApp(done=0, queue=8)
        app.focus = "queue"
        app.tview["queue"] = {"n": 8, "vis": 4}
        input.handle(app, ("key", "wheel_down"))
        self.assertEqual((app.qsel, app.qscroll, app.qfollow), (0, 1, False))
        input.handle(app, ("key", "scroll_up"))
        self.assertEqual(app.qscroll, 0)


if __name__ == "__main__":
    unittest.main()
