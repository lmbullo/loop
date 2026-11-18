"""Safe workspace paths and discovery for the mobile bridge.

Every operation resolves to a real directory, stays under the user's home and
under an explicitly configured root, and never follows a hidden or escaping
symlink.
"""

import os

from . import regstore

HIDDEN = {".git", ".hg", ".svn", "node_modules", "__pycache__"}
MARKERS = (".logs", "run.py", "AGENTS.md", ".git")
DEPTH = 2
LIMIT = 250


class PathError(Exception):
    def __init__(self, status, text):
        super().__init__(text)
        self.status = status
        self.text = text


def real(path):
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def home():
    return real(os.path.expanduser("~"))


def inside(path, parent):
    path, parent = real(path), real(parent)
    return path == parent or path.startswith(parent + os.sep)


def normalize_roots(paths):
    out = []
    for value in paths or ():
        if not isinstance(value, str) or not value.strip():
            continue
        path = real(value)
        if os.path.isdir(path) and path not in out:
            out.append(path)
    return out


def select_root(value, roots):
    if not isinstance(value, str) or not value.strip():
        raise PathError(400, "root is required")
    path = real(value)
    roots = normalize_roots(roots)
    if not inside(path, home()):
        raise PathError(403, "root is outside the home directory")
    if not any(inside(path, root) for root in roots):
        raise PathError(403, "root is outside the mobile allowlist")
    if not os.path.isdir(path):
        raise PathError(404, "root is not a directory")
    return path


def _marked(path):
    return any(os.path.exists(os.path.join(path, name)) for name in MARKERS)


def owner(value, roots):
    """Resolve a selected directory to the workspace tree that owns it."""
    path = select_root(value, roots)
    roots = normalize_roots(roots)
    base = home()
    known = {real(tree) for tree in regstore.entries()}
    known.update(root for root in roots if root != base)
    current = path
    while True:
        if current in known or _marked(current):
            return current
        if current in roots or current == base:
            return path
        parent = os.path.dirname(current)
        if parent == current or not inside(parent, base) or \
                not any(inside(parent, root) for root in roots):
            return path
        current = parent


def unsafe_state(tree):
    logs = os.path.join(tree, ".logs")
    if os.path.lexists(logs):
        resolved = real(logs)
        return not inside(resolved, tree) or not inside(resolved, home())
    return False


def discover(roots, extra=()):
    roots, base, found = normalize_roots(roots), home(), set()

    def consider(path, force=False):
        path = real(path)
        if len(found) >= LIMIT or not os.path.isdir(path):
            return
        if not inside(path, base) or not any(inside(path, root) for root in roots):
            return
        rel = os.path.relpath(path, base)
        if any(part.startswith(".") or part in HIDDEN
               for part in rel.split(os.sep) if part != "."):
            return
        if force or path != base:
            found.add(path)

    for entry in regstore.snapshot():
        consider(entry.get("tree"), force=True)
    for path in extra:
        consider(path, force=True)
    for root in roots:
        if inside(root, base):
            if root != base:
                consider(root, force=True)
            _walk(root, 0, consider)
    return sorted(found)


def _walk(parent, depth, consider):
    if depth > DEPTH:
        return
    try:
        entries = sorted(os.scandir(parent), key=lambda row: row.name.lower())
    except OSError:
        return
    for entry in entries:
        if entry.name.startswith(".") or entry.name in HIDDEN:
            continue
        try:
            if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        child = real(entry.path)
        marked = any(os.path.exists(os.path.join(child, name)) for name in MARKERS)
        if depth == 0 or marked:
            consider(child, force=True)
        if marked or depth < DEPTH:
            _walk(child, depth + 1, consider)
