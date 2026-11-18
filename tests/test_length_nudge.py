import json
import unittest
from unittest import mock

from harness import agent, record, recwrite, turn
from tests.support import NUDGE, RUN_ID, RUN_START, TURN, event, sandbox


def response(calls=None, finish="stop"):
    return {"usage": {"prompt_cache_hit_tokens": 1, "prompt_cache_miss_tokens": 1,
                      "completion_tokens": 10},
            "choices": [{"finish_reason": finish, "message": {
                "role": "assistant", "content": None,
                "tool_calls": calls or [], "reasoning_content": "ran away"}}]}


def done_call():
    return {"id": "d", "type": "function", "function": {
        "name": "done", "arguments": json.dumps({"result": "ok"})}}


def broken_write():
    return {"id": "c1.0", "type": "function", "function": {
        "name": "write", "arguments": '{"path":"poem.txt","data":"cut'}}


class LengthNudgeTest(unittest.TestCase):
    def test_truncated_turn_gets_one_length_nudge(self):
        with sandbox() as tmp:
            run_id = record.new_id()
            writer = recwrite.Writer(run_id)
            try:
                with mock.patch.object(agent.auth, "api_key", return_value="k"), \
                        mock.patch.object(agent.api, "call",
                                          side_effect=[response([broken_write()], "length"),
                                                       response([done_call()], "tool_calls")]):
                    summary = agent.run_task(writer, lambda ev: ev, task="t", root=tmp)
            finally:
                writer.close()
            with open(record.record_path(run_id), encoding="utf-8") as f:
                events = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(summary["finish"], "done")
        first = next(e["data"] for e in events if e["type"] == "turn")
        self.assertEqual(first["calls"], [])
        nudges = [e["data"]["text"] for e in events if e["type"] == "nudge"]
        self.assertEqual(nudges, [turn.LENGTH_NUDGE])

    def test_repeated_length_turns_keep_retrying(self):
        with sandbox() as tmp:
            run_id = record.new_id()
            writer = recwrite.Writer(run_id)
            try:
                with mock.patch.object(agent.auth, "api_key", return_value="k"), \
                        mock.patch.object(agent.api, "call",
                                          side_effect=[response([broken_write()], "length"),
                                                       response([broken_write()], "length"),
                                                       response([done_call()], "tool_calls")]):
                    summary = agent.run_task(writer, lambda ev: ev, task="t", root=tmp)
            finally:
                writer.close()
            with open(record.record_path(run_id), encoding="utf-8") as f:
                events = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(summary["finish"], "done")
        nudges = [e["data"]["text"] for e in events if e["type"] == "nudge"]
        self.assertEqual(nudges, [turn.LENGTH_NUDGE, turn.LENGTH_NUDGE])

    def test_length_nudge_does_not_consume_silent_retry(self):
        exec_call = {"id": "e", "type": "function", "function": {
            "name": "exec", "arguments": json.dumps({"argv": ["true"]})}}
        with sandbox() as tmp:
            run_id = record.new_id()
            writer = recwrite.Writer(run_id)
            try:
                with mock.patch.object(agent.auth, "api_key", return_value="k"), \
                        mock.patch.object(agent.api, "call",
                                          side_effect=[response([broken_write()], "length"),
                                                       response([exec_call], "tool_calls"),
                                                       response([], "stop"),
                                                       response([done_call()], "tool_calls")]):
                    summary = agent.run_task(writer, lambda ev: ev, task="t", root=tmp)
            finally:
                writer.close()
            with open(record.record_path(run_id), encoding="utf-8") as f:
                events = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(summary["finish"], "done")
        texts = [e["data"].get("text") for e in events if e["type"] == "nudge"]
        self.assertEqual(texts, [turn.LENGTH_NUDGE, turn.NUDGE])

    def test_length_turn_is_cleaned_for_retry(self):
        data = json.loads(json.dumps(TURN))
        data["finish_reason"] = "length"
        data["message"]["tool_calls"] = [broken_write()]
        msgs = agent.context([event(RUN_ID, 1, "run_start", dict(RUN_START)),
                              event(RUN_ID, 2, "turn", data),
                              event(RUN_ID, 3, "nudge", dict(NUDGE))], "t")
        self.assertNotIn("tool_calls", msgs[2])
        self.assertEqual((msgs[2]["content"], msgs[2]["reasoning_content"]), ("", ""))


if __name__ == "__main__":
    unittest.main()
