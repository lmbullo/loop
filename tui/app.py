import curses
import locale
import os
import select
import sys
import termios
import time
import tty

from . import (frame, input, keys, loginput, model, prompt, render,
               select as selection, theme, worker)

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
        self.qscroll = 0
        self.tfollow = True
        self.qfollow = True
        self.tview = {"n": 1, "vis": 1, "sel": 0, "scroll": 0}
        self.quit = False
        self.log = None
        self.sel = None
        self.prompt_from = "task"
        self.h, self.w = scr.getmaxyx()
        self.frame = frame.Frame(scr, sync=True)
        self.frame.resize(self.w, self.h)
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

    def invalidate(self):
        """Force a full repaint, e.g. after the terminal was cleared."""
        self.frame.invalidate()
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
            self.scr.erase()
        except curses.error:
            pass
        self.frame.resize(nw, nh)
        self.frame.invalidate()
        self.dirty = True

    def paint(self):
        snap = self.snapshot()
        if self.focus == "queue" and not snap["queue"]:
            self.focus = "task"
            self.dirty = True
        now = time.time()
        loginput.refresh_log(self, now)
        if snap["version"] != self.last_version or self.dirty or now - self.last_draw > 0.5:
            max_rows = max(1, self.h - 2)
            ph = 0
            if self.focus == "prompt":
                ph = self.prompt.layout(self.content_width(), max_rows)["height"] + 2
            if self.prompt_h is not None and ph != self.prompt_h:
                self.frame.invalidate()
            self.prompt_h = ph
            self.last_version = snap["version"]
            self.last_draw = now
            self.dirty = False
            self.frame.resize(self.w, self.h)
            self.frame.highlight(selection.spans(self.sel, self.w))
            self.layout = render.draw(self.frame, snap, self.prompt, self.w, self.h,
                                      self.focus, self.qsel, self.tsel, self.tscroll,
                                      self.log, self.qscroll, self.tfollow,
                                      self.qfollow)
            if self.layout:
                tv = self.layout.get("task")
                if tv:
                    self.tview = tv
                    self.tsel = tv["sel"]
                    self.tscroll = tv["scroll"]
                    self.tfollow = tv.get("follow", self.tfollow)
                qv = self.layout.get("queue") or {}
                if qv:
                    self.qscroll = qv.get("scroll", self.qscroll)
                    self.qfollow = qv.get("follow", self.qfollow)
                lv = self.layout.get("log")
                if lv and self.log is not None:
                    self.log["sel"] = lv["sel"] if lv["sel"] is not None else 0
                    self.log["scroll"] = lv["scroll"]
                    self.log["vis"] = max(1, lv["vis"])
                    self.log["rows"] = max(0, lv.get("n") or 0)
                    self.log["follow"] = lv.get("follow", True)

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
        os.write(1, b"\x1b[?2004h\x1b[?1002h\x1b[?1006h")
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
                os.write(1, b"\x1b[?2004l\x1b[?1006l\x1b[?1002l")
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
