import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = ".logs"
THINK_BUDGET = 32768
MAX_TOKENS = 65536
DEFAULT_MAX_INLINE = 2048
DEFAULT_READ_INLINE = 8192
DEFAULT_TURN_TOKENS = 16384
DEFAULT_CONTEXT_HIGH = 64000
DEFAULT_CONTEXT_LOW = 32000
DEFAULT_KEEP_TURNS = 16
DEFAULT_HTTP_TIMEOUT_S = 900
DEFAULT_RETRY_ATTEMPTS = 8
DEFAULT_RETRY_BASE_MS = 500
DEFAULT_RETRY_MAX_MS = 30000
DEFAULT_LENGTH_RETRIES = 8
DEFAULT_EXEC_TIMEOUT_MS = 600000
RENDERER = "obs/3"
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


def read_inline():
    return env_int("LOOP_READ_INLINE", DEFAULT_READ_INLINE)


def max_tokens():
    return env_int("LOOP_MAX_TOKENS", MAX_TOKENS)


def turn_tokens():
    """Per-turn completion ceiling; a length stop escalates to max_tokens."""
    return env_int("LOOP_TURN_TOKENS", DEFAULT_TURN_TOKENS)


def think_budget():
    return env_int("LOOP_THINK_BUDGET", THINK_BUDGET)


def context_high():
    return env_int("LOOP_CONTEXT_HIGH", DEFAULT_CONTEXT_HIGH)


def context_low():
    return env_int("LOOP_CONTEXT_LOW", DEFAULT_CONTEXT_LOW)


def keep_turns():
    return env_int("LOOP_KEEP_TURNS", DEFAULT_KEEP_TURNS)


def exec_timeout_ms():
    return env_int("LOOP_EXEC_TIMEOUT_MS", DEFAULT_EXEC_TIMEOUT_MS)


def http_timeout_s():
    return env_int("LOOP_HTTP_TIMEOUT_S", DEFAULT_HTTP_TIMEOUT_S)


def retry_attempts():
    return max(1, env_int("LOOP_RETRY_ATTEMPTS", DEFAULT_RETRY_ATTEMPTS))


def retry_base_ms():
    return max(1, env_int("LOOP_RETRY_BASE_MS", DEFAULT_RETRY_BASE_MS))


def retry_max_ms():
    return max(1, env_int("LOOP_RETRY_MAX_MS", DEFAULT_RETRY_MAX_MS))


def length_retries():
    return max(1, env_int("LOOP_LENGTH_RETRIES", DEFAULT_LENGTH_RETRIES))


def replay_reasoning():
    return env_int("LOOP_REPLAY_REASONING", 0) != 0
