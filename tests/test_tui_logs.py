import unittest

from harness import runlog
from tui.logview import log_block
from tui.prompt import swidth
from tui.rows import join_parts, log_parts

from tests import support


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


def stream(calls=1, terminal=True):
    message = {"role": "assistant", "content": None,
               "tool_calls": [{"id": f"c{i}", "type": "function",
                               "function": {"name": "exec",
                                            "arguments": '{"argv": ["ls"]}'}}
                              for i in range(calls)]}
    turn = dict(support.TURN)
    turn["message"] = message
    turn["calls"] = [{"id": f"c{i}", "name": "exec", "observation": "a.txt",
                      "bytes": 5, "saved": None} for i in range(calls)]
    events = [support.event(support.RUN_ID, 1, "run_start", dict(support.RUN_START)),
              support.event(support.RUN_ID, 2, "turn", turn)]
    if terminal:
        events.append(support.event(support.RUN_ID, 3, "end", dict(support.END)))
    return events


def data(calls=20):
    entries = [{"kind": "call", "turn": 1, "name": "exec",
                "args": '["ls"]', "obs": "ok", "failed": False}
               for _ in range(calls)]
    entries.append({"kind": "result", "result": "finished", "finish": "done"})
    return {"id": "run", "state": "complete", "entries": entries}


class RunLogTest(unittest.TestCase):
    def test_entries_are_tool_calls_then_the_final_summary(self):
        rows = runlog.entries(stream(2))
        self.assertEqual([row["kind"] for row in rows], ["call", "call", "result"])
        self.assertEqual(rows[0]["name"], "exec")
        self.assertEqual(rows[0]["args"], '{"argv":["ls"]}')
        self.assertEqual(rows[0]["obs"], "a.txt")
        self.assertEqual(rows[-1]["result"], "ok")
        self.assertEqual(rows[-1]["finish"], "done")

    def test_final_summary_keeps_full_text_and_paragraphs(self):
        events = stream(1)
        text = ("first " * 100).rstrip() + "\n\nLAST LINE"
        events[-1]["data"]["result"] = text
        rows = runlog.entries(events)
        self.assertEqual(rows[-1]["result"], text)

    def test_failed_observation_is_flagged(self):
        events = stream(1)
        events[1]["data"]["calls"][0]["observation"] = "err boom"
        rows = runlog.entries(events)
        self.assertTrue(rows[0]["failed"])

    def test_running_run_ends_with_a_pending_row(self):
        rows = runlog.entries(stream(1, terminal=False))
        self.assertEqual(rows[-1]["kind"], "pending")
        self.assertEqual([row["kind"] for row in rows].count("call"), 1)

    def test_interrupted_run_ends_with_the_reason(self):
        events = [support.event(support.RUN_ID, 1, "run_start", dict(support.RUN_START)),
                  support.event(support.RUN_ID, 2, "interrupted", dict(support.INTERRUPTED))]
        rows = runlog.entries(events)
        self.assertEqual(rows[-1], {"kind": "interrupted", "reason": "server_stop"})

    def test_load_reads_record_bytes(self):
        with support.sandbox():
            support.write_record(support.RUN_ID, stream(1))
            out = runlog.load(support.RUN_ID)
        self.assertEqual(out["state"], "complete")
        self.assertTrue(out["terminal"])
        self.assertEqual([row["kind"] for row in out["entries"]], ["call", "result"])

    def test_load_reports_a_missing_record_as_empty(self):
        with support.sandbox():
            out = runlog.load(support.RUN_ID)
        self.assertEqual(out["state"], "empty")
        self.assertEqual(out["entries"][-1]["kind"], "pending")


class LogRowsTest(unittest.TestCase):
    def test_every_log_entry_is_one_line(self):
        for entry in data(3)["entries"]:
            text = join_parts(log_parts(entry))
            self.assertNotIn("\n", text)
        call = {"kind": "call", "turn": 2, "name": "exec",
                "args": "a\nb\tc", "obs": "x\ny", "failed": False}
        text = join_parts(log_parts(call))
        self.assertNotIn("\n", text)
        self.assertNotIn("\t", text)
        self.assertIn("t2", text)
        self.assertIn("exec", text)
        self.assertIn("\u2192", text)

    def test_result_row_carries_the_glyph_and_summary(self):
        text = join_parts(log_parts(data(0)["entries"][0]))
        self.assertTrue(text.startswith("\u2713"))
        self.assertIn("result", text)
        self.assertIn("finished", text)


class LogBlockTest(unittest.TestCase):
    def test_rows_fit_their_cells(self):
        for width in (1, 5, 20, 80):
            screen = Screen()
            info = log_block(screen, data(20), 0, 8, width, 9, sel=19)
            self.assertEqual(info["sel"], 19)
            for row in screen.rows.values():
                self.assertLessEqual(swidth(row), width)

    def test_visible_rows_follow_the_available_height(self):
        short = Screen()
        info = log_block(short, data(20), 0, 8, 60, 9)
        self.assertEqual(info["vis"], 7)
        self.assertEqual(len(short.rows), 8)
        tall = Screen()
        info = log_block(tall, data(20), 0, 40, 60, 41)
        self.assertEqual(info["vis"], 39)
        self.assertEqual(len(tall.rows), 22)
        self.assertIn("finished", tall.rows[max(tall.rows)])

    def test_selection_scrolls_into_view(self):
        screen = Screen()
        info = log_block(screen, data(20), 0, 8, 60, 9, sel=19, scroll=0)
        self.assertEqual(info["scroll"], 13)
        self.assertIn("14\u201320/21", screen.rows[0])
        marked = [row for row in screen.rows.values() if row.startswith("\u203a")]
        self.assertEqual(len(marked), 1)
        self.assertIn("t1 exec", marked[0])

    def test_empty_log_still_draws_a_header(self):
        screen = Screen()
        info = log_block(screen, {"id": "run", "state": "empty", "entries": []},
                         0, 6, 60, 7)
        self.assertEqual(info["n"], 0)
        self.assertIn("logs:", screen.rows[0])




class RenderLogTest(unittest.TestCase):
    def test_draw_replaces_the_task_body_with_the_log(self):
        from unittest import mock
        from tui import render
        from tui.prompt import Prompt

        snap = {"daemon": {"state": "running", "detail": "", "pid": 1},
                "notice": "", "notice_at": 0, "current": None, "queue": [],
                "done": []}
        log = {"id": "run", "data": data(2), "sel": 0, "scroll": 0}
        screen = Screen()
        with mock.patch.object(render.curses, "doupdate", lambda: None), \
             mock.patch.object(render.curses, "curs_set", lambda n: None):
            lay = render.draw(screen, snap, Prompt(), 60, 10, "log", 0, 0, 0, log)
        text = "\n".join(screen.rows[y] for y in sorted(screen.rows))
        self.assertIn("logs:", text)
        self.assertIn("result", text)
        self.assertIn("finished", text)
        self.assertIn("esc back", text)
        self.assertNotIn("running:", text)
        self.assertEqual(lay["log"]["n"], 3)

if __name__ == "__main__":
    unittest.main()
