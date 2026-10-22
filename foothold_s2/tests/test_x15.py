"""SONNET-X15 (EX-15 = EX-11 + legged_gym A1 기저 묶음) CPU 시험. 답을 아는 입력 + 구성 소스 대조 (Kit 이름은 test_kit_names 의 AST 대조가 따로 본다)."""

import os

import pytest
import torch

from foothold_s2.rewards import core
from foothold_s2.rewards import lg_core as lg

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GO2_BODIES = (["base"] + [f"{leg}_{part}" for part in ("hip", "thigh", "calf", "foot") for leg in ("FL", "FR", "RL", "RR")] + ["Head_upper", "Head_lower"])


def _src(rel):
    return open(os.path.join(REPO, rel), encoding="utf-8").read()


# ------------------------------------------------------------------ dof_pos_limits (soft 0.9)
def test_soft_limits_formula_known_answer():
    hard = torch.tensor([[-1.0, 1.0], [0.0, 2.0], [-2.72, -0.83]])
    soft = lg.lg_soft_limits(hard, 0.9)

    assert soft[0].tolist() == pytest.approx([-0.9, 0.9])
    assert soft[1].tolist() == pytest.approx([0.1, 1.9])                          # 중심 1, 반폭 1 -> 0.9
    assert soft[2].tolist() == pytest.approx([-1.775 - 0.945 * 0.9, -1.775 + 0.945 * 0.9])


def test_dof_pos_limits_zero_inside_and_excess_beyond_soft_limit():
    hard = torch.tensor([[-1.0, 1.0]] * 3)
    soft = lg.lg_soft_limits(hard, 0.9).unsqueeze(0)                              # (1, 3, 2)
    inside = torch.tensor([[0.0, 0.5, -0.89]])                                    # 전부 soft 한계(±0.9) 안
    assert float(lg.lg_dof_pos_limits(inside, soft)) == 0.0
    beyond = torch.tensor([[0.95, -0.92, 0.9]])                                   # 0.05 + 0.02 + 0(경계는 초과 아님)
    assert float(lg.lg_dof_pos_limits(beyond, soft)) == pytest.approx(0.07, abs=1e-6)
    hard_limit = torch.tensor([[1.0, -1.0, 0.0]])                                 # 하드 한계에 닿아도 초과량은 soft 기준: 0.1 + 0.1 + 0
    assert float(lg.lg_dof_pos_limits(hard_limit, soft)) == pytest.approx(0.2, abs=1e-6)


def test_isaac_joint_pos_limits_is_the_same_formula_as_legged_gym():
    """Isaac Lab mdp.joint_pos_limits 의 식(우리가 쓰는 항)과 legged_gym 식이 무작위 입력에서 같다. soft 한계는 robot cfg 의 soft_joint_pos_limit_factor 0.9."""
    g = torch.Generator().manual_seed(0)
    lo = -torch.rand(256, 12, generator=g) * 2 - 0.1
    hi = lo + torch.rand(256, 12, generator=g) * 3 + 0.2
    hard = torch.stack([lo, hi], dim=-1)
    q = lo + (hi - lo) * (torch.rand(256, 12, generator=g) * 1.4 - 0.2)
    soft = lg.lg_soft_limits(hard, 0.9)

    assert torch.allclose(lg.lg_dof_pos_limits(q, soft), lg.isaac_joint_pos_limits(q, soft))
    assert float(lg.lg_dof_pos_limits(q, soft).max()) > 0                          # 자명하지 않다(초과가 실제로 있음)


def test_go2_robot_cfg_uses_soft_factor_0p9_and_isaac_formula_matches_source():
    unitree = open("C:/isaac/IsaacLab/source/isaaclab_assets/isaaclab_assets/robots/unitree.py", encoding="utf-8").read()
    go2 = unitree[unitree.index("UNITREE_GO2_CFG = ArticulationCfg("):]
    go2 = go2[:go2.index("\n)\n")]
    art = open("C:/isaac/IsaacLab/source/isaaclab/isaaclab/assets/articulation/articulation.py", encoding="utf-8").read()
    rew = open("C:/isaac/IsaacLab/source/isaaclab/isaaclab/envs/mdp/rewards.py", encoding="utf-8").read()
    fn = rew[rew.index("def joint_pos_limits"):]

    assert "soft_joint_pos_limit_factor=0.9" in go2
    assert "joint_pos_mean - 0.5 * joint_pos_range * soft_limit_factor" in art and "joint_pos_mean + 0.5 * joint_pos_range * soft_limit_factor" in art
    assert ".clip(max=0.0)" in fn and ".clip(min=0.0)" in fn and "soft_joint_pos_limits" in fn
    assert "soft_joint_pos_limit_factor" not in _src("foothold_s2/robots/go2_cfg.py")                          # S1 cfg 가 이 값을 바꾸지 않는다(UNITREE_GO2_CFG 의 0.9 그대로)


# ------------------------------------------------------------------ collision: calf 만, foot 은 아님
def test_collision_bodies_calf_penalised_foot_not():
    import re

    pens = [i for i, n in enumerate(GO2_BODIES) if any(re.fullmatch(p, n) for p in lg.COLLISION_BODY_PATTERNS)]
    table = lg.check_collision_bodies(GO2_BODIES, pens)

    assert table["calf"] == ["FL_calf", "FR_calf", "RL_calf", "RR_calf"] and table["foot"] == ["FL_foot", "FR_foot", "RL_foot", "RR_foot"]
    assert not any(n.endswith("_foot") for n in table["penalised"]) and all(f"{leg}_calf" in table["penalised"] for leg in ("FL", "FR", "RL", "RR"))
    assert "base" in table["penalised"] and "FL_thigh" in table["penalised"] and "Head_upper" in table["penalised"]


def test_collision_check_refuses_merged_foot_or_penalised_foot():
    pens = [i for i, n in enumerate(GO2_BODIES) if n.endswith("_calf")]
    merged = [n for n in GO2_BODIES if not n.endswith("_foot")]                  # 발이 calf 의 일부(별도 foot 강체 없음)

    with pytest.raises(RuntimeError, match="foot"):
        lg.check_collision_bodies(merged, [i for i, n in enumerate(merged) if n.endswith("_calf")])

    with pytest.raises(RuntimeError, match="foot 이 충돌"):
        lg.check_collision_bodies(GO2_BODIES, pens + [GO2_BODIES.index("FL_foot")])

    with pytest.raises(RuntimeError, match="calf 가"):
        lg.check_collision_bodies(GO2_BODIES, pens[:3])



def test_collision_threshold_and_weight_stay_start_values():
    assert core.WEIGHTS["collision"] == -10.0 and core.COLLISION_N == 0.1                                       # 가중치 -10 · 문턱 0.1 N 그대로
    cfg = _src("foothold_s2/tasks/s2_x15_cfg.py")

    assert "threshold" not in cfg and "collision.weight" not in cfg                                             # 문턱 · 가중치는 건드리지 않는다


# ------------------------------------------------------------------ 구성 · 등록 · 기존 파일을 안 건드림
def test_x15_cfg_changes_exactly_the_requested_terms():
    cfg = _src("foothold_s2/tasks/s2_x15_cfg.py")

    assert "FootholdS2X14EnvCfg" in cfg.split("class FootholdS2X15EnvCfg(")[1].split(")", 1)[0]               # feet_air_time +1.0 은 EX-14 상속
    assert "only_positive_rewards: bool = True" in cfg
    assert "self.rewards.joint_torques.weight = -2.0e-4" in cfg
    assert "RewTerm(func=mdp.joint_pos_limits, weight=-10.0)" in cfg
    assert "lg_terms.collision_checked" in cfg and "lg_core.COLLISION_BODY_PATTERNS" in cfg
    assert "motion_trot" not in cfg.split('"""', 2)[2] and "stand_still" not in cfg.split('"""', 2)[2]          # MGDP 고유 항은 넣지 않는다
    assert lg.COLLISION_BODY_PATTERNS == ["base", ".*_thigh", ".*_calf", "Head_.*"]


def test_x15_task_registration_and_run_script():
    import gymnasium as gym

    import foothold_s2.x15_tasks  # noqa: F401

    spec = gym.spec("FootholdS2-Go2-S2-X15-v0")

    assert spec.entry_point.endswith("s2_x13_env:FootholdS2PosRewardEnv")                                       # EX-13 의 only_positive env 재사용
    assert spec.kwargs["env_cfg_entry_point"].endswith("s2_x15_cfg:FootholdS2X15EnvCfg")
    assert spec.kwargs["rsl_rl_cfg_entry_point"].endswith("s2_x15_ppo_cfg:S2X15PPORunnerCfg")
    agent = _src("foothold_s2/tasks/agents/s2_x15_ppo_cfg.py")

    assert "S2X13PPORunnerCfg" in agent and 'experiment_name = "foothold_s2_x15"' in agent                      # est zero · clean52 · clip 17 · 1501 · 500 저장은 상속
    run = _src("foothold_s2/run_s2_x15.sh")

    assert "FootholdS2-Go2-S2-X15-v0" in run and "ex15-lgA1" in run and "--num_envs 3072" in run and "--seed 42" in run and "--max_iterations 1501" in run
    assert "import foothold_s2.x15_tasks" in _src("foothold_s2/scripts/train_start.py")


def test_existing_consumed_files_are_untouched_by_x15():
    """실행 중인 EX-14 가 소비하는 기존 파일에는 EX-15 이름이 없다(manifest 감시로 EX-14 가 무효가 되지 않게 새 파일로만 더했다)."""
    for rel in ("foothold_s2/tasks/__init__.py", "foothold_s2/tasks/s2_env_cfg.py", "foothold_s2/tasks/agents/s2_ppo_cfg.py", "foothold_s2/rewards/mgdp_terms.py",
                "foothold_s2/rewards/mgdp_core.py", "foothold_s2/tasks/s2_x13_env.py", "foothold_s2/runners/start_runner.py"):
        text = _src(rel)

        assert "X15" not in text and "x15" not in text and "lg_core" not in text, rel
