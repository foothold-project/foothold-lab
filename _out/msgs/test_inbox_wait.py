"""CPU tests for inbox_wait.py (Linux pins (8), analyst REPORT-analyst-linux-windows-pins-1108 2 절). No Orca, no network.
Run: python -m unittest _out/msgs/test_inbox_wait.py   (or from _out/msgs: python -m unittest test_inbox_wait)
"""
import importlib.util
import os
import pathlib
import subprocess
import unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("inbox_wait", HERE / "inbox_wait.py")
iw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iw)            # the wait loop only runs under __main__

SCREEN_READER_OUT = "Screen reader started\n"          # what GNOME orca prints: no JSON
INBOX_JSON = '{"ok": true, "result": {"messages": [{"sequence": 7, "type": "status"}]}}'


def fake_run(stdout, rc=0, calls=None):
    def run(cmd, **kw):
        if calls is not None:
            calls.append(cmd)
        return subprocess.CompletedProcess(cmd, rc, stdout=stdout, stderr="")
    return run


class OrcaCommand(unittest.TestCase):
    def test_windows_keeps_bare_orca(self):
        self.assertEqual(iw.orca_cli(env={}, platform="win32"), ["orca"])

    def test_linux_does_not_pick_gnome_orca(self):
        # before: ["orca", ...] on every OS. On Linux that is the screen reader
        self.assertEqual(iw.orca_cli(env={}, platform="linux"), ["orca-ide"])

    def test_env_overrides_in_orca_order(self):
        self.assertEqual(iw.orca_cli(env={"ORCA_CLI_COMMAND": " /opt/orca/bin/orca-ide "}, platform="linux"),
                         ["/opt/orca/bin/orca-ide"])
        self.assertEqual(iw.orca_cli(env={"ORCA_DEV_REPO_ROOT": "/src/orca"}, platform="linux"), ["orca-dev"])
        self.assertEqual(iw.orca_cli(env={"ORCA_CLI_COMMAND": "orca", "ORCA_DEV_REPO_ROOT": "x"}, platform="linux"),
                         ["orca"])


class Rows(unittest.TestCase):
    def test_counterexample_wrong_program_was_silent(self):
        # the old behaviour, still the Windows behaviour: no JSON -> [] -> an hour of waiting, then "timeout"
        self.assertEqual(iw.rows(["orca"], run=fake_run(SCREEN_READER_OUT), platform="win32"), [])

    def test_linux_wrong_program_fails_loudly(self):
        with self.assertRaises(SystemExit) as c:
            iw.rows(["orca"], run=fake_run(SCREEN_READER_OUT), platform="linux")
        self.assertIn("ORCA_CLI_COMMAND", str(c.exception))

    def test_linux_missing_cli_fails_loudly(self):
        def missing(cmd, **kw):
            raise FileNotFoundError(2, "No such file", cmd[0])
        with self.assertRaises(SystemExit):
            iw.rows(["orca-ide"], run=missing, platform="linux")

    def test_linux_good_answer_uses_resolved_command(self):
        calls = []
        got = iw.rows(platform="linux", run=fake_run(INBOX_JSON, calls=calls))
        self.assertEqual([m["sequence"] for m in got], [7])
        self.assertEqual(calls[0][:3], ["orca-ide", "orchestration", "inbox"])


class StateFile(unittest.TestCase):
    def test_windows_name_unchanged(self):
        self.assertEqual(iw.state_path(env={}, platform="win32").name, ".inbox_seq")

    def test_copied_windows_state_is_not_read_on_new_host(self):
        p = iw.state_path(env={}, platform="linux", host="ai-lx01")
        self.assertEqual(p.name, ".inbox_seq.ai-lx01")
        self.assertNotEqual(p, iw.state_path(env={}, platform="win32"))

    def test_inbox_state_env_still_respected(self):
        self.assertEqual(iw.state_path(env={"INBOX_STATE": ".seq_lead"}, platform="linux", host="h").name,
                         ".seq_lead.h")


if __name__ == "__main__":
    unittest.main()
