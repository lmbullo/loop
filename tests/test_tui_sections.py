import unittest
from unittest import mock

from tui import render
from tui.panes import done_rows
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


def snap(**over):
    base = {"daemon": {"state": "running", "detail": "", "pid": 0},
            "current": None, "queue": [], "done": [], "notice": "", "notice_at": 0}
    base.update(over)
    return base


def drawn(snapshot, width=70, height=24, focus="task", tsel=0, tscroll=0):
    screen = Screen()
    with mock.patch.object(render.curses, "doupdate", lambda: None), \
         mock.patch.object(render.curses, "curs_set", lambda n: None):
        render.draw(screen, snapshot, Prompt(), width, height, focus, 0,
                    tsel, tscroll)
    return screen.rows


def labels(rows):
    out = {}
    for y, line in rows.items():
        for label in ("running:", "queued:", "done:"):
            if label in line:
                out[label] = y
    return out


class SectionsTest(unittest.TestCase):
    def test_empty_queue_drops_the_word_queued(self):
        rows = drawn(snap())
        text = "\n".join(rows[y] for y in sorted(rows))
        self.assertIn("running:", text)
        self.assertNotIn("queued", text)
        self.assertIn("done:", text)

    def test_order_is_running_queued_done(self):
        rows = drawn(snap(
            current={"id": "run", "state": "running", "turns": 1, "cost": 0.1,
                     "text": "now"},
            queue=[{"id": "q1", "state": "queued", "text": "later"}],
            done=[{"id": "r1", "state": "complete", "turns": 2, "cost": 0.2,
                   "finish": "done", "text": "earlier"}]))
        where = labels(rows)
        self.assertEqual(set(where), {"running:", "queued:", "done:"})
        self.assertLess(where["running:"], where["queued:"])
        self.assertLess(where["queued:"], where["done:"])

    def test_running_row_does_not_repeat_the_section_state(self):
        rows = drawn(snap(
            current={"id": "run", "state": "running", "turns": 1, "cost": 0.1,
                     "text": "now"}))
        body = next(line for line in rows.values() if "id=run" in line)
        self.assertNotIn("running", body)
        self.assertIn("\u25cf", body)

    def test_only_focused_pane_has_selection_marker(self):
        from tui.panes import SELECT
        rows = drawn(snap(
            current={"id": "run", "state": "running", "turns": 1, "cost": 0.1,
                     "text": "now"},
            queue=[{"id": "q1", "state": "queued", "text": "later"}]))
        marks = [line for line in rows.values() if line.startswith(SELECT)]
        self.assertEqual(len(marks), 1)

    def test_done_list_is_newest_first(self):
        rows = drawn(snap(done=[
            {"id": "new", "state": "complete", "turns": 1, "cost": 0.1,
             "text": "newer task"},
            {"id": "old", "state": "interrupted", "turns": 1, "cost": 0.0,
             "text": "older task"}]))
        text = "\n".join(rows[y] for y in sorted(rows))
        self.assertIn("newer task", text)
        self.assertLess(text.index("newer task"), text.index("older task"))


class DoneRowsTest(unittest.TestCase):
    def test_done_rows_use_state_glyphs(self):
        data = {"done": [
            {"id": "ok", "state": "complete", "turns": 1, "cost": 0.1, "text": "one"},
            {"id": "bad", "state": "interrupted", "turns": 1, "cost": 0.1, "text": "two"}]}
        rows = done_rows(data, 200)
        self.assertIn("\u2713", rows[0][0])
        self.assertIn("\u25a0", rows[1][0])
        self.assertIn("two", rows[1][0])

    def test_done_rows_are_one_line_and_fitted(self):
        data = {"done": [{"id": "r", "state": "complete", "turns": 3, "cost": 0.5,
                          "finish": "done", "text": ("task " * 40) + "\nmore"}]}
        for width in (1, 7, 24, 80, 200):
            rows = done_rows(data, width)
            self.assertEqual(len(rows), 1)
            text, _ = rows[0]
            self.assertNotIn("\n", text)
            self.assertLessEqual(render.swidth(text), width)
        self.assertIn("id=r", done_rows(data, 200)[0][0])


class DoneSnapshotTest(unittest.TestCase):
    def test_recent_done_is_newest_first_and_skips_the_current_run(self):
        from harness import srvsnap
        rows = [{"run_id": "a", "task": "A", "state": "complete", "turns": 1},
                {"run_id": "b", "task": "B", "state": "interrupted", "turns": 2}]
        out = srvsnap.recent_done(rows, skip="a")
        self.assertEqual([row["id"] for row in out], ["b"])
        self.assertEqual([row["task"] for row in out], ["B"])

    def test_recent_done_is_bounded(self):
        from harness import srvsnap
        rows = [{"run_id": str(k), "task": str(k), "state": "complete", "turns": 0}
                for k in range(5)]
        with mock.patch.object(srvsnap, "DONE_LIMIT", 3):
            out = srvsnap.recent_done(rows)
        self.assertEqual([row["id"] for row in out], ["4", "3", "2"])

    def test_recent_done_skips_many_live_runs(self):
        from harness import srvsnap
        rows = [{"run_id": "a", "task": "A", "state": "complete", "turns": 1},
                {"run_id": "b", "task": "B", "state": "complete", "turns": 1},
                {"run_id": "c", "task": "C", "state": "complete", "turns": 1}]
        out = srvsnap.recent_done(rows, skip={"a", "b"})
        self.assertEqual([row["id"] for row in out], ["c"])


class ClientDoneFallbackTest(unittest.TestCase):
    def test_down_snapshot_keeps_done_history(self):
        from tui import client
        done = [{"id": "r1", "state": "complete", "turns": 1, "cost": 0.1,
                 "text": "finished"}]
        with mock.patch.object(client.workers, "live_entries", return_value=[]), \
             mock.patch.object(client.srvsnap, "local_done",
                               return_value=done) as local:
            snap = client.down()
        local.assert_called_once_with(skip=[])
        self.assertEqual(snap["done"], done)
        self.assertEqual(snap["last"], done[0])

    def test_down_snapshot_skips_a_live_worker_run(self):
        from tui import client
        with mock.patch.object(client.workers, "live_entries",
                               return_value=[{"run_id": "live"}]), \
             mock.patch.object(client.srvsnap, "local_done",
                               return_value=[]) as local:
            client.down()
        local.assert_called_once_with(skip=["live"])

    def test_snapshot_fills_done_for_an_old_daemon(self):
        from tui import client
        done = [{"id": "r1", "state": "complete", "turns": 1, "cost": 0.1}]
        reply = {"k": "snapshot", "current": {"run_id": "live"}, "last": None}
        with mock.patch.object(client, "_running", return_value={"pid": 1}), \
             mock.patch.object(client, "_call", return_value=reply), \
             mock.patch.object(client.srvsnap, "local_done",
                               return_value=done) as local:
            snap = client.snapshot()
        local.assert_called_once_with(skip="live")
        self.assertEqual(snap["done"], done)
        self.assertEqual(snap["last"], done[0])

    def test_snapshot_keeps_daemon_done_when_present(self):
        from tui import client
        reply = {"k": "snapshot", "done": [{"id": "r1"}]}
        with mock.patch.object(client, "_running", return_value={"pid": 1}), \
             mock.patch.object(client, "_call", return_value=reply), \
             mock.patch.object(client.srvsnap, "local_done") as local:
            snap = client.snapshot()
        local.assert_not_called()
        self.assertEqual(snap["done"], [{"id": "r1"}])


if __name__ == "__main__":
    unittest.main()
