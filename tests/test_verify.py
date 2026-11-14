import io
import json
import os
import tempfile
import unittest
import unittest.mock

from harness import agent, fold, recwrite, verifier, view
from tests.support import RUN_ID, RUN_START, TURN, event, read_events, sandbox


def verify_event(seq, command, ran=False, exit_code=None, note=None):
    return event(RUN_ID, seq, "verify", {"command": command, "ran": ran,
                                        "exit": exit_code, "note": note})


def turn_done(seq=2):
    data = json.loads(json.dumps(TURN))
    data["turn"] = seq
    data["done"] = {"id": "c9", "result": "r"}
    return event(RUN_ID, seq, "turn", data)


class FoldVerifyTest(unittest.TestCase):
    def test_pending_none(self):
        self.assertIsNone(fold.pending_verify([]))
        self.assertIsNone(fold.pending_verify([event(RUN_ID, 1, "run_start", dict(RUN_START))]))

    def test_declaration_then_clear(self):
        declared = verify_event(2, "make test")
        self.assertEqual(fold.pending_verify([declared]), "make test")
        self.assertIsNone(fold.pending_verify(
            [declared, verify_event(3, "make test", True, 0, "ok")]))

    def test_last_declaration_wins(self):
        events = [verify_event(2, "a"), verify_event(3, "b")]
        self.assertEqual(fold.pending_verify(events), "b")


class VerifierTest(unittest.TestCase):
    def test_exit_and_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, note = verifier.run(tmp, "printf 'ok\\n'")
            self.assertEqual(code, 0)
            self.assertTrue(note.startswith("ok ms="), note)
            code, note = verifier.run(tmp, "exit 7")
            self.assertEqual(code, 7)
            self.assertTrue(note.startswith("no output ms="), note)

    def test_runs_at_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, note = verifier.run(tmp, "pwd")
            self.assertEqual(code, 0)
            self.assertEqual(note.split(" ms=")[0], os.path.realpath(tmp))

    def test_timeout_is_not_a_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, note = verifier.run(tmp, "kill -9 $$")
            self.assertNotEqual(code, 0)
            self.assertIn("ms=", note)


class SettleTest(unittest.TestCase):
    def test_appends_verify_before_end(self):
        with sandbox(), tempfile.TemporaryDirectory() as tmp:
            writer = recwrite.Writer(RUN_ID)
            try:
                start = writer.append("run_start", dict(RUN_START))
                summary = agent.settle(writer, lambda ev: ev, [start], 0,
                                       "exit 0", tmp, "done", "r", 0)
            finally:
                writer.close()
            events = read_events(RUN_ID)
            self.assertEqual([e["type"] for e in events][-2:], ["verify", "end"])
            self.assertTrue(events[-2]["data"]["ran"])
            self.assertEqual(events[-2]["data"]["exit"], 0)
            self.assertEqual(summary["finish"], "done")

    def test_no_command_no_event(self):
        with sandbox():
            writer = recwrite.Writer(RUN_ID)
            try:
                start = writer.append("run_start", dict(RUN_START))
                agent.settle(writer, lambda ev: ev, [start], 0, None, None, "done", "r", 0)
            finally:
                writer.close()
            self.assertEqual([e["type"] for e in read_events(RUN_ID)], ["run_start", "end"])


class RunTaskVerifyTest(unittest.TestCase):
    def test_declares_then_runs(self):
        with sandbox(), tempfile.TemporaryDirectory() as tmp:
            writer = recwrite.Writer(RUN_ID)
            try:
                writer.append("run_start", dict(RUN_START))
                writer.append("turn", turn_done()["data"])
                agent.run_task(writer, lambda ev: ev, task="t", root=tmp, verify="exit 0")
            finally:
                writer.close()
            events = read_events(RUN_ID)
            self.assertEqual([e["type"] for e in events][-3:], ["verify", "verify", "end"])
            self.assertFalse(events[-3]["data"]["ran"])
            self.assertTrue(events[-2]["data"]["ran"])

    def test_resume_uses_recorded_command(self):
        with sandbox(), tempfile.TemporaryDirectory() as tmp:
            writer = recwrite.Writer(RUN_ID)
            try:
                writer.append("run_start", dict(RUN_START))
                writer.append("verify", {"command": "exit 0", "ran": False,
                                         "exit": None, "note": None})
                writer.append("turn", turn_done(3)["data"])
                agent.run_task(writer, lambda ev: ev, task="t", root=tmp, verify="exit 9")
            finally:
                writer.close()
            events = read_events(RUN_ID)
            self.assertEqual([e["type"] for e in events][-2:], ["verify", "end"])
            self.assertEqual(events[-2]["data"]["command"], "exit 0")
            self.assertEqual(events[-2]["data"]["exit"], 0)


class MainArgTest(unittest.TestCase):
    def test_verify_before_task(self):
        with unittest.mock.patch("harness.srvclient.run_local", return_value=7) as run:
            self.assertEqual(agent.main(["--verify", "make test", "task"]), 7)
            run.assert_called_once_with("task", False, "make test")

    def test_missing_value(self):
        with unittest.mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.assertEqual(agent.main(["--verify"]), 2)
        self.assertIn("--verify", err.getvalue())


class ViewVerifyTest(unittest.TestCase):
    def test_pending_and_ran(self):
        pending = view.lines(verify_event(1, "make test"))
        self.assertEqual(pending, ["[verify] pending cmd=make test"])
        ran = view.lines(verify_event(2, "make test", True, 0, "ok ms=1"))
        self.assertEqual(ran, ["[verify] ok=1 exit=0 ok ms=1"])
        failed = view.lines(verify_event(3, "make test", True, 1, "boom ms=1"))
        self.assertEqual(failed, ["[verify] ok=0 exit=1 boom ms=1"])


if __name__ == "__main__":
    unittest.main()
