import importlib
import json
import os
import subprocess
import sys
import unittest

from tests.support import ROOT, run_py, sandbox


class ManifestTest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "manifest.json"), encoding="utf-8") as f:
            self.manifest = json.load(f)

    def test_top_level_contract(self):
        m = self.manifest
        self.assertEqual(m["schema"], "harness-manifest/1")
        self.assertIn("summary", m["purpose"])
        self.assertTrue(m["runtime"]["stdlib_only"])
        self.assertEqual(m["runtime"]["third_party_deps"], [])
        for key in ("entrypoints", "files", "record", "checks", "layout",
                    "env", "scenarios"):
            self.assertIn(key, m)

    def test_files_exist_and_are_unique(self):
        paths = [entry["path"] for entry in self.manifest["files"]]
        self.assertEqual(len(paths), len(set(paths)))
        for path in paths:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, path)), path)
            self.assertFalse(os.path.isabs(path), path)

    def test_entrypoint_modules_are_importable(self):
        ids = set()
        for entry in self.manifest["entrypoints"]:
            ids.add(entry["id"])
            module = importlib.import_module(entry["module"])
            self.assertTrue(callable(getattr(module, entry.get("function", "main"))))
        for required in ("api", "server", "view", "resume", "sim1", "sim2", "check", "tui"):
            self.assertIn(required, ids)

    def test_record_schema_document(self):
        record = self.manifest["record"]
        self.assertEqual(record["schema"], "loop-record/1")
        self.assertEqual(record["version"], 1)
        for event in ("run_start", "turn", "verify", "resume", "error", "interrupted", "end"):
            self.assertIn(event, record["events"])
        self.assertTrue(record["events"]["end"]["terminal"])
        self.assertEqual(record["view"]["schema"], "loop-view/1")

    def test_scenarios_match_data_files(self):
        for row in self.manifest["scenarios"]:
            path = os.path.join(ROOT, "scenarios", row["id"] + ".json")
            self.assertTrue(os.path.isfile(path))
            with open(path, encoding="utf-8") as f:
                scenario = json.load(f)
            self.assertEqual(scenario["sim"], row["sim"])
            self.assertEqual(len(scenario["steps"]), row["steps"])

    def test_checks_have_argv_and_exit(self):
        for check in self.manifest["checks"]:
            self.assertIsInstance(check["argv"], list)
            self.assertTrue(check["argv"])
            self.assertIsInstance(check["expect_exit"], int)
            self.assertIsInstance(check["network"], bool)

    def test_cli_usage_and_schema(self):
        proc = run_py()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage:", proc.stderr)
        proc = run_py("view", "--schema")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["schema"], "loop-record/1")

    def test_view_list_and_line_audit(self):
        with sandbox():
            proc = run_py("view", "--list", "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["kind"], "list")
            proc = run_py("check", "lines")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("over=0", proc.stdout)

    def test_contract_script(self):
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check_manifest.py")],
                              cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ok manifest", proc.stdout)


if __name__ == "__main__":
    unittest.main()
