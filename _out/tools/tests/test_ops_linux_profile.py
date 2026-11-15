"""CPU regressions for the operations tools; no live GPU, queue, or Orca I/O."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

TOOLS = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name == "nt", reason="native POSIX branch")


@pytest.fixture
def profile(tmp_path):
    home = tmp_path / "home"
    path = tmp_path / "machine.json"
    paths = {
        "gpu_root": "~/mai/tmp/gpu",
        "c_layer_priority": str(tmp_path / "priority"),
        "c_layer_ledger": str(tmp_path / "ledger.jsonl"),
        "stage_table": str(tmp_path / "stage.yaml"),
        "eval_root": str(tmp_path / "eval"),
        "c_layer_manifest": str(tmp_path / "remaining.json"),
        "c_layer_out": str(tmp_path / "capture"),
        "w78_video": str(tmp_path / "video"),
        "p1_attempt_glob": str(tmp_path / "attempts/*/attempt.json"),
        "worklist": str(tmp_path / "WORKLIST.tsv"),
        "baseline_m6000": str(tmp_path / "baseline.json"),
        "canon_retry": str(tmp_path / "canon_retry.py"),
    }
    path.write_text(json.dumps({"format": "foothold-ops-machine-profile/1",
                                "platform": "linux", "paths": paths}), encoding="utf-8")
    env = dict(os.environ, HOME=str(home), FOOTHOLD_OPS_MACHINE_PROFILE=str(path),
               PYTHONPATH=os.pathsep.join([str(TOOLS / "gpu_jobs"), str(TOOLS / "ex41"),
                                          os.environ.get("PYTHONPATH", "")]),
               PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    env.pop("ORCA_CLI_COMMAND", None)
    env.pop("FOOTHOLD_OPS_PROFILE_SHA256", None)
    return env, home / "mai/tmp/gpu", paths


def probe(profile, code, *args):
    env, root, _ = profile
    return subprocess.run([sys.executable, "-c", code, str(root), *map(str, args)],
                          env=env, cwd=root.parents[2].parent, capture_output=True,
                          text=True, encoding="utf-8", timeout=25)


def assert_pass(proc):
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_dispatch_and_both_checkers_read_one_profile(profile):
    assert_pass(probe(profile, """
from pathlib import Path
import sys
import dispatch as d, ops_check as o, lead_rounds as l
root = Path(sys.argv[1])
assert d.LIVE["queue"] == str(root / "queue.json"), d.LIVE
assert d.LIVE["train_marker"] == str(root / "TRAINING_BUSY_GPU0")
assert d.LIVE["markers"] == [str(root), sys.argv[2]]
assert d.LIVE["ledgers"] == [sys.argv[3]]
assert d.LIVE["idle_state"] == str(root / "idle_since.json")
assert d.LIVE["stage_table"] == sys.argv[4]
assert d.LIVE["eval_root"] == sys.argv[5]
assert d.LIVE["c_layer_manifest"] == sys.argv[6]
assert d.DISPATCH["p1_attempt_globs"] == [sys.argv[7]]
assert d.DISPATCH["idle_log"] == str(root / "idle_log.jsonl")
assert d.DISPATCH["state"] == str(root / "dispatch_state.json")
assert d.DISPATCH["logs"] == str(root / "logs")
assert d.result_path(7).parent == root / "results"
assert o.QUEUE == l.QUEUE == root / "queue.json"
assert o.P1_MARKER == root / "PRIORITY_BUSY_GPU1"
assert o.TRAIN_MARKER == root / "TRAINING_BUSY_GPU0"
assert d.DISPATCH["p1_markers"] == [str(o.P1_MARKER)]
assert o.WORKLIST == l.WORKLIST == Path(sys.argv[8])
""", *(profile[2][k] for k in ("c_layer_priority", "c_layer_ledger", "stage_table",
                               "eval_root", "c_layer_manifest", "p1_attempt_glob", "worklist"))))


def test_gpu_registry_gate_uses_linux_marker(profile):
    env, root, _ = profile
    root.mkdir(parents=True)
    (root / "PRIORITY_BUSY_GPU1").write_text("malformed", encoding="utf-8")
    for tool in ("gpu_jobs.py", "dispatch.py"):
        proc = subprocess.run([sys.executable, str(TOOLS / "gpu_jobs" / tool), "gate", "c-layer"],
                              env=env, cwd=root, capture_output=True, text=True, timeout=20)
        assert proc.returncode == 3, proc.stdout + proc.stderr
        assert json.loads(proc.stdout)["reason"] == "ex41_p1_unknown"


def test_w28_serve_uses_profile_priority_marker(profile):
    assert_pass(probe(profile, """
from pathlib import Path
from unittest.mock import patch
import sys, queue_w28 as q
root = Path(sys.argv[1])
root.mkdir(parents=True)
(root/"PRIORITY_BUSY_GPU1").write_text("malformed")
def first_iteration(queue, gpu, *, sources):
    allowed, reason = q.external_clear({"gpu":gpu, "priority":4}, sources)
    assert not allowed and reason == "priority_busy_marker:JSONDecodeError", reason
    raise SystemExit(0)
with patch.object(q, "one", first_iteration):
    q.main(["--queue", str(root/"w28-fixture.json"), "serve", "--gpu", "1"])
raise AssertionError("serve did not reach the first gate")
"""))


def test_unconfigured_linux_cli_never_touches_legacy_queue(profile):
    env, root, _ = profile
    env.pop("FOOTHOLD_OPS_MACHINE_PROFILE")
    proc = subprocess.run([sys.executable, str(TOOLS / "gpu_jobs/dispatch.py"), "queue", "run", "7"],
                          env=env, cwd=root.parents[2].parent, capture_output=True, text=True, timeout=20)
    assert proc.returncode != 0 and "FOOTHOLD_OPS_MACHINE_PROFILE" in proc.stderr
    assert not (root.parents[2].parent / "D:").exists()


def test_linux_chrome_not_busy_but_unknown_and_python_still_block(profile):
    assert_pass(probe(profile, """
import queue_w28 as q
uuid=q.GPU_UUIDS[1]
def row(name): return [f"GPU-{uuid}, 321, {name}"]
assert q.compute_rows_busy(1, row("/opt/google/chrome/chrome"), lambda p: ("chrome", []))[0]
assert not q.compute_rows_busy(1, row("python3"), lambda p: ("python3", []))[0]
assert not q.compute_rows_busy(1, row("unknown"), lambda p: ("unknown", []))[0]
for name in ("Chrome", r"fake\\chrome"):
    assert not q.compute_rows_busy(1, row(name), lambda p: (name, []))[0], name
"""))


def test_wrapper_requests_a_new_session_without_running_the_queue(profile):
    assert_pass(probe(profile, """
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys, dispatch as d
with patch("subprocess.Popen", return_value=SimpleNamespace(pid=42)) as child:
    assert d.spawn_wrapper(7, str(Path(sys.argv[1]) / "logs/test.log")) == 42
    assert child.call_args.kwargs.get("start_new_session") is True, child.call_args
    assert child.call_args.kwargs.get("creationflags", 0) == 0
"""))


def test_wrapper_creates_real_session_and_result_for_cpu_only_queue(profile):
    assert_pass(probe(profile, """
import json, os, sys
from pathlib import Path
import dispatch as d
root = Path(sys.argv[1])
assert Path(d.LIVE["queue"]) == root/"queue.json"
root.mkdir(parents=True)
argv = [sys.executable, "-c", "import os,json; print(json.dumps({'sid':os.getsid(0),'ppid':os.getppid()}))"]
d.write_queue(str(root/"queue.json"), {"format":"foothold-gpu-queue/1","items":[{"id":7,"argv":argv}]})
pid = d.spawn_wrapper(7, str(root/"logs/fixture.log"))
_, status = os.waitpid(pid, 0)
result = json.loads((root/"results/item_7.json").read_text())
assert os.waitstatus_to_exitcode(status) == result["rc"] == 0, result
assert result["last_json"] == {"sid":pid,"ppid":pid}, result
assert pid != os.getsid(0)
"""))


def test_wrapper_rejects_profile_changed_since_parent_load(profile):
    assert_pass(probe(profile, """
import json, os, subprocess, sys
from pathlib import Path
from unittest.mock import patch
import dispatch as d
root = Path(sys.argv[1])
assert Path(d.LIVE["queue"]) == root/"queue.json"
other = root.parent/"other-gpu"
other.mkdir(parents=True)
d.write_queue(str(other/"queue.json"), {"format":"foothold-gpu-queue/1","items":[
    {"id":7,"argv":[sys.executable,"-c","raise SystemExit(0)"]}]})
path = Path(os.environ["FOOTHOLD_OPS_MACHINE_PROFILE"])
changed = json.loads(path.read_text())
changed["paths"]["gpu_root"] = str(other)
path.write_text(json.dumps(changed))
started=[]
popen=subprocess.Popen
def track(*args, **kwargs):
    child=popen(*args, **kwargs)
    started.append(child)
    return child
log = root/"logs/fixture.log"
with patch("subprocess.Popen", side_effect=track):
    d.spawn_wrapper(7, str(log))
assert started[0].wait(timeout=10) != 0
assert "operations profile changed" in log.read_text(), log.read_text()
assert not (other/"results").exists(), "ran item 7 from a different queue"
"""))


def test_ops_rejects_case_and_sibling_path_mixups(profile):
    assert_pass(probe(profile, """
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys, ops_check as o
root = Path(sys.argv[1]).parent / "EX42"
p = SimpleNamespace(pid=42)
def labels(rows): return {label: level for level, label, _ in rows}
def check(path):
    return labels(o.check(root, now=1000, procs=[(p, f"python train_start.py --ex41_log_root {path}/main")],
                          queue={"items":[]}, util=0))
assert check(str(root).lower())["train"] == "FAIL"
assert check(str(root)+"-other")["train"] == "FAIL"
assert check(root)["train"] == "OK"
wrong = [(p, f"python -m ex41_score_watch --run-dir {root}-other --score-dir {root}/eval/scores")]
rows = labels(o.check(root, now=1000, procs=wrong, queue={"items":[]}, util=0))
assert rows["score_watch"] == rows["I05 stray_watch"] == "FAIL", rows
def row(path):
    return {"state":"running","kind":"eval","owner":"ex41_score_watch","argv":["--out",str(path)],
            "run_at":1,"pid":42,"id":9}
def score(path):
    return o.score_attempt_wait(root, 9000, [], [row(path)], cpu_delta=lambda p: 0)[0]
assert score(str(root).lower()+"/eval") == "OK"
assert score(str(root)+"-other/eval") == "OK"
assert score(root/"eval") == "FAIL"
with patch.object(o, "_latest_output_file", return_value=None):
    attempt = root/"eval/score-watch/model_250/attempt.json"
    attempt.parent.mkdir(parents=True)
    attempt.write_text('{"state":"running","source":"/no-output","iteration":250}')
    import os
    os.utime(attempt,(1,1))
    calls=[]
    def cpu(pid): calls.append(pid); return 0
    o.score_attempt_wait(root, 9000, [(p, "ex41_score_watch --run-dir="+str(root).lower())], [], cpu_delta=cpu)
    assert calls == []
    o.score_attempt_wait(root, 9000, [(p, "ex41_score_watch --run-dir="+str(root))], [], cpu_delta=cpu)
    assert calls == [42]
"""))


def test_lead_round_uses_configured_worklist_queue_and_commands(profile):
    proc = probe(profile, """
import json, sys
from pathlib import Path
from unittest.mock import patch
from subprocess import CompletedProcess
import lead_rounds as l
root = Path(sys.argv[1])
root.mkdir(parents=True)
(root/"queue.json").write_text('{"items":[]}')
worklist, canon = map(Path, sys.argv[2:])
worklist.write_text("id\\tstatus\\towner\\tpriority\\tdue\\n")
seen=[]
def run(argv, **kw):
    seen.append(argv)
    return CompletedProcess(argv, 0, '{"ok":true,"result":{}}' if argv[0]=="orca-ide" else "retry 0", "")
with patch("subprocess.run", run):
    assert l.main() == 1
assert ["orca-ide", "terminal", "list", "--json"] in seen, seen
assert [sys.executable, str(canon)] in seen
assert [sys.executable, str(canon), "--gpu1"] in seen
""", profile[2]["worklist"], profile[2]["canon_retry"])
    assert_pass(proc)
    assert "ACT runner: 창 핸들 없음" in proc.stdout


def test_boundary_report_reads_selected_baseline(profile):
    assert_pass(probe(profile, """
import builtins, runpy, sys
from pathlib import Path
from unittest.mock import patch
baseline = Path(sys.argv[2])
baseline.write_text('{"modes":{}}')
run = baseline.parent / "run"
score = run / "eval/scores/score_250_fixture.json"
cells = run / "eval/score-watch/model_250_fixture/evaluation/map64/map_modes.json"
for path in (score, cells):
    path.parent.mkdir(parents=True)
    path.write_text('{"modes":{}}')
real_open = builtins.open
def opened(path, *args, **kw):
    if Path(path) in (score, cells):
        return real_open(path, *args, **kw)
    # Stop once the real report selects its baseline.
    assert Path(path) == baseline, path
    raise SystemExit(0)
sys.argv = [sys.argv[3], str(run), "250"]
with patch.object(builtins, "open", opened):
    runpy.run_path(sys.argv[0], run_name="__main__")
raise AssertionError("baseline was not read")
""", profile[2]["baseline_m6000"], TOOLS / "ex41/boundary_report.py"))
