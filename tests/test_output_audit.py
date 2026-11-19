import json
import unittest

from scripts.output_audit import audit
from tests.support import END, RUN_ID, RUN_START, TURN, event, sandbox, write_record


def wire():
    return {"schema": "loop-wire/1", "system": "S", "tools": "[]",
            "thinking": "{}", "model": "m", "max_tokens": 1,
            "renderer": "obs/3", "replay_reasoning": False, "sha": "abc"}


class OutputAuditTest(unittest.TestCase):
    def test_output_split_and_truncation(self):
        with sandbox():
            one = json.loads(json.dumps(TURN))
            one["turn"] = 1
            one["usage"].update({"out": 100, "reasoning_c": 200})
            one["message"]["tool_calls"] = [{
                "id": "c1.0", "type": "function",
                "function": {"name": "exec", "arguments": json.dumps({"argv": ["true"]})}}]
            one["calls"] = [{"id": "c1.0", "name": "exec", "observation": "ok",
                             "bytes": 2, "saved": None}]
            two = json.loads(json.dumps(TURN))
            two["turn"] = 2
            two["finish_reason"] = "length"
            two["usage"].update({"out": 50, "reasoning_c": 0})
            write_record(RUN_ID, [event(RUN_ID, 1, "run_start", dict(RUN_START)),
                                  event(RUN_ID, 2, "wire", wire()),
                                  event(RUN_ID, 3, "turn", one),
                                  event(RUN_ID, 4, "turn", two),
                                  event(RUN_ID, 5, "end", dict(END))])
            row = audit(RUN_ID, top=1)
        self.assertEqual(row["turns"], 2)
        self.assertEqual(row["out"], 150)
        self.assertEqual(row["reasoning_est"], 50.0)
        self.assertEqual(row["arg_bytes"], len(json.dumps({"argv": ["true"]})))
        self.assertEqual(row["truncated"], 1)
        self.assertEqual(row["top"][0]["turn"], 1)


if __name__ == "__main__":
    unittest.main()
