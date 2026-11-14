import json
import os
import sys
import tempfile
import unittest

from harness import agent, recwrite
from tests.support import END, RUN_ID, RUN_START, TURN, event, sandbox


def turn_with_call(seq=2, done=None):
    data = json.loads(json.dumps(TURN))
    data["message"]["tool_calls"] = [{
        "id": "c1", "type": "function",
        "function": {"name": "exec", "arguments": json.dumps({"argv": ["true"]})}}]
    data["calls"] = [{"id": "c1", "name": "exec", "observation": "ok",
                      "bytes": 2, "saved": None}]
    data["done"] = done
    data["turn"] = seq
    return event(RUN_ID, seq, "turn", data)


class AgentContextTest(unittest.TestCase):
    def test_totals_and_cost(self):
        events = [turn_with_call(), turn_with_call(3)]
        totals = agent.totals_of(events)
        self.assertEqual(totals, {"hit": 20, "miss": 40, "out": 60, "reasoning_c": 80})
        self.assertAlmostEqual(agent.cost_of(totals), agent.pricing.cost(20, 40, 60))

    def test_derive(self):
        done = {"id": "c9", "result": "finished"}
        events = [event(RUN_ID, 1, "run_start", dict(RUN_START)),
                  turn_with_call(2),
                  turn_with_call(3, done)]
        got = agent.derive(events)
        self.assertEqual(got["task"], RUN_START["task"])
        self.assertEqual(got["root"], RUN_START["root"])
        self.assertEqual(got["turn"], 3)
        self.assertEqual(got["obs_n"], 2)
        self.assertEqual(got["done"], done)

    def test_context_fold(self):
        events = [event(RUN_ID, 1, "run_start", dict(RUN_START)),
                  turn_with_call(2)]
        msgs = agent.context(events, RUN_START["task"])
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[1], {"role": "user", "content": RUN_START["task"]})
        self.assertEqual(msgs[2]["role"], "assistant")
        self.assertEqual(msgs[3], {"role": "tool", "tool_call_id": "c1", "content": "ok"})
        self.assertEqual(len(msgs), 4)

    def test_read_turn(self):
        response = {
            "usage": {"prompt_cache_hit_tokens": 1, "prompt_cache_miss_tokens": 2,
                      "completion_tokens": 3},
            "choices": [{"finish_reason": "tool_calls", "message": {
                "reasoning_content": "abcd",
                "tool_calls": [{"id": "c1", "type": "function",
                                "function": {"name": "exec", "arguments": "{}"}}]}}]}
        hit, miss, out, reasoning, finish, message, text = agent.read_turn(response)
        self.assertEqual((hit, miss, out, reasoning, finish), (1, 2, 3, 4, "tool_calls"))
        self.assertEqual(message["role"], "assistant")
        self.assertEqual(message["tool_calls"][0]["function"]["name"], "exec")
        self.assertIsNone(text)

    def test_run_calls_malformed_and_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            message = {"tool_calls": [
                {"id": "bad", "function": {"name": "exec", "arguments": "[]"}},
                {"id": "done", "function": {"name": "done", "arguments": '{"result":"r"}'}}]}
            calls, done, obs_n = agent.run_calls(message, tmp, tmp, 0)
            self.assertEqual(len(calls), 1)
            self.assertIn("malformed_arguments", calls[0]["observation"])
            self.assertEqual(done, {"id": "done", "result": "r"})
            self.assertEqual(obs_n, 0)

    def test_run_calls_exec(self):
        with tempfile.TemporaryDirectory() as tmp:
            message = {"tool_calls": [{
                "id": "c1", "function": {"name": "exec", "arguments": json.dumps(
                    {"argv": [sys.executable, "-c", "print('hi')"]})}}]}
            calls, done, obs_n = agent.run_calls(message, tmp, tmp, 0)
            self.assertIsNone(done)
            self.assertEqual(obs_n, 1)
            self.assertIn("hi", calls[0]["observation"])

    def test_run_calls_saved_path_is_root_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_dir = os.path.join(tmp, ".logs", "runs", "r1", "obs")
            message = {"tool_calls": [{
                "id": "c1", "function": {"name": "exec", "arguments": json.dumps(
                    {"argv": [sys.executable, "-c", "print('x' * 40000)"]})}}]}
            calls, _, _ = agent.run_calls(message, obs_dir, tmp, 0)
            saved = calls[0]["saved"]
            self.assertFalse(os.path.isabs(saved))
            self.assertTrue(os.path.isfile(os.path.join(tmp, saved)))

    def test_finish_and_stopped(self):
        with sandbox():
            writer = recwrite.Writer(RUN_ID)
            try:
                writer.append("run_start", dict(RUN_START))
                events = [writer.append("turn", dict(TURN))]
                summary = agent.finish(writer, lambda ev: ev, events, 1, "done", "ok", 0)
            finally:
                writer.close()
            self.assertEqual(summary["exit"], 0)
            self.assertEqual(summary["finish"], "done")
            self.assertEqual(summary["turns"], 1)
            self.assertEqual(summary["hit"], TURN["usage"]["hit"])
            self.assertTrue(os.path.isfile(os.path.join(
                os.path.dirname(writer.path), "record.jsonl")))

    def test_stopped(self):
        with sandbox():
            writer = recwrite.Writer(RUN_ID)
            try:
                events = [writer.append("run_start", dict(RUN_START))]
                summary = agent.stopped(writer, events, 0)
            finally:
                writer.close()
            self.assertEqual(summary["exit"], 130)
            self.assertEqual(summary["finish"], "stopped")

    def test_end_shape(self):
        self.assertEqual(END["result"], "ok")


if __name__ == "__main__":
    unittest.main()
