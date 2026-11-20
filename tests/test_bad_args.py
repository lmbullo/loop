import json
import tempfile
import unittest

from harness import turn


def reply(arguments, name="exec"):
    return {"usage": {}, "choices": [{"finish_reason": "tool_calls", "message": {
        "tool_calls": [{"id": "c1", "type": "function", "function": {
            "name": name, "arguments": arguments}}]}}]}


class CanonicalArgsTest(unittest.TestCase):
    def test_valid_object_is_compacted_and_sorted(self):
        self.assertEqual(turn.canonical_args('{ "argv" : ["a", "b"] }'),
                         '{"argv":["a","b"]}')

    def test_broken_or_empty_text_is_kept_verbatim(self):
        for raw in ("", "   ", "{oops", "[]"):
            self.assertEqual(turn.canonical_args(raw), raw)
        self.assertEqual(turn.canonical_args(None), "{}")


class BadArgsObservationTest(unittest.TestCase):
    def test_empty_string_and_malformed_json_are_not_dispatched(self):
        cases = (("", "arguments are empty"),
                 ("   ", "arguments are empty"),
                 ("{oops", "expected one JSON object"),
                 ("not json at all", "expected one JSON object"),
                 ("[1,2]", "arguments are list"))
        with tempfile.TemporaryDirectory() as tmp:
            for raw, expect in cases:
                _, _, _, _, _, message, _ = turn.read_turn(reply(raw), 1)
                calls, done, obs_n = turn.run_calls(message, tmp, tmp, 0)
                obs = calls[0]["observation"]
                self.assertTrue(obs.startswith("err bad_args exec"), obs)
                self.assertIn("not dispatched", obs)
                self.assertIn(expect, obs)
                self.assertIn("one JSON object", obs)
                self.assertNotIn("requires argv", obs)
                self.assertNotIn("got NoneType", obs)
                self.assertEqual((done, obs_n), (None, 0))

    def test_a_good_call_in_the_same_turn_still_runs(self):
        payload = reply("")
        payload["choices"][0]["message"]["tool_calls"].append(
            {"id": "c2", "type": "function", "function": {
                "name": "done", "arguments": json.dumps({"result": "r"})}})
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, _, _, message, _ = turn.read_turn(payload, 1)
            calls, done, obs_n = turn.run_calls(message, tmp, tmp, 0)
        self.assertIn("err bad_args exec", calls[0]["observation"])
        self.assertEqual((done, obs_n), ({"id": "c1.1", "result": "r"}, 0))


if __name__ == "__main__":
    unittest.main()
