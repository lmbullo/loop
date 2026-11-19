import os
import shlex

from . import config, observe, spawn

READ_WORDS = frozenset((
    "cat", "head", "tail", "sed", "grep", "egrep", "fgrep", "rg", "ag", "ack",
    "ls", "find", "tree", "wc", "stat", "file", "nl", "diff", "git"))
GIT_READ = frozenset(("diff", "show", "log", "status", "grep", "blame"))

SHELL_OPS = frozenset(("|", "||", "&&", ";", "&", ">", ">>", "<", "<<", "2>", "2>>", "&>", "|&"))
SHELL_WORDS = frozenset((
    "cd", "for", "while", "until", "if", "then", "elif", "else", "fi", "case", "esac",
    "do", "done", "select", "function", "export", "unset", "source", "alias", "unalias",
    "eval", "shift", "trap", "ulimit", "umask", "return", "break", "continue", "read",
    "local", "declare", "typeset"))
SHELL_HINT = 'exec has no shell. Use ["sh","-c","..."] for pipes, redirects or compound commands.'


def shell_syntax(argv):
    for tok in argv:
        if tok in SHELL_OPS:
            return f"err shell_syntax argv contains {tok!r} as a standalone token; {SHELL_HINT}"
    if argv[0] in SHELL_WORDS:
        return f"err shell_syntax argv[0]={argv[0]!r} is a shell keyword; {SHELL_HINT}"
    return None


def read_like(argv):
    """True for commands whose output is content, not a build/test report."""
    if not argv:
        return False
    if (os.path.basename(argv[0]) in ("sh", "bash", "dash", "zsh", "ksh")
            and len(argv) >= 3 and argv[1] in ("-c", "-lc")):
        try:
            argv = shlex.split(argv[2])
        except ValueError:
            argv = argv[2].split()
        if not argv:
            return False
    first = os.path.basename(argv[0])
    if first == "git":
        return len(argv) > 1 and argv[1] in GIT_READ
    return first in READ_WORDS


def do_exec(a, obs_dir, name, sandbox=None, rel_base=None, saved=None, max_inline=None,
            ledger=None, obs_id=None, read_inline=None):
    argv = a.get("argv")
    if isinstance(argv, str):
        argv = ["sh", "-c", argv]
    if argv is None and isinstance(a.get("cmd"), str):
        argv = ["sh", "-c", a["cmd"]]
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
        hint = "; send argv:list[str] or cmd:str for a shell command"
        return f"err bad_args exec requires argv:list[str] or cmd:str, got {type(argv).__name__}{hint}"
    bad = shell_syntax(argv)
    if bad is not None:
        return bad
    read = read_like(argv)
    cap = max_inline
    if read:
        cap = read_inline if read_inline is not None else config.read_inline()
        if max_inline is not None and read_inline is None:
            cap = max_inline
    cwd = config.resolve(a.get("cwd") or ".", sandbox or config.root())
    code, out, err, dur = spawn.spawn(
        argv, cwd, a.get("stdin", ""), a.get("timeout_ms", config.exec_timeout_ms()),
        kill_group=True)
    return observe.render_exec(code, dur, out, err, obs_dir, name, sandbox=sandbox,
                               rel_base=rel_base, saved=saved, max_inline=cap,
                               ledger=ledger, obs_id=obs_id,
                               mode="read" if read else "mixed")


def do_write(a, sandbox=None):
    if not isinstance(a.get("path"), str) or not a["path"]:
        return "err bad_args write requires path:str"
    data = a.get("data")
    alias = ""
    if data is None and isinstance(a.get("content"), str):
        data, alias = a["content"], " note=content taken as data"
    if not isinstance(data, str):
        return f"err bad_args write requires data:str (content accepted), got {type(data).__name__}"
    path = config.resolve(a["path"], sandbox)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        prior = os.path.getsize(path) if os.path.exists(path) else None
        appending = a.get("append") is True
        with open(path, "a" if appending else "w", encoding="utf-8") as f:
            f.write(data)
        note = "" if prior is None else (f" appended_to={prior}B" if appending else f" replaced={prior}B")
        return f"ok wrote {len(data.encode())}B {a['path']}{note}{alias}"
    except OSError as e:
        return f"err {type(e).__name__}: {e}"


def _line_numbers(data, needle, limit=8):
    out, start = [], 0
    while len(out) < limit:
        i = data.find(needle, start)
        if i < 0:
            break
        n = data.count(b"\n", 0, i) + 1
        if n not in out:
            out.append(n)
        start = i + 1
    return out


def _whitespace_near(data, old):
    """Line where the stripped old lines occur in order, if any."""
    pos, first = 0, None
    for part in old.splitlines():
        part = part.strip()
        if not part:
            continue
        i = data.find(part, pos)
        if i < 0:
            return None
        if first is None:
            first = data.count(b"\n", 0, i) + 1
        pos = i + len(part)
    return first


def edit_error(data, old, path):
    """Explain a non-unique match without spending a read turn."""
    count = data.count(old)
    if count == 1:
        return None
    out = [f"err match={count} expected=1 {path}"]
    if count == 0 and b"\r\n" in data and b"\r" not in old:
        crlf = old.replace(b"\n", b"\r\n")
        if data.count(crlf) == 1:
            out.append("hint=file uses CRLF; include \\r\\n in old")
            return " ".join(out)
    near = _whitespace_near(data, old) if count == 0 else None
    if near is not None:
        out.append(f"near={near} hint=check whitespace/indent")
    else:
        lines = _line_numbers(data, old) if count else []
        if not lines and count == 0:
            for part in old.splitlines():
                part = part.strip()
                if part:
                    lines = _line_numbers(data, part, 2)
                    if lines:
                        break
        if lines:
            out.append("lines=" + ",".join(str(n) for n in lines))
        if count > 1:
            out.append("hint=extend old with adjacent unique text")
    return " ".join(out)


def do_edit(a, sandbox=None):
    if not isinstance(a.get("path"), str) or not a["path"]:
        return "err bad_args edit requires path:str"
    for k in ("old", "new"):
        if not isinstance(a.get(k), str):
            return f"err bad_args edit requires old:str and new:str; {k} incorrect"
    path = config.resolve(a["path"], sandbox)
    try:
        with open(path, "rb") as f:
            s = f.read()
    except OSError as e:
        return f"err {type(e).__name__}: {e}"
    old, new = a["old"].encode(), a["new"].encode()
    if s.count(old) != 1:
        return edit_error(s, old, a["path"])
    i = s.find(old)
    s2 = s[:i] + new + s[i + len(old):]
    with open(path, "wb") as f:
        f.write(s2)
    lo, hi = max(0, i - 40), i + len(new) + 40
    return f"ok -{len(old)} +{len(new)} {a['path']}\n" + s2[lo:hi].decode("utf-8", "replace")


def _remember(text, ledger, obs_id):
    if ledger is None:
        return text
    raw = text.encode()
    prior = ledger.get(raw)
    if prior is not None and prior.get("id") != obs_id:
        return observe.same(prior)
    ledger.add(raw, obs_id or "obs", None, True)
    return text


def dispatch(fn, a, obs_dir, name, sandbox=None, rel_base=None, saved=None, max_inline=None,
             ledger=None, obs_id=None, read_inline=None):
    if fn == "exec":
        return do_exec(a, obs_dir, name, sandbox, rel_base, saved, max_inline,
                       ledger, obs_id, read_inline)
    if fn == "write":
        return _remember(do_write(a, sandbox), ledger, obs_id)
    if fn == "edit":
        return _remember(do_edit(a, sandbox), ledger, obs_id)
    return f"err unknown_tool {fn} expected one of exec, write, edit, done"
