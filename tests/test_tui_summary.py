import unittest

from tui.logview import entry_rows, log_block
from tui.prompt import swidth
from tui.rows import join_parts


class Screen:
    def __init__(self):
        self.rows = {}

    def addstr(self, y, x, text, at=0):
        self.rows[y] = self.rows.get(y, "") + text


class SummaryWrapTest(unittest.TestCase):
    def test_the_final_summary_wraps_and_keeps_every_paragraph(self):
        text = ("word " * 60).rstrip() + "\n\nLAST-PARAGRAPH"
        rows = entry_rows({"kind": "result", "result": text,
                           "finish": "done"}, 30)
        self.assertGreater(len(rows), 1)
        body = " ".join(join_parts(parts) for parts in rows)
        self.assertIn("word", body)
        self.assertIn("LAST-PARAGRAPH", body)
        for parts in rows:
            self.assertLessEqual(swidth(join_parts(parts)), 30)

    def test_a_long_summary_anchors_at_its_first_row(self):
        entries = [{"kind": "call", "turn": k, "name": "exec", "args": "",
                    "obs": "", "failed": False} for k in range(3)]
        entries.append({"kind": "result", "finish": "done",
                        "result": "line " * 200 + "\nEND-MARKER"})
        screen = Screen()
        info = log_block(screen, {"id": "run", "entries": entries}, 0, 6, 40,
                         7, sel=3)
        self.assertGreater(info["n"], info["entries"])
        self.assertEqual(info["scroll"], 3)
        self.assertTrue(screen.rows[1].startswith("\u203a"))
        bottom = Screen()
        tail = log_block(bottom, {"id": "run", "entries": entries}, 0, 6, 40,
                         7, sel=3, scroll=info["n"] - info["vis"],
                         follow=False)
        text = "\n".join(bottom.rows[y] for y in sorted(bottom.rows))
        self.assertIn("END-MARKER", text)
        self.assertEqual(tail["scroll"], info["n"] - info["vis"])


if __name__ == "__main__":
    unittest.main()
