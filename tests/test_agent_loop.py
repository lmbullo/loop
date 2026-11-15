import json
import sys
import unittest
from unittest import mock

from harness import agent, fold, record, recwrite, turn
from tests.support import RUN_START, TURN, sandbox


def response(content=None, calls=None, finish="stop", out=10):
    return {"usage": {"prompt_cache_hit_tokens": 100,
                      "prompt_cache_miss_tokens": 10,
                      "completion_tokens": out},
            "choices": [{"finish_reason": finish, "message": {
                "role": "assistant", "content": content,
                "tool_calls": calls or [], "reasoning_content": ""}}]}


def call(name, args):
    return {"id": "id-" + name, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def read(run_id):
    with open(record.record_path(run_id), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class AgentLoopTest(unittest.TestCase):
    def run_fake(self, responses, task="t"):
        with sandbox() as tmp:
            run_id = record.new_id()
            writer = recwrite.Writer(run_id)
            try:
                with mock.patch.object(agent.auth, "api_key", return_value="k"), \
                        mock.patch.object(agent.api, "call", side_effect=list(responses)):
                    summary = agent.run_task(writer, lambda ev: ev, task=task, root=tmp)
            finally:
                writer.close()
            return summary, read(run_id)

    def test_silent_stop_gets_one_nudge_then_done(self):
        summary, events = self.run_fake([
            response(None, [call("exec", {"argv": ["true"]})], "tool_calls"),
            response(None, [], "stop"),
            response(None, [call("done", {"result": "ok"})], "tool_calls")])
        self.assertEqual(summary["finish"], "done")
        self.assertEqual(summary["result"], "ok")
        self.assertEqual(summary["turns"], 3)
        self.assertEqual([ev["type"] for ev in events],
                         ["run_start", "wire", "turn", "turn", "nudge", "turn", "end"])
        self.assertEqual(events[3]["data"]["message"]["content"], "")
        self.assertEqual(events[4]["data"], {"text": turn.NUDGE})
        self.assertTrue(fold.derive(events)["nudged"])
        msgs = fold.context(events, "t")
        self.assertIn({"role": "user", "content": turn.NUDGE}, msgs)

    def test_second_silent_stop_ends_no_tool_call(self):
        summary, events = self.run_fake([
            response(None, [call("exec", {"argv": ["true"]})], "tool_calls"),
            response(None, [], "stop"),
            response(None, [], "stop")])
        self.assertEqual(summary["finish"], "no_tool_call")
        self.assertEqual(summary["turns"], 3)
        self.assertEqual([ev["type"] for ev in events].count("nudge"), 1)

    def test_offline_loop_dispatches_write_edit_exec_then_done(self):
        summary, events = self.run_fake([
            response(None, [call("write", {"path": "work.txt", "data": "alpha\n"})], "tool_calls"),
            response(None, [call("edit", {"path": "work.txt", "old": "alpha", "new": "beta"})], "tool_calls"),
            response(None, [call("exec", {"argv": ["cat", "work.txt"]})], "tool_calls"),
            response(None, [call("done", {"result": "beta"})], "tool_calls")])
        self.assertEqual(summary["finish"], "done")
        self.assertEqual(summary["result"], "beta")
        obs = [c["observation"] for ev in events if ev["type"] == "turn"
               for c in ev["data"]["calls"]]
        self.assertEqual(obs[0], "ok wrote 6B work.txt")
        self.assertIn("ok -5 +4 work.txt", obs[1])
        self.assertIn("beta", obs[2])

    def test_resume_after_nudge_does_not_nudge_again(self):
        with sandbox() as tmp:
            run_id = record.new_id()
            writer = recwrite.Writer(run_id)
            try:
                writer.append("run_start", {
                    "task": "t", "root": tmp, "entrypoint": "api", "model": "fake",
                    "tools": ["exec", "write", "edit", "done"],
                    "max_inline": 8192, "record_source": "live"})
                data = json.loads(json.dumps(TURN))
                data["message"]["tool_calls"] = [call("exec", {"argv": ["true"]})]
                data["calls"] = [{"id": "exec-1", "name": "exec", "observation": "ok",
                                  "bytes": 2, "saved": None}]
                writer.append("turn", data)
                writer.append("nudge", {"text": turn.NUDGE})
            finally:
                writer.close()
            writer = recwrite.Writer(run_id)
            try:
                with mock.patch.object(agent.auth, "api_key", return_value="k"), \
                        mock.patch.object(agent.api, "call", return_value=response(None, [], "stop")):
                    summary = agent.run_task(writer, lambda ev: ev, root=tmp)
            finally:
                writer.close()
            events = read(run_id)
        self.assertEqual(summary["finish"], "no_tool_call")
        self.assertEqual(summary["turns"], 2)
        self.assertEqual([ev["type"] for ev in events],
                         ["run_start", "turn", "nudge", "wire", "turn", "end"])

    def test_resume_reuses_the_recorded_wire_snapshot(self):
        with sandbox() as tmp:
            run_id = record.new_id()
            spec = {"schema": "loop-wire/1", "system": "PINNED", "tools": "[]",
                    "thinking": "{}", "model": "m", "max_tokens": 1,
                    "renderer": "obs/2", "sha": "x"}
            writer = recwrite.Writer(run_id)
            try:
                writer.append("run_start", dict(RUN_START, root=tmp))
                writer.append("wire", spec)
                data = json.loads(json.dumps(TURN))
                data["message"]["tool_calls"] = [call("exec", {"argv": ["true"]})]
                data["calls"] = [{"id": "c1.0", "name": "exec", "observation": "ok",
                                  "bytes": 2, "saved": None}]
                writer.append("turn", data)
                writer.append("nudge", {"text": turn.NUDGE})
            finally:
                writer.close()
            seen = {}

            def fake_call(msgs, key, wire=None):
                seen["system"] = msgs[0]["content"]
                seen["wire"] = wire["sha"]
                return response(None, [call("done", {"result": "ok"})], "tool_calls")

            writer = recwrite.Writer(run_id)
            try:
                with mock.patch.object(agent.auth, "api_key", return_value="k"), \
                        mock.patch.object(agent.api, "call", side_effect=fake_call):
                    summary = agent.run_task(writer, lambda ev: ev, root=tmp)
            finally:
                writer.close()
            events = read(run_id)
        self.assertEqual(summary["finish"], "done")
        self.assertEqual(seen, {"system": "PINNED", "wire": "x"})
        self.assertEqual([ev["type"] for ev in events].count("wire"), 1)

    def test_first_silent_stop_is_not_nudged(self):
        summary, events = self.run_fake([response(None, [], "stop")])
        self.assertEqual(summary["finish"], "no_tool_call")
        self.assertEqual(summary["turns"], 1)
        self.assertNotIn("nudge", [ev["type"] for ev in events])

    def test_non_str_done_result_is_an_observation(self):
        summary, events = self.run_fake([
            response(None, [call("done", {"result": 42})], "tool_calls"),
            response(None, [call("done", {"result": "ok"})], "tool_calls")])
        self.assertEqual(summary["finish"], "done")
        self.assertEqual(summary["result"], "ok")
        first = events[2]["data"]["calls"][0]
        self.assertEqual(first["name"], "done")
        self.assertIn("err bad_args done requires result:str", first["observation"])

    def test_identical_exec_observations_become_references(self):
        same = [{"id": "c1", "type": "function", "function": {
            "name": "exec", "arguments": json.dumps(
                {"argv": [sys.executable, "-c", "print('same')"]})}}]
        summary, events = self.run_fake([
            response(None, same, "tool_calls"),
            response(None, same, "tool_calls"),
            response(None, [call("done", {"result": "ok"})], "tool_calls")])
        self.assertEqual(summary["finish"], "done")
        obs = [c["observation"] for ev in events if ev["type"] == "turn"
               for c in ev["data"]["calls"]]
        self.assertIn("same", obs[0])
        self.assertTrue(obs[1].startswith("exit=") and "same=obs-1" in obs[1])

    def test_reasoning_content_is_recorded_and_replayed(self):
        reply = response(None, [call("exec", {"argv": ["true"]})], "tool_calls")
        reply["choices"][0]["message"]["reasoning_content"] = "because"
        summary, events = self.run_fake([
            reply, response(None, [call("done", {"result": "ok"})], "tool_calls")])
        self.assertEqual(summary["finish"], "done")
        first = events[2]["data"]["message"]
        self.assertEqual(first["reasoning_content"], "because")
        self.assertEqual(fold.context(events, "t")[2]["reasoning_content"], "because")

    def test_turn_module_owns_the_stop_policy(self):
        quiet = {"role": "assistant", "content": None, "tool_calls": []}
        self.assertEqual(turn.stop(quiet, None, 1, False), ("no_tool_call", None))
        self.assertEqual(turn.stop(quiet, None, 2, False), ("nudge", turn.NUDGE))
        self.assertEqual(turn.stop(quiet, " answer ", 2, True), ("done", "answer"))
        busy = {"role": "assistant", "content": None,
                "tool_calls": [{"id": "c", "function": {"name": "exec"}}]}
        self.assertIsNone(turn.stop(busy, "side text", 2, False))


if __name__ == "__main__":
    unittest.main()
