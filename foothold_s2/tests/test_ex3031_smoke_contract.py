"""SONNET-X25: EX-30/31 짧은 Kit 시험과 B1500 지도 모드 평가 스크립트의 CPU 사전 점검. Kit 없이.

Kit 쪽 파일은 가짜 cfg 시험이 실제 이름 불일치를 못 잡으므로(10/16, 10/18) 이름을 소스(AST)로 대조한다.
"""

import ast
import importlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from foothold_s2 import ex3031_smoke_contract as c
from foothold_s2.runners.start_runner import PERCEPTION_DEFAULTS
from foothold_s2.runners.stage_transfer import ALLOWED_PARENT_SHA256, TransferRefused, unexpected_cfg_diffs

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "foothold_s2/scripts/train_ex3031_smoke.py"
EVAL = ROOT / "foothold_s2/eval/eval_map_modes.py"
RUN = ROOT / "foothold_s2/run_ex3031_smoke.sh"
needs_parent = pytest.mark.skipif(not c.PARENT_PATH.exists(), reason="실제 B 부모 없음")


def _args(**kw):
    base = dict(exp="EX-30", mode="fresh", task=c.TASK, agent="rsl_rl_cfg_entry_point", parent=str(c.PARENT_PATH), child_ckpt=None, num_envs=None, seed=None, max_iterations=None, distributed=False)
    base.update(kw)

    return SimpleNamespace(**base)


# ------------------------------------------------------------------ 계약
@needs_parent
def test_valid_fresh_launch_passes():
    c.validate(_args())
    c.validate(_args(exp="EX-31", num_envs=3072, seed=42))


@needs_parent
@pytest.mark.parametrize("bad", [dict(exp="EX-29"), dict(mode="both"), dict(task="FootholdS2-Go2-S2-X23-v0"), dict(distributed=True), dict(num_envs=1536), dict(seed=7), dict(max_iterations=1501),
                                 dict(child_ckpt="x.pt"), dict(agent="other")])
def test_bad_launch_is_refused(bad):
    with pytest.raises(ValueError):
        c.validate(_args(**bad))


@needs_parent
def test_hydra_overrides_are_refused():
    with pytest.raises(ValueError, match="Hydra"):
        c.validate(_args(), ["agent.device=cuda:0"])


def test_parent_other_than_the_pinned_b1500_is_refused(tmp_path):
    other = tmp_path / "model_x.pt"
    other.write_bytes(b"not the parent")

    with pytest.raises(ValueError, match="허용 목록"):
        c.validate(_args(parent=str(other)))


def test_resume_needs_the_child_spec_next_to_the_checkpoint(tmp_path):
    ckpt = tmp_path / "model_1510.pt"
    ckpt.write_bytes(b"x")

    with pytest.raises(ValueError, match="child_spec"):
        c.validate(_args(mode="resume", child_ckpt=str(ckpt)))

    spec = c.make_spec("EX-31", ALLOWED_PARENT_SHA256[0])
    c.write_child_spec(tmp_path, spec, 1500)
    c.validate(_args(mode="resume", exp="EX-31", child_ckpt=str(ckpt)))
    got, parent_iter = c.read_child_spec(tmp_path)

    assert got == spec and parent_iter == 1500 and got.map_policy == "gt" and c.make_spec("EX-30", ALLOWED_PARENT_SHA256[0]).map_policy == "adaptive"
    (tmp_path / c.CHILD_SPEC_NAME).write_text((tmp_path / c.CHILD_SPEC_NAME).read_text(encoding="utf-8").replace('"seed": 42', '"seed": 43'), encoding="utf-8")

    with pytest.raises(ValueError, match="SHA"):
        c.read_child_spec(tmp_path)                                                                                 # 손으로 고친 spec 은 거절


def test_updates_are_ten_then_two_and_resume_dir_is_new(tmp_path):
    assert c.UPDATES == {"fresh": 10, "resume": 2}
    d = tmp_path / "run" / "x"
    d.mkdir(parents=True)
    t = c.resume_log_dir(str(d / "model_1510.pt"), "20261025_010000", 1)

    assert t.parent == d.parent and t.name == "x_resume_20261025_010000_1"
    t.mkdir()

    with pytest.raises(FileExistsError):
        c.resume_log_dir(str(d / "model_1510.pt"), "20261025_010000", 1)


# ------------------------------------------------------------------ B cfg 그대로, 처치만
@needs_parent
def test_child_pcfg_from_the_b_agent_cfg_equals_the_real_parent_pcfg_except_force_gt():
    """B agent cfg(소스) -> 자식 pcfg 가 실제 부모에 저장된 pcfg 와 force_gt 말고 같다: cfg 가 그 뒤에 달라지지 않았다는 증거."""
    x23 = ast.parse((ROOT / "foothold_s2/tasks/agents/s2_x23_ppo_cfg.py").read_text(encoding="utf-8"))
    cls = next(n for n in x23.body if isinstance(n, ast.ClassDef))
    perc = ast.literal_eval(next(n for n in cls.body if isinstance(n, ast.AnnAssign) and n.target.id == "perception").value)
    b = ast.parse((ROOT / "foothold_s2/tasks/agents/s2_23f_b_ppo_cfg.py").read_text(encoding="utf-8"))
    assert '"microbatch_envs": 64' in (ROOT / "foothold_s2/tasks/agents/s2_23f_b_ppo_cfg.py").read_text(encoding="utf-8") and b
    parent_pcfg = torch.load(c.PARENT_PATH, weights_only=False, map_location="cpu")["perception_cfg"]
    for exp, gt in (("EX-30", False), ("EX-31", True)):
        child = {**PERCEPTION_DEFAULTS, **perc, "microbatch_envs": 64, "force_gt": gt}

        assert unexpected_cfg_diffs(parent_pcfg, child, PERCEPTION_DEFAULTS) == {}, exp


def test_script_sets_only_force_gt_and_nothing_else_in_the_perception_dict():
    src = SCRIPT.read_text(encoding="utf-8")
    writes = [ast.unparse(n.targets[0]) for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Subscript) and ast.unparse(n.targets[0].value) == "pc"]

    assert writes == ["pc['force_gt']"] and 'args_cli.exp == "EX-31"' in src


# ------------------------------------------------------------------ AST: 이름이 실재하는가
def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))

    return [(n.module, [a.name for a in n.names]) for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("foothold_s2")]


@pytest.mark.parametrize("path", [SCRIPT, EVAL])
def test_foothold_names_imported_by_kit_scripts_exist(path):
    ast.parse(path.read_text(encoding="utf-8"))
    for module, names in _imports(path):
        try:
            mod = importlib.import_module(module)
        except ImportError:
            # Kit 이 있어야 import 되는 모듈은 소스 AST 로 정의를 찾는다
            src = (ROOT / (module.replace(".", "/") + ".py")).read_text(encoding="utf-8")
            defined = {n.name for n in ast.parse(src).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))} | {t.id for n in ast.parse(src).body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
            assert set(names) <= defined, (module, set(names) - defined)
            continue
        for name in names:
            assert hasattr(mod, name) or (ROOT / (module.replace(".", "/")) / (name + ".py")).exists(), (module, name)


def test_registered_modules_in_the_script_exist_and_include_the_b_task():
    src = SCRIPT.read_text(encoding="utf-8")
    regs = [n.value for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith("foothold_s2.x") and n.value.endswith("_tasks")]

    assert "foothold_s2.x23f_tasks" in regs
    for r in regs:
        assert (ROOT / (r.replace(".", "/") + ".py")).exists(), r
    assert "FootholdS2-Go2-S2-23f-B-v0" in (ROOT / "foothold_s2/x23f_tasks.py").read_text(encoding="utf-8") and c.TASK == "FootholdS2-Go2-S2-23f-B-v0"


def test_isaac_lab_names_used_by_the_scripts_exist_in_the_install():
    install = Path(os.environ.get("ISAACLAB_DIR", "C:/isaac/IsaacLab"))
    if not install.exists():
        pytest.skip("설치된 Isaac Lab 없음")
    # 두 스크립트가 쓰는 Isaac 이름 중 train_sol23f_common 에 없는 것은 projected_gravity_b 뿐(실제 Kit 에서 읽는 필드)
    data = (install / "source/isaaclab/isaaclab/assets/articulation/articulation_data.py").read_text(encoding="utf-8")

    for field in ("projected_gravity_b", "root_lin_vel_b", "root_ang_vel_b"):
        assert field in data, field


def test_run_script_shape():
    run = RUN.read_text(encoding="utf-8")

    assert "--mode fresh" in run and "--mode resume" in run and "model_1510.pt" in run and "EX3031_SMOKE_DONE" in run and "agent.device" not in run
    assert run.index("--mode fresh") < run.index("--mode resume")


def test_eval_map_modes_defaults_and_guards():
    src = EVAL.read_text(encoding="utf-8")

    assert 'default="eval_gt,eval_pred,probe_prop_only"' in src and "raise RuntimeError" in src and 'if mode in ("eval_pred", "probe_prop_only") and counts["gt"] != 0' in src
    assert "map_mode=mode" in src and "runner, sd = adapters.load_s2_runner" in src.split("for mode in")[1].split("for cname")[0]            # 모드마다 새 runner
