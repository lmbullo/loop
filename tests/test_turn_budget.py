import json
import inspect
import unittest
from unittest import mock

from harness import agent, record, recwrite, srvclient
from tests.support import sandbox


def response(calls=None):
    return {"usage": {}, "choices": [{"finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": None, "tool_calls": calls or [],
        "reasoning_content": ""}}]}


def call(name, args):
    return {"id": "c", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


class TurnBudgetTest(unittest.TestCase):
    def test_four_hundred_turns_are_not_capped(self):
        responses = [response([call("write", {"path": "n.txt", "data": str(i)})])
                     for i in range(399)]
        responses.append(response([call("done", {"result": "ok"})]))
        with sandbox() as tmp:
            run_id = record.new_id()
            writer = recwrite.Writer(run_id)
            try:
                with mock.patch.object(agent.auth, "api_key", return_value="k"), \
                        mock.patch.object(agent.api, "call", side_effect=responses):
                    summary = agent.run_task(writer, lambda ev: ev, task="t", root=tmp)
            finally:
                writer.close()
        self.assertEqual((summary["finish"], summary["turns"]), ("done", 400))

    def test_attach_budget_is_opt_in(self):
        self.assertIsNone(inspect.signature(srvclient.stream).parameters["budget"].default)


if __name__ == "__main__":
    unittest.main()
