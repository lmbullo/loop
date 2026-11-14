import unittest

from tui import frame, mouse


class Target:
    def __init__(self):
        self.calls = []

    def addstr(self, y, x, text, attr=0):
        self.calls.append((y, x, text, attr))

    def move(self, y, x):
        pass

    def noutrefresh(self):
        pass


class App:
    def __init__(self, lines=("hello world", "second line")):
        self.w, self.h = 20, 4
        self.frame = frame.Frame(Target())
        self.frame.resize(self.w, self.h)
        for y, line in enumerate(lines):
            self.frame.addstr(y, 0, line)
        self.sel = None
        self.dirty = False
        self.notices = []

    def say(self, text):
        self.notices.append(text)


class DecodeTest(unittest.TestCase):
    def test_left_press_drag_and_release_become_screen_cells(self):
        self.assertEqual(mouse.decode(0, 10, 5), ("mouse", ("down", 9, 4)))
        self.assertEqual(mouse.decode(32, 12, 6), ("mouse", ("drag", 11, 5)))
        self.assertEqual(mouse.decode(0, 12, 6, release=True),
                         ("mouse", ("up", 11, 5)))
        self.assertEqual(mouse.decode(3, 12, 6), ("mouse", ("up", 11, 5)))

    def test_other_buttons_and_shift_drag_are_ignored(self):
        self.assertIsNone(mouse.decode(1, 3, 3))
        self.assertIsNone(mouse.decode(2, 3, 3))
        self.assertIsNone(mouse.decode(4, 3, 3))
        self.assertIsNone(mouse.decode(36, 3, 3))

    def test_wheel_keeps_its_key_event(self):
        self.assertEqual(mouse.decode(64, 3, 3), ("key", "scroll_up"))
        self.assertEqual(mouse.decode(65, 3, 3), ("key", "scroll_down"))

    def test_sgr_and_x10_wire_forms_decode_alike(self):
        self.assertEqual(mouse.sgr_mouse(b"\x1b[<0;10;5M"),
                         ("mouse", ("down", 9, 4)))
        self.assertEqual(mouse.x10_mouse(b"\x1b[M" + bytes([32, 42, 37])),
                         ("mouse", ("down", 9, 4)))


class SelectionTest(unittest.TestCase):
    def test_drag_release_copies_the_covered_text_and_clears_the_highlight(self):
        app = App()
        mouse.down(app, 0, 0)
        mouse.drag(app, 4, 1)
        self.assertEqual(app.sel, {"a": (0, 0), "b": (4, 1)})
        got = []
        ok = mouse.up(app, 4, 1, copy=lambda text: got.append(text) or True)
        self.assertTrue(ok)
        self.assertEqual(got, ["hello world\nsecon"])
        self.assertIsNone(app.sel)
        self.assertEqual(app.notices, ["copied 17 chars"])

    def test_reverse_drag_reads_in_reading_order(self):
        app = App()
        mouse.down(app, 4, 1)
        mouse.drag(app, 1, 0)
        got = []
        mouse.up(app, 1, 0, copy=lambda text: got.append(text) or True)
        self.assertEqual(got, ["ello world\nsecon"])

    def test_a_click_without_motion_does_not_copy(self):
        app = App()
        got = []
        mouse.down(app, 2, 0)
        mouse.up(app, 2, 0, copy=lambda text: got.append(text) or True)
        self.assertEqual(got, [])
        self.assertIsNone(app.sel)

    def test_release_clears_the_highlight_even_when_copy_fails(self):
        app = App()
        mouse.down(app, 0, 0)
        mouse.drag(app, 3, 0)
        mouse.up(app, 3, 0, copy=lambda text: False)
        self.assertIsNone(app.sel)
        self.assertEqual(app.notices, ["clipboard copy failed"])

    def test_drag_without_a_press_does_nothing(self):
        app = App()
        mouse.drag(app, 3, 0)
        self.assertIsNone(app.sel)
        self.assertFalse(app.dirty)

    def test_cells_are_clamped_to_the_screen(self):
        app = App()
        mouse.down(app, -4, 99)
        self.assertEqual(app.sel, {"a": (0, 3), "b": (0, 3)})

    def test_input_dispatch_runs_a_full_press_drag_copy(self):
        from unittest import mock
        from tui import input as dispatch

        app = App()
        dispatch.handle(app, ("mouse", ("down", 0, 0)))
        dispatch.handle(app, ("mouse", ("drag", 4, 1)))
        with mock.patch.object(mouse.clipboard, "copy", return_value=True) as copy:
            dispatch.handle(app, ("mouse", ("up", 4, 1)))
        copy.assert_called_once_with("hello world\nsecon")
        self.assertIsNone(app.sel)
        self.assertEqual(app.notices, ["copied 17 chars"])


if __name__ == "__main__":
    unittest.main()
