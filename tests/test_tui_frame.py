import unittest
from unittest import mock

from tui import frame


class Target:
    def __init__(self, width=12, height=5):
        self.width, self.height = width, height
        self.calls = []
        self.lines = [""] * height
        self.cursor = None

    def addstr(self, y, x, text, attr=0):
        self.calls.append((y, x, text, attr))
        row = list(self.lines[y].ljust(self.width))
        for i, ch in enumerate(text):
            if x + i < self.width:
                row[x + i] = ch
        self.lines[y] = "".join(row).rstrip()

    def move(self, y, x):
        self.cursor = (y, x)

    def noutrefresh(self):
        pass


def flush(f, cursor=False):
    with mock.patch.object(frame.curses, "doupdate", lambda: None), \
         mock.patch.object(frame.curses, "curs_set", lambda n: None):
        f.flush(cursor)


class FrameTest(unittest.TestCase):
    def test_first_frame_paints_and_identical_frame_is_silent(self):
        target = Target()
        f = frame.Frame(target)
        f.resize(12, 5)
        f.erase()
        f.addstr(0, 0, "hello")
        f.addstr(2, 0, "log")
        flush(f)
        first = len(target.calls)
        f.erase()
        f.addstr(0, 0, "hello")
        f.addstr(2, 0, "log")
        target.calls = []
        flush(f)
        self.assertEqual(target.calls, [])
        self.assertGreater(first, 0)

    def test_only_the_changed_row_is_repainted(self):
        target = Target()
        f = frame.Frame(target)
        f.resize(12, 5)
        f.erase()
        f.addstr(0, 0, "one")
        f.addstr(2, 0, "log")
        flush(f)
        target.calls = []
        f.erase()
        f.addstr(0, 0, "one")
        f.addstr(2, 0, "log2")
        flush(f)
        self.assertEqual({call[0] for call in target.calls}, {2})
        self.assertEqual(target.lines[2], "log2")

    def test_shorter_row_clears_stale_cells(self):
        target = Target()
        f = frame.Frame(target)
        f.resize(12, 5)
        f.erase()
        f.addstr(0, 0, "long line")
        flush(f)
        f.erase()
        f.addstr(0, 0, "hi")
        flush(f)
        self.assertEqual(target.lines[0], "hi")

    def test_invalidate_and_resize_repaint_every_row(self):
        target = Target()
        f = frame.Frame(target)
        f.resize(12, 5)
        f.erase()
        flush(f)
        target.calls = []
        f.invalidate()
        flush(f)
        self.assertEqual(len({call[0] for call in target.calls}), 5)
        target.calls = []
        f.resize(10, 4)
        f.erase()
        flush(f)
        self.assertEqual(len({call[0] for call in target.calls}), 4)

    def test_cursor_moves_only_when_shown(self):
        target = Target()
        f = frame.Frame(target)
        f.resize(12, 5)
        f.erase()
        f.move(3, 4)
        flush(f, True)
        self.assertEqual(target.cursor, (3, 4))
        target.cursor = None
        flush(f, False)
        self.assertIsNone(target.cursor)

    def test_bottom_row_never_writes_the_last_cell(self):
        target = Target()
        f = frame.Frame(target)
        f.resize(12, 5)
        f.erase()
        f.addstr(4, 0, "x" * 40)
        flush(f)
        self.assertEqual(target.lines[4], "x" * 11)


if __name__ == "__main__":
    unittest.main()
