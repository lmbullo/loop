import contextlib
import io
import json
import os
import unittest

from scripts import call_audit
from tests.support import END, RUN_ID, RUN_START, TURN, event, sandbox, write_record


def turn(seq, usage, calls=()):
    data = dict(TURN)
    data["turn"] = seq
    data["usage"] = dict(usage)
    data["calls"] = list(calls)
    return event(RUN_ID, seq + 1, "turn", data)


def call(name, args, observation):
    return {"id": "c1", "name": name, "args": args, "observation": observation,
            "bytes": len(observation.encode()), "saved": None}


class CallAuditTest(unittest.TestCase):
    def run_dir(self):
        path = write_record(RUN_ID, [
            event(RUN_ID, 1, "run_start", dict(RUN_START)),
            turn(1, {"hit": 100, "miss": 20, "out": 7, "reasoning_c": 3, "cost": 0.5},
                 [call("exec", '{"argv":["ls"]}', "exit=0 ms=1\nok"),
                  call("read", '{"path":"f"}', "err read not found")]),
            turn(2, {"hit": 300, "miss": 40, "out": 11, "reasoning_c": 5, "cost": 0.25}),
            event(RUN_ID, 4, "end", dict(END))])
        return os.path.dirname(path)

    def test_tokens_are_hit_miss_out_reasoning(self):
        with sandbox():
            row = call_audit.report(self.run_dir())
        t = row["tokens"]
        self.assertEqual((t["hit"], t["miss"], t["out"], t["reasoning_c"]), (400, 60, 18, 8))
        self.assertEqual(t["prompt"], 460)
        self.assertEqual(t["cost"], 0.75)
        self.assertNotIn("prompt_tokens", t)
        self.assertNotIn("completion_tokens", t)
        self.assertEqual((row["turns"], row["calls"]), (2, 2))
        self.assertEqual((row["fails"], row["fail_kinds"]), (1, 1))

    def test_json_mode_matches_the_report(self):
        buf = io.StringIO()
        with sandbox(), contextlib.redirect_stdout(buf):
            self.assertEqual(call_audit.main([self.run_dir(), "--json"]), 0)
        row = json.loads(buf.getvalue())
        self.assertEqual(row["schema"], "loop-call-audit/1")
        self.assertEqual(row["tokens"]["prompt"], 460)

    def test_text_mode_names_the_token_split(self):
        buf = io.StringIO()
        with sandbox(), contextlib.redirect_stdout(buf):
            self.assertEqual(call_audit.main([self.run_dir()]), 0)
        out = buf.getvalue()
        self.assertIn("hit=400 miss=60 prompt=460 out=18 reasoning_c=8", out)
        self.assertIn("prompt/call=230", out)

    def test_missing_run_dir_is_a_clean_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(call_audit.main([os.path.join(".logs", "runs", "nope")]), 1)
        self.assertIn("err ", err.getvalue())


if __name__ == "__main__":
    unittest.main()
