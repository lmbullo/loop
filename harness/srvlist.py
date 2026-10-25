import os
import subprocess
import sys

from . import regprobe, regstore, registry


def view(entry):
    state, detail = regprobe.probe(entry)
    return {**entry, "state": state, "detail": detail}


def prune(keep=None):
    keep = keep or set()

    def fn(reg):
        gone = []
        for key, entry in list(reg["servers"].items()):
            if key in keep:
                continue
            if not isinstance(entry, dict):
                reg["servers"].pop(key)
                gone.append(key)
                continue
            tree = str(entry.get("tree") or "")
            if not tree or not os.path.isfile(os.path.join(tree, "run.py")):
                reg["servers"].pop(key)
                gone.append(key)
            elif regprobe.probe(entry)[0] != "running":
                reg["servers"].pop(key)
                gone.append(key)
        return gone

    return regstore.update(fn)


def child_env(entry):
    env = dict(os.environ)
    env["LOOP_REGISTRY"] = registry.global_path()
    if entry.get("runs"):
        env["LOOP_RUNS"] = entry["runs"]
    return env


def restart_all(rest=None):
    rest = list(rest or [])
    targets = regprobe.live()
    if not targets:
        print(f"no live servers registry={registry.global_path()}")
        prune()
        return 0
    args = ["--force"] if "--force" in rest else []
    worst = 0
    for entry in targets:
        tree = str(entry.get("tree") or "")
        run_py = os.path.join(tree, "run.py")
        if not os.path.isfile(run_py):
            print(f"skip tree={tree} reason=missing_run_py")
            continue
        try:
            proc = subprocess.run([sys.executable, run_py, "server", "restart", *args],
                                  cwd=tree, capture_output=True, timeout=180,
                                  env=child_env(entry))
            rc = proc.returncode
            out = (proc.stdout or b"").decode("utf-8", "replace").strip().replace("\n", " | ")
            err = (proc.stderr or b"").decode("utf-8", "replace").strip().replace("\n", " | ")
        except (OSError, subprocess.SubprocessError) as e:
            rc, out, err = 1, "", f"{type(e).__name__}: {e}"
        status = "ok" if rc == 0 else "err"
        worst = worst or (0 if rc == 0 else 1)
        print(f"{status} tree={tree} rc={rc} {out or err}".rstrip()[:400])
    gone = prune()
    live = regprobe.live()
    print(f"restarted={len(live)} pruned={len(gone)} registry={registry.global_path()}")
    return worst
