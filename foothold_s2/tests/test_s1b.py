"""S1-b L0: 단계 전이(S1-a -> S1-b) 시작 iteration · 옮기는 상태와 옮기지 않는 상태 · p_advance 의 자체 반복 수 · 설정 · 지형 비율 · 명령 분포."""

import ast
import os

import pytest
import torch

pytest.importorskip("rsl_rl")
pytest.importorskip("tensordict")

from foothold_s2.curriculum import terrain_levels_mixed as tlm  # noqa: E402
from foothold_s2.s1_runner import STAGE_TRANSFER_KEYS, S1Runner  # noqa: E402
from foothold_s2.terrains import columns, progression, s2_layout  # noqa: E402
from foothold_s2.tests.test_s1_runner import FakeS1Env, cfg  # noqa: E402

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def runner_with(tmp_path, cols, hook=False):
    env = FakeS1Env(num_envs=8, seed=1)
    env.scene.terrain.terrain_types = torch.arange(8) % cols               # 열 배치가 다른 지형 표 (23 열 대 50 열)

    if hook:
        env.stage_iteration_offset = 0
        env.foothold_state_dict = lambda: {"stage_iteration_offset": env.stage_iteration_offset}
        env.foothold_load_state_dict = lambda s: setattr(env, "stage_iteration_offset", s["stage_iteration_offset"])

    return S1Runner(env, cfg(), log_dir=str(tmp_path), device="cpu"), env


def test_stage_transfer_continues_the_iteration_and_moves_only_the_agreed_state(tmp_path):
    a, env_a = runner_with(tmp_path / "s1a", cols=23)
    rc = env_a.command_manager.t.range_curriculum
    rc.vmax_x, rc.flag_vmax = 1.5, 1.25
    env_a.scene.terrain.terrain_levels[:] = 7                                # S1-a 의 지형 칸(23 열 기준)
    a.learn(3)                                                               # 회차 0 1 2
    ck = str(tmp_path / "s1a" / "latest.pt")
    saved_steps = env_a.common_step_counter

    b, env_b = runner_with(tmp_path / "s1b", cols=50)
    b.load(ck, env_keys=STAGE_TRANSFER_KEYS)
    assert b.current_learning_iteration == 2                                 # 저장된 마지막 회차
    assert env_b.common_step_counter == saved_steps                          # step counter 는 이어진다
    assert env_b.command_manager.t.range_curriculum.vmax_x == 1.5 and env_b.command_manager.t.range_curriculum.flag_vmax == 1.25
    assert int(env_b.scene.terrain.terrain_levels.sum()) == 0                # 지형 칸은 옮기지 않았다(새 배치)
    assert torch.equal(env_b.scene.terrain.terrain_types, torch.arange(8) % 50)
    b.learn(2)                                                               # 3, 4 를 돈다(저장된 2 는 이미 끝난 회차)
    assert b.current_learning_iteration == 4
    assert torch.load(tmp_path / "s1b" / "latest.pt", weights_only=False)["iter"] == 4
    # 대조: env_keys 가 없으면(S1-a 안에서 이어) 지형 칸도 옮긴다
    c, env_c = runner_with(tmp_path / "c", cols=23)
    c.load(ck)
    assert int(env_c.scene.terrain.terrain_levels.sum()) == 7 * 8


def test_stage_offset_is_saved_with_the_checkpoint_and_restored_on_a_normal_resume(tmp_path):
    a, env_a = runner_with(tmp_path / "a", cols=50, hook=True)
    env_a.stage_iteration_offset = 6000
    a.learn(2)
    b, env_b = runner_with(tmp_path / "b", cols=50, hook=True)
    assert env_b.stage_iteration_offset == 0
    b.load(str(tmp_path / "a" / "latest.pt"))                                # S1-b 안에서 이어: 단계 시작 회차가 복원돼 T 가 안 틀어진다
    assert env_b.stage_iteration_offset == 6000


def test_p_advance_counts_the_stage_own_iterations_from_zero():
    T = tlm.stage_T
    assert T(6000, 6000) == 0 and T(6750, 6000) == 750 and T(7500, 6000) == 1500 and T(5000, 6000) == 0
    kw = dict(T_start=0, T_end=1500, p_max=0.9)
    assert progression.p_advance(T(6000, 6000), **kw) == 0.0
    assert progression.p_advance(T(6750, 6000), **kw) == pytest.approx(0.45)
    assert progression.p_advance(T(7500, 6000), **kw) == pytest.approx(0.9)
    # 오프셋 없이 S1-a 끝의 step counter 로 세면 처음부터 0.9 로 포화한다: 오프셋이 일을 한다는 대조
    assert progression.p_advance(6000, **kw) == pytest.approx(0.9)
    # S2 의 기본값(1000 · 8000)은 그대로
    assert progression.p_advance(1000) == 0.0 and progression.p_advance(8000) == pytest.approx(0.9)


def read(rel):
    return open(os.path.join(PKG, rel), encoding="utf-8").read()


def test_s1b_config_registration_and_scripts_say_what_the_design_says():
    cfg_src = read("tasks/s1b_env_cfg.py")
    tree = ast.parse(cfg_src)
    consts = {n.targets[0].id: n.value.value for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
              and isinstance(n.targets[0], ast.Name)}
    assert consts["S1B_T_START"] == 0 and consts["S1B_T_END"] == 1500                  # 15 §5 · VERIFY-lead-final 7
    assert "FootholdS1aBlindEnvCfg" in cfg_src and "foot_edge.weight = 0.0" in cfg_src and "apply_full_terrain_and_flags" in cfg_src
    init = read("tasks/__init__.py")
    assert "FootholdS2-Go2-S1b-blind-v0" in init and "s1b_env:FootholdS1bEnv" in init and "S1bPPORunnerCfg" in init
    agents = read("tasks/agents/s1_ppo_cfg.py")
    assert "max_iterations = 9000" in agents and 'experiment_name = "foothold_s1b"' in agents
    sh = read("run_s1b.sh")
    assert "--stage_transfer" in sh and "model_5999.pt" in sh and "foothold_s1a" in sh and "S1b-blind-v0" in sh
    env_src = read("tasks/s2_env_cfg.py")
    assert "BACKOFF_PARAMS" in env_src and '"backoff_prob": 0.15' in env_src and "dynamic_flags = True" in env_src
    assert "T_start" in read("curriculum/terrain_levels_mixed.py") and "stage_iteration_offset" in read("curriculum/terrain_levels_mixed.py")


def test_s1b_terrain_split_and_flag_share_match_the_design_arithmetic():
    layout = s2_layout.Layout()
    assert layout.num_cols == columns.FULL_COLS == 50
    sparse_or_gap = int((layout.group_by_col != "continuous").sum())
    assert sparse_or_gap == 27 and int((layout.group_by_col == "gap").sum()) == 3
    # 깃발 env 비율: 듬성한 칸(27/50 = 0.54)은 전부 + 이어진 칸(0.46)의 20 % = 0.632
    assert 27 / 50 + 23 / 50 * 0.2 == pytest.approx(0.632)


def test_s1b_command_params_have_the_design_values():
    from foothold_s2.commands import mixed_core as mc
    tree = ast.parse(read("tasks/s2_env_cfg.py"))
    params = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "BACKOFF_PARAMS")
    p = mc.CommandParams(**params)
    assert (p.backoff_prob, p.backoff_vmin, p.backoff_vmax, p.backoff_s) == (0.15, 0.1, 0.3, 2.0)   # 14 §3: 0.15 확률, -0.1~-0.3 m/s, 2 s
    assert p.backoff_vmax * p.backoff_s == pytest.approx(0.6)                                       # 최대 0.6 m
    assert p.flag_spin_threshold == 0.3 and p.flag_spin_wz == 1.2 and p.flag_wz_clip == 1.0         # v<0.3 제자리 회전 ±1.2, 이동 중 ±1.0
