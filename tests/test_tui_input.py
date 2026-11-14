import unittest

from tui import input, keys
from tui.prompt import Prompt


class FakeWorker:
    def __init__(self):
        self.moves = []
        self.drops = []

    def move(self, item_id, delta):
        self.moves.append((item_id, delta))

    def drop(self, item_id):
        self.drops.append(item_id)


class FakeApp:
    def __init__(self, queue):
        self.queue = queue
        self.prompt = Prompt()
        self.worker = FakeWorker()
        self.focus = "task"
        self.qsel = 0
        self.tsel = 0
        self.tscroll = 0
        self.tview = {"n": 3, "vis": 3, "sel": 0, "scroll": 0}
        self.layout = {"height": 10}
        self.quit = False
        self.dirty = False

    def snapshot(self):
        return {"queue": self.queue, "current": None}

    def content_width(self):
        return 80

    def say(self, text):
        pass


def item(item_id, state="queued", text="task"):
    return {"id": item_id, "state": state, "text": text}


class ArrowFocusTest(unittest.TestCase):
    def test_left_right_toggle_between_task_and_queue(self):
        app = FakeApp([item("a")])
        input.handle(app, ("key", "right"))
        self.assertEqual(app.focus, "queue")
        input.handle(app, ("key", "left"))
        self.assertEqual(app.focus, "task")

    def test_right_keeps_task_focus_when_queue_is_empty(self):
        app = FakeApp([])
        input.handle(app, ("key", "right"))
        self.assertEqual(app.focus, "task")

    def test_up_down_selection_uses_arrows(self):
        app = FakeApp([item("a"), item("b")])
        app.focus = "queue"
        input.handle(app, ("key", "down"))
        self.assertEqual(app.qsel, 1)
        input.handle(app, ("key", "up"))
        self.assertEqual(app.qsel, 0)


class TaskHistoryTest(unittest.TestCase):
    def test_task_arrows_walk_from_running_into_done_rows(self):
        app = FakeApp([])
        app.tview = {"n": 4, "vis": 3, "sel": 0, "scroll": 0}
        for want in (1, 2, 3):
            input.handle(app, ("key", "down"))
            self.assertEqual(app.tsel, want)
        input.handle(app, ("key", "down"))
        self.assertEqual(app.tsel, 3)
        input.handle(app, ("key", "up"))
        self.assertEqual(app.tsel, 2)
        input.handle(app, ("key", "home"))
        self.assertEqual(app.tsel, 0)
        input.handle(app, ("key", "end"))
        self.assertEqual(app.tsel, 3)

    def test_task_paging_uses_the_visible_row_count(self):
        app = FakeApp([])
        app.tview = {"n": 9, "vis": 3, "sel": 0, "scroll": 0}
        input.handle(app, ("key", "page_down"))
        self.assertEqual(app.tsel, 3)
        input.handle(app, ("key", "page_up"))
        self.assertEqual(app.tsel, 0)


class QueueArrowTest(unittest.TestCase):
    def test_shift_arrows_reorder_the_selected_item(self):
        app = FakeApp([item("a"), item("b")])
        app.focus = "queue"
        app.qsel = 1
        input.handle(app, ("key", "shift_up"))
        self.assertEqual(app.worker.moves, [("b", -1)])
        self.assertEqual(app.qsel, 0)
        app.qsel = 0
        input.handle(app, ("key", "shift_down"))
        self.assertEqual(app.worker.moves[-1], ("a", 1))
        self.assertEqual(app.qsel, 1)

    def test_delete_drops_the_selected_item(self):
        app = FakeApp([item("a"), item("b")])
        app.focus = "queue"
        app.qsel = 1
        input.handle(app, ("key", "delete"))
        self.assertEqual(app.worker.drops, ["b"])

    def test_text_opens_prompt_instead_of_vi_keys(self):
        app = FakeApp([item("a"), item("b")])
        app.focus = "queue"
        app.qsel = 1
        input.handle(app, ("text", "jjj"))
        self.assertEqual(app.prompt.text, "jjj")
        self.assertEqual(app.focus, "prompt")
        self.assertEqual(app.qsel, 1)
        self.assertEqual(app.worker.moves, [])


class ShiftArrowParserTest(unittest.TestCase):
    def test_shift_arrows_are_distinct_from_plain_arrows(self):
        parser = keys.Parser()
        parser.feed(b"\x1b[1;2A\x1b[1;2B\x1b[A\x1b[B")
        self.assertEqual(parser.events(), [("key", "shift_up"),
                                           ("key", "shift_down"),
                                           ("key", "up"), ("key", "down")])


if __name__ == "__main__":
    unittest.main()
