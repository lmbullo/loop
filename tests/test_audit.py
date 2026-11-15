import unittest

from scripts.cache_audit import audit
from tests.support import RUN_ID, RUN_START, TURN, END, event, sandbox, write_record


def wire():
    return {"schema": "loop-wire/1", "system": "S", "tools": "[]",
            "thinking": "{}", "model": "m", "max_tokens": 1,
            "renderer": "obs/2", "sha": "abc"}


class AuditTest(unittest.TestCase):
    def test_prefix_and_reuse_projection(self):
        with sandbox():
            turn1 = dict(TURN)
            turn1["turn"] = 1
            turn1["calls"] = [{"id": "c1.0", "name": "exec", "observation": "same=obs-0 bytes=1",
                               "bytes": 18, "saved": None}]
            turn2 = dict(TURN)
            turn2["turn"] = 2
            turn2["calls"] = []
            write_record(RUN_ID, [event(RUN_ID, 1, "run_start", dict(RUN_START)),
                                  event(RUN_ID, 2, "wire", wire()),
                                  event(RUN_ID, 3, "turn", turn1),
                                  event(RUN_ID, 4, "turn", turn2),
                                  event(RUN_ID, 5, "end", dict(END))])
            row = audit(RUN_ID)
        self.assertEqual(row["turns"], 2)
        self.assertTrue(row["prefix_ok"])
        self.assertEqual(row["reuse_refs"], 1)
        self.assertEqual(row["wire_sha"], "abc")


if __name__ == "__main__":
    unittest.main()
