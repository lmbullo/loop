import os
import unittest

from harness import regprobe, workers
from tests.support import RUN_ID, minimal_events, sandbox, write_record


def live_entry(run_id=RUN_ID):
    return {"run_id": run_id, "pid": os.getpid(),
            "proc_start": regprobe.fingerprint(os.getpid()),
            "state": "running", "task": "t", "seq": 0, "turns": 0}


class WorkersTest(unittest.TestCase):
    def test_write_update_read_find(self):
        with sandbox():
            workers.write(live_entry())
            self.assertEqual(workers.read(RUN_ID)["task"], "t")
            self.assertEqual(workers.find(RUN_ID)["pid"], os.getpid())
            self.assertEqual([e["run_id"] for e in workers.entries()], [RUN_ID])
            workers.update(RUN_ID, turns=3)
            self.assertEqual(workers.read(RUN_ID)["turns"], 3)
            self.assertEqual(workers.read("nope"), None)

    def test_liveness_uses_pid_and_start_fingerprint(self):
        with sandbox():
            good = live_entry()
            self.assertTrue(workers.live(good))
            workers.write(good)
            self.assertEqual(workers.current()["run_id"], RUN_ID)
            self.assertEqual(len(workers.live_entries()), 1)
            bad = dict(good, proc_start="not-the-start")
            self.assertFalse(workers.live(bad))
            self.assertFalse(workers.live(dict(good, pid=0)))
            self.assertFalse(workers.live(dict(good, state="done")))

    def test_reap_removes_dead_entries(self):
        with sandbox():
            workers.write(live_entry())
            workers.update(RUN_ID, state="done")
            self.assertEqual(workers.reap(), [RUN_ID])
            self.assertEqual(workers.entries(), [])

    def test_corrupt_entry_is_ignored(self):
        with sandbox():
            os.makedirs(workers.directory(), exist_ok=True)
            with open(os.path.join(workers.directory(), "bad.json"), "w", encoding="utf-8") as f:
                f.write("{")
            self.assertEqual(workers.entries(), [])

    def test_record_state(self):
        with sandbox():
            self.assertEqual(workers.record_state(RUN_ID), "empty")
            write_record(RUN_ID, minimal_events())
            self.assertEqual(workers.record_state(RUN_ID), "complete")


if __name__ == "__main__":
    unittest.main()
