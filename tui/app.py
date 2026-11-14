import curses
import locale
import os
import select
import sys
import termios
import time
import tty

from . import input, keys, model, prompt, render, theme, worker

USAGE = "usage: python3 run.py tui\n\ninteractive terminal client for this tree's daemon"


class App:
    def __init__(self, scr):
        self.scr = scr
        self.model = model.Model()
        self.worker = worker.Worker(self.model)
        self.prompt = prompt.Prompt()
        self.parser = keys.Parser()
        self.focus = "task"
        self.qsel = 0
        self.tsel = 0
        self.tscroll = 0
        self.tview = {"n": 1, "vis": 1, "sel": 0, "scroll": 0}
        self.quit = False
        self.h, self.w = scr.getmaxyx()
        self.dirty = True
        self.last_version = -1
        self.last_draw = 0.0
        self.layout = None
        self.prompt_h = None

    def content_width(self):
        return max(1, self.w)

    def say(self, text):
        self.model.say(text)
        self.dirty = True

    def snapshot(self):
        return self.model.snapshot()

    def resize(self):
        try:
            size = os.get_terminal_size(sys.stdin.fileno())
            nh, nw = size.lines, size.columns
        except OSError:
            nh, nw = self.scr.getmaxyx()
        if (nh, nw) == (self.h, self.w):
            return
        self.h, self.w = nh, nw
        try:
            curses.resizeterm(nh, nw)
            self.scr.clear()
        except curses.error:
            pass
        self.dirty = True

    def paint(self):
        snap = self.snapshot()
        now = time.time()
        if snap["version"] != self.last_version or self.dirty or now - self.last_draw > 0.5:
            max_rows = max(1, self.h - 2)
            ph = 0
            if self.focus == "prompt":
                ph = self.prompt.layout(self.content_width(), max_rows)["height"] + 1
            if self.prompt_h is not None and ph != self.prompt_h:
                try:
                    self.scr.clear()
                except curses.error:
                    pass
            self.prompt_h = ph
            self.last_version = snap["version"]
            self.last_draw = now
            self.dirty = False
            self.layout = render.draw(self.scr, snap, self.prompt, self.w, self.h,
                                      self.focus, self.qsel, self.tsel, self.tscroll)
            if self.layout:
                tv = self.layout.get("task")
                if tv:
                    self.tview = tv
                    self.tsel = tv["sel"]
                    self.tscroll = tv["scroll"]

    def run(self):
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        theme.init_colors()
        try:
            self.scr.keypad(True)
        except curses.error:
            pass
        fd = sys.stdin.fileno()
        os.write(1, b"\x1b[?2004h")
        try:
            old_term = termios.tcgetattr(fd)
            tty.setraw(fd)
        except (OSError, termios.error, curses.error):
            old_term = None
        self.worker.start()
        try:
            while not self.quit:
                self.resize()
                ready, _, _ = select.select([fd], [], [], 0.06)
                if ready:
                    try:
                        data = os.read(fd, 65536)
                    except OSError:
                        break
                    if not data:
                        break
                    self.parser.feed(data)
                for event in self.parser.events():
                    input.handle(self, event)
                for event in self.parser.flush():
                    input.handle(self, event)
                self.paint()
        finally:
            try:
                os.write(1, b"\x1b[?2004l")
            except OSError:
                pass
            if old_term is not None:
                try:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_term)
                except (OSError, termios.error):
                    pass
            self.worker.stop()
            try:
                curses.curs_set(1)
            except curses.error:
                pass
        return 0


def main(argv):
    if argv and argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    if argv:
        print(f"err tui unknown argument {argv[0]!r}\n{USAGE}", file=sys.stderr)
        return 2
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("err tui requires a terminal", file=sys.stderr)
        return 2
    locale.setlocale(locale.LC_ALL, "")
    try:
        return curses.wrapper(lambda scr: App(scr).run())
    except KeyboardInterrupt:
        return 0
