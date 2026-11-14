from . import spawn

TIMEOUT_MS = 120000


def run(root, cmd):
    code, out, err, dur = spawn.spawn(["sh", "-c", cmd], root, "", TIMEOUT_MS, kill_group=True)
    raw = (out + (b"\n" + err if err else b"")).decode("utf-8", "replace").strip()
    note = (raw.splitlines()[0][:180] if raw else "no output") + f" ms={dur}"
    return (code if isinstance(code, int) else 127), note
