#!/usr/bin/env python3
"""Enforce the agent commit protocol: conventional subject, why:, check: lines."""
import argparse
import re
import subprocess
import sys

SUBJECT = re.compile(r"^(feat|fix|refactor|test|docs|chore|perf|build|ci|revert)"
                     r"(\([a-z0-9_.\-/]+\))?: .{3,}$")
TRAILER = {"why": re.compile(r"(?m)^why: .+"), "check": re.compile(r"(?m)^check: .+")}


def git(argv):
    proc = subprocess.run(["git"] + argv, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(argv)} failed")
    return proc.stdout


def commits(args):
    argv = ["log", "--format=%H%x1f%P%x1f%B%x1e"]
    if args.all:
        argv.append("--all")
    elif args.range:
        argv.append(args.range)
    else:
        argv.append("HEAD")
    out = git(argv)
    for record in out.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split("\x1f", 2)
        if len(parts) != 3:
            continue
        sha, parents, body = parts
        yield sha, len(parents.split()), body


def validate(body):
    lines = body.splitlines()
    subject = lines[0].strip() if lines else ""
    problems = []
    if not SUBJECT.match(subject):
        problems.append("subject is not '<type>(<scope>): <summary>' with >=3 char summary")
    if len(subject) > 100:
        problems.append("subject longer than 100 chars")
    for name, pattern in TRAILER.items():
        if not pattern.search(body):
            problems.append(f"missing '{name}: <text>' line")
    return subject, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--range", default="HEAD", help="git revision range, e.g. HEAD~99..HEAD")
    parser.add_argument("--all", action="store_true", help="check every reachable commit")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    try:
        rows = list(commits(args))
    except RuntimeError as e:
        print(f"err git: {e}", file=sys.stderr)
        return 2
    bad = 0
    for sha, parent_count, body in rows:
        if parent_count > 1:
            if not args.quiet:
                print(f"skip {sha[:12]} merge")
            continue
        subject, problems = validate(body)
        if problems:
            bad += 1
            print(f"err {sha[:12]} {subject[:70]}")
            for problem in problems:
                print(f"  {problem}")
        elif not args.quiet:
            print(f"ok   {sha[:12]} {subject[:90]}")
    print(f"summary: commits={len(rows)} bad={bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
