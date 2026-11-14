import unittest

from tui import loginput


class FakeWorker:
    def __init__(self, data):
        self.data = data
        self.calls = 0

    def log(self, run_id):
        self.calls += 1
        return self.data


class FakeApp:
    def __init__(self, data, live=True):
        self.current = {"id": "run"} if live else None
        self.done = [] if live else [{"id": "run"}]
        self.worker = FakeWorker(data)
        self.focus = "task"
        self.tsel = 0 if live else 1
        self.log = None
        self.dirty = False

    def snapshot(self):
        return {"current": self.current, "queue": [], "done": self.done}

    def say(self, text):
        pass


def data(calls, terminal=False):
    entries = [{"kind": "call", "turn": k, "name": "exec", "args": "",
                "obs": "", "failed": False} for k in range(calls)]
    entries.append({"kind": "pending", "text": "summary pending"})
    return {"id": "run", "state": "complete" if terminal else "running",
            "terminal": terminal, "entries": entries}


class LiveTailTest(unittest.TestCase):
    def test_a_live_log_opens_on_its_newest_entry(self):
        app = FakeApp(data(3))
        loginput.open_log(app)
        self.assertTrue(app.log["tail"])
        self.assertEqual(app.log["sel"], 3)
        self.assertEqual(app.log["data"]["entries"][-1]["kind"], "pending")

    def test_refresh_moves_the_selection_with_the_record(self):
        app = FakeApp(data(3))
        loginput.open_log(app)
        app.worker.data = data(6)
        app.log["at"] = 0.0
        loginput.refresh_log(app, 10.0)
        self.assertEqual(app.log["sel"], 6)
        self.assertTrue(app.dirty)

    def test_navigation_pauses_the_tail_and_end_resumes_it(self):
        app = FakeApp(data(6))
        loginput.open_log(app)
        loginput.log_key(app, "home")
        self.assertEqual(app.log["sel"], 0)
        self.assertFalse(app.log["tail"])
        app.worker.data = data(9)
        app.log["at"] = 0.0
        loginput.refresh_log(app, 10.0)
        self.assertEqual(app.log["sel"], 0)
        loginput.log_key(app, "end")
        self.assertTrue(app.log["tail"])
        self.assertEqual(app.log["sel"], 9)

    def test_wheel_pauses_the_tail(self):
        app = FakeApp(data(6))
        loginput.open_log(app)
        app.log["vis"] = 3
        loginput.log_key(app, "scroll_up")
        self.assertFalse(app.log["tail"])
        self.assertFalse(app.log["follow"])

    def test_a_finished_log_opens_at_the_top_without_following(self):
        app = FakeApp(data(5, terminal=True), live=False)
        loginput.open_log(app)
        self.assertEqual(app.log["sel"], 0)
        self.assertFalse(app.log["tail"])

    def test_unchanged_refresh_does_not_dirty_the_frame(self):
        app = FakeApp(data(3))
        loginput.open_log(app)
        app.dirty = False
        app.log["at"] = 0.0
        loginput.refresh_log(app, 10.0)
        self.assertFalse(app.dirty)


if __name__ == "__main__":
    unittest.main()
