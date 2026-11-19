"""Transport retries and error classification for one API turn.

A long run must survive a rate limit, a dropped socket, a 503 or a truncated
JSON body without spending a turn or losing the record. Retryable failures use
capped exponential backoff and honour Retry-After. A 4xx that will never
succeed (auth, bad request, context length) is raised immediately so the loop
can decide whether compaction or a terminal error is the right answer.
"""

import json
import random
import time
import urllib.error

from . import api, config

RETRY_HTTP = frozenset((408, 409, 425, 429, 500, 502, 503, 504))
CONTEXT_WORDS = ("context length", "context_length", "maximum context",
                 "too many tokens", "prompt is too long", "input too long",
                 "reduce the length", "context window", "exceeds the maximum")


class Error(Exception):
    def __init__(self, code, text, attempts=1):
        super().__init__(f"code={code} {text[:200]}")
        self.code = int(code)
        self.text = str(text)
        self.attempts = int(attempts)


def is_context(text):
    low = (text or "").lower()
    return any(word in low for word in CONTEXT_WORDS)


def _text(exc):
    try:
        body = exc.read().decode("utf-8", "replace")
    except (OSError, AttributeError):
        body = ""
    return body[:600] or str(exc)


def _retry_after(headers):
    try:
        seconds = float(headers.get("Retry-After"))
    except (TypeError, ValueError, AttributeError):
        return None
    return max(0.0, min(seconds, 120.0))


def _delay(attempt, headers=None):
    if attempt <= 1:
        base = config.retry_base_ms()
    else:
        base = min(config.retry_max_ms(), config.retry_base_ms() * (2 ** (attempt - 1)))
    wait = _retry_after(headers)
    if wait is None:
        wait = base / 1000.0
    jitter = random.uniform(0.75, 1.0)
    return max(0.05, wait * jitter)


def call(msgs, key, wire=None, max_tokens=None, on_retry=None):
    attempts = config.retry_attempts()
    last_code, last_text = 0, "no attempt"
    for attempt in range(1, attempts + 1):
        code, headers = 0, None
        try:
            r = api.call(msgs, key, wire, max_tokens=max_tokens)
            if not isinstance(r, dict):
                raise ValueError("response is not a JSON object")
            if r.get("error"):
                err = r["error"]
                text = err.get("message") if isinstance(err, dict) else str(err)
                raise Error(0, text or json.dumps(err)[:600], attempt)
            if not r.get("choices"):
                raise ValueError("response has no choices")
            return r
        except urllib.error.HTTPError as exc:
            code, headers = int(exc.code), exc.headers
            last_code, last_text = code, _text(exc)
        except Error as exc:
            last_code, last_text = exc.code, exc.text
            if exc.code not in RETRY_HTTP:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError,
                ValueError, json.JSONDecodeError) as exc:
            last_code, last_text = 0, f"{type(exc).__name__}: {exc}"[:600]
        if attempt >= attempts or code not in RETRY_HTTP and code != 0:
            raise Error(last_code, last_text, attempt)
        wait = _delay(attempt, headers)
        if on_retry is not None:
            on_retry(attempt, last_code, int(wait * 1000), last_text)
        time.sleep(wait)
    raise Error(last_code, last_text, attempts)
