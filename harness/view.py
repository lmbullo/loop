import json
import sys

from . import record, recread, recschema


def _limit(name):
    return int(recschema.view_doc()["text_limits"][name])


def one(value, limit):
    text = "" if value is None else str(value)
    text = text.replace("\r", "").replace("\n", "\\n").replace("\t", "\\t")
    return text[:limit]


def _args(message, call_id):
    for call in message.get("tool_calls") or []:
        if call.get("id") == call_id:
            raw = call["function"]["arguments"]
            try:
                return one(record.canonical(json.loads(raw)), _limit("args"))
            except ValueError:
                return one(raw, _limit("args"))
    return ""


def lines(ev):
    kind, data, out = ev["type"], ev["data"], []
    if kind == "run_start":
        out.append(f"run={ev['run_id']} schema={ev['schema']} v={ev['v']} "
                   f"entrypoint={data['entrypoint']} model={data['model']} "
                   f"tools={','.join(data['tools'])} max_inline={data['max_inline']} "
                   f"source={data['record_source']}")
        out.append("task=" + one(data["task"], _limit("task")))
    elif kind == "turn":
        usage = data["usage"]
        out.append(f"[turn {data['turn']}] finish={data['finish_reason']} "
                   f"hit={usage['hit']} miss={usage['miss']} out={usage['out']} "
                   f"reason_c={usage['reasoning_c']} cost=${usage['cost']:.6f}")
        if data["message"]["content"]:
            out.append("  text: " + one(data["message"]["content"], _limit("text")))
        for call in data["calls"]:
            out.append(f"  {call['name']}: {_args(data['message'], call['id'])}")
            out.append("   -> " + one(call["observation"], _limit("obs")))
        if data["done"] is not None:
            out.append("  done: " + one(data["done"]["result"], _limit("text")))
    elif kind == "wire":
        out.append(f"[wire] schema={data['schema']} renderer={data['renderer']} "
                   f"model={data['model']} sha={data['sha']}")
    elif kind == "nudge":
        out.append("[nudge] " + one(data["text"], _limit("text")))
    elif kind == "resume":
        out.append(f"[resume] from_seq={data['from_seq']} turn={data['turn']} "
                   f"messages={data['messages']} by={data['by']}")
    elif kind == "verify":
        if data["ran"]:
            ok = 1 if data["exit"] == 0 else 0
            out.append(f"[verify] ok={ok} exit={data['exit']} " + one(data["note"] or "", _limit("obs")))
        else:
            out.append("[verify] pending cmd=" + one(data["command"], _limit("obs")))
    elif kind == "error":
        out.append(f"[err] code={data['code']} finish={data['finish']} "
                   + one(data["text"], _limit("err")))
    elif kind == "interrupted":
        out.append(f"[interrupted] reason={data['reason']} last_seq={data['last_seq']} "
                   f"by={data['by']}")
    elif kind == "end":
        out.append(f"[end] exit={data['exit']} finish={data['finish']} "
                   f"turns={data['turns']} hit={data['hit']} miss={data['miss']} "
                   f"out={data['out']} reason_c={data['reasoning_c']} "
                   f"cost=${data['cost']:.6f}")
        if data["result"] is not None:
            out.append("result=" + one(data["result"], _limit("text")))
    else:
        raise record.Corrupt(f"view: unknown event type {kind!r}")
    return out


def render(events, torn_tail_bytes=0):
    out = []
    for ev in events:
        out.extend(lines(ev))
    if recread.state(events) != "complete" and (not events or events[-1]["type"] != "interrupted"):
        last = events[-1]["seq"] if events else 0
        out.append(f"[interrupted] reason=no_terminal_event last_seq={last} by=-")
    if torn_tail_bytes:
        out.append(f"[torn] bytes={torn_tail_bytes} dropped=1")
    return "".join(line + "\n" for line in out)


def envelope(rec):
    spec = recschema.view_doc()
    return {"schema": spec["schema"], "version": int(spec["version"]),
            "run_id": rec["run_id"], "source_schema": recschema.schema(),
            "source_version": recschema.version(), "state": rec["state"],
            "seq": rec["seq"], "torn_tail_bytes": rec["torn_tail_bytes"],
            "events": rec["events"]}


def read_envelope(raw):
    try:
        got = json.loads(raw)
    except ValueError as e:
        raise record.Corrupt(f"view: stdin is not view json: {type(e).__name__}")
    spec = recschema.view_doc()
    fields = set(spec["fields"])
    if not isinstance(got, dict) or set(got) != fields:
        raise record.Corrupt(f"view: stdin fields {sorted(got) if isinstance(got, dict) else type(got).__name__} != {sorted(fields)}")
    if got["schema"] != spec["schema"] or got["version"] != int(spec["version"]):
        raise record.Corrupt(f"view: stdin schema {got['schema']!r} v{got['version']!r}")
    events = got["events"]
    if not isinstance(events, list):
        raise record.Corrupt("view: stdin events is not a list")
    for idx, ev in enumerate(events):
        if not isinstance(ev, dict):
            raise record.Corrupt(f"view: stdin events[{idx}] is not an object")
        recschema.check(ev, ev.get("run_id"), idx + 1)
    if got["state"] != recread.state(events):
        raise record.Corrupt(f"view: stdin state {got['state']!r} != {recread.state(events)!r}")
    return events, int(got["torn_tail_bytes"]), got["run_id"], got["state"]


def list_rows(rows):
    out = []
    for row in rows:
        cost = row.get("cost")
        out.append(f"run={row['run_id']} state={row['state']} seq={row['seq']} "
                   f"turns={row['turns']} ts={row['ts']} finish={row['finish']} "
                   f"cost=" + (f"${cost:.6f}" if isinstance(cost, (int, float)) else "-"))
    return out


def main(argv):
    as_json = "--json" in argv
    args = [a for a in argv if a not in ("--json", "--text", "--list", "--schema")]
    unknown = [a for a in argv if a.startswith("-") and a not in ("--json", "--text", "--list", "--schema", "-")]
    if unknown:
        print(f"err view unknown option {unknown[0]!r}", file=sys.stderr)
        return 2
    if "--schema" in argv:
        print(json.dumps(recschema.doc(), indent=2, sort_keys=True))
        return 0
    if "--list" in argv:
        try:
            rows = recread.scan()
        except record.Corrupt as e:
            print(f"err view {e}", file=sys.stderr)
            return 2
        if as_json:
            print(record.canonical({"schema": recschema.view_doc()["schema"], "version": int(recschema.view_doc()["version"]), "kind": "list", "runs": rows}))
        else:
            for line in list_rows(rows):
                print(line)
        return 0
    if len(args) > 1:
        print("err view takes at most one RUN_ID ('-' reads view json from stdin)", file=sys.stderr)
        return 2
    target = args[0] if args else None
    try:
        if target == "-":
            raw = sys.stdin.read()
            events, torn, _, _ = read_envelope(raw)
            if as_json:
                print(record.canonical(json.loads(raw)))
                return 0
            sys.stdout.write(render(events, torn))
            return 0
        rec = recread.read(record.resolve(target))
    except record.Missing as e:
        print(f"err view {e}", file=sys.stderr)
        return 2
    except record.Corrupt as e:
        print(f"err corrupt {e}", file=sys.stderr)
        return 2
    if as_json:
        print(record.canonical(envelope(rec)))
    else:
        sys.stdout.write(render(rec["events"], rec["torn_tail_bytes"]))
    return 0
