import json
import sys

from . import render
from .prompt import Prompt


class Screen:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.grid = [[" "] * width for _ in range(height)]
        self.y = self.x = 0

    def getmaxyx(self):
        return self.height, self.width

    def erase(self):
        self.grid = [[" "] * self.width for _ in range(self.height)]

    clear = erase

    def addstr(self, y, x, text, attr=0):
        if 0 <= y < self.height:
            for i, ch in enumerate(str(text)):
                if 0 <= x + i < self.width:
                    self.grid[y][x + i] = ch

    def move(self, y, x):
        self.y, self.x = y, x

    def noutrefresh(self):
        pass

    def keypad(self, flag):
        pass


def lines(screen):
    return ["".join(row).rstrip() for row in screen.grid]


def parse(argv):
    width, height, focus, qsel, path = 80, 24, "task", 0, None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--size" and i + 1 < len(argv):
            width, height = (int(v) for v in argv[i + 1].lower().split("x"))
            i += 1
        elif arg == "--focus" and i + 1 < len(argv):
            focus = argv[i + 1]
            i += 1
        elif arg == "--qsel" and i + 1 < len(argv):
            qsel = int(argv[i + 1])
            i += 1
        elif arg.startswith("-") and arg != "-":
            raise ValueError(f"unknown arg {arg}")
        else:
            path = arg
        i += 1
    return width, height, focus, qsel, path


def main(argv):
    try:
        width, height, focus, qsel, path = parse(argv)
    except ValueError as e:
        print(f"err {e}", file=sys.stderr)
        return 2
    if path is None:
        from . import client
        snap = client.snapshot()
    else:
        if path == "-":
            raw = sys.stdin.read()
        else:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
        try:
            snap = json.loads(raw)
        except ValueError as e:
            print(f"err snapshot is not json: {e}", file=sys.stderr)
            return 2
    if not isinstance(snap, dict) or not isinstance(snap.get("daemon"), dict):
        print("err snapshot needs daemon/current/queue/done; capture with a tui client", file=sys.stderr)
        return 2
    screen = Screen(width, height)
    render.draw(screen, snap, Prompt(), width, height, focus, qsel)
    sys.stdout.write("".join(line + "\n" for line in lines(screen)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
