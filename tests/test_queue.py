import os
import unittest

from harness import queue
from tests.support import sandbox


class QueueTest(unittest.TestCase):
    def test_empty_snapshot(self):
        with sandbox():
            snap = queue.snapshot()
            self.assertEqual(snap, {"seq": 0, "current": None, "items": []})
            self.assertEqual(queue.waiting(), [])
            self.assertIsNone(queue.current())

    def test_add_front_and_back(self):
        with sandbox():
            first = queue.add("a", "/root", {"LOOP_MODEL": "m"})
            second = queue.add("b", "/root", {})
            front = queue.add("c", "/root", {}, front=True)
            self.assertEqual(first["id"], "q000001")
            self.assertEqual(second["id"], "q000002")
            self.assertEqual(front["id"], "q000003")
            self.assertEqual([x["task"] for x in queue.waiting()], ["c", "a", "b"])
            self.assertEqual(queue.snapshot()["seq"], 3)

    def test_promote_update_finish(self):
        with sandbox():
            item = queue.add("a", "/root", {})
            promoted = queue.promote()
            self.assertEqual(promoted["run_id"], item["run_id"])
            self.assertEqual(promoted["state"], "running")
            self.assertEqual(queue.current()["task"], "a")
            self.assertEqual(queue.waiting(), [])
            queue.update(item["id"], turns=2, cost=0.25)
            self.assertEqual(queue.current()["turns"], 2)
            done = queue.finish("done", exit=0)
            self.assertEqual(done["state"], "done")
            self.assertEqual(done["exit"], 0)
            self.assertIsNone(queue.current())
            self.assertIsNone(queue.promote())

    def test_drop_and_move(self):
        with sandbox():
            a = queue.add("a", "/root", {})
            b = queue.add("b", "/root", {})
            self.assertTrue(queue.move(a["id"], 1))
            self.assertFalse(queue.move(a["id"], 1))
            self.assertEqual([x["task"] for x in queue.waiting()], ["b", "a"])
            self.assertTrue(queue.drop(b["id"]))
            self.assertFalse(queue.drop(b["id"]))
            self.assertEqual([x["task"] for x in queue.waiting()], ["a"])

    def test_set_current_removes_from_waiting(self):
        with sandbox():
            a = queue.add("a", "/root", {})
            queue.set_current(a)
            self.assertEqual(queue.current()["id"], a["id"])
            self.assertEqual(queue.waiting(), [])

    def test_corrupt_queue_file_resets(self):
        with sandbox() as tmp:
            os.makedirs(os.path.dirname(queue.path()), exist_ok=True)
            with open(queue.path(), "w", encoding="utf-8") as f:
                f.write("{not json")
            self.assertEqual(queue.snapshot(), {"seq": 0, "current": None, "items": []})
            self.assertTrue(tmp)


if __name__ == "__main__":
    unittest.main()
