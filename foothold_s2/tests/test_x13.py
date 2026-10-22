"""SONNET-X13 (EX-13 · EX-14) CPU 시험: MGDP 보상 묶음의 식 · 게이트 · 고친 곳 · 기록. Kit 없이 답을 아는 입력으로.

Kit 쪽 이름(보상 항 클래스 · 속성)은 AST 대조(test_kit_names 의 KIT_FILES 에 새 파일을 넣음)와 소스 확인으로 보고, 실제 Kit 이름은 lead 의 smoke 가 확인한다.
"""

import os
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.commands import mixed_core as mc
from foothold_s2.rewards import mgdp_core as m
from foothold_s2.robots import go2_kinematics as kin
from foothold_s2.runners.reward_split import RewardSplit, split_stats

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DT = 0.02
LEGS = ("FL", "FR", "RL", "RR")
ISAAC_ORDER = [f"{leg}_{part}_joint" for part in ("hip", "thigh", "calf") for leg in LEGS]            # Isaac Lab: 종류별 hip 4 · thigh 4 · calf 4
LEGGED_GYM_ORDER = list(kin.JOINT_NAMES)                                                              # legged_gym: 다리별 hip · thigh · calf


# ------------------------------------------------------------------ feet_air_time
def _run_air(contact_seq, cmd=0.5, n_feet=1):
    """contact_seq: step 마다 접촉(True)/공중(False) 한 발. 돌려줌: 보상 목록."""
    air, last = torch.zeros(1, n_feet), torch.zeros(1, n_feet, dtype=torch.bool)
    out = []

    for c in contact_seq:
        fz = torch.full((1, n_feet), 5.0 if c else 0.0)
        rew, air, last = m.air_time_step(air, last, fz, torch.tensor([cmd]), DT)
        out.append(float(rew[0]))

    return out


def test_air_time_070s_then_first_contact_gives_plus_0p2():
    # 공중 35 step 뒤 첫 접촉 step. 원문의 «직전 접촉과 OR» 때문에 이륙 첫 step 은 아직 접촉으로 걸러져 air 가 0 으로 돌아가므로(원문 동작 그대로),
    # 공중 n step 이면 접촉 step 에서 air = n x dt (이륙 첫 step 은 세지 않고 접촉 step 의 dt 를 더함) -> 35 step = 0.70 s -> 보상 0.70 - 0.5 = 0.2
    seq = [True] + [False] * 35 + [True]
    out = _run_air(seq)

    assert out[-1] == pytest.approx(0.2, abs=1e-5)
    assert all(v == 0.0 for v in out[:-1])


def test_air_time_zero_command_gives_zero_and_threshold_is_exclusive():
    assert _run_air([True] + [False] * 35 + [True], cmd=0.0)[-1] == 0.0                  # |cmd_xy| <= 0.1 이면 0
    assert _run_air([True] + [False] * 35 + [True], cmd=0.1)[-1] == 0.0                  # 0.1 은 «> 0.1» 이 아니다
    assert _run_air([True] + [False] * 35 + [True], cmd=0.11)[-1] == pytest.approx(0.2, abs=1e-5)
    assert _run_air([True] * 10) == [0.0] * 10                                           # 계속 땅에 있으면 0
    short = _run_air([True] + [False] * 11 + [True])                                     # 짧은 스윙(11 step = 0.22 s)은 음수 보상(0.22 - 0.5)
    assert short[-1] == pytest.approx(0.22 - 0.5, abs=1e-5)


def test_air_time_contact_filter_ignores_one_step_flicker():
    """접촉 판정은 직전 접촉과 OR: 접촉 한 step 뒤 힘이 끊겨도 다음 step 에 «새 첫 접촉» 이 생기지 않는다."""
    seq = [False] * 30 + [True, False, False, False]
    out = _run_air(seq)

    assert out[30] == pytest.approx(30 * DT + DT - 0.5, abs=1e-5)                        # 처음부터 공중이면 30 step 이 다 센다: 0.60 + 접촉 step 의 dt = 0.62 -> 0.12
    assert out[31] == 0.0 and out[32] == 0.0 and out[33] == 0.0                          # 이후 공중 step 은 air 가 다시 쌓일 뿐 보상 없음


def test_air_time_two_feet_independent_and_equals_mgdp_reference():
    """MGDP 원문(random_dog.py:1004~1018)을 그대로 옮긴 기준 구현과 무작위 접촉열에서 같은 값."""
    g = torch.Generator().manual_seed(3)
    N, T = 64, 200
    forces = (torch.rand(T, N, 4, generator=g) > 0.55).float() * 8.0
    cmd = torch.rand(T, N, generator=g) * 0.4

    class Ref:
        def __init__(self):
            self.feet_air_time = torch.zeros(N, 4)
            self.last_contacts = torch.zeros(N, 4, dtype=torch.bool)
            self.dt = DT

        def step(self, fz, cmd_norm):
            contact = fz > 1.0
            contact_filt = torch.logical_or(contact, self.last_contacts)
            self.last_contacts = contact
            first_contact = (self.feet_air_time > 0.0) * contact_filt
            self.feet_air_time += self.dt
            rew_airTime = torch.sum((self.feet_air_time - 0.5) * first_contact, dim=1)
            rew_airTime *= cmd_norm > 0.1
            self.feet_air_time *= ~contact_filt

            return rew_airTime

    ref = Ref()
    air, last = torch.zeros(N, 4), torch.zeros(N, 4, dtype=torch.bool)
    total = 0.0

    for t in range(T):
        want = ref.step(forces[t], cmd[t])
        got, air, last = m.air_time_step(air, last, forces[t], cmd[t], DT)
        assert torch.allclose(got, want, atol=1e-6)
        total += float(got.abs().sum())

    assert total > 0                                                                      # 시험이 자명하지 않다(보상이 실제로 나옴)


# ------------------------------------------------------------------ motion_trot
def test_joint_pairs_by_name_are_the_same_for_isaac_and_legged_gym_orders():
    for order in (ISAAC_ORDER, LEGGED_GYM_ORDER):
        a, b = m.pair_indices(order)
        names_a, names_b = [order[i] for i in a], [order[i] for i in b]

        assert names_a == ["FL_hip_joint", "FL_thigh_joint", "FL_calf_joint", "FR_hip_joint", "FR_thigh_joint", "FR_calf_joint"]
        assert names_b == ["RR_hip_joint", "RR_thigh_joint", "RR_calf_joint", "RL_hip_joint", "RL_thigh_joint", "RL_calf_joint"]

    # 번호로 짝을 지었다면 Isaac 순서에서 틀린다: legged_gym 번호 [0,1,2] vs [9,10,11] 을 Isaac 순서에 쓰면 FL_hip · FR_hip · RL_hip 대 RR_thigh ... 로 어긋남
    assert [ISAAC_ORDER[i] for i in (0, 1, 2)] != ["FL_hip_joint", "FL_thigh_joint", "FL_calf_joint"]


def _q(order, values):
    return torch.tensor([[values[n] for n in order]])


def test_trot_zero_when_diagonal_legs_have_the_same_offset_from_default():
    order = ISAAC_ORDER
    a, b = m.pair_indices(order)
    dq = {n: 0.0 for n in order}
    dq.update({"FL_hip_joint": 0.3, "RR_hip_joint": 0.3, "FR_calf_joint": -0.2, "RL_calf_joint": -0.2})        # 대각 다리가 같은 (q - q_default)
    pen = m.trot_penalty(_q(order, dq), a, b, torch.tensor([0.0]), 0)

    assert float(pen) == pytest.approx(0.0)
    dq["RR_hip_joint"] = 0.1                                                                                      # 어긋나면 |0.3 - 0.1| = 0.2
    assert float(m.trot_penalty(_q(order, dq), a, b, torch.tensor([0.0]), 0)) == pytest.approx(0.2)


def test_trot_is_zero_at_the_default_standing_pose_but_the_original_formula_is_not():
    order = ISAAC_ORDER
    a, b = m.pair_indices(order)
    default = {n: 0.0 for n in order}
    default.update({"FL_hip_joint": 0.1, "RL_hip_joint": 0.1, "FR_hip_joint": -0.1, "RR_hip_joint": -0.1})      # Go2 기본 hip: 왼쪽 +0.1 · 오른쪽 -0.1
    q = _q(order, default)

    assert float(m.trot_penalty(q - q, a, b, torch.tensor([0.0]), 0)) == 0.0                                      # 고친 식: (q - q_default) = 0 -> 0
    raw = (q[:, a] - q[:, b]).abs().sum()                                                                         # 원식(관절각 그대로): 상수 벌점
    assert float(raw) == pytest.approx(0.4)


def test_trot_gates_terrain_level_and_step_counter():
    order = ISAAC_ORDER
    a, b = m.pair_indices(order)
    dq = _q(order, {n: (0.5 if n.startswith("FL") else 0.0) for n in order}).repeat(3, 1)
    levels = torch.tensor([0.0, 3.0, 4.0])
    pen = m.trot_penalty(dq, a, b, levels, 0)

    assert pen[0] > 0 and pen[1] > 0 and float(pen[2]) == 0.0                                                     # 단계 > 3 이면 0, 3 은 아직 켜짐
    assert float(m.trot_penalty(dq, a, b, torch.zeros(3), 20000).max()) > 0                                       # 정확히 2e4 는 아직 켜짐(원문 > 2e4)
    assert float(m.trot_penalty(dq, a, b, torch.zeros(3), 20001).max()) == 0.0                                    # 2e4 초과면 전부 0
    assert 2e4 / 24 == pytest.approx(833.33, abs=0.01)                                                            # update 약 833 회


# ------------------------------------------------------------------ stand_still
def test_stand_still_gate_uses_xy_and_yaw():
    dq = torch.full((4, 12), 0.1)
    cmd = torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.0, 1.2], [0.5, 0.0, 0.0], [0.0, 0.0, 0.05]])
    pen = m.stand_still_penalty(dq, cmd)

    assert float(pen[0]) == pytest.approx(1.2)                                                                    # 0 명령이면 sum|dq| = 12 x 0.1
    assert float(pen[1]) == 0.0                                                                                   # 회전 명령(vx 0, wz 1.2): 켜지지 않는다
    assert float(pen[2]) == 0.0                                                                                   # 전진
    assert float(pen[3]) == pytest.approx(1.2)                                                                    # 거의 0 인 회전은 켜짐(|wz| < 0.1)
    # 원식(xy 만 보는 문)이었다면 회전 명령에서 켜졌을 것이다
    assert bool((cmd[:, :2].norm(dim=1) < 0.1)[1])


def test_stand_still_is_nearly_but_not_exactly_off_under_start_commands():
    """START 명령 표집에서 이 문이 켜지는 비율: 회전 가지(20 %) 안의 |wz| < 0.1(0.1 / 1.2 = 8.3 %) 이라 약 1.7 %."""
    g = torch.Generator().manual_seed(5)
    out = mc.resample_start(g, 400000, mc.CommandParams(start_mode=True))["cmd"]
    on = (out[:, :2].norm(dim=1) < 0.1) & (out[:, 2].abs() < 0.1)

    assert 0.012 < float(on.float().mean()) < 0.022
    assert float(on.float().mean()) > 0.0                                                                         # «사실상 꺼짐» 이지 «완전히 꺼짐» 이 아니다


# ------------------------------------------------------------------ only_positive_rewards + 기록
def test_clamp_positive_known_answer():
    total = torch.tensor([-0.3, 0.0, 0.7, -2.0])
    steps = torch.zeros(4)
    out, neg, steps = m.clamp_positive(total, steps)

    assert out.tolist() == pytest.approx([0.0, 0.0, 0.7, 0.0])
    assert neg.tolist() == [True, False, False, True]
    assert steps.tolist() == [1.0, 0.0, 0.0, 1.0]
    assert m.clamp_positive(torch.tensor([1.0, 2.0]))[0].tolist() == [1.0, 2.0]                                     # 양수는 그대로


def test_reward_split_keeps_pre_clamp_terms_and_reports_clipped_fraction():
    T, N = 4, 2
    names = ["track_lin_vel", "action_rate"]
    rew = torch.tensor([[[0.2, -1.0], [0.9, -0.1]]] * T)                       # env0 합 -0.8 (잘림) · env1 합 0.8
    vx = torch.full((T, N), 0.4)
    wz = torch.zeros(T, N)
    cmd = torch.tensor([[[0.5, 0, 0]] * N] * T)
    clipped = torch.tensor([[True, False]] * T)
    out = split_stats(rew, names, vx, wz, cmd, clipped=clipped)

    assert out["only_positive_clipped_frac"] == pytest.approx(0.5)
    assert out["moving"]["only_positive_clipped_frac"] == pytest.approx(0.5)
    assert out["moving"]["action_rate"] == pytest.approx(-0.55)                 # 항별 값은 자르기 전 값(평균 (-1.0 + -0.1) / 2)
    assert split_stats(rew, names, vx, wz, cmd)["only_positive_clipped_frac"] is None      # X11 처럼 자르지 않는 env 는 None


def test_reward_split_reads_reward_neg_clipped_from_the_env():
    N = 2
    data = SimpleNamespace(root_lin_vel_b=torch.zeros(N, 3), root_ang_vel_b=torch.zeros(N, 3))
    term = SimpleNamespace(vel_command_b=torch.zeros(N, 3))
    env = SimpleNamespace(scene={"robot": SimpleNamespace(data=data)}, command_manager=SimpleNamespace(get_term=lambda name: term), reset_buf=torch.zeros(N, dtype=torch.bool),
                          reward_neg_clipped=torch.tensor([True, False]))
    env.reward_manager = SimpleNamespace(active_terms=["a"], _step_reward=torch.zeros(N, 1), compute=lambda *a, **k: torch.zeros(N))
    rs = RewardSplit()
    rs.attach(env)
    data.root_lin_vel_b[:, 0] = 0.4
    term.vel_command_b[:, 0] = 0.5
    env.reward_manager.compute()
    rs.add()
    out = rs.summary()

    assert out["only_positive_clipped_frac"] == pytest.approx(0.5)


# ------------------------------------------------------------------ 구성 · 등록 (소스 대조)
def _src(rel):
    return open(os.path.join(REPO, rel), encoding="utf-8").read()


def test_env_cfgs_add_exactly_the_requested_terms_with_requested_weights():
    src = _src("foothold_s2/tasks/s2_env_cfg.py")
    x14 = src[src.index("class FootholdS2X14EnvCfg"):src.index("class FootholdS2X13EnvCfg")]
    x13 = src[src.index("class FootholdS2X13EnvCfg"):]

    assert "FootholdS2X11EnvCfg" in x14.split(":", 1)[0] and "feet_air_time_mgdp" in x14 and "weight=1.0" in x14
    assert "motion_trot" not in x14 and "stand_still" not in x14 and "only_positive" not in x14               # EX-14 는 feet_air_time 하나만
    assert "FootholdS2X14EnvCfg" in x13.split(":", 1)[0]                                                      # EX-13 = EX-14 + 셋
    assert "motion_trot_mgdp, weight=-0.1" in x13 and "stand_still_mgdp, weight=-0.1" in x13 and "only_positive_rewards: bool = True" in x13


def test_task_registration_and_agent_cfg():
    import gymnasium as gym

    import foothold_s2.tasks  # noqa: F401

    s13, s14 = gym.spec("FootholdS2-Go2-S2-X13-v0"), gym.spec("FootholdS2-Go2-S2-X14-v0")

    assert s13.entry_point.endswith("s2_x13_env:FootholdS2PosRewardEnv")
    assert s14.entry_point == "isaaclab.envs:ManagerBasedRLEnv"                                              # EX-14 는 자르지 않는 기본 env
    assert s13.kwargs["env_cfg_entry_point"].endswith("FootholdS2X13EnvCfg") and s14.kwargs["env_cfg_entry_point"].endswith("FootholdS2X14EnvCfg")
    agent = _src("foothold_s2/tasks/agents/s2_ppo_cfg.py")
    body = agent[agent.index("class S2X13PPORunnerCfg"):]

    assert '"est_mode": "zero"' in body and '"critic_mode": "clean52"' in body and "S2X11PPORunnerCfg" in body.split(":", 1)[0]


def test_pos_reward_env_uses_the_pure_clamp_and_records_the_fraction():
    src = _src("foothold_s2/tasks/s2_x13_env.py")

    assert "mc.clamp_positive(total" in src and "reward_neg_clipped" in src and "Episode_Reward/only_positive_clipped_fraction" in src
    assert 'getattr(cfg, "only_positive_rewards", False)' in src


def test_terms_use_names_and_runner_scripts_exist():
    terms = _src("foothold_s2/rewards/mgdp_terms.py")

    assert "mc.pair_indices(self._robot.joint_names)" in terms and "env.common_step_counter" in terms and "env.scene.terrain.terrain_levels" in terms
    assert "env.step_dt" in terms
    run = _src("foothold_s2/run_s2_x13.sh")

    assert "FootholdS2-Go2-S2-X13-v0" in run and "FootholdS2-Go2-S2-X14-v0" in run and "--num_envs 3072" in run and "--seed 42" in run and "--max_iterations 1501" in run
