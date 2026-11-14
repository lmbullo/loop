import unittest
from unittest import mock

from harness import srvconn


LIVE = [{"run_id": "r1", "pid": 123, "task": "one"}]


class CancelCommandTest(unittest.TestCase):
    def test_cancel_drops_a_waiting_item(self):
        with mock.patch.object(srvconn.queue, "drop", return_value=True) as drop, \
             mock.patch.object(srvconn.workers, "live_entries") as live:
            reply = srvconn._cancel({"id": "q000001"})
        drop.assert_called_once_with("q000001")
        live.assert_not_called()
        self.assertEqual(reply, {"k": "cancelled", "kind": "queued",
                                 "id": "q000001", "changed": True})

    def test_cancel_signals_the_matching_live_run(self):
        with mock.patch.object(srvconn.queue, "drop", return_value=False), \
             mock.patch.object(srvconn.workers, "live_entries",
                               return_value=LIVE), \
             mock.patch.object(srvconn, "_interrupt") as interrupt:
            reply = srvconn._cancel({"run_id": "r1"})
        interrupt.assert_called_once_with(LIVE)
        self.assertEqual(reply, {"k": "cancelled", "kind": "running",
                                 "run_id": "r1", "pid": 123, "changed": True})

    def test_cancel_uses_the_id_as_a_run_id_fallback(self):
        with mock.patch.object(srvconn.queue, "drop", return_value=False), \
             mock.patch.object(srvconn, "_run_for_item", return_value=None), \
             mock.patch.object(srvconn.workers, "live_entries",
                               return_value=LIVE), \
             mock.patch.object(srvconn, "_interrupt"):
            reply = srvconn._cancel({"id": "r1"})
        self.assertEqual(reply["kind"], "running")
        self.assertTrue(reply["changed"])

    def test_cancel_resolves_a_promoted_item_id_to_its_run(self):
        with mock.patch.object(srvconn.queue, "drop", return_value=False), \
             mock.patch.object(srvconn, "_run_for_item", return_value="r1"), \
             mock.patch.object(srvconn.workers, "live_entries",
                               return_value=LIVE), \
             mock.patch.object(srvconn, "_interrupt") as interrupt:
            reply = srvconn._cancel({"id": "q000001"})
        interrupt.assert_called_once_with(LIVE)
        self.assertEqual(reply["run_id"], "r1")
        self.assertEqual(reply["kind"], "running")

    def test_cancel_reports_no_change_for_an_unknown_task(self):
        with mock.patch.object(srvconn.queue, "drop", return_value=False), \
             mock.patch.object(srvconn, "_run_for_item", return_value=None), \
             mock.patch.object(srvconn.workers, "live_entries", return_value=[]):
            reply = srvconn._cancel({"id": "missing"})
        self.assertEqual(reply["changed"], False)
        self.assertIsNone(reply["kind"])


if __name__ == "__main__":
    unittest.main()
