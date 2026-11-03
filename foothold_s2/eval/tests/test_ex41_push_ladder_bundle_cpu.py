from pathlib import Path
from contextlib import contextmanager
import json
import pytest

from foothold_s2.eval.ex41_push_ladder_bundle import build_argv, bundle_cases, build_stage_criteria, load_pinned_baseline
from foothold_s2.eval.ex41_push_ladder_contract import PUSH_LADDER_EXPECTED_CHILDREN
from foothold_s2.curriculum.continuous import sha256_lf_text
import yaml


def _baseline():
    root = Path(__file__).resolve().parents[3]
    plan = yaml.safe_load((root / 'foothold_s2/curriculum/ex41-fixed5000.yaml').read_text(encoding='utf-8-sig'))
    row = plan['fixed_schedule']['push_baseline']
    return root / row['path'], row['sha256']


def test_pinned_m6000_baseline_checks_derived_and_source_sha():
    path, sha = _baseline()
    baseline=load_pinned_baseline(path,sha)
    assert baseline['baseline_checkpoint_iteration']==6000
    assert len(baseline['cells'])==9
    import pytest
    with pytest.raises(ValueError,match='baseline SHA'):
        load_pinned_baseline(path,'0'*64)


def test_pinned_baseline_hash_is_stable_across_git_lf_and_windows_crlf(tmp_path):
    path, _ = _baseline()
    source = path.read_bytes()
    lf = source.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    crlf_path = tmp_path / path.name
    crlf_path.write_bytes(lf.replace(b'\n', b'\r\n'))
    expected = sha256_lf_text(path)
    assert sha256_lf_text(crlf_path) == expected
    assert load_pinned_baseline(crlf_path, expected)['baseline_checkpoint_iteration'] == 6000


def test_bundle_has_four_nine_cell_commands_and_three_flat_stand_supplements():
    cases = bundle_cases()
    assert len(cases) == PUSH_LADDER_EXPECTED_CHILDREN == 39
    commands = [row for row in cases if row['command'] != 'stand']
    stand = [row for row in cases if row['command'] == 'stand']
    assert len(commands) == 36 and len(stand) == 3
    assert {row['command'] for row in commands} == {'walk_0.5','walk_1.0','walk_1.5','stand_turn_1.2'}
    assert all(row['envs'] == 3072 and row['directions'] == 'full' for row in commands)
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


def test_stage_criterion_uses_worst_direction_and_2mps_compares_pinned_m6000():
    rows=[]
    baseline={'cells':{}}
    for terrain in ('flat','random_rough','pyramid_stairs'):
        for mode in ('eval_gt','eval_pred','probe_prop_only'):
            baseline['cells'][f'{terrain}/{mode}']={'survival_fraction':.4,
                'worst_direction_survival_fraction':.25}
            rows.extend([
                {'state':'done','terrain':terrain,'map_mode':mode,'command':'walk_1.5',
                 'summary':{'magnitudes':{'1.5':{'worst_direction_survival_fraction':.875}}}},
                {'state':'done','terrain':terrain,'map_mode':mode,'command':'walk_0.5',
                 'summary':{'magnitudes':{'2.0':{'survival_fraction':.45,
                     'worst_direction_survival_fraction':.375}}}},
            ])
    result=build_stage_criteria(rows,baseline,'b'*64)
    criterion=result['walk_1.5mps_worst_direction']['flat/eval_gt']
    assert criterion['passed'] is False and criterion['threshold']==.90
    compared=result['push_2.0mps_vs_m6000']['flat/eval_gt']
    assert compared['difference_from_m6000']==pytest.approx(.05)
    assert compared['baseline_source_sha256']=='b'*64
    with pytest.raises(ValueError,match='missing'):
        build_stage_criteria(rows[:-1],baseline,'b'*64)


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
    baseline_json, baseline_sha = _baseline()
    doc = bundle.run_bundle(checkpoint, output, device="cuda:0", task="fake",
                            include_stand=False, checkpoint_iteration=6000,
                            baseline_json=baseline_json, baseline_sha256=baseline_sha)
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
