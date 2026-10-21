import json
import os
import shutil

from . import config


def scenario_path(sid):
    return config.asset("scenarios", f"{sid}.json")


def available():
    d = config.asset("scenarios")
    if not os.path.isdir(d):
        return []
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))


def load_scenario(sid, expect_sim=None):
    path = scenario_path(sid)
    with open(path, encoding="utf-8") as f:
        sc = json.load(f)
    if expect_sim and sc.get("sim") != expect_sim:
        raise ValueError(f"scenario {sid!r} belongs to sim={sc.get('sim')!r}, not {expect_sim!r}")
    sc.setdefault("id", sid)
    sc.setdefault("label", sc["id"])
    sc.setdefault("fixture", "ws1")
    return sc


def mount(run_dir, fixture="ws1"):
    src = config.asset("fixtures", fixture)
    if not os.path.isdir(src):
        raise FileNotFoundError(f"fixture missing: fixtures/{fixture}")
    dst = os.path.join(run_dir, "ws")
    os.makedirs(run_dir, exist_ok=True)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def write_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=0)
        f.write("\n")
    return path
