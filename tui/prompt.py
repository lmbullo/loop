import unicodedata
MAX_ROWS = 10
HISTORY = 80
def cw(ch):
    if ch == "\t":
        return 4
    if ch == "\n":
        return 0
    if ord(ch) < 32 or ord(ch) == 127:
        return 1
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
def swidth(text):
    return sum(cw(ch) for ch in text)
def display(text):
    out = []
    for ch in text:
        if ch == "\t":
            out.append("    ")
        elif ch in "\r\n":
            out.append(" ")
        elif ord(ch) < 32 or ord(ch) == 127:
            out.append("?")
        else:
            out.append(ch)
    return "".join(out)
def wrap(text, width):
    width = max(1, width)
    rows, start, col, i, n = [], 0, 0, 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            rows.append({"start": start, "end": i, "text": text[start:i], "term": "\n"})
            i += 1
            start, col = i, 0
            continue
        w = cw(ch)
        if col + w > width and col > 0:
            rows.append({"start": start, "end": i, "text": text[start:i], "term": ""})
            i += 1 if text[i] == " " else 0
            start, col = i, 0
            continue
        col += w
        i += 1
    rows.append({"start": start, "end": n, "text": text[start:n], "term": ""})
    return rows
def _index_at(row, col):
    acc = 0
    for k, ch in enumerate(row["text"]):
        if acc >= col:
            return row["start"] + k
        acc += cw(ch)
    return row["end"]
def _word(ch):
    return ch.isalnum() or ch == "_"
class Prompt:
    def __init__(self):
        self.text = ""
        self.cursor = 0
        self.scroll = 0
        self.anchor = None
        self.history = []
        self.hist = None
        self.draft = ""
    def set(self, text):
        self.text, self.cursor, self.anchor = text, len(text), None
    def clear(self):
        self.text, self.cursor, self.scroll = "", 0, 0
        self.anchor = self.hist = self.draft = None
    def insert(self, text):
        i = max(0, min(self.cursor, len(self.text)))
        self.text = self.text[:i] + text + self.text[i:]
        self.cursor, self.anchor = i + len(text), None
    def backspace(self):
        if self.cursor > 0:
            i = self.cursor
            self.text = self.text[:i - 1] + self.text[i:]
            self.cursor, self.anchor = i - 1, None
    def delete(self):
        if self.cursor < len(self.text):
            i = self.cursor
            self.text = self.text[:i] + self.text[i + 1:]
            self.anchor = None
    def left(self):
        self.cursor, self.anchor = max(0, self.cursor - 1), None
    def right(self):
        self.cursor, self.anchor = min(len(self.text), self.cursor + 1), None
    def word_left(self):
        i, text = self.cursor, self.text
        while i > 0 and not _word(text[i - 1]) and not text[i - 1].isspace():
            i -= 1
        while i > 0 and text[i - 1].isspace():
            i -= 1
        while i > 0 and _word(text[i - 1]):
            i -= 1
        self.cursor, self.anchor = i, None
    def word_right(self):
        n, i, text = len(self.text), self.cursor, self.text
        while i < n and text[i].isspace():
            i += 1
        if i < n and not _word(text[i]):
            while i < n and not _word(text[i]) and not text[i].isspace():
                i += 1
        else:
            while i < n and _word(text[i]):
                i += 1
        self.cursor, self.anchor = i, None
    def word_back(self):
        old = self.cursor
        self.word_left()
        self.text = self.text[:self.cursor] + self.text[old:]
    def word_next(self):
        old = self.cursor
        self.word_right()
        self.text = self.text[:old] + self.text[self.cursor:]
        self.cursor, self.anchor = old, None
    def kill_start(self):
        self.text, self.cursor, self.anchor = "", 0, None
    def kill_end(self):
        self.text, self.anchor = self.text[:self.cursor], None
    def home(self, width):
        lay = self.layout(width)
        self.cursor = lay["rows"][lay["cursor_row"]]["start"]
        self.anchor = lay["cursor_row"]
    def end(self, width):
        lay = self.layout(width)
        self.cursor = lay["rows"][lay["cursor_row"]]["end"]
        self.anchor = lay["cursor_row"]
    def vertical(self, delta, width):
        lay = self.layout(width)
        tr = max(0, min(len(lay["rows"]) - 1, lay["cursor_row"] + delta))
        if tr != lay["cursor_row"]:
            self.cursor = _index_at(lay["rows"][tr], lay["cursor_col"])
            self.anchor = tr
    def page(self, delta, width, height):
        for _ in range(max(1, height - 1)):
            self.vertical(delta, width)
    def prev(self):
        if self.history:
            if self.hist is None:
                self.draft, self.hist = self.text, len(self.history) - 1
            else:
                self.hist = max(0, self.hist - 1)
            self.set(self.history[self.hist])
            self.scroll = 0
    def next(self):
        if self.hist is not None:
            if self.hist + 1 < len(self.history):
                self.hist += 1
                self.set(self.history[self.hist])
            else:
                self.hist = None
                self.set(self.draft or "")
            self.scroll = 0
    def remember(self):
        if self.text.strip() and (not self.history or self.history[-1] != self.text):
            self.history.append(self.text)
            del self.history[:-HISTORY]
        self.hist, self.draft = None, ""
    def layout(self, width, max_rows=MAX_ROWS):
        rows = wrap(self.text, width)
        n = len(rows)
        height = min(max_rows, MAX_ROWS, max(1, n))
        idx = max(0, min(self.cursor, len(self.text)))
        cr = None
        for j, row in enumerate(rows):
            if row["start"] <= idx <= row["end"]:
                if idx == row["end"] and row["term"] == "" and j + 1 < n and rows[j + 1]["start"] == idx:
                    cr = j + 1 if self.anchor == j + 1 else j
                else:
                    cr = j
                break
        cr = n - 1 if cr is None else cr
        cc = swidth(rows[cr]["text"][:idx - rows[cr]["start"]])
        if cr < self.scroll:
            self.scroll = cr
        if cr >= self.scroll + height:
            self.scroll = cr - height + 1
        self.scroll = max(0, min(self.scroll, max(0, n - height)))
        return {"rows": rows, "height": height, "cursor_row": cr, "cursor_col": cc,
                "n": n, "scroll": self.scroll}
