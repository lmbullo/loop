import os

from . import regstore, registry


def directory():
    return os.path.join(registry.state_dir(), "jobs")


def path(run_id):
    return os.path.join(directory(), f"{run_id}.json")


def write(run_id, data):
    os.makedirs(directory(), exist_ok=True)
    payload = {"schema": "loop-job/1", "run_id": run_id, **data}
    regstore.write_json(path(run_id), payload)
    return payload


def read(run_id):
    return regstore.read_json(path(run_id), None)


def remove(run_id):
    try:
        os.unlink(path(run_id))
    except OSError:
        pass


def load_for_record(run_id):
    job = read(run_id)
    if job and job.get("run_id") == run_id:
        return job
    return None
