"""Classify one command line: content to keep whole, or a report to shape.

A compound line counts as read-like only when every segment is, so
`cd x && sed -n 1,80p f` keeps the contiguous read bound instead of falling
back to the mixed head/tail shape. A misclassified read costs a whole extra
turn to fetch the elided half, so a doubt resolves to `mixed`.
"""

import os
import shlex

SHELLS = frozenset(("sh", "bash", "dash", "zsh", "ksh"))
SHELL_OPS = frozenset(("|", "||", "&&", ";", "&", ">", ">>", "<", "<<", "2>",
                       "2>>", "&>", "|&"))
SHELL_WORDS = frozenset((
    "cd", "for", "while", "until", "if", "then", "elif", "else", "fi", "case",
    "esac", "do", "done", "select", "function", "export", "unset", "source",
    "alias", "unalias", "eval", "shift", "trap", "ulimit", "umask", "return",
    "break", "continue", "read", "local", "declare", "typeset"))
READ_WORDS = frozenset((
    "cat", "head", "tail", "sed", "grep", "egrep", "fgrep", "rg", "ag", "ack",
    "ls", "find", "tree", "wc", "stat", "file", "nl", "diff", "awk", "sort",
    "uniq", "cut", "tr", "column", "basename", "dirname", "realpath", "readlink",
    "pwd", "echo", "printf", "which", "whoami", "date", "env", "id", "du", "df",
    "sha256sum", "md5sum", "jq", "git", "python3", "python"))
GIT_READ = frozenset(("diff", "show", "log", "status", "grep", "blame", "describe",
                      "rev-parse", "ls-files", "shortlog", "remote", "branch",
                      "cat-file", "show-ref"))
NEUTRAL = frozenset(("cd", "true", "false", "export", "set", "unset", "test",
                     "[", ":", "sleep", "wait"))
WRITE_OPS = frozenset((">", ">>", "&>", "2>"))
OPS = ("2>&1", "&&", "||", ">>", "&>", "2>", "|&", ";", "|", "&", ">", "<", "\n")
SHELL_HINT = 'exec has no shell. Use cmd:"..." for pipes, redirects or compound commands.'


def shell_syntax(argv):
    """Reject the argv forms that a literal spawn cannot honour."""
    for tok in argv:
        if tok in SHELL_OPS:
            return f"err shell_syntax argv contains {tok!r} as a standalone token; {SHELL_HINT}"
    if argv[0] in SHELL_WORDS:
        return f"err shell_syntax argv[0]={argv[0]!r} is a shell keyword; {SHELL_HINT}"
    return None


def segments(cmd):
    """Split a shell line on top-level operators, keeping quoted text intact."""
    out, buf, quote, i = [], [], None, 0
    while i < len(cmd):
        c = cmd[i]
        if quote is not None:
            buf.append(c)
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "\"'":
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < len(cmd):
            buf.append(cmd[i:i + 2])
            i += 2
            continue
        for op in OPS:
            if cmd.startswith(op, i):
                out.append("".join(buf))
                out.append(op)
                buf = []
                i += len(op)
                break
        else:
            buf.append(c)
            i += 1
    out.append("".join(buf))
    return out


def _argv_read(argv, depth=0):
    if not argv:
        return True
    first = os.path.basename(argv[0])
    if first in SHELLS and len(argv) >= 3 and argv[1] in ("-c", "-lc", "-cl"):
        return cmd_read_like(argv[2], depth + 1) if depth < 3 else False
    if first == "git":
        return len(argv) > 1 and argv[1] in GIT_READ
    if first in ("python3", "python"):
        return len(argv) in (2, 3) and "-c" in argv
    return first in READ_WORDS


def cmd_read_like(cmd, depth=0):
    """True when every segment of a shell line only reads."""
    if depth > 3 or not isinstance(cmd, str):
        return False
    rest, i = segments(cmd), 0
    while i < len(rest):
        seg = rest[i]
        if seg in WRITE_OPS:
            target = rest[i + 1].strip() if i + 1 < len(rest) else ""
            if target not in ("/dev/null", ""):
                return False
            i += 2
            continue
        if seg in ("&&", "||", ";", "|", "&", "|&", "<", "2>&1", "\n", ""):
            i += 1
            continue
        try:
            argv = shlex.split(seg)
        except ValueError:
            return False
        if argv and os.path.basename(argv[0]) not in NEUTRAL and not _argv_read(argv, depth):
            return False
        i += 1
    return True


def read_like(argv):
    """True for commands whose output is content, not a build/test report.

    One rule for both forms: a literal argv and the inner line of `sh -c` must
    classify alike, so a wrapper cannot turn a test run into a contiguous read.
    """
    return bool(argv) and _argv_read(list(argv))
