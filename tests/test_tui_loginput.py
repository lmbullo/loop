import unittest

from tui import input, loginput
from tui.logview import log_block
from tui.prompt import Prompt


class FakeWorker:
    def __init__(self):
        self.calls = []
        self.enqueued = []
        self.result = {"id": "run", "state": "complete", "terminal": True,
                       "entries": [{"kind": "result", "result": "ok",
                                    "finish": "done"}]}

    def log(self, run_id):
        self.calls.append(run_id)
        return self.result

    def enqueue(self, text):
        self.enqueued.append(text)


class FakeApp:
    def __init__(self, current=None, done=(), queue=()):
        self.current = current
        self.done = list(done)
        self.queue = list(queue)
        self.prompt = Prompt()
        self.worker = FakeWorker()
        self.focus = "task"
        self.tsel = 0
        self.qsel = 0
        self.tview = {"n": 1, "vis": 1, "sel": 0, "scroll": 0}
        self.log = None
        self.dirty = False
        self.said = []

    def snapshot(self):
        return {"current": self.current, "done": self.done, "queue": self.queue}

    def say(self, text):
        self.said.append(text)


class LogInputTest(unittest.TestCase):
    def test_enter_opens_the_selected_run_and_enter_closes_it(self):
        app = FakeApp(current={"id": "live"})
        input.handle(app, ("key", "enter"))
        self.assertEqual(app.focus, "log")
        self.assertEqual(app.log["id"], "live")
        self.assertEqual(app.worker.calls, ["live"])
        input.handle(app, ("key", "enter"))
        self.assertEqual(app.focus, "task")
        self.assertIsNone(app.log)

    def test_enter_on_a_done_row_opens_that_run(self):
        app = FakeApp(done=[{"id": "old"}, {"id": "older"}])
        app.tsel = 2
        input.handle(app, ("key", "enter"))
        self.assertEqual(app.log["id"], "older")

    def test_enter_accounts_for_queued_rows_before_done(self):
        app = FakeApp(done=[{"id": "old"}, {"id": "older"}],
                      queue=[{"id": "q1"}])
        app.tsel = 3
        input.handle(app, ("key", "enter"))
        self.assertEqual(app.log["id"], "older")

    def test_enter_with_no_run_opens_the_prompt(self):
        app = FakeApp()
        input.handle(app, ("key", "enter"))
        self.assertEqual(app.focus, "prompt")
        self.assertIsNone(app.log)
        self.assertEqual(app.said, [])

    def test_escape_closes_the_log(self):
        app = FakeApp(current={"id": "run"})
        loginput.open_log(app)
        input.handle(app, ("key", "esc"))
        self.assertEqual(app.focus, "task")
        self.assertIsNone(app.log)

    def test_arrows_move_the_log_selection(self):
        app = FakeApp(current={"id": "run"})
        loginput.open_log(app)
        app.log["data"] = {"entries": [{"kind": "pending", "text": str(k)}
                                       for k in range(6)]}
        app.log["vis"] = 2
        input.handle(app, ("key", "down"))
        self.assertEqual(app.log["sel"], 1)
        input.handle(app, ("key", "page_down"))
        self.assertEqual(app.log["sel"], 3)
        input.handle(app, ("key", "end"))
        self.assertEqual(app.log["sel"], 5)
        input.handle(app, ("key", "home"))
        self.assertEqual(app.log["sel"], 0)

    def test_typing_opens_the_prompt_over_the_log(self):
        app = FakeApp(current={"id": "run"})
        loginput.open_log(app)
        input.handle(app, ("text", "hello"))
        self.assertEqual(app.focus, "prompt")
        self.assertEqual(app.log["id"], "run")
        self.assertEqual(app.prompt.text, "hello")
        input.handle(app, ("text", "!"))
        self.assertIsNotNone(app.log)
        self.assertEqual(app.prompt.text, "hello!")
        input.handle(app, ("key", "esc"))
        self.assertEqual(app.focus, "log")
        self.assertEqual(app.log["id"], "run")

    def test_submit_from_the_log_queues_and_focuses_the_tasks(self):
        app = FakeApp(current={"id": "run"})
        loginput.open_log(app)
        input.handle(app, ("text", "hello"))
        input.handle(app, ("key", "enter"))
        self.assertEqual(app.worker.enqueued, ["hello"])
        self.assertEqual(app.focus, "task")
        self.assertIsNotNone(app.log)

    def test_tab_opens_and_closes_the_prompt_from_the_log(self):
        app = FakeApp(current={"id": "run"})
        loginput.open_log(app)
        input.handle(app, ("key", "tab"))
        self.assertEqual(app.focus, "prompt")
        self.assertEqual(app.log["id"], "run")
        input.handle(app, ("key", "tab"))
        self.assertEqual(app.focus, "log")
        self.assertEqual(app.log["id"], "run")

    def test_tab_opens_the_prompt_from_the_queue_and_returns(self):
        app = FakeApp(queue=[{"id": "q1", "state": "queued", "text": "later"}])
        app.focus = "queue"
        input.handle(app, ("key", "tab"))
        self.assertEqual(app.focus, "prompt")
        input.handle(app, ("key", "esc"))
        self.assertEqual(app.focus, "queue")

    def test_wheel_scrolls_the_log_without_moving_the_selection(self):
        app = FakeApp(current={"id": "run"})
        loginput.open_log(app)
        app.log["data"] = {"entries": [{"kind": "pending", "text": str(k)}
                                       for k in range(20)]}
        app.log["vis"] = 5
        input.handle(app, ("key", "scroll_down"))
        self.assertEqual((app.log["sel"], app.log["scroll"]), (0, 1))
        self.assertFalse(app.log["follow"])
        input.handle(app, ("key", "scroll_down"))
        self.assertEqual((app.log["sel"], app.log["scroll"]), (0, 2))
        input.handle(app, ("key", "scroll_up"))
        self.assertEqual((app.log["sel"], app.log["scroll"]), (0, 1))
        input.handle(app, ("key", "down"))
        self.assertEqual((app.log["sel"], app.log["follow"]), (1, True))

    def test_free_scroll_keeps_the_offset_without_a_visible_selection(self):
        class Screen:
            def __init__(self):
                self.rows = {}

            def addstr(self, y, x, text, at=0):
                self.rows[y] = self.rows.get(y, "") + text

        entries = [{"kind": "call", "turn": k, "name": "exec", "args": "x",
                    "obs": "", "failed": False} for k in range(20)]
        entries.append({"kind": "result", "result": "ok", "finish": "done"})
        screen = Screen()
        info = log_block(screen, {"id": "run", "entries": entries}, 0, 8, 60,
                         9, sel=0, scroll=5, follow=False)
        self.assertEqual((info["sel"], info["scroll"], info["follow"]),
                         (0, 5, False))
        self.assertIn("6\u201312/21", screen.rows[0])
        self.assertEqual([row for row in screen.rows.values()
                          if row.startswith("\u203a")], [])

    def test_live_run_is_labelled_running(self):
        app = FakeApp(current={"id": "run"})
        app.worker.result = dict(app.worker.result, state="interrupted",
                                 terminal=False)
        loginput.open_log(app)
        self.assertTrue(app.log["live"])
        self.assertEqual(app.log["data"]["state"], "running")

    def test_refresh_skips_terminal_runs(self):
        app = FakeApp(current={"id": "run"})
        loginput.open_log(app)
        app.log["at"] = 0.0
        app.log["data"] = {"entries": [], "terminal": False}
        loginput.refresh_log(app, 10.0)
        self.assertEqual(app.worker.calls, ["run", "run"])
        loginput.refresh_log(app, 20.0)
        self.assertEqual(app.worker.calls, ["run", "run"])


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
