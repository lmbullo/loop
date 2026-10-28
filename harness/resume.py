import os
import sys

from . import agent, config, record, recread, recwrite, view


def resumable():
    return [row["run_id"] for row in recread.scan() if row["state"] != "complete"]


def main(argv):
    as_json = "--json" in argv
    args = [a for a in argv if a != "--json"]
    if not args or args[0] in ("-h", "--help", "help"):
        open_runs = resumable()
        print("usage: python3 run.py resume RUN_ID [--json]", file=sys.stderr)
        print("  resumable runs: " + (", ".join(open_runs) if open_runs else "none"), file=sys.stderr)
        return 2
    if len(args) > 1:
        print("err resume takes exactly one RUN_ID", file=sys.stderr)
        return 2
    try:
        run_id = record.resolve(args[0])
        rec = recread.read(run_id)
    except (record.Missing, record.Corrupt) as e:
        print(f"err resume run={args[0]} {e}", file=sys.stderr)
        return 2
    if rec["state"] == "complete":
        print(f"err run={run_id} is complete (end at seq {rec['seq']}); nothing to resume", file=sys.stderr)
        return 2

    def emit(event):
        if as_json:
            print(record.canonical(event), flush=True)
        else:
            sys.stdout.write("".join(line + "\n" for line in view.lines(event)))
            sys.stdout.flush()

    try:
        lock = recwrite.acquire_tree()
    except record.Busy as e:
        print(f"err run={run_id} {e}", file=sys.stderr)
        return 5
    try:
        writer = recwrite.Writer(run_id)
    except record.Busy as e:
        lock.release()
        print(f"err run={run_id} {e}; another process is executing it", file=sys.stderr)
        return 5
    except record.Corrupt as e:
        lock.release()
        print(f"err corrupt run={run_id} {e}", file=sys.stderr)
        return 2
    if rec["torn_tail_bytes"]:
        print(f"[resume] run={run_id} dropping torn tail bytes={rec['torn_tail_bytes']}",
              file=sys.stderr)
    root = (rec["events"][0]["data"].get("root") if rec["events"] else None) or config.root()
    if not os.path.isdir(root):
        root = config.root()
        print(f"[resume] recorded root missing; using {config.display(root)}", file=sys.stderr)
    try:
        st = agent.derive(rec["events"])
        emit(writer.append("resume", {"from_seq": rec["seq"], "turn": st["turn"],
                                      "messages": len(agent.context(rec["events"], st["task"])),
                                      "root": root, "by": "resume"}))
        summary = agent.run_task(writer, emit, root=root)
        return int((summary or {}).get("exit") or 0)
    except record.Sealed as e:
        print(f"err resume run={run_id} {e}", file=sys.stderr)
        return 2
    finally:
        writer.close()
        lock.release()
