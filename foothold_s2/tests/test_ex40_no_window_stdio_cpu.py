"""Reproduce the W57 Git Bash hash call under the production no-window flags."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT.parent))
from foothold_s2.ex40_eval_once import BASH, _run


def test_git_bash_sha256sum_succeeds_with_create_no_window_and_closed_stdin(tmp_path):
    source = tmp_path / "known.txt"
    source.write_text("known input\n", encoding="utf-8")
    result = _run([str(BASH), "-c", 'sha256sum "$1"', "runner-test", str(source)],
                  os.environ.copy(), cwd=tmp_path)
    assert result == 0


def test_shell_sha256_invocations_close_stdin_explicitly():
    shell_files = [*ROOT.glob("*.sh"), *ROOT.joinpath("eval").glob("*.sh")]
    offenders = []
    for path in shell_files:
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if "sha256sum" in line and "</dev/null" not in line:
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []
