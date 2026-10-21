import os

from . import config, observe, spawn


def do_exec(a, obs_dir, name, sandbox=None, rel_base=None, saved=None):
    cwd = config.resolve(a.get("cwd") or ".", sandbox or config.root())
    code, out, err, dur = spawn.spawn(a["argv"], cwd, a.get("stdin", ""), a.get("timeout_ms", 120000), kill_group=True)
    raw = out + (b"\n--stderr--\n" + err if err else b"")
    return f"exit={code} ms={dur}\n" + observe.render_api(raw, obs_dir, name, saved=saved, rel_base=rel_base)


def do_write(a, sandbox=None):
    data = a.get("data")
    if not isinstance(data, str):
        return f"err bad_args write requires data:str, got {type(data).__name__}"
    path = config.resolve(a["path"], sandbox)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        prior = os.path.getsize(path) if os.path.exists(path) else None
        appending = a.get("append") is True
        with open(path, "a" if appending else "w", encoding="utf-8") as f:
            f.write(data)
        note = "" if prior is None else (f" appended_to={prior}B" if appending else f" replaced={prior}B")
        return f"ok wrote {len(data.encode())}B {a['path']}{note}"
    except OSError as e:
        return f"err {type(e).__name__}: {e}"


def do_edit(a, sandbox=None):
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
        return f"err match={s.count(old)} expected=1"
    i = s.find(old)
    s2 = s[:i] + new + s[i + len(old):]
    with open(path, "wb") as f:
        f.write(s2)
    lo, hi = max(0, i - 40), i + len(new) + 40
    return f"ok -{len(old)} +{len(new)} {a['path']}\n" + s2[lo:hi].decode("utf-8", "replace")


def dispatch(fn, a, obs_dir, name, sandbox=None, rel_base=None, saved=None):
    if fn == "exec":
        return do_exec(a, obs_dir, name, sandbox, rel_base, saved)
    if fn == "write":
        return do_write(a, sandbox)
    return do_edit(a, sandbox)
