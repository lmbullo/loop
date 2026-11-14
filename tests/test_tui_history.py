import unittest
from unittest import mock

from tui import render
from tui.panes import SELECT
from tui.prompt import Prompt
from tui.rows import window


class Screen:
    def __init__(self):
        self.rows = {}

    def erase(self):
        self.rows = {}

    def addstr(self, y, x, text, at=0):
        self.rows[y] = self.rows.get(y, "") + text

    def noutrefresh(self):
        pass


def snap(current=True, done=6, queue=()):
    base = {"daemon": {"state": "running", "detail": "", "pid": 0},
            "current": {"id": "run", "state": "running", "turns": 1,
                        "cost": 0.1, "text": "now"} if current else None,
            "queue": [{"id": qid, "state": "queued", "text": qid} for qid in queue],
            "done": [{"id": f"r{k}", "state": "complete", "turns": 1, "cost": 0.1,
                      "text": f"task {k}"} for k in range(done)],
            "notice": "", "notice_at": 0}
    return base


def drawn(snapshot, width=70, height=24, focus="task", tsel=0, tscroll=0):
    screen = Screen()
    with mock.patch.object(render.curses, "doupdate", lambda: None), \
         mock.patch.object(render.curses, "curs_set", lambda n: None):
        lay = render.draw(screen, snapshot, Prompt(), width, height, focus, 0,
                          tsel, tscroll)
    return screen.rows, lay


def body(rows):
    return [rows[y] for y in sorted(rows)]


class WindowTest(unittest.TestCase):
    def test_window_keeps_the_selection_visible(self):
        self.assertEqual(window(6, 4, 5, 0), (6, 4, 5, 2))
        self.assertEqual(window(6, 4, 0, 2), (6, 4, 0, 0))
        self.assertEqual(window(6, 4, 2, 2), (6, 4, 2, 2))
        self.assertEqual(window(6, 4, None, 2), (6, 4, None, 2))
        self.assertEqual(window(0, 4, 3, 9), (0, 4, None, 0))


class TaskSelectionTest(unittest.TestCase):
    def test_flat_selection_maps_running_queue_then_done(self):
        from tui.rows import task_count, task_sel
        snap = {"current": {"id": "r"}, "queue": [{"id": "q1"}, {"id": "q2"}],
                "done": [{"id": "d1"}, {"id": "d2"}]}
        self.assertEqual(task_count(snap), 5)
        self.assertEqual(task_sel(snap, 0), ("running", 0))
        self.assertEqual(task_sel(snap, 1), ("queue", 0))
        self.assertEqual(task_sel(snap, 2), ("queue", 1))
        self.assertEqual(task_sel(snap, 3), ("done", 0))
        self.assertEqual(task_sel(snap, 99), ("done", 1))
        self.assertEqual(task_sel({"current": None}, 9), ("running", 0))


class TaskHistoryLayoutTest(unittest.TestCase):
    def test_task_focus_marks_a_done_row(self):
        rows, lay = drawn(snap(), tsel=2)
        marked = [line for line in body(rows) if line.startswith(SELECT)]
        self.assertEqual(len(marked), 1)
        self.assertIn("task 1", marked[0])
        self.assertEqual(lay["task"]["n"], 7)
        self.assertEqual(lay["task"]["sel"], 2)
        running = next(line for line in body(rows) if "id=run" in line)
        self.assertFalse(running.startswith(SELECT))

    def test_task_focus_marks_a_queued_row(self):
        rows, lay = drawn(snap(queue=("q1", "q2")), tsel=2)
        marked = [line for line in body(rows) if line.startswith(SELECT)]
        self.assertEqual(len(marked), 1)
        self.assertIn("q2", marked[0])
        self.assertEqual(lay["task"]["n"], 9)
        self.assertEqual(lay["task"]["sel"], 2)

    def test_queue_rows_shift_the_done_selection_index(self):
        rows, lay = drawn(snap(queue=("q1",), done=2), tsel=2)
        marked = [line for line in body(rows) if line.startswith(SELECT)]
        self.assertEqual(len(marked), 1)
        self.assertIn("task 0", marked[0])
        self.assertEqual(lay["task"]["n"], 4)
        self.assertEqual(lay["task"]["sel"], 2)

    def test_queue_selection_scrolls_into_view(self):
        rows, lay = drawn(snap(queue=("q1", "q2", "q3", "q4", "q5", "q6"),
                               done=0), height=8, tsel=6)
        marked = [line for line in body(rows) if line.startswith(SELECT)]
        self.assertEqual(len(marked), 1)
        self.assertIn("q6", marked[0])
        self.assertIn("queued: 3\u20136/6", body(rows))
        self.assertEqual(lay["task"]["n"], 7)
        self.assertEqual(lay["task"]["sel"], 6)

    def test_done_selection_scrolls_into_view(self):
        rows, lay = drawn(snap(), height=8, tsel=6)
        self.assertEqual(lay["task"]["scroll"], 2)
        self.assertIn("done: 3\u20136/6", body(rows))
        marked = [line for line in body(rows) if line.startswith(SELECT)]
        self.assertEqual(len(marked), 1)
        self.assertIn("task 5", marked[0])

    def test_leaving_task_focus_keeps_the_done_scroll(self):
        rows, lay = drawn(snap(queue=("q1",)), height=8, focus="queue",
                          tsel=6, tscroll=2)
        header = next(line for line in body(rows) if line.startswith("done:"))
        self.assertTrue(header.startswith("done: 3\u2013"), header)
        self.assertTrue(header.endswith("/6"), header)
        marked = [line for line in body(rows) if line.startswith(SELECT)]
        self.assertEqual(len(marked), 1)
        self.assertIn("q1", marked[0])
        self.assertEqual(lay["task"]["scroll"], 2)

    def test_selection_is_clamped_when_done_shrinks(self):
        rows, lay = drawn(snap(current=False, done=1), tsel=9)
        self.assertEqual(lay["task"]["n"], 2)
        self.assertEqual(lay["task"]["sel"], 1)
        marked = [line for line in body(rows) if line.startswith(SELECT)]
        self.assertEqual(len(marked), 1)
        self.assertIn("task 0", marked[0])


if __name__ == "__main__":
    unittest.main()
