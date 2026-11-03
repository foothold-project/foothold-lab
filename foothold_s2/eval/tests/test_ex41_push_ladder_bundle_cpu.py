from pathlib import Path
from contextlib import contextmanager
import json

from foothold_s2.eval.ex41_push_ladder_bundle import build_argv, bundle_cases


def test_bundle_has_nine_walk_cases_and_three_flat_stand_supplements():
    cases = bundle_cases()
    assert len(cases) == 12
    walk = [row for row in cases if row['command'] == 'walk_0.5']
    stand = [row for row in cases if row['command'] == 'stand']
    assert len(walk) == 9 and len(stand) == 3
    assert all(row['envs'] == 3072 and row['directions'] == 'full' for row in walk)
    assert all(row['terrain'] == 'flat' and row['envs'] == 1536
               and row['directions'] == 'cardinal' for row in stand)


def test_bundle_child_cli_records_fixed_l0_single_mode_and_actual_device():
    checkpoint = Path('D:/known/model_6000.pt')
    case = bundle_cases()[0]
    argv = build_argv(case, checkpoint=checkpoint, out=Path('D:/known/out'),
                      device='cuda:0', task='FootholdS2-Go2-S2-SB-v0', seed=42)
    assert argv[argv.index('--envs') + 1] == '3072'
    assert argv[argv.index('--fixed-level') + 1] == '0'
    assert argv[argv.index('--push-ladder-map-mode') + 1] == case['map_mode']
    assert argv[argv.index('--device') + 1] == 'cuda:0'
    assert argv[argv.index('--steps') + 1] == '350'


def test_gpu0_bundle_claims_and_records_priority_markers(tmp_path, monkeypatch):
    import foothold_s2.eval.ex41_push_ladder_bundle as bundle
    from foothold_s2.eval.ex41_gpu_priority import GPU0_UUID

    checkpoint = tmp_path / "model_6000.pt"
    checkpoint.write_bytes(b"known checkpoint")
    observed = []

    @contextmanager
    def fake_priority(*, job, iteration, run):
        observed.append((job, iteration, run))
        yield [{"path": "C:/test/TRAINING_BUSY", "owner": {"pid": 123}}]

    class Result:
        returncode = 1

    monkeypatch.setattr(bundle, "gpu0_priority", fake_priority)
    admission = {"state": "idle", "gpu_uuid": GPU0_UUID, "checks": 2}
    monkeypatch.setattr(bundle, "wait_for_gpu0_python_idle", lambda: admission)
    monkeypatch.setattr(bundle.subprocess, "run", lambda *_a, **_k: Result())
    output = tmp_path / "out"
    doc = bundle.run_bundle(checkpoint, output, device="cuda:0", task="fake",
                            include_stand=False, checkpoint_iteration=6000)
    assert observed == [("EX-41-push-ladder-eval", 6000, str(output.resolve()))]
    assert doc["priority_markers"][0]["path"] == "C:/test/TRAINING_BUSY"
    assert doc["gpu0_admission"] == admission
    saved = json.loads((output / "push_ladder_bundle.json").read_text(encoding="utf-8"))
    assert saved["checkpoint_iteration"] == 6000
    assert saved["priority_markers"] == doc["priority_markers"]
    assert saved["gpu0_admission"] == admission


def test_gpu0_admission_waits_for_other_python_without_signaling_it(monkeypatch):
    from foothold_s2.eval import ex41_gpu_priority as priority
    import psutil

    own_python = __import__("os").getpid()
    outputs = iter([
        f"GPU-{priority.GPU0_UUID}, {own_python}, python.exe\n",
        "",
    ])

    class Query:
        returncode = 0

        def __init__(self, stdout):
            self.stdout = stdout

    monkeypatch.setattr(priority.subprocess, "run", lambda *_a, **_k: Query(next(outputs)))
    monkeypatch.setattr(priority.os, "getpid", lambda: own_python + 1)
    monkeypatch.setattr(priority.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(psutil, "process_iter", lambda **_kwargs: [])
    receipt = priority.wait_for_gpu0_python_idle(timeout_seconds=1, poll_seconds=0)
    assert receipt["state"] == "idle"
    assert receipt["checks"] == 2


def test_gpu0_admission_waits_for_c_layer_unit_even_when_nvidia_smi_is_empty(monkeypatch):
    from foothold_s2.eval import ex41_gpu_priority as priority
    import psutil

    class Query:
        returncode = 0
        stdout = ""

    class Process:
        def __init__(self, pid, command):
            self.info = {"pid": pid, "name": "python.exe", "cmdline": command.split()}

    batches = iter([
        [Process(23456, "python D:/mai-tmp/c_layer_visibility_fix_v1/c_layer_shard.py --gpu 0")],
        [],
    ])
    monkeypatch.setattr(priority.subprocess, "run", lambda *_a, **_k: Query())
    monkeypatch.setattr(psutil, "process_iter", lambda **_kwargs: next(batches))
    monkeypatch.setattr(priority.time, "sleep", lambda _seconds: None)
    receipt = priority.wait_for_gpu0_python_idle(timeout_seconds=1, poll_seconds=0)
    assert receipt["state"] == "idle"
    assert receipt["checks"] == 2
