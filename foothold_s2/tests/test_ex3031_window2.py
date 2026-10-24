"""SONNET-X25 후속: EX-30/31 창 2(model_1750 정확 재개, 추가 250) 계약 · 스크립트 사전 점검. Kit 없이."""

import ast
import importlib
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from foothold_s2 import ex3031_window1_contract as w1
from foothold_s2 import ex3031_window2_contract as w
from foothold_s2.ex3031_smoke_contract import write_child_spec

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "foothold_s2/scripts/train_ex3031_window2.py"
RUN_SH = ROOT / "foothold_s2/run_ex3031_window2.sh"


def _args(**kw):
    base = dict(exp="EX-30", task=w.TASK, agent="rsl_rl_cfg_entry_point", child_ckpt=None, num_envs=None, seed=None, max_iterations=None, distributed=False, device="cuda:0")
    base.update(kw)

    return SimpleNamespace(**base)


def _ckpt_dir(tmp_path, exp="EX-30", parent_iter=1500, name="model_1750.pt"):
    d = tmp_path / "w1"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text("x")
    write_child_spec(d, w1.make_spec(exp, "a" * 64), parent_iter)

    return d / name


def test_constants_follow_window1_and_the_request():
    assert w.START_ITER == w1.FINAL_ITER == 1750 and w.EXTRA_UPDATES == 250 and w.FINAL_ITER == 2000 and w.SAVE_INTERVAL == w1.SAVE_INTERVAL == 50
    assert w.EXPECTED_CHECKPOINTS == ("model_1800.pt", "model_1850.pt", "model_1900.pt", "model_1950.pt", "model_2000.pt") and w.ALLOWED_DEVICES == {"EX-30": ("cuda:0",), "EX-31": ("cuda:0",)}


def test_valid_launch_passes_and_each_bad_one_is_refused(tmp_path):
    ck = _ckpt_dir(tmp_path)
    w.validate(_args(child_ckpt=str(ck)))
    w.validate(_args(child_ckpt=str(_ckpt_dir(tmp_path / "x", "EX-31")), exp="EX-31"))
    bad = [dict(device="cuda:1"), dict(max_iterations=10), dict(num_envs=64), dict(seed=1), dict(distributed=True), dict(exp="EX-32"), dict(task="other"), dict(child_ckpt=None),
           dict(exp="EX-31")]                                                                    # 체크포인트 폴더의 spec 은 EX-30
    for kw in bad:
        with pytest.raises(ValueError):
            w.validate(_args(**{"child_ckpt": str(ck), **kw}))
    with pytest.raises(ValueError, match="hydra|Hydra"):
        w.validate(_args(child_ckpt=str(ck)), ("agent.x=1",))


def test_only_the_window1_final_checkpoint_with_its_spec_is_accepted(tmp_path):
    with pytest.raises(ValueError, match="model_1750"):
        w.validate(_args(child_ckpt=str(_ckpt_dir(tmp_path / "a", name="model_1700.pt"))))
    with pytest.raises(ValueError, match="부모 번호"):
        w.validate(_args(child_ckpt=str(_ckpt_dir(tmp_path / "b", parent_iter=1000))))
    ck = _ckpt_dir(tmp_path / "c")
    (ck.parent / "child_spec.json").unlink()

    with pytest.raises(ValueError, match="child_spec"):
        w.validate(_args(child_ckpt=str(ck)))


def test_check_outputs_names_what_is_missing(tmp_path):
    assert set(w.check_outputs(tmp_path)) == set(w.EXPECTED_CHECKPOINTS) | {"transfer_receipt_w2.json", "window2_result.json", "cfg_pair_diff.json"}
    for n in list(w.EXPECTED_CHECKPOINTS) + ["transfer_receipt_w2.json", "window2_result.json", "cfg_pair_diff.json"]:
        (tmp_path / n).write_text("x")

    assert w.check_outputs(tmp_path) == []
    (tmp_path / "model_2000.pt").unlink()

    assert w.check_outputs(tmp_path) == ["model_2000.pt"]


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))

    return [(n.module, [a.name for a in n.names]) for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("foothold_s2")]


def test_foothold_names_imported_by_the_window2_script_exist():
    for module, names in _imports(SCRIPT):
        try:
            mod = importlib.import_module(module)
        except ImportError:
            src = (ROOT / (module.replace(".", "/") + ".py")).read_text(encoding="utf-8")
            tree = ast.parse(src).body
            defined = {n.name for n in tree if isinstance(n, (ast.FunctionDef, ast.ClassDef))} | {t.id for n in tree if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
            assert set(names) <= defined, (module, set(names) - defined)
            continue
        for name in names:
            assert hasattr(mod, name) or (ROOT / (module.replace(".", "/")) / (name + ".py")).exists(), (module, name)


def test_window2_script_order_treatment_and_scattered_episode_lengths():
    src = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src)
    writes = [ast.unparse(n.targets[0]) for n in ast.walk(tree) if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Subscript) and ast.unparse(n.targets[0].value) == "pc"]

    assert writes == ["pc['force_gt']"] and 'args_cli.exp == "EX-31"' in src
    order = ["record_realized_physics(gym_env", "RslRlVecEnvWrapper(gym_env", "runner.set_spec(", "runner.load(args_cli.child_ckpt)", "runner.reset_segment_physics()", "transfer_receipt_w2.json",
             "check_dumped_cfg_against_parent(log_dir", "runner.learn("]
    pos = [src.index(x) for x in order]

    assert pos == sorted(pos)
    learn = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and ast.unparse(n.func) == "runner.learn"]

    assert len(learn) == 1 and {k.arg: ast.unparse(k.value) for k in learn[0].keywords} == {"num_learning_iterations": "EXTRA_UPDATES", "init_at_random_ep_len": "True"}      # reviewer 고침 1
    assert "boundary_stop(runner_class, SAVE_INTERVAL)" in src and "stop_file=stop_file" in src and "EX3031_W2_DONE" in src and "agent_cfg.max_iterations = EXTRA_UPDATES" in src
    assert "saved_terrain == restored_terrain == after_reset" in src and "runner.current_learning_iteration != START_ITER" in src and "begin_from_parent" not in src


def test_run_script_shape():
    run = RUN_SH.read_text(encoding="utf-8")

    assert "train_ex3031_window2 --exp" in run and "--child_ckpt" in run and "EX3031_W2_DONE" in run and "\r" not in run
    git_bash = Path("C:/Program Files/Git/bin/bash.exe")

    if git_bash.exists():
        assert subprocess.run([str(git_bash), "-n", str(RUN_SH).replace("\\", "/")], capture_output=True, stdin=subprocess.DEVNULL, timeout=30).returncode == 0
