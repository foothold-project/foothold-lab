"""M-T6 끔 대상 지형 (DESIGN-MAPRATIO v0.6 3.2 · 7 절). CPU, 가짜 env 로 실제 StartRunner 를 돌린다.

연속 7 종 + flat 은 끔 허용, 듬성 5 종은 0. 지형 이름으로만 정하고 레벨은 안 본다. 뽑기는 n 개 전부 뽑은 뒤 & eligible 이라 난수열 소비가 같다.
읽는 자리는 env.step 이 끝난 뒤의 칸(새 에피소드 값). 23 열 연속 배치(S1-a)에서는 지금 코드와 비트 동일.
"""

import json

import pytest
import torch

from foothold_s2.runners import map_switch as MS
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.terrains import columns
from foothold_s2.tests.start_fake_env import train_cfg
from foothold_s2.tests.test_mapratio import HookEnv


class _Sub:
    def __init__(self, p):
        self.proportion = p


class TerrEnv(HookEnv):
    """HookEnv 에 지형 importer 흉내를 붙인 env: terrain_types 는 env 번호로 고정(재배정은 reassign 으로 시험이 부름), 로봇 위치는 xy."""

    def __init__(self, props, num_cols, num_envs=64, rows=10, seed=0):
        super().__init__(num_envs=num_envs, seed=seed)
        self.xy = torch.zeros(num_envs, 2)
        terrain = type("T", (), {})()
        terrain.terrain_types = torch.arange(num_envs) % num_cols
        terrain.terrain_levels = torch.arange(num_envs) % rows
        terrain.terrain_origins = torch.zeros(rows, num_cols, 3)
        terrain.terrain_origins[..., 0] = torch.arange(num_cols).float()[None, :] * 10.0              # 칸 중심: 열 j 는 x = 10 j
        terrain.terrain_origins[..., 1] = torch.arange(rows).float()[:, None] * 10.0
        terrain.cfg = type("C", (), {"terrain_generator": type("G", (), {"sub_terrains": {k: _Sub(v) for k, v in props.items()}, "num_cols": num_cols})()})()
        env = self
        robot = type("R", (), {})()
        robot.data = type("D", (), {"root_pos_w": property(lambda d: torch.cat([env.xy, torch.zeros(len(env.xy), 1)], dim=1))})()         # 시험이 xy 를 바꾸면 바로 읽힌다
        self.robot = robot
        self.scene = type("S", (), {"terrain": terrain, "__getitem__": lambda s, k: robot})()
        self.terrain = terrain

def _runner(env, p, log_dir=None, **kw):
    torch.manual_seed(0)
    r = StartRunner(env, train_cfg(24, {"microbatch_envs": 4, "p_map_off": p, **kw}), log_dir=log_dir, device="cpu")
    env.runner = r

    return r


FULL50 = columns.FULL
NAMES50 = columns.column_types(columns.FULL, columns.FULL_COLS)
NAMES23 = columns.column_types(columns.CONTINUOUS, columns.CONTINUOUS_COLS)


def test_eligibility_is_by_name_only_continuous_and_flat_yes_sparse_no_levels_ignored():
    types = torch.arange(columns.FULL_COLS)
    ok = MS.eligible_map_off(types, torch.zeros(columns.FULL_COLS, dtype=torch.long), NAMES50)

    for j, name in enumerate(NAMES50):
        assert bool(ok[j]) == (name in columns.CONTINUOUS or name == "flat"), (j, name)
    assert not any(bool(ok[j]) for j, n in enumerate(NAMES50) if n in ("gaps", "stepping_stones_low", "stepping_stones_high", "balance_beams", "stepping_beams"))
    assert "flat" in NAMES50 and bool(ok[NAMES50.index("flat")]) and bool(ok[NAMES50.index("pyramid_stairs")])
    other = MS.eligible_map_off(types, torch.full((columns.FULL_COLS,), 9, dtype=torch.long), NAMES50)

    assert torch.equal(ok, other)                                                                      # 레벨만 바꾼 입력은 결과 불변
    assert MS.eligible_map_off(torch.arange(23), torch.zeros(23), NAMES23).all()                       # S1-a 23 열은 전부 허용


def test_unknown_column_name_is_refused():
    with pytest.raises(ValueError, match="끔 대상"):
        MS.check_column_names(["pyramid_stairs", "lava"])
    with pytest.raises(ValueError, match="끔 대상"):
        MS.eligible_map_off(torch.tensor([0, 1]), torch.zeros(2), ["gaps", "mystery"])


def test_23_column_continuous_layout_is_bit_identical_to_a_run_without_the_terrain_tools():
    props = dict(columns.CONTINUOUS)
    a = _runner(TerrEnv(props, 23), 0.3)
    b = _runner(HookEnv(num_envs=64, seed=0), 0.3)                                                      # 지형 도구가 없는 env = 지금 코드의 경로
    a.learn(3)
    b.learn(3)

    assert torch.equal(a.pstate.map_off, b.pstate.map_off) and bool(a.pstate.map_off.any())
    assert torch.equal(a.map_switch_gen.get_state(), b.map_switch_gen.get_state())                      # 난수열 소비가 같다
    assert a.map_switch.summary()["off_frac_steps"] == b.map_switch.summary()["off_frac_steps"]


def test_full_50_column_layout_never_turns_the_map_off_on_sparse_columns_and_keeps_the_ratio_on_the_rest(tmp_path):
    env = TerrEnv(dict(columns.FULL), columns.FULL_COLS)
    r = _runner(env, 0.3, log_dir=str(tmp_path))
    sparse_envs = torch.tensor([n in columns.SPARSE and n != "flat" for n in NAMES50])[env.terrain.terrain_types]
    seen_off, seen_n, sparse_off = 0, 0, 0
    orig = env.reward_hook

    def hook(rewards, runner):
        nonlocal seen_off, seen_n, sparse_off
        off = runner.pstate.map_off.bool()
        sparse_off += int((off & sparse_envs).sum())
        seen_off += int((off & ~sparse_envs).sum())
        seen_n += int((~sparse_envs).sum())

        return rewards if orig is None else orig(rewards, runner)

    env.reward_hook = hook
    r.learn(6)

    assert sparse_envs.any() and sparse_off == 0                                                        # 듬성 열 env 는 끔 0
    assert abs(seen_off / seen_n - 0.3) <= 0.04                                                         # 허용 열 env 의 실제 끔 비율이 p ± 0.04 (허용 칸 안에서 0.3)
    rows = [json.loads(ln) for ln in (tmp_path / "map_switch.jsonl").read_text(encoding="utf-8").splitlines()]
    st = [x["off_eligibility"] for x in rows if x.get("off_eligibility")]

    assert st and sum(s["sparse_starts"] for s in st) > 0 and all(s["off_starts"] <= s["eligible_starts"] for s in st) and sum(s["off_starts"] for s in st) > 0
    ev = [e for e in r.map_ratio_events if e["kind"] == "off_eligibility"][0]

    assert "gaps" in ev["sparse"] and "flat" in ev["eligible"] and ev["num_cols"] == 50 and sum(ev["column_counts"].values()) == 50


def test_the_draw_still_consumes_the_generator_for_all_envs_not_only_the_eligible_ones():
    env = TerrEnv(dict(columns.FULL), columns.FULL_COLS)
    r = _runner(env, 0.3)
    s0 = r.map_switch_gen.get_state().clone()
    r.pstate = r.perception.init_state(64, "cpu")
    off = MS.draw_map_off(64, 0.3, "cpu", r.map_switch_gen)
    r.map_switch_gen.set_state(s0)
    out = r._restrict_map_off(MS.draw_map_off(64, 0.3, "cpu", r.map_switch_gen), torch.ones(64, dtype=torch.bool))

    assert torch.equal(torch.where(out, off, torch.zeros_like(off)), out) and (out <= off).all() and int(out.sum()) < int(off.sum())     # n 개를 모두 뽑고 허용 칸만 남긴다


def test_the_cell_is_read_after_the_step_so_a_reassigned_env_uses_its_new_column():
    env = TerrEnv(dict(columns.FULL), columns.FULL_COLS)
    r = _runner(env, 1.0)
    sparse_col = NAMES50.index("gaps")
    easy_col = NAMES50.index("pyramid_stairs")
    env.terrain.terrain_types[:] = sparse_col                                                           # 새 에피소드가 전부 듬성 칸에 배정된 상태
    out = r._restrict_map_off(MS.draw_map_off(64, 1.0, "cpu", r.map_switch_gen), torch.ones(64, dtype=torch.bool))

    assert not out.any()
    env.terrain.terrain_types[:] = easy_col

    assert r._restrict_map_off(MS.draw_map_off(64, 1.0, "cpu", r.map_switch_gen), torch.ones(64, dtype=torch.bool)).all()


def test_off_episodes_that_ended_on_a_sparse_tile_are_counted_from_the_position(tmp_path):
    env = TerrEnv(dict(columns.FULL), columns.FULL_COLS)
    env.terrain.terrain_types[:] = NAMES50.index("pyramid_stairs")                                      # 시작 칸은 모두 허용(끔)
    gap = NAMES50.index("gaps")
    env.xy[:, 0] = gap * 10.0 + 0.5                                                                     # 위치는 gaps 열 칸 안(이동해 들어갔다)
    env.xy[:, 1] = 20.0
    r = _runner(env, 1.0, log_dir=str(tmp_path))
    r.learn(2)
    rows = [json.loads(ln) for ln in (tmp_path / "map_switch.jsonl").read_text(encoding="utf-8").splitlines()]
    st = [x["off_eligibility"] for x in rows if x.get("off_eligibility")]

    assert sum(s["off_ended"] for s in st) > 0 and sum(s["off_ended_on_sparse_prev_step"] for s in st) == sum(s["off_ended"] for s in st)
    env2 = TerrEnv(dict(columns.FULL), columns.FULL_COLS)
    env2.terrain.terrain_types[:] = NAMES50.index("pyramid_stairs")
    env2.xy[:, 0] = NAMES50.index("pyramid_stairs") * 10.0
    r2 = _runner(env2, 1.0, log_dir=str(tmp_path / "b"))
    (tmp_path / "b").mkdir()
    r2.learn(2)
    rows = [json.loads(ln) for ln in (tmp_path / "b" / "map_switch.jsonl").read_text(encoding="utf-8").splitlines()]

    assert sum(x["off_eligibility"]["off_ended_on_sparse_prev_step"] for x in rows if x.get("off_eligibility")) == 0


def test_an_env_without_terrain_tools_keeps_every_cell_eligible_and_records_nothing():
    r = _runner(HookEnv(num_envs=16, seed=0), 0.5)
    r.learn(1)

    assert r.off_elig is None if hasattr(r, "off_elig") else True
    assert not [e for e in r.map_ratio_events if e["kind"] == "off_eligibility"]


def test_per_name_and_level_denominators_and_numerators_are_recorded_and_the_end_position_is_labelled_approximate(tmp_path):
    env = TerrEnv(dict(columns.FULL), columns.FULL_COLS)
    r = _runner(env, 0.5, log_dir=str(tmp_path))
    r.learn(4)
    rows = [json.loads(ln) for ln in (tmp_path / "map_switch.jsonl").read_text(encoding="utf-8").splitlines()]
    st = [x["off_eligibility"] for x in rows if x.get("off_eligibility")]
    by = {}

    for s in st:
        assert "마지막 물리 step 이전" in s["ended_position_note"] and "off_ended_on_sparse" not in s
        for name, v in s["by_name"].items():
            t = by.setdefault(name, [0, 0, 0])
            t[0] += v["starts"]
            t[1] += v["eligible_starts"]
            t[2] += v["off_starts"]
            assert v["starts"] == sum(x["starts"] for x in v["by_level"].values()) and v["off_starts"] == sum(x["off_starts"] for x in v["by_level"].values())

    assert by and sum(v[0] for v in by.values()) == sum(s["starts"] for s in st)
    assert all(v[2] == 0 and v[1] == 0 for k, v in by.items() if k in ("gaps", "stepping_stones_low", "stepping_stones_high", "balance_beams", "stepping_beams"))     # 듬성 이름: 허용 0 · 끔 0
    assert any(v[2] > 0 for k, v in by.items() if k in ("pyramid_stairs", "flat", "boxes")) and by["gaps"][0] > 0                                                      # 분모(시작 수)는 듬성도 남는다
    assert {lv for s in st for v in s["by_name"].values() for lv in v["by_level"]} <= {str(i) for i in range(10)}


def test_ended_stats_stay_zero_for_the_boundary_case_documented_as_an_approximation():
    st = MS.OffEligibilityStats()
    st.add_ended(torch.tensor([True]), torch.tensor([False]))                     # 마지막 step 직전 위치가 허용 칸이면 센다(경계를 마지막 step 에 넘은 종료는 못 센다: 알려진 근사)
    out = st.take()

    assert out["off_ended"] == 1 and out["off_ended_on_sparse_prev_step"] == 0 and "근사" in out["ended_position_note"]
