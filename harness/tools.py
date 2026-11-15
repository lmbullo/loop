import os

from . import config, observe, spawn

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


def do_exec(a, obs_dir, name, sandbox=None, rel_base=None, saved=None, max_inline=None):
    argv = a.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
        return f"err bad_args exec requires argv:list[str], got {type(argv).__name__}"
    bad = shell_syntax(argv)
    if bad is not None:
        return bad
    cwd = config.resolve(a.get("cwd") or ".", sandbox or config.root())
    code, out, err, dur = spawn.spawn(argv, cwd, a.get("stdin", ""), a.get("timeout_ms", 120000), kill_group=True)
    raw = out + (b"\n--stderr--\n" + err if err else b"")
    return f"exit={code} ms={dur}\n" + observe.render_api(raw, obs_dir, name, max_inline=max_inline,
                                                          saved=saved, rel_base=rel_base)


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
        return f"err match={s.count(old)} expected=1 {a['path']}"
    i = s.find(old)
    s2 = s[:i] + new + s[i + len(old):]
    with open(path, "wb") as f:
        f.write(s2)
    lo, hi = max(0, i - 40), i + len(new) + 40
    return f"ok -{len(old)} +{len(new)} {a['path']}\n" + s2[lo:hi].decode("utf-8", "replace")


def dispatch(fn, a, obs_dir, name, sandbox=None, rel_base=None, saved=None, max_inline=None):
    if fn == "exec":
        return do_exec(a, obs_dir, name, sandbox, rel_base, saved, max_inline)
    if fn == "write":
        return do_write(a, sandbox)
    if fn == "edit":
        return do_edit(a, sandbox)
    return f"err unknown_tool {fn} expected one of exec, write, edit, done"
