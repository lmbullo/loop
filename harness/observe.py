import hashlib
import os
import re

from . import bound, config

V1_HEAD = 600
V1_TAIL = 400
V2_MAX_TEXT = 2000
V2_MAX_LINES = 40
ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")
STDERR_SEP = bound.STDERR_SEP


def is_binary(b, sample=4096, threshold=0.20):
    """Classify bytes as binary without mistaking UTF-8 text for a blob.

    A valid UTF-8 sample is text unless it is dominated by control bytes; its
    high bytes encode characters, not noise. An invalid sample uses the byte
    heuristic. A multi-byte character cut by the sample boundary is text.
    """
    s = b[:sample]
    if not s:
        return False
    try:
        s.decode("utf-8")
        text = True
    except UnicodeDecodeError as e:
        text = e.reason == "unexpected end of data"
    if text:
        bad = sum(1 for c in s if c < 9 or (13 < c < 32) or c == 127)
    else:
        bad = sum(1 for c in s if c < 9 or (13 < c < 32) or c > 126)
    return bad / len(s) > threshold


def save(raw, obs_dir, name, rel_base=None):
    os.makedirs(obs_dir, exist_ok=True)
    path = os.path.join(obs_dir, name)
    with open(path, "wb") as f:
        f.write(raw)
    if rel_base:
        rel = os.path.relpath(path, rel_base)
        return path if rel.startswith(os.pardir + os.sep) or rel == os.pardir else rel
    return config.display(path)


def digest(raw):
    return f"kind=binary bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()[:16]} head_hex={raw[:24].hex()}"


def same(entry):
    text = f"same={entry['id']} bytes={entry['bytes']}"
    if entry.get("saved"):
        text += f" saved={entry['saved']}"
    if entry.get("next"):
        text += f" next: {entry['next']}"
    return text


def render_api(raw, obs_dir, name, max_inline=None, saved=None, rel_base=None,
               ledger=None, obs_id=None, mode="mixed"):
    """Bound one observation.

    Small payloads stay verbatim. Larger ones are archived and replaced by a
    budget-filling shape; read-like output keeps a contiguous head. A
    duplicate of an earlier payload becomes a one-line reference.
    """
    max_inline = config.max_inline() if max_inline is None else max_inline
    if not raw:
        return ""
    prior = ledger.get(raw) if ledger is not None else None
    if prior is not None and prior.get("id") != obs_id:
        if not prior.get("saved") or os.path.isfile(
                prior["saved"] if os.path.isabs(prior["saved"])
                else os.path.join(rel_base or config.root(), prior["saved"])):
            if saved is not None and prior.get("saved"):
                saved.append(prior["saved"])
            return same(prior)
    if is_binary(raw):
        text = digest(raw)
    elif len(raw) <= max_inline:
        text = raw.decode("utf-8", "replace")
    else:
        path = save(raw, obs_dir, f"{name}.txt", rel_base)
        if saved is not None:
            saved.append(path)
        text = bound.summary(raw, path, max_inline, mode)
    if ledger is not None:
        nxt = next((l[6:] for l in text.split("\n") if l.startswith("next: ")), None)
        ledger.add(raw, obs_id or name, saved[-1] if saved else None,
                   inline=len(raw) <= max_inline, next=nxt)
    return text


def render_exec(code, dur, out, err, obs_dir, name, sandbox=None, rel_base=None,
                saved=None, max_inline=None, ledger=None, obs_id=None, mode="mixed"):
    raw = out + (STDERR_SEP + err if err else b"")
    body = render_api(raw, obs_dir, name, max_inline=max_inline, saved=saved,
                      rel_base=rel_base, ledger=ledger, obs_id=obs_id, mode=mode)
    return f"exit={code} ms={dur}\n" + body


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
