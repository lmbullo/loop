import unittest
from unittest import mock

from tui import indicator, render
from tui.indicator import THUMB, TRACK
from tui.logview import log_block
from tui.panes import done_block, queue_block
from tui.prompt import Prompt
from tui.probe import Screen, lines


def log_data(calls=20):
    entries = [{"kind": "call", "turn": k + 1, "name": "exec", "args": "x",
                "obs": "ok", "failed": False} for k in range(calls)]
    entries.append({"kind": "result", "result": "done", "finish": "done"})
    return {"id": "run", "state": "complete", "entries": entries}


def task_snap(done=0, queue=0, current=False):
    return {
        "daemon": {"state": "running", "detail": "", "pid": 1},
        "notice": "", "notice_at": 0,
        "current": {"id": "run", "state": "running", "turns": 1,
                    "cost": 0.1, "text": "now"} if current else None,
        "queue": [{"id": f"q{k}", "state": "queued", "text": f"q{k}"}
                  for k in range(queue)],
        "done": [{"id": f"r{k}", "state": "complete", "turns": 1,
                  "cost": 0.1, "text": f"task {k}"} for k in range(done)],
    }


def right_edges(rows):
    return {row[-1] for row in rows if row}


class IndicatorMathTest(unittest.TestCase):
    def test_nothing_is_drawn_when_every_row_fits(self):
        self.assertIsNone(indicator.bar(4, 4, 0))
        self.assertIsNone(indicator.bar(3, 8, 0))
        self.assertIsNone(indicator.window(9, 0, 0))
        self.assertEqual(indicator.layout(12, 4, 4, 0), (12, None))

    def test_bar_is_one_pure_column_of_the_visible_height(self):
        text = indicator.bar(20, 6, 0)
        self.assertEqual(len(text), 6)
        self.assertEqual(set(text), {TRACK, THUMB})
        self.assertTrue(text.startswith(THUMB))
        self.assertEqual(indicator.layout(12, 20, 6, 0)[0], 11)

    def test_thumb_tracks_the_scroll_offset_and_clamps(self):
        top = indicator.bar(20, 6, 0)
        middle = indicator.bar(20, 6, 7)
        bottom = indicator.bar(20, 6, 99)
        self.assertLess(top.index(THUMB), middle.index(THUMB))
        self.assertLess(middle.index(THUMB), bottom.index(THUMB))
        self.assertTrue(bottom.endswith(THUMB))
        self.assertEqual(indicator.window(20, 6, 99),
                         indicator.window(20, 6, 14))

    def test_the_thumb_never_disappears_on_very_long_content(self):
        text = indicator.bar(1000, 10, 500)
        self.assertEqual(text.count(THUMB), 1)
        self.assertEqual(len(text), 10)


class LogIndicatorTest(unittest.TestCase):
    def test_an_overflowing_log_shows_the_bar_beside_its_rows(self):
        screen = Screen(20, 10)
        log_block(screen, log_data(), 0, 8, 20, 10, sel=20)
        rows = lines(screen)
        self.assertNotIn(rows[0][-1:], (TRACK, THUMB))
        for row in rows[1:8]:
            self.assertIn(row[-1:], (TRACK, THUMB))

    def test_a_short_log_has_no_indicator(self):
        screen = Screen(40, 20)
        log_block(screen, log_data(2), 0, 12, 40, 20)
        self.assertFalse(set("".join(lines(screen))) & {TRACK, THUMB})

    def test_resize_and_content_changes_recompute_visibility(self):
        short = Screen(30, 6)
        log_block(short, log_data(20), 0, 5, 30, 6)
        self.assertTrue(right_edges(lines(short)[1:4]) & {TRACK, THUMB})
        tall = Screen(30, 40)
        log_block(tall, log_data(20), 0, 39, 30, 40)
        self.assertFalse(right_edges(lines(tall)) & {TRACK, THUMB})
        grown = Screen(30, 6)
        log_block(grown, log_data(40), 0, 5, 30, 6)
        self.assertTrue(right_edges(lines(grown)[1:4]) & {TRACK, THUMB})


class TaskIndicatorTest(unittest.TestCase):
    def test_done_and_queue_overflow_show_the_same_column(self):
        screen = Screen(40, 8)
        done_block(screen, task_snap(done=8), 0, 6, 40, 8)
        done_rows = lines(screen)
        self.assertNotIn(done_rows[0][-1:], (TRACK, THUMB))
        self.assertTrue(right_edges(done_rows[1:5]) & {TRACK, THUMB})

        queue = Screen(40, 8)
        queue_block(queue, task_snap(queue=8), 0, 6, 40, 8, qsel=7)
        queue_rows = lines(queue)
        self.assertNotIn(queue_rows[0][-1:], (TRACK, THUMB))
        self.assertTrue(right_edges(queue_rows[1:5]) & {TRACK, THUMB})

    def test_fitting_sections_have_no_indicator(self):
        screen = Screen(40, 20)
        done_block(screen, task_snap(done=2), 0, 8, 40, 20)
        self.assertFalse(set("".join(lines(screen))) & {TRACK, THUMB})
        queue = Screen(40, 20)
        queue_block(queue, task_snap(queue=2), 0, 8, 40, 20, qsel=0)
        self.assertFalse(set("".join(lines(queue))) & {TRACK, THUMB})

    def test_render_draws_the_indicator_in_the_task_view(self):
        screen = Screen(40, 8)
        with mock.patch.object(render.curses, "doupdate", lambda: None), \
             mock.patch.object(render.curses, "curs_set", lambda n: None):
            render.draw(screen, task_snap(done=8), Prompt(), 40, 8, "task", 0)
        rows = lines(screen)
        done_at = next(k for k, row in enumerate(rows) if row.startswith("done:"))
        self.assertNotIn(rows[done_at][-1:], (TRACK, THUMB))
        self.assertTrue(right_edges(rows[done_at + 1:]) & {TRACK, THUMB})


if __name__ == "__main__":
    unittest.main()
