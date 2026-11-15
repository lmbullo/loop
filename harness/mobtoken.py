"""Bearer-token storage for the opt-in mobile bridge.

The token is read from LOOP_MOBILE_TOKEN or generated once at
.logs/mobile.token with mode 0600.  It is never sent to the agent worker.
"""

import os
import secrets

from . import config, registry

TOKEN_BYTES = 24
TOKEN_PATH = "mobile.token"


def path():
    return os.path.join(registry.state_dir(), TOKEN_PATH)


def load():
    value = config.env("LOOP_MOBILE_TOKEN")
    if value:
        return value
    filename = path()
    try:
        with open(filename, encoding="utf-8") as stream:
            token = stream.read().strip()
    except OSError:
        token = ""
    if token:
        return token
    token = secrets.token_urlsafe(TOKEN_BYTES)
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(token + "\n")
    return token
