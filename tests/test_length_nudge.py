import json
import unittest
from unittest import mock

from harness import agent, record, recwrite, turn
from tests.support import sandbox


def response(calls=None, finish="stop"):
    return {"usage": {"prompt_cache_hit_tokens": 1, "prompt_cache_miss_tokens": 1,
                      "completion_tokens": 10},
            "choices": [{"finish_reason": finish, "message": {
                "role": "assistant", "content": None,
                "tool_calls": calls or [], "reasoning_content": ""}}]}


def done_call():
    return {"id": "d", "type": "function", "function": {
        "name": "done", "arguments": json.dumps({"result": "ok"})}}


class LengthNudgeTest(unittest.TestCase):
    def test_truncated_turn_gets_one_length_nudge(self):
        with sandbox() as tmp:
            run_id = record.new_id()
            writer = recwrite.Writer(run_id)
            try:
                with mock.patch.object(agent.auth, "api_key", return_value="k"), \
                        mock.patch.object(agent.api, "call",
                                          side_effect=[response(finish="length"),
                                                       response([done_call()], "tool_calls")]):
                    summary = agent.run_task(writer, lambda ev: ev, task="t", root=tmp)
            finally:
                writer.close()
            with open(record.record_path(run_id), encoding="utf-8") as f:
                events = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(summary["finish"], "done")
        nudges = [e["data"]["text"] for e in events if e["type"] == "nudge"]
        self.assertEqual(nudges, [turn.LENGTH_NUDGE])


if __name__ == "__main__":
    unittest.main()
