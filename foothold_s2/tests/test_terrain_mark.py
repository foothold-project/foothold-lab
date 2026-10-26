"""J-T5: 지형 커리큘럼의 새 과제 표식 (JUDGE-SPEC v0.2 5 절). CPU, Kit 없음.

5.3 의 «답 아는 입력» 일곱 줄과, 명령 term(Isaac 안에서만 import 됨)의 호출 순서 대조(AST), 지형 커리큘럼 term 의 실제 함수를 가짜 env 로 돌린 시험.
설계 동의와 구현 통과는 별개다: Kit 안에서 1000 스텝 비트 동등성은 미확인이다(여기서는 같은 규칙 함수 · 같은 term 함수를 CPU 에서 돌려 확인).
"""

import ast
from pathlib import Path

import pytest
import torch

from foothold_s2.commands import mixed_core as mc
from foothold_s2.curriculum import rules
from foothold_s2.curriculum import terrain_levels_mixed as tlm

PKG = Path(__file__).resolve().parents[1]
START = mc.CommandParams(start_mode=True)
OLD = mc.CommandParams()                                                  # 옛 혼합 명령(start_mode 끔)


def judge_example(mark):
    """5.1 반례: 원운동(vx 0.5 · wz 0.5 로 20 s, 반지름 1 m)은 max_dist 2 m, 명령 합 10 m 로 강등으로 읽힌다."""
    move = rules.judge_free([10.0, 2.0], [[2.5, 0.0], [2.5, 0.0]])

    return rules.mask_new_task(move, mark).tolist()


# ------------------------------------------------------------------ 5.3 답 아는 입력 일곱 줄


def test_5_3_row1_unmarked_episodes_keep_todays_rule():
    assert rules.judge_free([10.0, 2.0], [[2.5, 0.0], [2.5, 0.0]]).tolist() == [1, -1]                  # 지금 코드의 오판: 원운동이 강등
    assert judge_example([False, False]) == [1, -1]


def test_5_3_row2_a_marked_episode_is_neither_promoted_nor_demoted():
    assert judge_example([False, True]) == [1, 0]
    assert judge_example([True, True]) == [0, 0]                                                       # 승급 · 강등 둘 다 막고 행을 유지


def test_5_3_row3_spin_only_episode_is_already_outside_the_judgement():
    assert rules.judge_free([0.0], [[0.0, 0.0]]).tolist() == [0] and rules.mask_new_task(rules.judge_free([0.0], [[0.0, 0.0]]), [False]).tolist() == [0]


def test_5_3_row4_walk_turn_then_straight_then_reset_is_still_marked_when_read():
    """새 과제 -> 직진 -> reset: curriculum 이 읽는 시점(reset 직전)에 표식 참. 마지막 명령이 직진이어도 0 이 된다. command reset 에서 비운다."""
    mk = mc.NewTaskMark(2)
    ids = torch.arange(2)
    mk.clear(ids)
    mk.on_resample(ids, torch.tensor([[0.5, 0.0, 0.5], [1.0, 0.0, 0.0]]), START)               # env 0 은 걸으며 돌기, env 1 은 직진
    mk.on_resample(ids, torch.tensor([[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]), START)               # 다음 재추출은 둘 다 직진(마지막 명령은 직진)

    assert mk.flag.tolist() == [True, False]
    move = rules.mask_new_task(rules.judge_free([10.0, 10.0], [[2.5, 0.0], [2.5, 0.0]]), mk.flag)
    assert move.tolist() == [0, 1]                                                                    # 표식 참은 0, 직진 env 는 승급 그대로
    mk.clear(ids)                                                                                    # command reset
    assert mk.flag.tolist() == [False, False]


def test_5_3_row5_partial_reset_clears_only_that_env():
    mk = mc.NewTaskMark(5)
    mk.on_resample(torch.arange(5), torch.tensor([[0.5, 0.0, 0.5]] * 5), START)
    mk.clear(torch.tensor([3]))

    assert mk.flag.tolist() == [True, True, True, False, True]


def test_5_3_row5b_cleared_right_after_reset_but_may_be_true_after_the_new_resample():
    """«비운 직후» 와 «새 과제를 재추출한 직후» 를 나눈다."""
    mk = mc.NewTaskMark(3)
    ids = torch.tensor([1])
    mk.on_resample(torch.arange(3), torch.tensor([[0.5, 0.0, 0.5]] * 3), START)
    mk.clear(ids)

    assert mk.flag.tolist() == [True, False, True]                                                    # 비운 직후: 거짓
    mk.on_resample(ids, torch.tensor([[1.0, 0.0, 0.0]]), START)
    assert mk.flag.tolist() == [True, False, True]                                                    # 재추출이 직진이면 계속 거짓
    mk.on_resample(ids, torch.tensor([[0.5, 0.0, -0.5]]), START)
    assert mk.flag.tolist() == [True, True, True]                                                     # 재추출이 다시 새 과제면 참


def test_5_3_row6_leftover_commands_from_the_old_contract_are_not_new_tasks():
    """창 전환 직후 잔여 명령이 옛 계약(S1 직진 · spin)이어도 표식은 거짓. 표식은 재추출 때만 켜지고 명령 값에서 매 스텝 유도하지 않는다."""
    mk = mc.NewTaskMark(4)
    old_contract = torch.tensor([[1.2, 0.0, 0.0], [0.0, 0.0, 1.2], [0.0, 0.0, -1.2], [0.4, 0.0, 0.0]])
    mk.on_resample(torch.arange(4), old_contract, START)

    assert mk.flag.tolist() == [False] * 4
    assert mc.new_task_mask(torch.tensor([[0.5, 0.0, 0.5]]), OLD).tolist() == [False]                  # 옛 혼합 명령(start_mode 아님)은 표식 대상이 아니다


def test_5_3_row7_s1_contract_1000_steps_never_marks_and_the_curriculum_result_is_bit_identical():
    gen = mc.make_generator(11)
    n = 64
    mk = mc.NewTaskMark(n)
    ids = torch.arange(n)
    ever = torch.zeros(n, dtype=torch.bool)

    for step in range(1000):                                                                           # 재추출 1000 번(S1 START 명령 계약)
        out = mc.resample_start(gen, n, START)
        mk.on_resample(ids, out["cmd"], START)
        ever |= mk.flag

        if step % 7 == 0:
            mk.clear(torch.tensor([step % n]))

    assert int(mk.flag.sum()) == 0 and int(ever.sum()) == 0                                            # 표식 참 수 0
    g = torch.Generator().manual_seed(5)
    max_dist = torch.rand(200, generator=g) * 9.0
    cmd_sum = (torch.rand(200, 2, generator=g) - 0.5) * 8.0
    base = rules.judge_free(max_dist, cmd_sum)
    after = rules.mask_new_task(base, torch.zeros(200, dtype=torch.bool))

    assert torch.equal(base, after) and base.dtype == after.dtype and (base != 0).any()                  # 승급 · 강등 결과가 수정 전과 비트 단위로 같다


# ------------------------------------------------------------------ 표식을 켜는 때 · 읽는 때


def test_marking_rule_is_walk_plus_turn_only_and_only_under_the_start_contract():
    cmd = torch.tensor([[0.5, 0.0, 0.5], [0.5, 0.0, -0.5], [0.0, 0.0, 1.2], [1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [-0.3, 0.0, 0.5], [0.5, 0.0, 1e-9]])

    assert mc.new_task_mask(cmd, START).tolist() == [True, True, False, False, False, False, False]
    assert mc.new_task_mask(cmd, OLD).tolist() == [False] * 7


def test_a_per_step_new_task_is_marked_when_it_is_actually_consumed_not_by_the_last_command():
    mk = mc.NewTaskMark(3)
    mk.on_consumed(torch.tensor([False, True, False]))                                                 # S4 같은 매 스텝 바뀌는 과제가 env 1 에서 소비된 스텝
    mk.on_resample(torch.arange(3), torch.tensor([[1.0, 0.0, 0.0]] * 3), START)                       # 이후 재추출이 직진이어도 표식은 남는다

    assert mk.flag.tolist() == [False, True, False]


# ------------------------------------------------------------------ 지형 커리큘럼 term (가짜 env 로 실제 함수를 호출)


class FakeTerrain:
    def __init__(self, levels, size_x=8.0):
        self.terrain_levels = torch.as_tensor(levels).long()
        self.cfg = type("C", (), {"terrain_generator": type("G", (), {"size": (size_x, size_x)})()})()
        self.calls = []

    def update_env_origins(self, env_ids, move_up, move_down):
        self.calls.append((env_ids.clone(), move_up.clone(), move_down.clone()))


class FakeTerm:
    def __init__(self, max_dist, cmd_sum_xy, mark):
        n = len(max_dist)
        self.cmd_sum_xy = torch.as_tensor(cmd_sum_xy, dtype=torch.float32)
        self.max_dist = torch.as_tensor(max_dist, dtype=torch.float32)
        self.is_flag_env = torch.zeros(n, dtype=torch.bool)
        self.goals = torch.zeros(n, dtype=torch.long)
        self.walk_frac = torch.ones(n)
        self.cfg = type("C", (), {"flag_count": 4})()
        self.had_new_task = torch.as_tensor(mark, dtype=torch.bool) if mark is not None else None
        self.new_task_stats = rules.NewTaskStats()


def run_tlm(term, terrain, ids, without_attr=False):
    if without_attr:
        del term.had_new_task

    cm = type("CM", (), {"get_term": lambda self, name: term})()
    env = type("E", (), {})()
    env.command_manager, env.scene, env.device = cm, type("S", (), {"terrain": terrain})(), "cpu"
    env.step_dt = 0.02
    tlm.terrain_levels_mixed(env, torch.as_tensor(ids), "base_velocity", 4.0)

    return terrain.calls[-1]


def test_terrain_levels_mixed_skips_marked_episodes_end_to_end_with_a_fake_env():
    # cmd_sum 는 step_dt/4 s 로 곱해지므로 «한 번 뽑힌 값 x 200 스텝» 으로 넣는다: 2.5 m/s 상당
    term = FakeTerm([10.0, 2.0, 10.0, 2.0], [[500.0, 0.0]] * 4, [False, False, True, True])
    terrain = FakeTerrain([2, 2, 3, 3])
    ids, up, down = run_tlm(term, terrain, [0, 1, 2, 3])

    assert up.tolist() == [True, False, False, False] and down.tolist() == [False, True, False, False]   # 표식 있는 둘은 승급도 강등도 아님
    st = term.new_task_stats.take()
    assert st["episodes"] == 4 and st["marked"] == 2 and st["marked_frac"] == 0.5
    assert st["unmarked"] == {"up": 1, "down": 1, "stay": 0} and st["marked_would_have"] == {"up": 1, "down": 1, "stay": 0}
    assert st["marked_actual"] == {"up": 0, "down": 0, "stay": 2} and st["per_row"] == {"2": 2, "3": 2} and st["per_row_marked"] == {"2": 0, "3": 2}
    assert term.new_task_stats.take() is None                                                         # 꺼내면 비운다


def test_terrain_levels_mixed_with_no_marks_equals_the_old_path_and_without_the_attribute_is_untouched():
    mx, cs = [10.0, 2.0, 5.0, 0.1], [[500.0, 0.0], [500.0, 0.0], [0.0, 0.0], [500.0, 0.0]]
    _i, up0, down0 = run_tlm(FakeTerm(mx, cs, [False] * 4), FakeTerrain([1, 1, 1, 1]), [0, 1, 2, 3])
    _i, up1, down1 = run_tlm(FakeTerm(mx, cs, None), FakeTerrain([1, 1, 1, 1]), [0, 1, 2, 3], without_attr=True)         # 표식 속성이 없는 옛 명령 term

    assert torch.equal(up0, up1) and torch.equal(down0, down1) and up0.tolist() == [True, False, False, False] and down0.tolist() == [False, True, False, True]


def test_partial_curriculum_call_only_looks_at_the_given_envs():
    term = FakeTerm([10.0] * 4, [[500.0, 0.0]] * 4, [True, False, True, False])
    _i, up, _d = run_tlm(term, FakeTerrain([0, 0, 0, 0]), [1, 2])

    assert up.tolist() == [True, False]                                                               # env 1(표식 없음)은 승급, env 2(표식 있음)는 0


# ------------------------------------------------------------------ Isaac 안 명령 term 은 AST 로 (CPU 에는 isaaclab 이 없다)


def _method(path, cls, name):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    c = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)

    return next(n for n in c.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _calls(fn):
    out = []

    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            out.append((n.lineno, ast.unparse(n.func)))

    return sorted(out)


def test_command_term_clears_in_reset_episode_state_before_the_resample_that_may_set_it_again():
    path = PKG / "commands/mixed_command.py"
    rs = _method(path, "MixedVelocityCommand", "_reset_episode_state")
    reset = _method(path, "MixedVelocityCommand", "reset")
    rc = _method(path, "MixedVelocityCommand", "_resample_command")

    assert ast.unparse(rs.body[0]) == "self.new_task.clear(env_ids)"                                  # 첫 문장: 지난 에피소드 표식을 비운다
    names = [f for _l, f in _calls(reset)]
    assert names.index("self._reset_episode_state") < names.index("super().reset")                    # 비움은 재추출(super().reset 안)보다 앞
    assert "self.new_task.on_resample" in [f for _l, f in _calls(rc)]
    free_block = ast.unparse(rc)
    assert free_block.index("self.new_task.on_resample") < free_block.index("self.cfg.fixed_cmd")      # 평가 고정 명령 덮어쓰기 이전의 뽑힌 값으로 분류


def test_command_term_exposes_the_marker_and_the_curriculum_reads_it_between_judge_and_origin_update():
    cmd_src = (PKG / "commands/mixed_command.py").read_text(encoding="utf-8")
    cur_src = (PKG / "curriculum/terrain_levels_mixed.py").read_text(encoding="utf-8")

    assert "def had_new_task" in cmd_src and "def mark_new_task_consumed" in cmd_src and "self.new_task_stats = curriculum_rules.NewTaskStats()" in cmd_src
    i_judge, i_mask, i_update = cur_src.index("move = rules.judge("), cur_src.index("rules.mask_new_task(move, marked)"), cur_src.index("terrain.update_env_origins(env_ids, move > 0, move < 0)")
    assert i_judge < i_mask < i_update                                                                # 판정 뒤, 지형 이동 앞


def test_runner_writes_the_mark_statistics_into_train_extra():
    src = (PKG / "runners/start_runner.py").read_text(encoding="utf-8")

    assert "def _take_new_task_stats" in src and 'extra["new_task_mark"] = nt_stats' in src and "nt_stats is not None) and self.log_dir" in src


def test_stats_accumulate_across_calls_until_taken():
    s = rules.NewTaskStats()
    s.add([1, -1, 0], [False, True, False], [0, 0, 1])
    s.add([1], [True], [1])
    t = s.take()

    assert t["episodes"] == 4 and t["marked"] == 2 and t["unmarked"] == {"up": 1, "down": 0, "stay": 1} and t["marked_would_have"] == {"up": 1, "down": 1, "stay": 0}
    assert t["per_row"] == {"0": 2, "1": 2} and t["per_row_marked"] == {"0": 1, "1": 1}
