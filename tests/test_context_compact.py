import json
import unittest

from harness import budget, fold, memo
from tests.support import RUN_ID, RUN_START, TURN, event


def turn_event(seq, turn, obs="exit=0 ms=1\nok", args=None, reasoning="x" * 40):
    data = json.loads(json.dumps(TURN))
    data["turn"] = turn
    data["message"]["reasoning_content"] = reasoning
    data["message"]["tool_calls"] = [{
        "id": f"c{turn}.0", "type": "function",
        "function": {"name": "exec", "arguments": '{"argv":["true"]}'}}]
    data["calls"] = [{"id": f"c{turn}.0", "name": "exec", "observation": obs,
                      "bytes": len(obs.encode()), "saved": None,
                      "args": args or '{"argv":["true"]}'}]
    return event(RUN_ID, seq, "turn", data)


def compact_event(seq, after, count, digest, state):
    return event(RUN_ID, seq, "compact", {
        "after": after, "from": 0, "count": count, "digest": digest,
        "state": json.dumps(state), "bytes": len(digest),
        "tokens": budget.est_text(digest), "prompt": 1000})


class ContextCompactTest(unittest.TestCase):
    def test_plan_keeps_a_recent_tail(self):
        events = [event(RUN_ID, 1, "run_start", dict(RUN_START))]
        for i in range(1, 61):
            events.append(turn_event(i + 1, i))
        upto = budget.plan(events, 0, 400, 10)
        self.assertGreater(upto, 0)
        self.assertLess(upto, 60)
        self.assertLessEqual(budget.tail_tokens(events, upto), 1000)

    def test_forced_plan_keeps_four_turns(self):
        events = [event(RUN_ID, 1, "run_start", dict(RUN_START))]
        for i in range(1, 21):
            events.append(turn_event(i + 1, i))
        upto = budget.plan(events, 0, 1, 16, force=True)
        self.assertEqual(upto, 16)

    def test_digest_is_deterministic_and_merges_files(self):
        events = [event(RUN_ID, 1, "run_start", dict(RUN_START))]
        data = json.loads(json.dumps(TURN))
        data["turn"] = 1
        data["calls"] = [{"id": "c1.0", "name": "write", "observation": "ok wrote 3B a.txt",
                          "bytes": 17, "saved": None,
                          "args": '{"path":"a.txt","bytes":3}'}]
        data["message"]["tool_calls"] = [{"id": "c1.0", "type": "function",
                                          "function": {"name": "write",
                                                       "arguments": '{"path":"a.txt"}'}}]
        events.append(event(RUN_ID, 2, "turn", data))
        one = memo.build(events, 0, 1, None)
        two = memo.build(events, 0, 1, None)
        self.assertEqual(one, two)
        self.assertIn("a.txt(write@1,3B)", one[1])
        state = memo.collect(events, 0, 1, None)
        self.assertIn("a.txt", state["files"])

    def test_context_starts_at_the_checkpoint(self):
        events = [event(RUN_ID, 1, "run_start", dict(RUN_START))]
        for i in range(1, 21):
            events.append(turn_event(i + 1, i))
        state, digest = memo.build(events, 0, 15, None)
        events.append(compact_event(100, 15, state["count"], digest, state))
        for i in range(16, 21):
            events.append(turn_event(100 + i, i))
        msgs = fold.context(events, "t")
        self.assertEqual(msgs[2], {"role": "user", "content": digest})
        self.assertEqual(len(msgs), 3 + 5 * 2)
        self.assertEqual(fold.derive(events)["base_turn"], 15)

    def test_prefix_is_stable_between_compactions(self):
        events = [event(RUN_ID, 1, "run_start", dict(RUN_START))]
        prev, epoch = [], 0
        for i in range(1, 41):
            events.append(turn_event(i + 1, i))
            if i == 20:
                state, digest = memo.build(events, 0, 10, None)
                events.append(compact_event(900, 10, state["count"], digest, state))
            now = fold.context(events, "t")
            current = sum(1 for ev in events if ev["type"] == "compact")
            if current == epoch:
                self.assertEqual(now[:len(prev)], prev)
            epoch = current
            prev = now

    def test_reasoning_replay_is_a_wire_choice(self):
        events = [event(RUN_ID, 1, "run_start", dict(RUN_START))]
        events.append(turn_event(2, 1, reasoning="private"))
        self.assertEqual(fold.context(events, "t")[2]["reasoning_content"], "")
        wire = {"schema": "loop-wire/1", "system": "s", "tools": "[]",
                "thinking": "{}", "model": "m", "max_tokens": 1,
                "renderer": "obs/3", "replay_reasoning": True, "sha": "x"}
        events.insert(1, event(RUN_ID, 2, "wire", wire))
        self.assertEqual(fold.context(events, "t")[2]["reasoning_content"], "private")


if __name__ == "__main__":
    unittest.main()
