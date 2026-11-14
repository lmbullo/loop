import time

from .mouse import sgr_mouse, x10_mouse


CTRL = {
    0x01: "home", 0x02: "left", 0x03: "ctrl_c", 0x04: "delete",
    0x05: "end", 0x06: "right", 0x07: "retry", 0x08: "backspace",
    0x09: "tab", 0x0a: "newline", 0x0b: "kill_end", 0x0c: "redraw",
    0x0d: "enter", 0x0e: "hist_next", 0x0f: "focus_queue",
    0x10: "hist_prev", 0x11: "ctrl_q", 0x12: "refresh",
    0x15: "kill_start", 0x17: "word_back", 0x18: "ctrl_x", 0x7f: "backspace",
}

CSI = {
    b"\x1b[A": "up", b"\x1b[B": "down", b"\x1b[C": "right", b"\x1b[D": "left",
    b"\x1b[H": "home", b"\x1b[F": "end",
    b"\x1b[1~": "home", b"\x1b[2~": "insert", b"\x1b[3~": "delete",
    b"\x1b[4~": "end", b"\x1b[5~": "page_up", b"\x1b[6~": "page_down",
    b"\x1b[7~": "home", b"\x1b[8~": "end", b"\x1b[Z": "backtab",
    # Application cursor mode (DECCKM): keypad(True) sends smkx, so xterm and
    # friends report the arrows as SS3. Accept them as well as CSI arrows.
    b"\x1bOA": "up", b"\x1bOB": "down", b"\x1bOC": "right", b"\x1bOD": "left",
    b"\x1bOH": "home", b"\x1bOF": "end",
    b"\x1b[1;2A": "shift_up", b"\x1b[1;2B": "shift_down",
    b"\x1b[1;2C": "right", b"\x1b[1;2D": "left",
    b"\x1b[1;3A": "hist_prev", b"\x1b[1;3B": "hist_next",
    b"\x1b[1;3C": "word_right", b"\x1b[1;3D": "word_left",
    b"\x1b[1;5A": "hist_prev", b"\x1b[1;5B": "hist_next",
    b"\x1b[1;5C": "word_right", b"\x1b[1;5D": "word_left",
    b"\x1b[1;9A": "hist_prev", b"\x1b[1;9B": "hist_next",
    b"\x1b[1;9C": "word_right", b"\x1b[1;9D": "word_left",
    b"\x1b[3;5~": "word_back", b"\x1b[3;3~": "word_back",
}

PASTE_ON = b"\x1b[200~"
PASTE_OFF = b"\x1b[201~"


def _text(raw):
    return raw.decode("utf-8", "replace")


def _paste(raw):
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode("utf-8", "replace")


def _csi_end(b, start):
    i = start
    while i < len(b):
        c = b[i]
        if 0x40 <= c <= 0x7e:
            return i + 1
        i += 1
    return -1


def _modified_enter(seq):
    body = seq[2:-1].decode("ascii", "ignore")
    if seq.endswith(b"u"):
        parts = body.split(";")
        try:
            code = int(parts[0])
            mod = int(parts[1]) if len(parts) > 1 else 1
        except ValueError:
            return None
        if code == 13:
            return "enter" if mod == 1 else "newline"
    if seq.endswith(b"~") and body.startswith("27;"):
        parts = body.split(";")
        if len(parts) >= 3 and parts[2] == "13":
            return "enter" if parts[1] == "1" else "newline"
    return None


class Parser:
    def __init__(self):
        self.buf = bytearray()
        self.paste = False
        self.pending = 0.0

    def feed(self, data):
        self.buf.extend(data)
        self.pending = time.time() if self.buf else 0.0

    def flush(self, timeout=0.06):
        if bytes(self.buf) == b"\x1b" and self.pending and time.time() - self.pending >= timeout:
            self.buf.clear()
            return [("key", "esc")]
        return []

    def events(self):
        out = []
        while self.buf:
            b = bytes(self.buf)
            if self.paste:
                end = b.find(PASTE_OFF)
                if end < 0:
                    break
                out.append(("paste", _paste(b[:end])))
                del self.buf[:end + len(PASTE_OFF)]
                self.paste = False
                continue
            if b.startswith(PASTE_ON):
                del self.buf[:len(PASTE_ON)]
                self.paste = True
                continue
            if b[0] == 0x1b:
                ev, used, need = self._esc(b)
                if need:
                    break
                del self.buf[:used]
                if ev is not None:
                    out.append(ev)
                continue
            c = b[0]
            if c in CTRL:
                del self.buf[:1]
                out.append(("key", CTRL[c]))
                continue
            if c < 0x20:
                del self.buf[:1]
                continue
            i = 1
            while i < len(b) and b[i] >= 0x20 and b[i] != 0x7f and b[i] != 0x1b:
                i += 1
            raw = b[:i]
            del self.buf[:i]
            text = _text(raw)
            if text:
                out.append(("text", text))
        return out

    def _esc(self, b):
        if len(b) == 1:
            return None, 0, True
        if b.startswith(b"\x1b[M"):
            if len(b) < 6:
                return None, 0, True
            return x10_mouse(b), 6, False
        if b.startswith(b"\x1b[") or b.startswith(b"\x1bO"):
            end = _csi_end(b, 2)
            if end < 0:
                return None, 0, True
            seq = b[:end]
            if seq in CSI:
                return ("key", CSI[seq]), end, False
            ev = sgr_mouse(seq)
            if ev:
                return ev, end, False
            mod = _modified_enter(seq)
            if mod:
                return ("key", mod), end, False
            return None, end, False
        if b[1:2] in (b"\r", b"\n"):
            return ("key", "newline"), 2, False
        c = b[1]
        if c == 0x7f:
            return ("key", "word_back"), 2, False
        if c in (ord("b"), ord("B")):
            return ("key", "word_left"), 2, False
        if c in (ord("f"), ord("F")):
            return ("key", "word_right"), 2, False
        if c in (ord("d"), ord("D")):
            return ("key", "word_next"), 2, False
        if 0x20 <= c < 0x7f:
            return ("text", chr(c)), 2, False
        return ("key", "esc"), 1, False
