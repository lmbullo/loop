import copy
import unittest

from harness import record, recschema
from tests.support import END, RUN_ID, RUN_START, TURN


class RecSchemaTest(unittest.TestCase):
    def test_document(self):
        self.assertEqual(recschema.schema(), "loop-record/1")
        self.assertEqual(recschema.version(), 1)
        self.assertEqual(recschema.view_doc()["schema"], "loop-view/1")

    def test_event_constructs_valid_envelope(self):
        ev = recschema.event(RUN_ID, 1, "run_start", dict(RUN_START),
                             ts="2024-01-01T00:00:00.000Z")
        self.assertEqual(set(ev), set(recschema.ENVELOPE))
        self.assertEqual(ev["seq"], 1)
        self.assertEqual(ev["schema"], "loop-record/1")

    def test_check_rejects_envelope_problems(self):
        ev = recschema.event(RUN_ID, 1, "end", dict(END))
        cases = []
        extra = copy.deepcopy(ev); extra["x"] = 1; cases.append(extra)
        wrong_schema = copy.deepcopy(ev); wrong_schema["schema"] = "bad"; cases.append(wrong_schema)
        wrong_v = copy.deepcopy(ev); wrong_v["v"] = 2; cases.append(wrong_v)
        wrong_run = copy.deepcopy(ev); wrong_run["run_id"] = "other"; cases.append(wrong_run)
        wrong_seq = copy.deepcopy(ev); wrong_seq["seq"] = 2; cases.append(wrong_seq)
        bool_seq = copy.deepcopy(ev); bool_seq["seq"] = True; cases.append(bool_seq)
        bad_ts = copy.deepcopy(ev); bad_ts["ts"] = 1; cases.append(bad_ts)
        unknown = copy.deepcopy(ev); unknown["type"] = "nope"; cases.append(unknown)
        for case in cases:
            with self.assertRaises(record.Corrupt):
                recschema.check(case, RUN_ID, 1)

    def test_check_rejects_payload_problems(self):
        ev = recschema.event(RUN_ID, 1, "end", dict(END))
        missing = copy.deepcopy(ev); missing["data"].pop("cost")
        bad_type = copy.deepcopy(ev); bad_type["data"]["exit"] = "x"
        for case in (missing, bad_type):
            with self.assertRaises(record.Corrupt):
                recschema.check(case, RUN_ID, 1)

    def test_nullable_and_nested_types(self):
        end = dict(END, result=None)
        recschema.check(recschema.event(RUN_ID, 1, "end", end), RUN_ID, 1)
        turn = copy.deepcopy(TURN)
        turn["done"] = {"id": "c1", "result": "ok"}
        recschema.check(recschema.event(RUN_ID, 2, "turn", turn), RUN_ID, 2)
        turn["done"] = None
        recschema.check(recschema.event(RUN_ID, 2, "turn", turn), RUN_ID, 2)

    def test_optional_reasoning_content_is_accepted_not_required(self):
        turn = copy.deepcopy(TURN)
        turn["message"]["reasoning_content"] = "because"
        recschema.check(recschema.event(RUN_ID, 2, "turn", turn), RUN_ID, 2)
        turn["message"]["other"] = "x"
        with self.assertRaises(record.Corrupt):
            recschema.check(recschema.event(RUN_ID, 2, "turn", turn), RUN_ID, 2)

    def test_event_builder_validates(self):
        with self.assertRaises(record.Corrupt):
            recschema.event(RUN_ID, 1, "end", {"exit": 0})

    def test_wire_field_is_backward_compatible(self):
        old = {"schema": "loop-wire/1", "system": "s", "tools": "[]",
               "thinking": "{}", "model": "m", "max_tokens": 1,
               "renderer": "obs/2", "sha": "x"}
        recschema.check(recschema.event(RUN_ID, 1, "wire", old), RUN_ID, 1)
        new = dict(old, replay_reasoning=False)
        recschema.check(recschema.event(RUN_ID, 1, "wire", new), RUN_ID, 1)

    def test_view_doc_has_text_limits(self):
        limits = recschema.view_doc()["text_limits"]
        for key in ("args", "err", "obs", "task", "text"):
            self.assertIsInstance(limits[key], int)


if __name__ == "__main__":
    unittest.main()
