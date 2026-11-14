import json
import os
import subprocess
import sys
import tempfile
import unittest

from tests.support import ROOT

INSTALL = os.path.join(ROOT, "install.sh")


def run_install(*args, env=None, cwd=ROOT, script=INSTALL):
    full = dict(os.environ)
    full["PYTHON"] = sys.executable
    full.update(env or {})
    return subprocess.run(["sh", script] + list(args), cwd=cwd, env=full,
                          capture_output=True, text=True, timeout=60)


def launcher(path, *args, cwd=None):
    return subprocess.run([path] + list(args), cwd=cwd, capture_output=True,
                          text=True, timeout=60)


class InstallTest(unittest.TestCase):
    def test_help_documents_user_and_system_modes(self):
        proc = run_install("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for text in ("--prefix", "--bindir", "--system", "--uninstall",
                     "--dry-run", "$HOME/.local", "/usr/local"):
            self.assertIn(text, proc.stdout)

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = os.path.join(tmp, "prefix")
            proc = run_install("--prefix", prefix, "--dry-run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("would install", proc.stdout)
            self.assertFalse(os.path.exists(os.path.join(prefix, "bin", "loop")))

    def test_system_mode_targets_usr_local(self):
        proc = run_install("--system", "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("/usr/local/bin/loop", proc.stdout)

    def test_default_user_install_runs_from_any_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = os.path.join(tmp, "home")
            os.makedirs(home)
            proc = run_install(env={"HOME": home, "PREFIX": ""})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            dest = os.path.join(home, ".local", "bin", "loop")
            self.assertTrue(os.path.isfile(dest))
            self.assertTrue(os.access(dest, os.X_OK))
            out = launcher(dest, "--json", cwd=tmp)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout)["schema"], "loop-index/1")

    def test_prefix_with_spaces_and_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = os.path.join(tmp, "space dir")
            proc = run_install("--prefix", prefix)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            dest = os.path.join(prefix, "bin", "loop")
            with open(dest, encoding="utf-8") as f:
                self.assertIn("# loop-install/1", f.read())
            self.assertEqual(launcher(dest, "--json").returncode, 0)
            again = run_install("--prefix", prefix)
            self.assertEqual(again.returncode, 0, again.stderr)
            proc = run_install("--prefix", prefix, "--uninstall")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(os.path.exists(dest))
            proc = run_install("--prefix", prefix, "--uninstall")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("not installed", proc.stdout)

    def test_refuses_foreign_launcher_unless_forced(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = os.path.join(tmp, "bin")
            os.makedirs(bindir)
            dest = os.path.join(bindir, "loop")
            with open(dest, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\necho foreign\n")
            proc = run_install("--bindir", bindir)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("foreign file", proc.stderr)
            out = subprocess.run(["sh", dest], capture_output=True, text=True,
                                 timeout=60)
            self.assertEqual(out.stdout.strip(), "foreign")
            proc = run_install("--bindir", bindir, "--force")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(launcher(dest, "--json").returncode, 0)
            proc = run_install("--bindir", bindir, "--uninstall", "--force")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(os.path.exists(dest))

    def test_unknown_option_is_usage_error(self):
        proc = run_install("--nope")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unknown option", proc.stderr)

    def test_target_must_be_a_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = os.path.join(tmp, "install.sh")
            with open(INSTALL, encoding="utf-8") as f:
                data = f.read()
            with open(copy, "w", encoding="utf-8") as f:
                f.write(data)
            proc = run_install("--prefix", os.path.join(tmp, "prefix"),
                               cwd=tmp, script=copy)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("run.py not found", proc.stderr)


if __name__ == "__main__":
    unittest.main()
