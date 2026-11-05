import os
import unittest

from harness import record
from tests.support import RUN_ID, minimal_events, sandbox, write_record


class RecordTest(unittest.TestCase):
    def test_run_id_pattern_and_uniqueness(self):
        ids = {record.new_id() for _ in range(20)}
        self.assertEqual(len(ids), 20)
        for run_id in ids:
            self.assertRegex(run_id, record.ID_RE)

    def test_utc_is_fixed_width(self):
        self.assertEqual(record.utc(0), "1970-01-01T00:00:00.000Z")
        self.assertEqual(record.utc(1.234), "1970-01-01T00:00:01.234Z")

    def test_canonical_is_sorted_and_compact(self):
        self.assertEqual(record.canonical({"b": 1, "a": [2]}), '{"a":[2],"b":1}')

    def test_paths(self):
        with sandbox() as tmp:
            self.assertEqual(record.runs_dir(), os.path.join(tmp, "logs", "runs"))
            self.assertEqual(record.run_dir(RUN_ID), os.path.join(tmp, "logs", "runs", RUN_ID))
            self.assertEqual(record.record_path(RUN_ID),
                             os.path.join(record.run_dir(RUN_ID), "record.jsonl"))
            self.assertEqual(record.obs_dir(RUN_ID), os.path.join(record.run_dir(RUN_ID), "obs"))
            self.assertEqual(record.lock_path(RUN_ID),
                             os.path.join(record.run_dir(RUN_ID), "record.lock"))

    def test_ids_and_resolve_newest(self):
        with sandbox():
            other = "20240102T000000000Z-abcdef02"
            write_record(RUN_ID, minimal_events(RUN_ID))
            write_record(other, minimal_events(other))
            self.assertEqual(record.ids(), [RUN_ID, other])
            self.assertEqual(record.resolve(), other)
            self.assertEqual(record.resolve(RUN_ID), RUN_ID)

    def test_resolve_errors(self):
        with sandbox():
            with self.assertRaises(record.Missing):
                record.resolve()
            with self.assertRaises(record.Missing):
                record.resolve("20240101T000000000Z-00000000")

    def test_ids_ignores_non_matching_and_broken_records(self):
        with sandbox():
            write_record(RUN_ID, minimal_events(RUN_ID))
            os.makedirs(record.run_dir("not-a-run"))
            self.assertEqual(record.ids(), [RUN_ID])
            os.unlink(record.record_path(RUN_ID))
            self.assertEqual(record.ids(), [])


if __name__ == "__main__":
    unittest.main()
