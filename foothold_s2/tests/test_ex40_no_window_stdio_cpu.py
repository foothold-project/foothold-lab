"""Reproduce the W57 Git Bash hash call under the production no-window flags."""
import ast
import os
from pathlib import Path
import subprocess
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


def test_ex40_python_child_processes_explicitly_close_stdin():
    paths = [ROOT / "foothold_s2" / name for name in (
        "ex40_eval_once.py", "ex40_score_watch.py", "ex40_supervisor.py")]
    missing = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if (isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"
                    and node.func.attr in {"run", "Popen", "check_output"}
                    and not any(keyword.arg == "stdin"
                                and isinstance(keyword.value, ast.Attribute)
                                and isinstance(keyword.value.value, ast.Name)
                                and keyword.value.value.id == "subprocess"
                                and keyword.value.attr == "DEVNULL"
                                for keyword in node.keywords)):
                missing.append(f"{path.name}:{node.lineno}:{node.func.attr}")
    assert missing == []


def test_hidden_parent_can_launch_hidden_child_with_closed_stdin(tmp_path):
    parent_receipt = tmp_path / "parent.json"
    child_receipt = tmp_path / "child.json"
    child_code = (
        "from pathlib import Path; import sys; "
        "Path(sys.argv[1]).write_text('child-ok', encoding='utf-8')"
    )
    parent_code = (
        "import os, sys; from pathlib import Path; "
        "from foothold_s2.ex40_eval_once import _run; "
        "rc = _run([sys.executable, '-c', sys.argv[2], sys.argv[3]], "
        "os.environ.copy(), cwd=Path(sys.argv[1])); "
        "Path(sys.argv[4]).write_text(str(rc), encoding='utf-8'); "
        "raise SystemExit(rc)"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    parent = subprocess.run(
        [sys.executable, "-c", parent_code, str(tmp_path), child_code,
         str(child_receipt), str(parent_receipt)],
        cwd=tmp_path, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=flags, check=False, timeout=30)
    assert parent.returncode == 0, parent.stderr
    assert parent_receipt.read_text(encoding="utf-8") == "0"
    assert child_receipt.read_text(encoding="utf-8") == "child-ok"
