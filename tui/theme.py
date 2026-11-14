import curses

# One pair per role. Every pair keeps the terminal background (-1), so the
# terminal background is never repainted.
PAIR = {"muted": 1, "strong": 2, "accent": 3, "ok": 4, "warn": 5, "err": 6}

# Restrained 256-color scale: neutral greys for chrome, muted hues only for
# state. The prompt box is deliberately grey in both focus states.
SCHEME = {
    "muted": 244,   # #808080 - labels, hints, idle, unfocused prompt
    "strong": 252,  # #d0d0d0 - status, focus, selection
    "accent": 67,   # #5f87af - running
    "ok": 108,      # #87af87 - complete
    "warn": 179,    # #d7af5f - notice
    "err": 167,     # #d75f5f - error
}
BASE = {  # eight-color terminals: the same roles from the basic palette
    "muted": curses.COLOR_WHITE,
    "strong": curses.COLOR_WHITE,
    "accent": curses.COLOR_BLUE,
    "ok": curses.COLOR_GREEN,
    "warn": curses.COLOR_YELLOW,
    "err": curses.COLOR_RED,
}

PROMPT_IDLE = "muted"
PROMPT_FOCUS = "strong"
STATE = {"running": "accent", "complete": "ok", "corrupt": "err"}


def init_colors():
    try:
        curses.start_color()
        curses.use_default_colors()
        scheme = SCHEME if curses.COLORS >= 256 else BASE
    except curses.error:
        return
    for role, pair in PAIR.items():
        try:
            curses.init_pair(pair, scheme[role], -1)
        except curses.error:
            pass


def attr(role):
    if role not in PAIR:
        return 0
    try:
        return curses.color_pair(PAIR[role])
    except curses.error:
        return 0


def state_role(state):
    return STATE.get((state or "").lower(), "muted")


def status_role(snap):
    state = ((snap or {}).get("daemon") or {}).get("state", "").lower()
    return "err" if state and state != "running" else "muted"
