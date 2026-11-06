import json
import unittest

from harness import record, recread, recschema, view
from tests.support import (END, ERROR, INTERRUPTED, RESUME, RUN_ID, RUN_START, TURN,
                           event)


def turn_event(seq=2):
    data = json.loads(json.dumps(TURN))
    data["message"]["tool_calls"] = [{
        "id": "c1", "type": "function",
        "function": {"name": "exec", "arguments": json.dumps({"argv": ["true"]})}}]
    data["calls"] = [{"id": "c1", "name": "exec", "observation": "hello\nworld",
                      "bytes": 11, "saved": None}]
    return event(RUN_ID, seq, "turn", data)


class ViewTest(unittest.TestCase):
    def test_one_escapes_and_limits(self):
        self.assertEqual(view.one("a\nb\tc\r", 100), "a\\nb\\tc")
        self.assertEqual(view.one("abcdef", 3), "abc")
        self.assertEqual(view.one(None, 5), "")

    def test_lines_for_every_event(self):
        events = [event(RUN_ID, 1, "run_start", dict(RUN_START)), turn_event(),
                  event(RUN_ID, 3, "resume", dict(RESUME)),
                  event(RUN_ID, 4, "error", dict(ERROR)),
                  event(RUN_ID, 5, "interrupted", dict(INTERRUPTED)),
                  event(RUN_ID, 6, "end", dict(END))]
        text = "\n".join(line for ev in events for line in view.lines(ev))
        self.assertIn("run=" + RUN_ID, text)
        self.assertIn("[turn 1]", text)
        self.assertIn("exec: ", text)
        self.assertIn("-> hello", text)
        self.assertIn("[resume]", text)
        self.assertIn("[err]", text)
        self.assertIn("[interrupted]", text)
        self.assertIn("[end]", text)
        self.assertIn("result=ok", text)

    def test_render_adds_derived_interrupted_marker(self):
        events = [event(RUN_ID, 1, "run_start", dict(RUN_START))]
        text = view.render(events)
        self.assertIn("[interrupted] reason=no_terminal_event last_seq=1 by=-", text)

    def test_render_respects_explicit_interrupted_marker(self):
        events = [event(RUN_ID, 1, "run_start", dict(RUN_START)),
                  event(RUN_ID, 2, "interrupted", dict(INTERRUPTED))]
        text = view.render(events)
        self.assertEqual(text.count("[interrupted]"), 1)
        self.assertIn("reason=server_stop", text)

    def test_render_torn_marker(self):
        events = [event(RUN_ID, 1, "run_start", dict(RUN_START)),
                  event(RUN_ID, 2, "end", dict(END))]
        self.assertIn("[torn] bytes=7 dropped=1", view.render(events, 7))

    def test_envelope_round_trip(self):
        events = [event(RUN_ID, 1, "run_start", dict(RUN_START)),
                  event(RUN_ID, 2, "end", dict(END))]
        rec = {"run_id": RUN_ID, "events": events, "state": "complete",
               "seq": 2, "torn_tail_bytes": 0}
        raw = json.dumps(view.envelope(rec))
        got_events, torn, run_id, state = view.read_envelope(raw)
        self.assertEqual(got_events, events)
        self.assertEqual((torn, run_id, state), (0, RUN_ID, "complete"))

    def test_read_envelope_rejects_bad_documents(self):
        spec = recschema.view_doc()
        base = {"schema": "loop-view/1", "version": 1, "run_id": RUN_ID,
                "source_schema": "loop-record/1", "source_version": 1,
                "state": "empty", "seq": 0, "torn_tail_bytes": 0, "events": []}
        self.assertEqual(set(base), set(spec["fields"]))
        bad = dict(base, state="complete")
        with self.assertRaises(record.Corrupt):
            view.read_envelope(json.dumps(bad))
        bad = dict(base, schema="nope")
        with self.assertRaises(record.Corrupt):
            view.read_envelope(json.dumps(bad))
        with self.assertRaises(record.Corrupt):
            view.read_envelope("not json")

    def test_list_rows(self):
        row = {"run_id": RUN_ID, "state": "complete", "seq": 2, "turns": 1,
               "ts": "2024-01-01T00:00:00.000Z", "finish": "done", "cost": 0.5}
        line = view.list_rows([row])[0]
        self.assertIn("state=complete", line)
        self.assertIn("cost=$0.500000", line)
        row["cost"] = None
        self.assertIn("cost=-", view.list_rows([row])[0])

    def test_args_lookup(self):
        data = json.loads(json.dumps(TURN))
        data["message"]["tool_calls"] = [{
            "id": "c1", "type": "function",
            "function": {"name": "exec", "arguments": '{"b":1,"a":2}'}}]
        self.assertEqual(view._args(data["message"], "c1"), '{"a":2,"b":1}')
        self.assertEqual(view._args(data["message"], "missing"), "")


if __name__ == "__main__":
    unittest.main()
