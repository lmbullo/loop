import unittest

from tests.test_tui_input import FakeApp, item
from tui import input


class CancelKeyTest(unittest.TestCase):
    def test_ctrl_x_cancels_the_selected_running_row(self):
        app = FakeApp([], current=item("r1", state="running"))
        input.handle(app, ("key", "ctrl_x"))
        self.assertEqual(app.worker.cancels, [("r1", None)])

    def test_ctrl_x_cancels_the_selected_queued_row(self):
        app = FakeApp([item("q1"), item("q2")], done=[{"id": "d1"}])
        app.tview = {"n": 4, "vis": 4, "sel": 0, "scroll": 0}
        app.tsel = 2
        input.handle(app, ("key", "ctrl_x"))
        self.assertEqual(app.worker.cancels, [("q2", None)])

    def test_ctrl_x_on_a_done_row_does_nothing(self):
        app = FakeApp([], done=[{"id": "d1"}])
        app.tsel = 1
        input.handle(app, ("key", "ctrl_x"))
        self.assertEqual(app.worker.cancels, [])
        self.assertIn("finished", app.said[0])

    def test_ctrl_x_in_queue_focus_cancels_the_queue_selection(self):
        app = FakeApp([item("q1"), item("q2")])
        app.focus = "queue"
        app.qsel = 1
        input.handle(app, ("key", "ctrl_x"))
        self.assertEqual(app.worker.cancels, [("q2", None)])

    def test_ctrl_x_while_typing_does_not_cancel_a_task(self):
        app = FakeApp([], current=item("r1", state="running"))
        app.focus = "prompt"
        input.handle(app, ("key", "ctrl_x"))
        self.assertEqual(app.worker.cancels, [])


class CancelModuleTest(unittest.TestCase):
    def test_cancel_task_signals_the_running_id(self):
        from tui import cancel
        app = FakeApp([], current=item("r1", state="running"))
        cancel.cancel_task(app)
        self.assertEqual(app.worker.cancels, [("r1", None)])

    def test_cancel_running_without_a_current_says_nothing_to_cancel(self):
        from tui import cancel
        app = FakeApp([])
        cancel.cancel_running(app)
        self.assertEqual(app.worker.cancels, [])
        self.assertIn("nothing to cancel", app.said[0])

    def test_cancel_queue_clamps_the_selection(self):
        from tui import cancel
        app = FakeApp([item("q1")])
        app.qsel = 9
        cancel.cancel_queue(app)
        self.assertEqual(app.qsel, 0)
        self.assertEqual(app.worker.cancels, [("q1", None)])


if __name__ == "__main__":
    unittest.main()
