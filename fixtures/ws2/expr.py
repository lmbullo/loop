import json
import re
import sys

TOKEN_RE = re.compile(r"\s*((?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[-+*/()])")


class ExprError(Exception):
    pass


def tokenize(s):
    toks = []
    pos = 0
    while pos < len(s):
        if s[pos].isspace():
            pos += 1
            continue
        m = TOKEN_RE.match(s, pos)
        if not m:
            word = re.match(r"[A-Za-z0-9_.]+", s[pos:])
            raise ExprError("invalid token: %r" % (word.group(0) if word else s[pos]))
        tok = m.group(1)
        if tok in "+-*/()":
            toks.append(tok)
        else:
            toks.append(float(tok))
        pos = m.end()
    return toks


class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self):
        tok = self.peek()
        if tok is None:
            raise ExprError("unexpected end of expression")
        self.i += 1
        return tok

    def parse(self):
        if not self.toks:
            raise ExprError("empty expression")
        value = self.expr()
        tok = self.peek()
        if tok is not None:
            raise ExprError("unexpected token: %r" % tok)
        return value

    def expr(self):
        value = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            rhs = self.term()
            if op == "+":
                value = value + rhs
            else:
                value = value - rhs
        return value

    def term(self):
        value = self.unary()
        while self.peek() in ("*", "/"):
            op = self.take()
            rhs = self.unary()
            if op == "*":
                value = value * rhs
            elif rhs == 0:
                raise ExprError("division by zero")
            else:
                value = value / rhs
        return value

    def unary(self):
        if self.peek() == "-":
            self.take()
            return -self.unary()
        if self.peek() == "+":
            self.take()
            return self.unary()
        return self.primary()

    def primary(self):
        tok = self.take()
        if tok == "(":
            value = self.expr()
            if self.peek() != ")":
                raise ExprError("expected ')'")
            self.take()
            return value
        if tok == ")":
            raise ExprError("unexpected ')'")
        if isinstance(tok, float):
            return tok
        raise ExprError("unexpected token: %r" % tok)


def evaluate(s):
    return Parser(tokenize(s)).parse()


def fail(message):
    sys.stderr.write(json.dumps({"error": message}) + "\n")
    return 2


def main(argv):
    if len(argv) != 2:
        return fail("usage: expr.py '<expression>'")
    try:
        result = evaluate(argv[1])
    except ExprError as exc:
        return fail(str(exc))
    except ZeroDivisionError:
        return fail("division by zero")
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
