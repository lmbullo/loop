import json
import os
import unittest

from harness import record, recread
from tests.support import (END, RUN_ID, RUN_START, TURN, event, minimal_events,
                           sandbox, write_record)


class RecReadTest(unittest.TestCase):
    def test_empty_record(self):
        with sandbox():
            events, torn = recread.read_raw(record.record_path(RUN_ID), RUN_ID)
            self.assertEqual((events, torn), ([], 0))
            self.assertEqual(recread.state([]), "empty")

    def test_complete_record(self):
        with sandbox():
            write_record(RUN_ID, minimal_events())
            rec = recread.read(RUN_ID)
            self.assertEqual(rec["state"], "complete")
            self.assertEqual(rec["seq"], 2)
            self.assertEqual(recread.turns(rec["events"]), 0)
            self.assertEqual(recread.state(rec["events"]), "complete")

    def test_interrupted_record(self):
        with sandbox():
            events = [event(RUN_ID, 1, "run_start", dict(RUN_START)),
                      event(RUN_ID, 2, "turn", dict(TURN))]
            write_record(RUN_ID, events)
            rec = recread.read(RUN_ID)
            self.assertEqual(rec["state"], "interrupted")
            self.assertEqual(recread.turns(rec["events"]), 1)

    def test_torn_tail_is_reported(self):
        with sandbox():
            path = write_record(RUN_ID, minimal_events())
            with open(path, "ab") as f:
                f.write(b'{"schema":"loop-record/1"')
            events, torn = recread.read_raw(path, RUN_ID)
            self.assertEqual(len(events), 2)
            self.assertGreater(torn, 0)
            self.assertEqual(recread.read(RUN_ID)["torn_tail_bytes"], torn)

    def test_blank_line_is_corrupt(self):
        with sandbox():
            path = write_record(RUN_ID, minimal_events())
            with open(path, "ab") as f:
                f.write(b"\n")
            with self.assertRaises(record.Corrupt):
                recread.read(RUN_ID)

    def test_bad_json_is_corrupt(self):
        with sandbox():
            path = write_record(RUN_ID, minimal_events())
            with open(path, "ab") as f:
                f.write(b"{not json}\n")
            with self.assertRaises(record.Corrupt):
                recread.read(RUN_ID)

    def test_schema_violation_is_corrupt(self):
        with sandbox():
            path = record.record_path(RUN_ID)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            bad = {"schema": "loop-record/1", "v": 1, "run_id": RUN_ID, "seq": 1,
                   "ts": "x", "type": "end", "data": {"exit": 0}}
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(bad) + "\n")
            with self.assertRaises(record.Corrupt):
                recread.read(RUN_ID)

    def test_summary_row(self):
        with sandbox():
            write_record(RUN_ID, minimal_events())
            row = recread.summary_row(recread.read(RUN_ID))
            self.assertEqual(row["run_id"], RUN_ID)
            self.assertEqual(row["state"], "complete")
            self.assertEqual(row["entrypoint"], "api")
            self.assertEqual(row["task"], RUN_START["task"])
            self.assertEqual(row["finish"], END["finish"])
            self.assertEqual(row["cost"], END["cost"])

    def test_scan_keeps_corrupt_rows(self):
        with sandbox():
            write_record(RUN_ID, minimal_events())
            bad_id = "20240102T000000000Z-abcdef02"
            path = record.record_path(bad_id)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("not json\n")
            rows = {row["run_id"]: row for row in recread.scan()}
            self.assertEqual(rows[RUN_ID]["state"], "complete")
            self.assertEqual(rows[bad_id]["state"], "corrupt")
            self.assertIn("detail", rows[bad_id])


if __name__ == "__main__":
    unittest.main()
