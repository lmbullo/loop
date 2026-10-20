import json
import os

from . import config


def auth_file():
    return os.path.expanduser(config.env("LOOP_AUTH_FILE", config.DEFAULT_AUTH_FILE))


def api_key():
    key = config.env("LOOP_API_KEY")
    if key:
        return key
    with open(auth_file(), encoding="utf-8") as f:
        return json.load(f)["deepseek"]["key"]
