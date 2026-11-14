"""Clipboard writes: an OSC 52 sequence plus an installed local helper.

OSC 52 lets the terminal own the clipboard without X11/Wayland access and works
over ssh; tmux needs the sequence wrapped in its passthrough. A local helper is
tried as well so a terminal that ignores OSC 52 still copies.
"""

import base64
import os
import shutil
import subprocess

# Terminals and tmux often cap the base64 payload; larger text still goes to a
# local helper when one is installed.
MAX = 100000
COMMANDS = (("wl-copy",), ("xclip", "-selection", "clipboard"),
            ("xsel", "--clipboard", "--input"), ("pbcopy",))


def sequence(text, env=None):
    payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
    osc = f"\x1b]52;c;{payload}\x07"
    if (os.environ if env is None else env).get("TMUX"):
        return "\x1bPtmux;\x1b" + osc + "\x1b\\"
    return osc


def helper(text, which=None, run=None):
    """Feed the text to the first installed clipboard command; name it or None."""
    which = which or shutil.which
    run = run or subprocess.run
    for cmd in COMMANDS:
        if not which(cmd[0]):
            continue
        try:
            done = run(list(cmd), input=text.encode("utf-8"), timeout=1,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            continue
        if getattr(done, "returncode", 0) == 0:
            return cmd[0]
    return None


def copy(text, write=None, env=None, which=None, run=None):
    """Copy ``text``; return True when at least one transport accepted it."""
    if not text:
        return False
    wrote = False
    if len(text) <= MAX:
        write = write or (lambda data: os.write(1, data))
        try:
            write(sequence(text, env).encode("ascii"))
            wrote = True
        except OSError:
            pass
    return bool(helper(text, which, run)) or wrote
