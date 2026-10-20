import hashlib
import os
import re

from . import config

V1_HEAD = 600
V1_TAIL = 400
V2_MAX_TEXT = 2000
V2_MAX_LINES = 40
ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")


def is_binary(b, sample=4096, threshold=0.20):
    s = b[:sample]
    bad = sum(1 for c in s if c < 9 or (13 < c < 32) or c > 126)
    return bool(s) and bad / len(s) > threshold


def save(raw, obs_dir, name, rel_base=None):
    os.makedirs(obs_dir, exist_ok=True)
    path = os.path.join(obs_dir, name)
    with open(path, "wb") as f:
        f.write(raw)
    if rel_base:
        return os.path.relpath(path, rel_base)
    return config.display(path)


def digest(raw):
    return f"kind=binary bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()[:16]} head_hex={raw[:24].hex()}"


def render_api(raw, obs_dir, name, max_inline=None, saved=None, rel_base=None):
    max_inline = config.max_inline() if max_inline is None else max_inline
    if is_binary(raw):
        return digest(raw)
    if len(raw) <= max_inline:
        return raw.decode("utf-8", "replace")
    lines = raw.split(b"\n")
    path = save(raw, obs_dir, f"{name}.txt", rel_base)
    if saved is not None:
        saved.append(path)

    def cut(x):
        return x[:160].decode("utf-8", "replace")

    head = "\n".join("  " + cut(l) for l in lines[:15])
    tail = "\n".join("  " + cut(l) for l in lines[-5:])
    return (f"kind=text bytes={len(raw)} lines={len(lines)} saved={path}\n"
            f"first15:\n{head}\nlast5:\n{tail}")


def render_v1(payload, obs_dir, name):
    if len(payload) <= V1_HEAD + V1_TAIL:
        return payload.decode("utf-8", "replace"), len(payload), False
    saved = save(payload, obs_dir, f"{name}.txt")
    head = payload[:V1_HEAD].decode("utf-8", "replace")
    tail = payload[-V1_TAIL:].decode("utf-8", "replace")
    cut = len(payload) - V1_HEAD - V1_TAIL
    return f"{head}\n...[truncated {cut}B -> {saved}]...\n{tail}", len(payload), True


def shape(b):
    lines = b.count(b"\n")
    first = b.split(b"\n", 1)[0][:120]
    last = b.rstrip(b"\n").rsplit(b"\n", 1)[-1][:120]
    return f"lines={lines} first={first!r} last={last!r}"


def render_v2(out, err, obs_dir, name):
    b = ANSI_RE.sub(b"", out + (b"\n--stderr--\n" + err if err else b""))
    if not b:
        return "", 0
    if is_binary(b):
        return f"kind=binary sha256={hashlib.sha256(b).hexdigest()[:16]} head_hex={b[:24].hex()}", len(b)
    if len(b) > V2_MAX_TEXT:
        saved = save(b, obs_dir, f"{name}.txt")
        inline = b[:V2_MAX_TEXT].decode("utf-8", "replace") if b.count(b"\n") <= V2_MAX_LINES else ""
        return f"kind=text {shape(b)} saved={saved}\n{inline}".strip(), len(b)
    return re.sub(r"\n{3,}", "\n\n", b.decode("utf-8", "replace")), len(b)
