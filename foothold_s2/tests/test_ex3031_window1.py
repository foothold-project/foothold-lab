"""SONNET-X25 후속: EX-30/31 창 1 장기 판(스크립트 · 런처 · 평가 비교)의 CPU 사전 점검. Kit 없이.

Kit 쪽 파일은 가짜 cfg 시험이 실제 이름 불일치를 못 잡으므로(10/16, 10/18) 이름을 소스(AST)로 대조한다.
"""

import ast
import importlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
import yaml

from foothold_s2 import ex3031_window1_contract as w
from foothold_s2.eval import compare_map_modes as cmp
from foothold_s2.runners import stage_transfer as st
from foothold_s2.runners.course_runner import Ex30Runner
from foothold_s2.tests.test_stage_transfer import LV, TY, _runner, _w1_spec, parent_varied  # noqa: F401  (fixture)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "foothold_s2/scripts/train_ex3031_window1.py"
SMOKE = ROOT / "foothold_s2/scripts/train_ex3031_smoke.py"
COMMON = ROOT / "foothold_s2/ex3031_common.py"
LAUNCH = ROOT / "foothold_s2/launch_ex3031_window1.py"
RUN_SH = ROOT / "foothold_s2/run_ex3031_window1.sh"
EVAL_SH = ROOT / "foothold_s2/run_eval_window1.sh"
needs_parent = pytest.mark.skipif(not w.PARENT_PATH.exists(), reason="실제 B 부모 없음")


def _fake_result(iter_=1500):
    row = {"body_vx_integral_median_m": 2.94, "yaw_follow_median": -0.02, "stalled_fraction_2to4s": 0.0, "tilt_rad_mean_alive": 0.09, "alive_envs_at_end": 64, "gt_used": 0, "policy_steps_x_envs": 19200}
    cmds = ("fwd0.5", "fwd1.0", "spin+1.2", "spin-1.2")

    return {"task": w.TASK, "checkpoint": "x.pt", "checkpoint_sha256": "a" * 64, "checkpoint_iter": iter_, "envs": 64, "steps": 300, "dr_off": ["physics_material", "add_base_mass"],
            "curriculum_off": ["terrain_levels", "command_range"], "terrain_hash": {f"{m}/{c}": "ead62030" + "0" * 56 for m in ("eval_gt", "eval_pred", "probe_prop_only") for c in cmds},
            "modes": {m: {c: dict(row) for c in cmds} for m in ("eval_gt", "eval_pred", "probe_prop_only")}}


def _args(**kw):
    base = dict(exp="EX-30", task=w.TASK, agent="rsl_rl_cfg_entry_point", parent=str(w.PARENT_PATH), num_envs=None, seed=None, max_iterations=None, distributed=False, device="cuda:0")
    base.update(kw)

    return SimpleNamespace(**base)


# ------------------------------------------------------------------ 계약
def test_constants_match_the_request():
    assert w.EXTRA_UPDATES == 250 and w.PARENT_ITER == 1500 and w.FINAL_ITER == 1750 and w.SAVE_INTERVAL == 50
    assert w.EXPECTED_CHECKPOINTS == ("model_1550.pt", "model_1600.pt", "model_1650.pt", "model_1700.pt", "model_1750.pt")
    assert w.DEVICE == {"EX-30": "cuda:0", "EX-31": "cuda:1"} and w.STAGGER_SECONDS == 30 and w.TERRAIN_RESTORE == "parent_levels"


@needs_parent
def test_save_interval_is_the_b_agent_cfg_value():
    parent_agent, _ = st.load_parent_agent_cfg(w.PARENT_PATH)

    assert parent_agent["save_interval"] == w.SAVE_INTERVAL and parent_agent["num_steps_per_env"] == 24


@needs_parent
def test_valid_launches_pass_and_each_experiment_is_pinned_to_its_gpu():
    w.validate(_args())
    w.validate(_args(exp="EX-31", device="cuda:1", num_envs=3072, seed=42))
    w.validate(_args(exp="EX-31", device="cuda:0", num_envs=3072, seed=42))             # 단독 재기동(EX-30 이 끝난 뒤)


@needs_parent
@pytest.mark.parametrize("bad", [dict(exp="EX-29"), dict(exp="EX-31", device="cuda:2"), dict(exp="EX-30", device="cuda:1"), dict(task="FootholdS2-Go2-S2-X23-v0"), dict(agent="other"),
                                 dict(distributed=True), dict(num_envs=1536), dict(seed=7), dict(max_iterations=1751), dict(max_iterations=250)])
def test_bad_launch_is_refused(bad):
    with pytest.raises(ValueError):
        w.validate(_args(**bad))


@needs_parent
def test_hydra_overrides_and_other_parents_are_refused(tmp_path):
    with pytest.raises(ValueError, match="Hydra"):
        w.validate(_args(), ["agent.algorithm.entropy_coef=0.1"])
    other = tmp_path / "model_x.pt"
    other.write_bytes(b"x")

    with pytest.raises(ValueError, match="허용 목록"):
        w.validate(_args(parent=str(other)))


def test_spec_restores_parent_levels_and_differs_by_map_policy_only():
    a, b = w.make_spec("EX-30", st.ALLOWED_PARENT_SHA256[0]), w.make_spec("EX-31", st.ALLOWED_PARENT_SHA256[0])

    assert a.terrain_restore == b.terrain_restore == "parent_levels" and a.map_policy == "adaptive" and b.map_policy == "gt" and a.curriculum_spec_sha256 == b.curriculum_spec_sha256
    assert {k: v for k, v in a.__dict__.items() if k not in ("experiment_id", "map_policy")} == {k: v for k, v in b.__dict__.items() if k not in ("experiment_id", "map_policy")}


def test_check_outputs_names_what_is_missing(tmp_path):
    assert set(w.check_outputs(tmp_path)) == set(w.EXPECTED_CHECKPOINTS) | {w.CHILD_SPEC_NAME, "transfer_receipt.json", "window1_result.json", "cfg_pair_diff.json"}
    for name in list(w.EXPECTED_CHECKPOINTS) + [w.CHILD_SPEC_NAME, "transfer_receipt.json", "window1_result.json", "cfg_pair_diff.json"]:
        (tmp_path / name).write_text("x")

    assert w.check_outputs(tmp_path) == []
    (tmp_path / "model_1750.pt").unlink()

    assert w.check_outputs(tmp_path) == ["model_1750.pt"]


# ------------------------------------------------------------------ 창 1 은 끝까지 가고 재개도 된다 (CPU, 가짜 env)
def test_child_with_parent_levels_saves_with_the_field_and_resumes_exactly(parent_varied, tmp_path):
    r = _runner(Ex30Runner, tmp_path, False, "w1")
    r.begin_from_parent(parent_varied["path"], _w1_spec(parent_varied, "EX-30"), parent_varied["shapes"], parent_varied["allowed"])
    r.learn(2)
    ckpt = tmp_path / "w1" / f"model_{r.current_learning_iteration}.pt"
    saved = torch.load(ckpt, weights_only=False)

    assert saved["stage_transfer"]["spec"]["terrain_restore"] == "parent_levels" and torch.equal(saved["env_state"]["terrain_levels"], LV) and torch.equal(saved["env_state"]["terrain_types"], TY)
    r2 = _runner(Ex30Runner, tmp_path, False, "w1b")
    spec = _w1_spec(parent_varied, "EX-30")
    r2.set_spec(spec, saved["stage_transfer"]["parent_iter"])
    r2.load(str(ckpt))

    assert r2.current_learning_iteration == r.current_learning_iteration and torch.equal(r2.env.scene.terrain.terrain_levels, LV)
    other = _runner(Ex30Runner, tmp_path, False, "w1c")
    other.set_spec(st.TransferSpec(spec.parent_sha256, spec.experiment_id, spec.map_policy, spec.seed, spec.curriculum_spec_sha256), saved["stage_transfer"]["parent_iter"])         # terrain_restore 가 다른 spec

    with pytest.raises(st.TransferRefused, match="spec SHA"):
        other.load(str(ckpt))


# ------------------------------------------------------------------ AST: 이름이 실재하고 순서가 맞는가
def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))

    return [(n.module, [a.name for a in n.names]) for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("foothold_s2")]


def test_foothold_names_imported_by_the_window1_script_exist():
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


def test_window1_script_order_and_treatment():
    src = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src)
    writes = [ast.unparse(n.targets[0]) for n in ast.walk(tree) if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Subscript) and ast.unparse(n.targets[0].value) == "pc"]

    assert writes == ["pc['force_gt']"] and 'args_cli.exp == "EX-31"' in src and "curriculum" not in src.replace("TrainingTraceBridge", "")
    order = ["record_realized_physics(gym_env", "RslRlVecEnvWrapper(gym_env", "runner.begin_from_parent(", "runner.reset_segment_physics()", "write_child_spec(log_dir", "check_dumped_cfg_against_parent(log_dir", "runner.learn("]
    pos = [src.index(x) for x in order]

    assert pos == sorted(pos)
    assert "num_learning_iterations=EXTRA_UPDATES" in src and "stop_file=stop_file" in src and "evidence=evidence" in src and "EX3031_W1_DONE" in src and "FINAL_ITER" in src
    assert "agent_cfg.save_interval != SAVE_INTERVAL" in src and "agent_cfg.max_iterations = EXTRA_UPDATES" in src


def test_common_helpers_are_the_same_code_as_the_smoke_script_copies():
    def funcs(path):
        tree = ast.parse(path.read_text(encoding="utf-8"))

        return {n.name: ast.dump(n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("record_realized_physics", "check_dumped_cfg_against_parent")}

    assert funcs(COMMON) == funcs(SMOKE) and len(funcs(COMMON)) == 2


def test_run_script_shape():
    run = RUN_SH.read_text(encoding="utf-8")
    ev = EVAL_SH.read_text(encoding="utf-8")

    assert "train_ex3031_window1 --exp" in run and "EX3031_W1_DONE" in run and "\r" not in run and "\r" not in ev
    assert ev.index("parent_b1500") < ev.index("ex30_1750") < ev.index("ex31_1750") and "model_1750.pt" in ev and "compare_map_modes" in ev
    git_bash = Path("C:/Program Files/Git/bin/bash.exe")

    if git_bash.exists():
        for sh in (RUN_SH, EVAL_SH):
            assert subprocess.run([str(git_bash), "-n", str(sh).replace("\\", "/")], capture_output=True, stdin=subprocess.DEVNULL, timeout=30).returncode == 0


# ------------------------------------------------------------------ 런처
def test_launcher_order_gpu_guard_and_first_update_pattern(tmp_path):
    spec = importlib.util.spec_from_file_location("launch_w1", LAUNCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.ORDER == ("EX-30", "EX-31") and mod.DEVICE["EX-30"] == "cuda:0" and mod.DEVICE["EX-31"] == "cuda:1"
    assert mod.gpu_used_mib("0, 0\n1, 4572\n") == {0: 0, 1: 4572} and mod.guard({0: 0, 1: 4572}) == []
    assert len(mod.guard({0: 12267, 1: 4572})) == 1 and len(mod.guard({0: 0})) == 1 and len(mod.guard({0: 0, 1: 9000})) == 1
    cmd = mod.command("EX-31", str(tmp_path / "o"))

    assert cmd[0].endswith("bash.exe") and "run_ex3031_window1.sh EX-31 cuda:1" in cmd[2]
    assert mod.FIRST_UPDATE.search(re.sub(r"\x1b\[[0-9;]*m", "", "\x1b[1m Learning iteration 1501/1751 \x1b[0m"))
    assert not mod.FIRST_UPDATE.search("Learning iteration 1500/1751") and not mod.FIRST_UPDATE.search("Learning iteration 1/10")
    log = tmp_path / "train.log"
    log.write_text("boot\n Learning iteration 1501/1751\n")
    line, _ = mod.wait_for(str(log), mod.FIRST_UPDATE, 5)

    assert line == "Learning iteration 1501/1751"
    log.write_text("Traceback (most recent call last):\n")

    assert mod.wait_for(str(log), mod.FIRST_UPDATE, 5)[0] is None


def test_launcher_dry_run_prints_both_commands_without_starting_anything():
    out = subprocess.run([sys.executable, str(LAUNCH), "--dry-run"], capture_output=True, text=True, cwd=str(ROOT), env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})

    assert out.returncode == 0 and out.stdout.count("DRY") == 2 and out.stdout.index("EX-30") < out.stdout.index("EX-31") and "cuda:0" in out.stdout and "cuda:1" in out.stdout
    src = LAUNCH.read_text(encoding="utf-8")

    assert "CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP" in src and "DETACHED_PROCESS" not in src.replace("DETACHED_PROCESS 와", "") and "time.sleep(STAGGER_SECONDS)" in src


# ------------------------------------------------------------------ 평가 비교 표
def test_compare_builds_a_table_from_equal_condition_results_and_refuses_unequal_ones():
    base = _fake_result()
    table = cmp.table({"parent": base, "ex30": base, "ex31": base})

    assert table.count("\n| eval_gt") == 4 and "parent: vx적분 m" in table and "ex31: 생존" in table and "지형 해시" in table
    for key, bad in (("dr_off", []), ("curriculum_off", ["terrain_levels"]), ("envs", 32), ("steps", 100)):
        other = json.loads(json.dumps(base))
        other[key] = bad

        with pytest.raises(ValueError, match=key):
            cmp.table({"parent": base, "ex30": other})
    other = json.loads(json.dumps(base))
    other["terrain_hash"] = {k: "0" * 64 for k in other["terrain_hash"]}

    with pytest.raises(ValueError, match="지형 해시"):
        cmp.table({"parent": base, "ex30": other})
    other = json.loads(json.dumps(base))
    other["modes"]["eval_gt"].pop("fwd0.5")

    with pytest.raises(ValueError, match="모드"):
        cmp.table({"parent": base, "ex30": other})


# ---- STOP 은 저장 경계(50 배수)에서만 받는다 (REVIEW-35fd1478 막음 1) ----

def _drive(monkeypatch, tmp_path, stop_after, wrap=True, start=1501, last=1750):
    """실제 Sol23FRunner.log 를 쓰고 StartRunner.log 만 가짜(경계마다 저장)로 바꿔, stop_after 회차를 끝낸 직후 STOP 을 만든다. 저장된 회차 목록과 멈춘 회차를 돌려준다."""
    from foothold_s2.runners import start_runner as sr
    from foothold_s2.runners.boundary_stop import boundary_stop
    from foothold_s2.runners.sol23f_runner import DeadlineReached, Sol23FRunner

    saved = []

    def fake_start_log(self, locs, width=80, pad=35):
        if int(locs["it"]) % 50 == 0:
            saved.append(int(locs["it"]))

    monkeypatch.setattr(sr.StartRunner, "log", fake_start_log)
    cls = boundary_stop(Sol23FRunner, 50) if wrap else Sol23FRunner
    r = object.__new__(cls)
    r.evidence, r.deadline_epoch, r.stop_file = None, None, str(tmp_path / "STOP")
    r.log_dir, r.env = str(tmp_path), SimpleNamespace(num_envs=1)
    r.save = lambda path, infos=None: (Path(path).write_bytes(b"x"), saved.append(("model", Path(path).name)))
    r._manifest_checkpoint = lambda *a, **k: None
    r.save_latest = lambda: None

    for it in range(start, last + 1):
        if it == stop_after + 1:
            (tmp_path / "STOP").write_text("x")

        try:
            r.log({"it": it})
        except DeadlineReached as e:
            return saved, json.loads(str(e))["iter"], r

    return saved, None, r


@pytest.mark.parametrize("stop_after,expected", [(1623, 1650), (1649, 1650), (1651, 1700), (1550, 1600), (1501, 1550)])
def test_stop_file_waits_for_the_next_50_boundary(monkeypatch, tmp_path, stop_after, expected):
    saved, stopped, r = _drive(monkeypatch, tmp_path, stop_after)

    assert stopped == expected
    assert not [x for x in saved if isinstance(x, tuple) and int(re.search(r"\d+", x[1]).group()) % 50], "경계 아닌 회차 저장 금지"
    assert ("model", f"model_{expected}.pt") in saved
    assert r.stop_file == str(tmp_path / "STOP"), "가린 stop_file 은 되돌려 놓는다"


def test_stop_created_at_a_boundary_stops_at_that_boundary(monkeypatch, tmp_path):
    saved, stopped, _ = _drive(monkeypatch, tmp_path, 1649)              # 1650 의 log 가 불리기 직전에 STOP

    assert stopped == 1650
    (tmp_path / "STOP").unlink()
    saved, stopped, _ = _drive(monkeypatch, tmp_path, 1650)              # 1650 을 끝낸 직후에 STOP -> 다음 경계

    assert stopped == 1700


def test_without_the_wrapper_stop_halts_off_boundary_so_the_guard_is_real(monkeypatch, tmp_path):
    _, stopped, _ = _drive(monkeypatch, tmp_path, 1623, wrap=False)

    assert stopped == 1624


def test_without_stop_the_wrapper_changes_nothing(monkeypatch, tmp_path):
    saved, stopped, _ = _drive(monkeypatch, tmp_path, 99999)

    assert stopped is None and saved == [1550, 1600, 1650, 1700, 1750]


def test_deadline_is_also_held_to_the_boundary(monkeypatch, tmp_path):
    from foothold_s2.runners.sol23f_runner import DeadlineReached

    saved, stopped, r = _drive(monkeypatch, tmp_path, 99999)
    r.stop_file, r.deadline_epoch = None, 0.0                            # 이미 지난 마감

    with pytest.raises(DeadlineReached):
        r.log({"it": 1800})
    r.log({"it": 1801})                                                    # 경계가 아니면 마감도 기다린다
    assert r.deadline_epoch == 0.0


def test_window1_script_wraps_the_runner_with_boundary_stop():
    src = SCRIPT.read_text(encoding="utf-8")

    assert "runner_class = boundary_stop(runner_class, SAVE_INTERVAL)" in src and src.index("boundary_stop(runner_class") < src.index("runner_class(env, train_cfg")
