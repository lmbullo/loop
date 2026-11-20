import unittest

from harness import cmds


class ReadLikeTest(unittest.TestCase):
    def test_plain_read_commands(self):
        for argv in (["cat", "f"], ["sed", "-n", "1,5p", "f"], ["grep", "-n", "x", "f"],
                     ["ls", "-a"], ["head", "-n", "5", "f"], ["wc", "-l", "f"],
                     ["git", "diff"], ["git", "show", "HEAD"]):
            self.assertTrue(cmds.read_like(argv), argv)

    def test_report_and_write_commands_are_mixed(self):
        for argv in (["python3", "-m", "unittest"], ["pytest", "-q"], ["make", "test"],
                     ["git", "commit", "-m", "x"], ["rm", "-rf", "x"], []):
            self.assertFalse(cmds.read_like(argv), argv)

    def test_sh_c_delegates_to_the_inner_line(self):
        self.assertTrue(cmds.read_like(["sh", "-c", "grep -n x f | head"]))
        self.assertFalse(cmds.read_like(["sh", "-c", "pytest -q"]))
        self.assertFalse(cmds.read_like(["bash", "-c", "sed -n 1,2p f; rm f"]))


class CompoundTest(unittest.TestCase):
    def test_segments_keep_quotes_and_operators(self):
        self.assertEqual(cmds.segments("cd a && grep 'x|y' f | head"),
                         ["cd a ", "&&", " grep 'x|y' f ", "|", " head"])

    def test_every_segment_must_read(self):
        self.assertTrue(cmds.cmd_read_like("cd sub && sed -n 1,80p f | head"))
        self.assertTrue(cmds.cmd_read_like("cd . && git status --porcelain | wc -l"))
        self.assertFalse(cmds.cmd_read_like("cd sub && python3 -m unittest"))
        self.assertFalse(cmds.cmd_read_like("cat f | tee out"))
        self.assertFalse(cmds.cmd_read_like("grep x f > hits.txt"))

    def test_dev_null_and_neutral_segments(self):
        self.assertTrue(cmds.cmd_read_like("grep -q x f > /dev/null"))
        self.assertTrue(cmds.cmd_read_like("test -f f && cat f"))
        self.assertFalse(cmds.cmd_read_like("cat f 2>&1 > log"))
        self.assertTrue(cmds.cmd_read_like("cat f 2>&1"))

    def test_unbalanced_quote_is_not_read_like(self):
        self.assertFalse(cmds.cmd_read_like("cat 'unclosed"))


class ShellSyntaxTest(unittest.TestCase):
    def test_operator_token_and_keyword_are_rejected_with_the_fix(self):
        out = cmds.shell_syntax(["echo", "hi", "|", "cat"])
        self.assertIn("err shell_syntax", out)
        self.assertIn('cmd:"..."', out)
        self.assertIn("err shell_syntax", cmds.shell_syntax(["for", "x", "in", "a"]))
        self.assertIsNone(cmds.shell_syntax(["sh", "-c", "echo hi | cat"]))


if __name__ == "__main__":
    unittest.main()
