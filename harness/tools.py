"""The four tool bodies and one dispatch: exec, read, write, edit.

Every tool answers in one line or a bounded shape; nothing needs a second call
to become actionable. A wrong argument is answered with the exact fix, never
with a traceback, and an edit failure names the lines that did match.

`cmds` owns shell classification, `read` numbered file access, `edits` the
multi-hunk write, `observe` the byte bound. This module owns argument coercion
and routing. `SIGNATURES` is the one spelling of each call and `api.signatures()`
builds the header lines from it; `api.TOOLS` carries its own schema per name and
`tests/test_tools.py` pins that list (names and order) to `SIGNATURES`, so the
wire and the behaviour here cannot drift unnoticed.
"""

from . import cmds, config, edits, observe, read, spawn

import os

SIGNATURES = {
    "exec": "exec(cmd?|argv?, cwd?, stdin?, timeout_ms?)",
    "read": "read(path, start?, end?, find?, ctx?, offset?)",
    "write": "write(path, data, append?)",
    "edit": "edit(path, old?, new?, edits?, replace_all?)",
    "done": "done(result)",
}

EXEC_USAGE = 'err bad_args exec needs cmd:"<shell line>" or argv:["prog","arg"]'
WRITE_USAGE = "err bad_args write needs path:str and data:str"


def _exec_argv(a):
    """(argv, err): a shell string becomes sh -c, a list runs literally."""
    argv = a.get("argv")
    if isinstance(argv, str):
        return ["sh", "-c", argv], None
    if argv is None and isinstance(a.get("cmd"), str):
        return ["sh", "-c", a["cmd"]], None
    if argv is None and isinstance(a.get("command"), str):
        return ["sh", "-c", a["command"]], None
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
        return None, EXEC_USAGE
    return argv, None


def do_exec(a, obs_dir, name, sandbox=None, rel_base=None, saved=None, max_inline=None,
            ledger=None, obs_id=None, read_inline=None):
    argv, err = _exec_argv(a)
    if err is not None:
        return err
    bad = cmds.shell_syntax(argv)
    if bad is not None:
        return bad
    is_read = cmds.read_like(argv)
    cap = max_inline
    if is_read:
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
                               mode="read" if is_read else "mixed")


def do_write(a, sandbox=None):
    path = a.get("path")
    if not isinstance(path, str) or not path:
        return WRITE_USAGE
    data = a.get("data")
    alias = ""
    if data is None and isinstance(a.get("content"), str):
        data, alias = a["content"], " note=content taken as data"
    if not isinstance(data, str):
        return f"{WRITE_USAGE}, got data={type(data).__name__}; for a large body send two calls with append=true"
    full = config.resolve(path, sandbox)
    try:
        os_makedirs(full)
        prior = os.path.getsize(full) if os.path.exists(full) else None
        appending = a.get("append") is True
        with open(full, "a" if appending else "w", encoding="utf-8") as f:
            f.write(data)
    except OSError as e:
        return f"err {type(e).__name__}: {e}"
    note = "" if prior is None else (f" appended_to={prior}B" if appending else f" replaced={prior}B")
    return f"ok wrote {len(data.encode())}B {path}{note}{alias}"


def os_makedirs(path):
    import os
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def do_edit(a, sandbox=None):
    if not isinstance(a.get("path"), str) or not a["path"]:
        return "err bad_args edit needs path:str"
    return edits.apply(a, sandbox)


def do_read(a, sandbox=None, max_inline=None):
    return read.do_read(a, sandbox, max_inline)


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
    if fn == "read":
        text = do_read(a, sandbox, read_inline if read_inline is not None else max_inline)
        return _remember(text, ledger, obs_id)
    if fn == "write":
        return _remember(do_write(a, sandbox), ledger, obs_id)
    if fn == "edit":
        return _remember(do_edit(a, sandbox), ledger, obs_id)
    return (f"err unknown_tool {fn} expected one of exec, read, write, edit, done; "
            f"signatures: {', '.join(SIGNATURES[k] for k in sorted(SIGNATURES))}")
