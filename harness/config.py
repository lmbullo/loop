import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = ".logs"
THINK_BUDGET = 32768
DEFAULT_MAX_INLINE = 8192
DEFAULT_AUTH_FILE = "~/.pi/agent/auth.json"


def asset(*parts):
    return os.path.join(ROOT, *parts)


def root():
    return os.path.abspath(os.environ.get("LOOP_ROOT") or ROOT)


def resolve(path, base=None):
    if not path:
        return path
    return path if os.path.isabs(path) else os.path.join(base or root(), path)


def runs():
    return os.path.abspath(os.environ.get("LOOP_RUNS") or os.path.join(root(), LOGS))


def display(path):
    try:
        rel = os.path.relpath(path, ROOT)
    except ValueError:
        return path
    return path if rel.startswith(".." + os.sep) or rel == ".." else rel


def env(name, default=None):
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def env_int(name, default):
    try:
        return int(env(name, default))
    except (TypeError, ValueError):
        return default


def max_inline():
    return env_int("LOOP_MAX_INLINE", DEFAULT_MAX_INLINE)
