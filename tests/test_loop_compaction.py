import json
import os
import unittest
from unittest import mock

from harness import agent, budget, fold, memo, record, recwrite, retry
from tests.support import RUN_START, sandbox
from tests.test_context_compact import compact_event, turn_event


def response(calls=None, finish="tool_calls", out=10):
    return {"usage": {"prompt_cache_hit_tokens": 10, "prompt_cache_miss_tokens": 2,
                      "completion_tokens": out},
            "choices": [{"finish_reason": finish, "message": {
                "role": "assistant", "content": None, "tool_calls": calls or [],
                "reasoning_content": ""}}]}


def call(name, args):
    return {"id": "c", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def run_fake(responses, task="t", env=None):
    with sandbox() as tmp:
        run_id = record.new_id()
        writer = recwrite.Writer(run_id)
        try:
            with mock.patch.dict(os.environ, env or {}, clear=False), \
                    mock.patch.object(agent.auth, "api_key", return_value="k"), \
                    mock.patch.object(agent.api, "call", side_effect=responses):
                summary = agent.run_task(writer, lambda ev: ev, task=task, root=tmp)
        finally:
            writer.close()
        with open(record.record_path(run_id), encoding="utf-8") as f:
            events = [json.loads(line) for line in f if line.strip()]
        return summary, events


class LoopCompactionTest(unittest.TestCase):
    def test_four_hundred_turns_compact_but_finish(self):
        responses = [response([call("write", {"path": f"n{i}.txt", "data": str(i)})])
                     for i in range(399)]
        responses.append(response([call("done", {"result": "ok"})]))
        summary, events = run_fake(responses, env={
            "LOOP_CONTEXT_HIGH": "1500", "LOOP_CONTEXT_LOW": "700",
            "LOOP_KEEP_TURNS": "2"})
        self.assertEqual((summary["finish"], summary["turns"]), ("done", 400))
        compacts = [ev for ev in events if ev["type"] == "compact"]
        self.assertGreater(len(compacts), 0)
        self.assertTrue(all(len(ev["data"]["digest"].encode()) <= 6000
                            for ev in compacts))
        self.assertEqual(fold.derive(events)["base_turn"],
                         compacts[-1]["data"]["after"])
        spec = fold.wire(events)
        sizes = [budget.est_request(fold.context(events[:i], "t", spec), spec)
                 for i, ev in enumerate(events) if ev["type"] == "turn"]
        self.assertLess(max(sizes), 12000)

    def test_length_stop_escalates_the_output_ceiling(self):
        caps = []

        def fake(msgs, key, wire=None, max_tokens=None):
            caps.append(max_tokens)
            if len(caps) == 1:
                return response([], finish="length")
            return response([call("done", {"result": "ok"})])

        with sandbox() as tmp:
            run_id = record.new_id()
            writer = recwrite.Writer(run_id)
            try:
                with mock.patch.object(agent.auth, "api_key", return_value="k"), \
                        mock.patch.object(agent.api, "call", side_effect=fake):
                    summary = agent.run_task(writer, lambda ev: ev, task="t", root=tmp)
            finally:
                writer.close()
        self.assertEqual(summary["finish"], "done")
        self.assertEqual(caps, [16384, 65536])

    def test_context_error_forces_a_compact_and_retries(self):
        responses = [response([call("write", {"path": f"f{i}.txt", "data": "x"})])
                     for i in range(6)]
        err = retry.Error(400, "maximum context length is 8192 tokens")
        responses += [err, response([call("done", {"result": "ok"})])]
        summary, events = run_fake(responses, env={
            "LOOP_CONTEXT_HIGH": "100000", "LOOP_KEEP_TURNS": "4"})
        self.assertEqual(summary["finish"], "done")
        self.assertGreaterEqual(len([e for e in events if e["type"] == "compact"]), 1)
        self.assertFalse([e for e in events if e["type"] == "error"])

    def test_silent_stop_gets_a_nudge_after_real_work(self):
        summary, events = run_fake([
            response([call("exec", {"argv": ["true"]})]),
            response([], finish="stop"),
            response([call("exec", {"argv": ["true"]})]),
            response([], finish="stop"),
            response([call("done", {"result": "ok"})])])
        self.assertEqual(summary["finish"], "done")
        self.assertEqual([ev["type"] for ev in events].count("nudge"), 2)

    def test_resume_after_a_compact_does_not_recompact(self):
        wire = {"schema": "loop-wire/1", "system": "s", "tools": "[]",
                "thinking": "{}", "model": "m", "max_tokens": 65536,
                "renderer": "obs/3", "replay_reasoning": False, "sha": "x"}
        with sandbox() as tmp:
            run_id = record.new_id()
            writer = recwrite.Writer(run_id)
            try:
                writer.append("run_start", dict(RUN_START))
                writer.append("wire", wire)
                for t in range(1, 6):
                    writer.append("turn", turn_event(t + 2, t)["data"])
                state, digest = memo.build(
                    [event for event in [turn_event(t + 2, t) for t in range(1, 6)]],
                    0, 5, None)
                writer.append("compact", compact_event(
                    90, 5, state["count"], digest, state)["data"])
                for t in range(6, 11):
                    writer.append("turn", turn_event(t + 2, t)["data"])
                with mock.patch.object(agent.auth, "api_key", return_value="k"), \
                        mock.patch.object(agent.api, "call",
                                          return_value=response(
                                              [call("done", {"result": "ok"})])):
                    summary = agent.run_task(writer, lambda ev: ev, root=tmp)
            finally:
                writer.close()
            with open(record.record_path(run_id), encoding="utf-8") as f:
                events = [json.loads(line) for line in f if line.strip()]
        self.assertEqual((summary["finish"], summary["turns"]), ("done", 11))
        self.assertEqual([ev["type"] for ev in events].count("compact"), 1)

    def test_context_budget_is_bounded(self):
        responses = [response([call("write", {"path": "a.txt", "data": "x" * 800})])
                     for _ in range(40)]
        responses.append(response([call("done", {"result": "ok"})]))
        summary, events = run_fake(responses, env={
            "LOOP_CONTEXT_HIGH": "1200", "LOOP_CONTEXT_LOW": "600",
            "LOOP_KEEP_TURNS": "2"})
        self.assertEqual(summary["finish"], "done")
        spec = fold.wire(events)
        sizes = [budget.est_request(fold.context(events[:i], "t", spec), spec)
                 for i, ev in enumerate(events) if ev["type"] == "turn"]
        self.assertGreater(max(sizes), 0)
        self.assertLess(max(sizes), 12000)


if __name__ == "__main__":
    unittest.main()
