"""J-T10: 세계 좌표 기대 변위 proxy (JUDGE-SPEC v0.5 5.3 새 여섯 행 · 5.4). CPU, Kit 없음.

스위치 `world_frame` 기본 켬(팀장 결정 8): 끔(False)은 옛 식과 비트 동일. 두 판정을 둘 다 계산해 9 칸 표로 병행 기록한다. 설정(커리큘럼 term params) 과 실행 인자로 고른다.
"""

import math
from pathlib import Path

import pytest
import torch

from foothold_s2.commands import mixed_core as mc
from foothold_s2.curriculum import rules
from foothold_s2.curriculum import terrain_levels_mixed as tlm

PKG = Path(__file__).resolve().parents[1]
DT = 0.02
SLOT = 200                                                            # 4 s


def _sim(slots):
    """완벽 추종 모의: 슬롯마다 (몸 기준 vx, 각속도) 를 주고 yaw 를 적분한다. cmd_sum_xy · cmd_sum_w · 시작점에서 가장 먼 거리를 돌려준다."""
    yaw = torch.zeros(1)
    pos = torch.zeros(1, 2)
    body = torch.zeros(1, 2)
    world = torch.zeros(1, 2)
    far = 0.0

    for vx, wz in slots:
        for _ in range(SLOT):
            cmd = torch.tensor([[vx, 0.0]])
            body += cmd
            world += mc.world_cmd_step(yaw, cmd)
            pos += mc.world_cmd_step(yaw, cmd) * DT
            yaw = yaw + wz * DT
            far = max(far, float(torch.linalg.norm(pos)))

    return far, body, world


class Term:
    def __init__(self, far, body, world, mark=None, with_world=True, flag=False):
        n = len(body)
        self.cmd_sum_xy = body.clone()
        self.max_dist = torch.as_tensor([far] * n, dtype=torch.float32)
        self.is_flag_env = torch.full((n,), flag, dtype=torch.bool)
        self.goals = torch.zeros(n, dtype=torch.long)
        self.walk_frac = torch.ones(n)
        self.cfg = type("C", (), {"flag_count": 4})()
        self.had_new_task = None if mark is None else torch.as_tensor(mark, dtype=torch.bool)
        self.new_task_stats = rules.NewTaskStats()
        self.frame_stats = rules.FrameCompareStats()

        if with_world:
            self.cmd_sum_w = world.clone()


class Terrain:
    def __init__(self, n):
        self.terrain_levels = torch.zeros(n, dtype=torch.long)
        self.cfg = type("C", (), {"terrain_generator": type("G", (), {"size": (8.0, 8.0)})()})()
        self.calls = []

    def update_env_origins(self, ids, up, down):
        self.calls.append((up.clone(), down.clone()))


def _run(term, world_frame):
    n = len(term.cmd_sum_xy)
    terrain = Terrain(n)
    env = type("E", (), {})()
    env.command_manager = type("CM", (), {"get_term": lambda self, name: term})()
    env.scene, env.device, env.step_dt = type("S", (), {"terrain": terrain})(), "cpu", DT
    tlm.terrain_levels_mixed(env, torch.arange(n), "base_velocity", 4.0, world_frame=world_frame)
    up, down = terrain.calls[-1]

    return int(up[0]) - int(down[0])


COUNTER = [(0.5, 0.0), (0.0, math.pi / 4.0), (0.5, 0.0), (0.0, -math.pi / 4.0), (0.5, 0.0)]       # 전진 0.5 · 반바퀴 · 전진 · 반바퀴 · 전진, 20 s


def test_row_analyst_counterexample_switch_off_keeps_today_and_on_gives_zero():
    far, body, world = _sim(COUNTER)

    assert abs(far - 2.0) < 0.05 and abs(float(body[0, 0]) * DT / 4.0 - 1.5) < 1e-4                    # 몸 기준 합 1.5 m 상당, 실제 최대 거리 2 m
    assert rules.judge_free([2.0], [[1.5, 0.0]]).tolist() == [-1]
    assert _run(Term(far, body, world), False) == -1                                                  # 끔: 지금과 같음(오판 강등)
    assert abs(float(torch.linalg.norm(world[0])) * DT / 4.0 - 0.5) < 0.02                            # 세계 좌표 기대 변위 2 m -> 슬롯 단위 0.5
    assert _run(Term(far, body, world), True) == 0                                                    # 켬: 0
    assert rules.judge_free([2.0], [[0.5, 0.0]]).tolist() == [0]


def test_row_circle_with_switch_on_is_zero():
    far, body, world = _sim([(0.5, 0.5)] * 5)                                                         # 반지름 1 m 원운동 20 s

    assert far <= 2.05 and _run(Term(far, body, world), True) == 0


def test_row_straight_ten_meters_is_promoted_with_the_switch_off_or_on():
    far, body, world = _sim([(0.5, 0.0)] * 5)

    assert far > 4.0 and _run(Term(far, body, world), False) == 1 and _run(Term(far, body, world), True) == 1


def test_switch_off_is_bit_identical_to_a_term_without_the_world_sum_and_the_world_sum_never_changes_the_off_result():
    g = torch.Generator().manual_seed(3)
    far = torch.rand(300, generator=g) * 9.0
    body = (torch.rand(300, 2, generator=g) - 0.5) * 800.0
    world = (torch.rand(300, 2, generator=g) - 0.5) * 800.0
    a, b = Term(0, body, world), Term(0, body, world, with_world=False)
    a.max_dist = b.max_dist = far
    ta, tb = Terrain(300), Terrain(300)

    for term, terrain in ((a, ta), (b, tb)):
        env = type("E", (), {})()
        env.command_manager = type("CM", (), {"get_term": lambda self, name, t=term: t})()
        env.scene, env.device, env.step_dt = type("S", (), {"terrain": terrain})(), "cpu", DT
        tlm.terrain_levels_mixed(env, torch.arange(300), "base_velocity", 4.0, world_frame=False)    # 결정 8: 기본이 켬이라 끔은 인자로 준다

    assert torch.equal(ta.calls[-1][0], tb.calls[-1][0]) and torch.equal(ta.calls[-1][1], tb.calls[-1][1]) and (ta.calls[-1][1]).any()


def test_world_frame_without_the_sum_is_refused():
    far, body, world = _sim([(0.5, 0.0)] * 5)

    with pytest.raises(ValueError, match="cmd_sum_w"):
        _run(Term(far, body, world, with_world=False), True)


def test_both_judgements_are_recorded_in_a_nine_cell_table_with_marks_and_flag_envs_left_out():
    far, body, world = _sim(COUNTER)
    term = Term(far, body.repeat(3, 1), world.repeat(3, 1), mark=[False, True, False])
    term.is_flag_env[2] = True                                                                         # 깃발 env 는 표에서 뺀다
    _run_n(term, False)
    st = term.frame_stats.take()

    assert st["world_frame"] is False and st["episodes"] == 2
    assert st["unmarked"] == {"c-1w0": 1} and st["marked"] == {"c-1w0": 1} and st["mismatch"] == {"unmarked": 1, "marked": 1}
    assert term.frame_stats.take() is None                                                             # 꺼내면 비운다


def _run_n(term, world_frame):
    n = len(term.cmd_sum_xy)
    env = type("E", (), {})()
    env.command_manager = type("CM", (), {"get_term": lambda self, name: term})()
    env.scene, env.device, env.step_dt = type("S", (), {"terrain": Terrain(n)})(), "cpu", DT
    tlm.terrain_levels_mixed(env, torch.arange(n), "base_velocity", 4.0, world_frame=world_frame)


def test_world_step_rotates_by_the_actual_yaw():
    out = mc.world_cmd_step(torch.tensor([0.0, math.pi / 2, math.pi]), torch.tensor([[1.0, 0.0]] * 3))

    assert torch.allclose(out, torch.tensor([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]]), atol=1e-6)
    out = mc.world_cmd_step(torch.tensor([math.pi / 2]), torch.tensor([[0.0, 1.0]]))                  # 몸 기준 옆걸음은 세계의 -x

    assert torch.allclose(out, torch.tensor([[-1.0, 0.0]]), atol=1e-6)


def test_command_term_accumulates_clears_and_the_runner_records_it():
    cmd = (PKG / "commands/mixed_command.py").read_text(encoding="utf-8")
    run = (PKG / "runners/start_runner.py").read_text(encoding="utf-8")

    assert "self.cmd_sum_w += mc.world_cmd_step(yaw, self.vel_command_b[:, :2])" in cmd and "self.cmd_sum_w[env_ids] = 0.0" in cmd
    assert 'extra["world_frame_compare"] = fc_stats' in run and "def _take_frame_stats" in run
    assert 'world_frame: bool = True' in (PKG / "curriculum/terrain_levels_mixed.py").read_text(encoding="utf-8")


def test_perfect_following_simulation_with_the_real_resampler_demotes_only_with_the_old_frame():
    """5.3 마지막 행의 축소판(시드 0, 2000 에피소드): 실제 `resample_start`, 20 s = 5 슬롯, 완벽 추종. 켬 강등 0, 끔 강등 > 0 이고 모두 회전 뒤 전진."""
    gen = mc.make_generator(0, device="cpu")
    n = 2000
    yaw = torch.zeros(n)
    pos = torch.zeros(n, 2)
    body = torch.zeros(n, 2)
    world = torch.zeros(n, 2)
    far = torch.zeros(n)
    params = mc.CommandParams(start_mode=True)

    for _ in range(5):
        cmd = mc.resample_start(gen, n, params)["cmd"]
        for _ in range(SLOT):
            body += cmd[:, :2]
            step = mc.world_cmd_step(yaw, cmd[:, :2])
            world += step
            pos += step * DT
            yaw = yaw + cmd[:, 2] * DT
            far = torch.maximum(far, torch.linalg.norm(pos, dim=1))

    old = rules.judge_free(far, body * DT / 4.0)
    new = rules.judge_free(far, world * DT / 4.0)

    assert int((new < 0).sum()) == 0 and int((old < 0).sum()) > 0 and int((old < 0).sum()) < 0.03 * n
    assert float((new > 0).float().mean()) > 0.9


def test_decision_8_default_is_on_and_old_behavior_stays_behind_the_argument():
    import inspect

    assert inspect.signature(tlm.terrain_levels_mixed).parameters["world_frame"].default is True
    far, body, world = _sim(COUNTER)
    term = Term(far, body, world)
    env = type("E", (), {})()
    env.command_manager = type("CM", (), {"get_term": lambda self, name: term})()
    terrain = Terrain(1)
    env.scene, env.device, env.step_dt = type("S", (), {"terrain": terrain})(), "cpu", DT
    tlm.terrain_levels_mixed(env, torch.arange(1), "base_velocity", 4.0)                              # 인자 없음 = 켬
    up, down = terrain.calls[-1]

    assert int(up[0]) - int(down[0]) == 0 and _run(Term(far, body, world), False) == -1


class _Cur:
    def __init__(self, func, params=None):
        self.func, self.params = func, params


def _cfg(func, params=None):
    return type("C", (), {"curriculum": type("U", (), {"terrain_levels": _Cur(func, params)})()})()


def test_judge_settings_report_the_values_actually_used_for_s1_and_s2_terms_and_the_config_can_turn_it_off():
    assert tlm.judge_settings(_cfg(tlm.terrain_levels_mixed)) == {"world_frame": True, "mask_new_task": False}
    assert tlm.judge_settings(_cfg(tlm.terrain_levels_s2, {"t_start": 1000})) == {"world_frame": True, "mask_new_task": False}
    assert tlm.judge_settings(_cfg(tlm.terrain_levels_s2, {"world_frame": False, "mask_new_task": True})) == {"world_frame": False, "mask_new_task": True}
    assert tlm.judge_settings(type("C", (), {"curriculum": type("U", (), {})()})()) == {}


def test_run_arguments_write_into_the_term_params_and_unknown_terms_are_refused():
    cfg = _cfg(tlm.terrain_levels_s2, {"t_start": 1000})
    tlm.apply_judge_args(cfg, "off", "on")

    assert cfg.curriculum.terrain_levels.params == {"t_start": 1000, "world_frame": False, "mask_new_task": True}
    assert tlm.judge_settings(cfg) == {"world_frame": False, "mask_new_task": True}
    tlm.apply_judge_args(cfg, None, None)                                                              # None 은 건드리지 않음
    assert tlm.judge_settings(cfg) == {"world_frame": False, "mask_new_task": True}

    with pytest.raises(ValueError, match="world_frame"):
        tlm.apply_judge_args(_cfg(lambda env, env_ids: 0), "off", None)


def test_s2_term_passes_world_frame_and_mask_through_and_train_start_records_and_exposes_them():
    src = (PKG / "curriculum/terrain_levels_mixed.py").read_text(encoding="utf-8")
    run = (PKG / "scripts/train_start.py").read_text(encoding="utf-8")

    assert "terrain_levels_mixed(env, env_ids, command_name, resample_s, world_frame=world_frame, mask_new_task=mask_new_task)" in src
    assert '"terrain_judge": tlm.judge_settings(env_cfg)' in run and "--judge_world_frame" in run and "--judge_mask_new_task" in run
    assert run.index("tlm.apply_judge_args(") < run.index("gym.make(") < run.index("tlm.judge_settings(env_cfg)")        # 인자 반영은 env 만들기 앞, 기록은 뒤


def test_parent_judge_reads_the_parent_manifest_and_falls_back_to_the_old_judgement_text(tmp_path):
    import json

    ck = tmp_path / "model_1500.pt"
    ck.write_bytes(b"x")

    assert tlm.parent_judge(ck) == "world_frame=False (10/26 이전)" and tlm.judged_with(tlm.parent_judge(ck)) == "body_frame"            # manifest 없음
    (tmp_path / "manifest.json").write_text(json.dumps({"modes": {"seed": 1}}), encoding="utf-8")

    assert tlm.parent_judge(ck) == "world_frame=False (10/26 이전)"                                                                  # terrain_judge 키 없음(결정 8 이전 판)
    (tmp_path / "manifest.json").write_text(json.dumps({"modes": {"terrain_judge": {"world_frame": True, "mask_new_task": False}}}), encoding="utf-8")
    got = tlm.parent_judge(ck)

    assert got == {"world_frame": True, "mask_new_task": False} and tlm.judged_with(got) == "world_frame"
    (tmp_path / "manifest.json").write_text("{not json", encoding="utf-8")

    assert tlm.parent_judge(ck) == "world_frame=False (10/26 이전)"


def test_sb_task_chain_sets_the_terrain_levels_term_only_in_s2_env_cfg_so_the_defaults_are_what_run_and_args_pin_them_into_params():
    import re

    chain = ["s2_sb_cfg", "s2_23f_b_cfg", "s2_x23_cfg", "s2_env_cfg"]
    srcs = {n: (PKG / f"tasks/{n}.py").read_text(encoding="utf-8") for n in chain}
    owners = [n for n, t in srcs.items() if re.search(r"curriculum\.terrain_levels\s*=", t)]

    assert owners == ["s2_env_cfg"] and "func=tlm.terrain_levels_s2, params={\"t_start\": t_start, \"t_end\": t_end}" in srcs["s2_env_cfg"]
    cfg = _cfg(tlm.terrain_levels_s2, {"t_start": 1000, "t_end": 8000})

    assert tlm.judge_settings(cfg) == {"world_frame": True, "mask_new_task": False}
    tlm.apply_judge_args(cfg, None, None)                                                              # 인자가 없어도 실제 값을 params 에 박는다(env.yaml 에 남음)

    assert cfg.curriculum.terrain_levels.params == {"t_start": 1000, "t_end": 8000, "world_frame": True, "mask_new_task": False}
    tlm.apply_judge_args(type("C", (), {"curriculum": None})(), None, None)                          # term 이 없는 task 는 인자가 없으면 그냥 지나감

    with pytest.raises(ValueError):
        tlm.apply_judge_args(type("C", (), {"curriculum": None})(), "off", None)


def test_sol23f_common_exposes_the_args_and_records_judge_and_parent_judge_in_the_manifest_in_order():
    run = (PKG / "scripts/train_sol23f_common.py").read_text(encoding="utf-8")

    assert "--judge_world_frame" in run and "--judge_mask_new_task" in run
    assert '"terrain_judge": tlm.judge_settings(env_cfg)' in run and '"parent_judge": tlm.parent_judge(resume_path)' in run and '"start_checkpoint_judged_with"' in run
    assert run.index("tlm.apply_judge_args(") < run.index("gym.make(") < run.index("tlm.judge_settings(env_cfg)")
    assert 'sys.argv = [sys.argv[0], "--task", "FootholdS2-Go2-S2-SB-v0", "--variant", "SB", *sys.argv[1:]]' in (PKG / "scripts/train_sb.py").read_text(encoding="utf-8")        # train_sb 는 나머지 인자를 그대로 넘김
