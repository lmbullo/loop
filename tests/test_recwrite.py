import os
import unittest

from harness import record, recread, recwrite
from tests.support import END, RUN_ID, RUN_START, TURN, event, sandbox, write_record


class RecWriteTest(unittest.TestCase):
    def test_append_and_seal(self):
        with sandbox() as tmp:
            writer = recwrite.Writer(RUN_ID)
            try:
                self.assertEqual(writer.seq, 0)
                writer.append("run_start", dict(RUN_START))
                writer.append("turn", dict(TURN))
                self.assertEqual(writer.seq, 2)
                writer.seal()
                with self.assertRaises(record.Sealed):
                    writer.append("end", dict(END))
            finally:
                writer.close()
            rec = recread.read(RUN_ID)
            self.assertEqual(rec["state"], "interrupted")
            self.assertEqual(rec["seq"], 2)
            self.assertTrue(os.path.isdir(tmp))

    def test_writer_rejects_bad_run_id(self):
        with sandbox():
            with self.assertRaises(ValueError):
                recwrite.Writer("not-a-run")

    def test_second_writer_is_busy(self):
        with sandbox():
            first = recwrite.Writer(RUN_ID)
            try:
                with self.assertRaises(record.Busy):
                    recwrite.Writer(RUN_ID)
            finally:
                first.close()
            second = recwrite.Writer(RUN_ID)
            second.close()

    def test_torn_tail_is_truncated_before_append(self):
        with sandbox():
            path = write_record(RUN_ID, [event(RUN_ID, 1, "run_start", dict(RUN_START))])
            with open(path, "ab") as f:
                f.write(b'{"partial"')
            writer = recwrite.Writer(RUN_ID)
            try:
                self.assertEqual(writer.seq, 1)
                writer.append("end", dict(END))
            finally:
                writer.close()
            rec = recread.read(RUN_ID)
            self.assertEqual(rec["state"], "complete")
            self.assertEqual(rec["torn_tail_bytes"], 0)

    def test_interrupt_is_idempotent_and_marks_state(self):
        with sandbox():
            writer = recwrite.Writer(RUN_ID)
            try:
                writer.append("run_start", dict(RUN_START))
                ev = writer.interrupt("server_stop", "server")
                self.assertEqual(ev["type"], "interrupted")
                self.assertIsNone(writer.interrupt("again", "server"))
            finally:
                writer.close()
            self.assertEqual(recread.read(RUN_ID)["state"], "interrupted")

    def test_tree_lock_is_exclusive(self):
        with sandbox():
            first = recwrite.acquire_tree()
            try:
                with self.assertRaises(record.Busy):
                    recwrite.acquire_tree()
            finally:
                first.release()
            second = recwrite.acquire_tree()
            second.release()

    def test_reconcile_marks_only_unfinished_unlocked_records(self):
        with sandbox():
            write_record(RUN_ID, [event(RUN_ID, 1, "run_start", dict(RUN_START))])
            done_id = "20240102T000000000Z-abcdef02"
            write_record(done_id, [event(done_id, 1, "run_start", dict(RUN_START)),
                                   event(done_id, 2, "end", dict(END))])
            marked = recwrite.reconcile("server_start", "server")
            self.assertEqual(marked, [RUN_ID])
            self.assertEqual(recread.read(RUN_ID)["state"], "interrupted")
            self.assertEqual(recread.read(done_id)["state"], "complete")
            self.assertEqual(recwrite.reconcile("again", "server"), [])

    def test_reconcile_skips_a_record_with_no_events(self):
        with sandbox():
            write_record(RUN_ID, [])
            self.assertEqual(recread.read(RUN_ID)["state"], "empty")
            self.assertEqual(recwrite.reconcile("server_start", "server"), [])
            self.assertEqual(recread.read(RUN_ID)["state"], "empty")

    def test_sync_dir_does_not_raise(self):
        with sandbox() as tmp:
            recwrite.sync_dir(tmp)
            recwrite.sync_dir(os.path.join(tmp, "missing"))


if __name__ == "__main__":
    unittest.main()
