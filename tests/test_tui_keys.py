import unittest

from tui import keys


class ArrowParserTest(unittest.TestCase):
    def test_ss3_arrows_parse_as_arrows(self):
        parser = keys.Parser()
        parser.feed(b"\x1bOA\x1bOB\x1bOC\x1bOD\x1bOH\x1bOF")
        self.assertEqual(parser.events(), [
            ("key", "up"), ("key", "down"), ("key", "right"),
            ("key", "left"), ("key", "home"), ("key", "end")])

    def test_shift_arrows_are_distinct_from_plain_arrows(self):
        parser = keys.Parser()
        parser.feed(b"\x1b[1;2A\x1b[1;2B\x1b[A\x1b[B")
        self.assertEqual(parser.events(), [("key", "shift_up"),
                                           ("key", "shift_down"),
                                           ("key", "up"), ("key", "down")])


class ControlAndWheelParserTest(unittest.TestCase):
    def test_ctrl_x_parses_as_its_own_key(self):
        parser = keys.Parser()
        parser.feed(b"\x18")
        self.assertEqual(parser.events(), [("key", "ctrl_x")])

    def test_wheel_events_are_scroll_up_and_scroll_down(self):
        parser = keys.Parser()
        parser.feed(b"\x1b[<64;10;5M\x1b[<65;10;5M")
        self.assertEqual(parser.events(), [("key", "scroll_up"),
                                           ("key", "scroll_down")])
        parser.feed(b"\x1b[M" + bytes([64 + 32, 10 + 32, 5 + 32]))
        self.assertEqual(parser.events(), [("key", "scroll_up")])

    def test_wheel_modifiers_keep_the_direction(self):
        parser = keys.Parser()
        parser.feed(b"\x1b[<68;10;5M\x1b[<69;10;5M")
        self.assertEqual(parser.events(), [("key", "scroll_up"),
                                           ("key", "scroll_down")])


class MouseParserTest(unittest.TestCase):
    def test_sgr_left_press_drag_and_release_carry_screen_cells(self):
        parser = keys.Parser()
        parser.feed(b"\x1b[<0;10;5M\x1b[<32;12;5M\x1b[<0;12;5m")
        self.assertEqual(parser.events(), [
            ("mouse", ("down", 9, 4)), ("mouse", ("drag", 11, 4)),
            ("mouse", ("up", 11, 4))])

    def test_x10_left_press_drag_and_release_carry_screen_cells(self):
        parser = keys.Parser()
        parser.feed(b"\x1b[M" + bytes([32, 42, 37]))
        parser.feed(b"\x1b[M" + bytes([32 + 32, 44, 37]))
        parser.feed(b"\x1b[M" + bytes([32 + 3, 44, 37]))
        self.assertEqual(parser.events(), [
            ("mouse", ("down", 9, 4)), ("mouse", ("drag", 11, 4)),
            ("mouse", ("up", 11, 4))])

    def test_shift_and_non_left_buttons_are_dropped(self):
        parser = keys.Parser()
        parser.feed(b"\x1b[<4;10;5M\x1b[<1;10;5M\x1b[<2;10;5M")
        self.assertEqual(parser.events(), [])


if __name__ == "__main__":
    unittest.main()
