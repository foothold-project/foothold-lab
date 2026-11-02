"""D94 · D125 DR 켠 평가 모드의 답 아는 CPU 시험. Kit · CUDA 없음.

끝점: 끔 모드는 아무것도 설치 · 기록하지 않고(출력 키 불변 · 끔 블록은 실제 코드를 실행해 확인), 켠 모드는 시동 DR 둘을
지우지 않고 런타임 DR 다섯을 학습과 같은 설치 함수 서명으로 설치하며, 롤아웃마다 가운데 step 에 밀기를 정확히 한 번 env
전부에 넣고, 배율 0 에서는 표본이 명목값 · 배율 1.0 에서는 표본이 전체 범위 안이며 이벤트마다 env 전부에 닿았을 때만 통과한다.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from foothold_s2.eval import eval_dr_mode as M

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "foothold_s2" / "eval" / "eval_map_modes.py"
EX40 = ROOT / "foothold_s2" / "curriculum" / "ex40.yaml"
REAL_M6000 = Path("C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch-b/model_6000_d5e9ec400f33/map64/map_modes.json")
N = 64


def args(**over):
    base = dict(dr_mode="off", dr_scale=1.0, dr_table=str(M.DEFAULT_TABLE), axis_v2=False, eval_seed=42)
    base.update(over)
    return SimpleNamespace(**base)


def b_env_cfg(**events):
    ev = {"physics_material": object(), "add_base_mass": object()}
    ev.update(events)
    return SimpleNamespace(events=SimpleNamespace(**ev),
                           actions=SimpleNamespace(joint_pos=SimpleNamespace(asset_name="robot", joint_names=[".*"])))


def fake_installer(calls):
    def install(env_cfg, ranges, push_interval_s, *, delay_max_s):
        calls.append((ranges, push_interval_s, delay_max_s))
        for name in M.RUNTIME_RESET_TERMS:
            setattr(env_cfg.events, name, SimpleNamespace(func=lambda *a, **k: None, mode="reset"))
        env_cfg.events.ex40_push = SimpleNamespace(func=lambda *a, **k: None, mode="interval", interval_range_s=push_interval_s)
        env_cfg.actions.joint_pos = SimpleNamespace(max_delay_s=delay_max_s, dr_scale_from_env=True)
        return {"reset_terms": list(M.RUNTIME_RESET_TERMS), "interval_terms": ["ex40_push"], "delay_max_s": delay_max_s}
    return install


def summary(scale, *, com=None, gains=None, motor=None, push=None, allowed=None, observed=None, counts=N, envs=N,
            push_envs=N, push_count=None, delay=True, delay_resets=N, dt=0.005):
    """RuntimeReadback.summary() 꼴의 가짜: 배율만큼 접힌 전체 범위 표본 · env 전부에 닿음 · 밀기 한 번."""
    full = {"base_com_offset_m": (-0.05 * scale, 0.05 * scale), "actuator_gains": (1 - 0.1 * scale, 1 + 0.1 * scale),
            "motor_strength_multiplier": (1 - 0.1 * scale, 1 + 0.1 * scale)}
    given = {"base_com_offset_m": com, "actuator_gains": gains, "motor_strength_multiplier": motor}
    samples = {}
    for key, default in full.items():
        lo, hi = given[key] or default
        samples[key] = {"count": counts, "min": lo, "max": hi, "mean": (lo + hi) / 2, "target_envs": envs}
    lo, hi = push or (-1.0 * scale, 1.0 * scale)
    samples[M.PUSH_SAMPLE_KEY] = {"count": push_envs * M.PUSH_RECORD_DIMS if push_count is None else push_count,
                                  "min": lo, "max": hi, "mean": (lo + hi) / 2, "target_envs": push_envs}
    expected = int(math.floor(0.015 * scale / dt + 1e-9))
    row = {"actual_samples": samples, "scale": scale}
    if delay:
        row["delay_readback"] = {"count": N, "physics_dt_seconds": dt, "reset_sample_count": delay_resets,
                                 "max_allowed_substeps": expected if allowed is None else allowed,
                                 "observed_max_substeps": observed}
    return row


def fired(scale, observed=None):
    return {"base_com": N, "actuator_gains": N, "motor_strength": N, "push": N, "push_events": 1,
            "delay_reset_samples": N, "delay_observed_max_substeps": observed}


def on_mode(scale=1.0, pushes=None):
    """켠 모드 DRMode + 가짜 env(배율 심김). pushes 목록에 (범위, 시드) 를 적고 env 별 Δv 기록을 돌려주는 가짜 밀기."""
    import torch

    pushes = [] if pushes is None else pushes

    def pusher(raw, target_range, seed):
        pushes.append((dict(target_range), seed))
        raw._ex40_dr_samples[M.PUSH_SAMPLE_KEY] = {"count": N * M.PUSH_RECORD_DIMS, "target_envs": N, "min": -scale, "max": scale, "sum": 0.0}
        dv = torch.zeros(N, 6, dtype=torch.float64)
        dv[:, 0], dv[:, 1] = scale * 0.6, -scale * 0.8
        return M._push_event_record(torch.zeros(N, 2), torch.zeros(N), dv)

    dr = M.DRMode.from_args(args(dr_mode="on", dr_scale=scale), b_env_cfg(), installer=fake_installer([]), pusher=pusher)
    action = SimpleNamespace(_ex40_sample_counts="stale")
    raw = SimpleNamespace(scene=SimpleNamespace(), action_manager=SimpleNamespace(get_term=lambda name: action))
    dr.after_make(raw)
    raw._ex40_dr_samples = {"base_com_offset_m": {"count": 1, "target_envs": 1, "min": 0.0, "max": 0.0, "sum": 0.0}}   # 지난 롤아웃 찌꺼기
    return dr, raw, action, pushes


def ranges():
    return M.load_table(M.DEFAULT_TABLE)["full_ranges"]


def test_default_table_is_ex41_and_matches_ex40_training_ranges():
    table = M.load_table(M.DEFAULT_TABLE)
    assert Path(table["path"]).name == "ex41-fixed5000.yaml"
    assert table["sha256"] == hashlib.sha256(Path(table["path"]).read_bytes()).hexdigest()
    ex40 = yaml.safe_load(EX40.read_text(encoding="utf-8"))["domain_randomization"]
    assert table["full_ranges"] == ex40["full_ranges"]
    assert table["push_interval_s"] == (10.0, 15.0) and table["delay_max_s"] == 0.015
    assert table["push_interval_s"][0] > 300 * 0.02                                   # B1 의 전제: W15 명령 6 s 가 최소 간격보다 짧다


def test_installer_signature_is_the_training_one():
    from foothold_s2.curriculum import ex40_dr_runtime as R

    assert list(inspect.signature(R.install_runtime_events).parameters) == ["env_cfg", "ranges", "push_interval_s", "delay_max_s"]
    assert list(inspect.signature(M._default_installer).parameters) == ["env_cfg", "ranges", "push_interval_s", "delay_max_s"]
    assert list(inspect.signature(R.interval_push).parameters) == ["env", "env_ids", "asset_cfg", "target_range"]


def test_off_mode_is_a_no_op_and_records_nothing():
    cfg = b_env_cfg()
    dr = M.DRMode.from_args(args(), cfg)
    assert dr.mode == "off" and dr.record is None
    assert cfg.events.physics_material is not None and cfg.events.add_base_mass is not None   # 끔은 eval 본문이 한다
    assert not hasattr(cfg.events, "ex40_base_com")
    raw = SimpleNamespace()
    assert dr.after_make(raw) is None and not hasattr(raw, "_ex40_dr_scale")
    assert dr.begin(raw, "eval_gt/fwd1.0", 300, N, 0.02) is None and dr.step(raw, 100) is False and not hasattr(raw, "_ex40_dr_samples")
    res, row = {"envs": N}, {"alive_envs_at_end": 60}
    assert dr.collect(raw, "eval_gt/fwd1.0", res, row, arrays={"alive": None}) is None and res == {"envs": N} and row == {"alive_envs_at_end": 60}


def _off_block_nodes():
    """eval_map_modes.py 에서 dr_off 초기화 · 끔 블록 · EXPECTED_DR_OFF · 관문 네 문장을 실제 소스에서 꺼낸다."""
    body = ast.parse(EVAL.read_text(encoding="utf-8")).body
    init = [n for n in body if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "dr_off"]
    block = [n for n in body if isinstance(n, ast.If) and ast.unparse(n.test) == "args.dr_mode == 'off'"]
    expected = [n for n in body if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "EXPECTED_DR_OFF"]
    gate = [n for n in body if isinstance(n, ast.If) and "sorted(dr_off)" in ast.unparse(n.test)]
    assert len(init) == len(block) == len(expected) == len(gate) == 1
    return [init[0], block[0], expected[0], gate[0]]


def fake_b_cfg(extra_event=None, delay_cfg=False):
    """B env 꼴: 시동 DR 둘만 있고 지연 행동 칸은 없다(옵션으로 더한다)."""
    events = {"physics_material": object(), "add_base_mass": object()}
    if extra_event:
        events[extra_event] = object()
    joint_pos = SimpleNamespace(max_delay_s=0.015) if delay_cfg else SimpleNamespace(scale=0.25)
    return SimpleNamespace(events=SimpleNamespace(**events), actions=SimpleNamespace(joint_pos=joint_pos))


def run_off_block(dr_mode, cfg):
    """끔 블록 네 문장을 실제 코드로 실행한다(B7 동작 시험). 관문이 거절하면 그 RuntimeError 가 그대로 올라온다."""
    ns = {"args": SimpleNamespace(dr_mode=dr_mode), "env_cfg": cfg}
    exec(compile(ast.Module(body=_off_block_nodes(), type_ignores=[]), str(EVAL), "exec"), ns)
    return ns["dr_off"], ns["EXPECTED_DR_OFF"]


def test_off_block_behaviour_removes_startup_dr_and_zeroes_delay_only_in_off_mode():
    cfg = fake_b_cfg()
    dr_off, expected = run_off_block("off", cfg)
    assert expected == ["physics_material", "add_base_mass"] and dr_off == expected
    assert cfg.events.physics_material is None and cfg.events.add_base_mass is None and cfg.actions.joint_pos.scale == 0.25
    cfg = fake_b_cfg(delay_cfg=True)                                                  # 지연 칸이 있으면 0 으로 두고 관문이 거절한다(B env 가 아님)
    with pytest.raises(RuntimeError, match="action_delay"):
        run_off_block("off", cfg)
    assert cfg.actions.joint_pos.max_delay_s == 0.0
    cfg = fake_b_cfg(extra_event="push_robot")                                       # 모르는 DR 이 더 있어도 관문이 거절한다
    with pytest.raises(RuntimeError, match="push_robot"):
        run_off_block("off", cfg)
    assert cfg.events.push_robot is None
    cfg = fake_b_cfg(extra_event="push_robot", delay_cfg=True)                       # on 은 아무것도 지우지 않고 관문도 안 건다
    dr_off, _ = run_off_block("on", cfg)
    assert dr_off == [] and cfg.events.physics_material is not None and cfg.events.push_robot is not None
    assert cfg.actions.joint_pos.max_delay_s == 0.015


def test_eval_script_keeps_off_path_and_gates_on_path_before_kit():
    src = EVAL.read_text(encoding="utf-8")
    assert 'EXPECTED_DR_OFF = ["physics_material", "add_base_mass"]' in src
    assert 'if args.dr_mode == "off" and sorted(dr_off) != sorted(EXPECTED_DR_OFF):' in src
    assert 'if args.dr_mode == "off":' in src and src.index('if args.dr_mode == "off":') < src.index('for name in ("actuator_gains"')
    assert src.index("eval_dr_mode.validate_args(args)") < src.index("app = AppLauncher(args).app")
    assert src.index("DR = eval_dr_mode.DRMode.from_args(args, env_cfg)") < src.index("gym.make(")
    assert src.index("_made = gym.make(") < src.index("DR.after_make(_made.unwrapped)") < src.index("RslRlVecEnvWrapper(_made")
    assert src.count('res["dr"] = DR.record') == 1 and src.index("if DR.record is not None:") < src.index('res["dr"] = DR.record')
    assert src.count("DR.begin(raw, ") == 2 and src.count("DR.step(raw, ") == 2 and src.count("DR.collect(raw, ") == 2
    cmd = src.index("for cname, cmd in ((c, v) for c, v in CMDS.items() if c in WANT_CMDS):")
    assert cmd < src.index('DR.begin(raw, "%s/%s" % (mode, cname), S, args.envs, dt)') < src.index("env.reset()", cmd)   # reset 전에 비운다
    assert src.index("DR.step(raw, k)") < src.index("obs, _r, dones, _x = env.step(a)")                      # env.step 전에 민다
    collect = src.index('DR.collect(raw, "%s/%s" % (mode, cname), res, row,')
    assert collect < src.index('arrays={"alive": al, "dones": DN.cpu().numpy(), "vx": vx, "vy": vy, "xy": XY.cpu().numpy()}') < src.index('print("MAPMODE", mode, cname, json.dumps(row)')
    seq = src.index("for seq_name, seq_commands in map_mode_cells.SEQUENCES.items():")
    assert seq < src.index('DR.begin(raw, "%s/seq/%s" % (mode, seq_name), S, args.envs, dt)') < src.index("env.reset()", seq)
    assert src.index('DR.step(raw, sum(seq_row["phase_steps"][:phase_index]) + step)') < src.index("obs, _reward, dones, _extra = env.step(action)")
    assert src.index('DR.collect(raw, "%s/seq/%s" % (mode, seq_name), res, seq_row)') < src.index('print("MAPMODE_SEQUENCE"')
    assert "runner.perception.ie.mask_map_tokens = False" in src


def test_on_mode_keeps_startup_events_installs_runtime_dr_removes_interval_push_and_pins_scale():
    cfg = b_env_cfg()
    calls = []
    dr = M.DRMode.from_args(args(dr_mode="on", dr_scale=1.0), cfg, installer=fake_installer(calls))
    table = M.load_table(M.DEFAULT_TABLE)
    assert calls == [(table["full_ranges"], (10.0, 15.0), 0.015)]
    assert cfg.events.physics_material is not None and cfg.events.add_base_mass is not None
    assert cfg.events.ex40_push is None                                                 # B1: interval 밀기는 떼고 가운데 step 밀기로
    assert all(callable(getattr(cfg.events, n).func) for n in M.RUNTIME_RESET_TERMS)
    assert dr.startup_events_kept == ["physics_material", "add_base_mass"]
    assert dr.record["mode"] == "on" and dr.record["scale"] == 1.0 and dr.record["table_sha256"] == table["sha256"]
    assert dr.record["push_schedule"]["removed_interval_term"] == "ex40_push" and dr.record["push_schedule"]["training_interval_s"] == [10.0, 15.0]
    assert dr.record["push_schedule"]["at_s"] == 2.0 and dr.record["push_schedule"]["eval_seed"] == 42 and dr.eval_seed == 42
    assert dr.record["recovery_definition"] == {"band_mps": 0.1, "hold_s": 0.2, "pre_s": 1.0}
    assert "같은 --eval-seed · 다른 잡음 실현" in dr.record["seed_note"]
    assert dr.record["env_scale_before_first_reset"] is None and dr.record["readback"] == {}
    raw = SimpleNamespace(scene=SimpleNamespace(), action_manager=SimpleNamespace())
    assert dr.after_make(raw) == 1.0
    assert raw._ex40_dr_scale == 1.0 and dr.readback.scale == 1.0 and dr.record["env_scale_before_first_reset"] == 1.0
    json.dumps(dr.record, allow_nan=False)


@pytest.mark.parametrize("missing", ["physics_material", "add_base_mass"])
def test_on_mode_refuses_env_without_both_startup_dr_events(missing):
    cfg = b_env_cfg(**{missing: None})
    with pytest.raises(RuntimeError, match="시동 DR"):
        M.DRMode.from_args(args(dr_mode="on"), cfg, installer=fake_installer([]))


def test_on_mode_refuses_installer_that_leaves_delay_reset_or_push_terms_out():
    def no_delay(env_cfg, ranges, push_interval_s, *, delay_max_s):
        for name in M.RUNTIME_RESET_TERMS + ("ex40_push",):
            setattr(env_cfg.events, name, SimpleNamespace(func=lambda *a, **k: None))
        return {}

    with pytest.raises(RuntimeError, match="지연 행동"):
        M.DRMode.from_args(args(dr_mode="on"), b_env_cfg(), installer=no_delay)

    def no_terms(env_cfg, ranges, push_interval_s, *, delay_max_s):
        env_cfg.actions.joint_pos = SimpleNamespace(max_delay_s=delay_max_s, dr_scale_from_env=True)
        return {}

    with pytest.raises(RuntimeError, match="reset 이벤트"):
        M.DRMode.from_args(args(dr_mode="on"), b_env_cfg(), installer=no_terms)

    def no_push(env_cfg, ranges, push_interval_s, *, delay_max_s):
        for name in M.RUNTIME_RESET_TERMS:
            setattr(env_cfg.events, name, SimpleNamespace(func=lambda *a, **k: None))
        env_cfg.actions.joint_pos = SimpleNamespace(max_delay_s=delay_max_s, dr_scale_from_env=True)
        return {}

    with pytest.raises(RuntimeError, match="interval 밀기"):
        M.DRMode.from_args(args(dr_mode="on"), b_env_cfg(), installer=no_push)


def test_validate_args_rejects_axis_v2_bad_scale_and_missing_table_before_kit(tmp_path):
    assert M.validate_args(args()) is None
    assert M.validate_args(args(dr_mode="on")) is None
    assert M.validate_args(args(dr_mode="on", dr_scale=0.0)) is None
    assert "axis-v2" in M.validate_args(args(dr_mode="on", axis_v2=True))
    for bad in (1.5, -0.1, float("nan"), float("inf")):
        assert "dr-scale" in M.validate_args(args(dr_mode="on", dr_scale=bad))
    assert "dr-table" in M.validate_args(args(dr_mode="on", dr_table=str(tmp_path / "none.yaml")))
    assert M.validate_args(args(dr_scale=7.0)) is None            # off 는 배율을 쓰지 않는다


def test_push_schedule_is_one_push_two_seconds_after_the_command_start():
    assert M.push_schedule(300, 0.02) == {"total_steps": 300, "dt": 0.02, "push_step": 100, "push_t_s": 2.0, "expected_pushes": 1}
    assert M.push_schedule(300, 0.02)["push_step"] == int(2.0 / 0.02)                    # 평가기 측정 창 2~4 s 의 첫 step
    assert M.push_schedule(1000, 0.005)["push_step"] == 400
    assert M.push_schedule(100, 0.02) == {"total_steps": 100, "dt": 0.02, "push_step": None, "push_t_s": None, "expected_pushes": 0}   # 2.0 s 전에 끝나는 롤아웃은 0 번
    assert M.push_schedule(0, 0.02)["expected_pushes"] == 0
    with pytest.raises(RuntimeError, match="dt"):
        M.push_schedule(300, 0.0)


def test_push_seed_is_fixed_by_eval_seed_and_rollout_key():
    assert M.push_seed(42, "eval_gt/fwd1.0") == M.push_seed(42, "eval_gt/fwd1.0")
    assert M.push_seed(42, "eval_gt/fwd1.0") != M.push_seed(42, "eval_gt/side+0.5")
    assert M.push_seed(42, "eval_gt/fwd1.0") != M.push_seed(43, "eval_gt/fwd1.0")
    assert 0 <= M.push_seed(0, "") < 2 ** 31


def test_push_event_record_lists_every_env_with_world_delta_v():
    import torch

    dv = torch.zeros(3, 6)
    dv[0, 0], dv[1, 1], dv[2, 0] = 1.0, -0.5, 0.0
    rec = M._push_event_record(torch.tensor([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]), torch.tensor([0.0, 1.0, -1.0]), dv)
    assert rec["env_ids"] == [0, 1, 2] and rec["frame"] == "world" and rec["pos_xy_w_m"][1] == [3.0, 4.0] and rec["yaw_w_rad"] == [0.0, 1.0, -1.0]
    assert rec["dv_xyz_w_mps"] == [[1.0, 0.0, 0.0], [0.0, -0.5, 0.0], [0.0, 0.0, 0.0]] and rec["dv_rpy_w_radps"] == [[0.0] * 3] * 3
    assert rec["dv_xy_norm_mps"] == [1.0, 0.5, 0.0] and rec["dv_xy_dir_w_rad"][1] == pytest.approx(-math.pi / 2)
    assert rec["dv_xy_norm_mps_median"] == 0.5 and rec["dv_xy_norm_mps_max"] == 1.0
    json.dumps(rec, allow_nan=False)


def test_begin_clears_samples_and_step_pushes_exactly_once_at_two_seconds():
    dr, raw, action, pushes = on_mode(1.0)
    plan = dr.begin(raw, "eval_gt/fwd1.0", 300, N, 0.02)
    assert plan == {"key": "eval_gt/fwd1.0", "total_steps": 300, "dt": 0.02, "push_step": 100, "push_t_s": 2.0, "expected_pushes": 1,
                    "num_envs": N, "push_seed": M.push_seed(42, "eval_gt/fwd1.0"), "pushed": 0}
    assert raw._ex40_dr_samples == {} and action._ex40_sample_counts is None             # B3: 지난 롤아웃 표본 · 지연 히스토그램을 비운다
    fired_steps = [k for k in range(300) if dr.step(raw, k)]
    assert fired_steps == [100] and pushes == [(ranges()["push_velocity"], M.push_seed(42, "eval_gt/fwd1.0"))]
    (event,) = dr._rollout["events"]
    assert event["step"] == 100 and event["t_s"] == 2.0 and event["seed"] == M.push_seed(42, "eval_gt/fwd1.0") and event["scale"] == 1.0
    assert len(event["env_ids"]) == N and event["dv_xy_norm_mps_median"] == pytest.approx(1.0) and event["dv_xyz_w_mps"][0] == [0.6, -0.8, 0.0]
    with pytest.raises(RuntimeError, match="collect 없이"):
        dr.begin(raw, "eval_gt/side+0.5", 300, N, 0.02)
    dr2, raw2, _, _ = on_mode(1.0)
    with pytest.raises(RuntimeError, match="begin 없이"):
        dr2.step(raw2, 0)
    with pytest.raises(RuntimeError, match="begin 없이"):
        dr2.collect(raw2, "eval_gt/fwd1.0", {})
    dr3, raw3, _, _ = on_mode(1.0)
    dr3.pusher = lambda raw, target_range, seed: {"env_ids": [0]}                            # env 전부를 안 담은 기록은 거절
    dr3.begin(raw3, "eval_gt/fwd1.0", 300, N, 0.02)
    with pytest.raises(RuntimeError, match="env 전부"):
        dr3.step(raw3, 100)


def synthetic_rollout():
    """답 아는 롤아웃: T 300 · N 4 · dt 0.02 · 밀기 step 100. env0 옆으로 0.5 m 밀렸다 1.0 s 뒤 복귀 · env1 0.4 s 뒤 쓰러짐 ·
    env2 밀기 전에 끝남(모집단 밖) · env3 속도가 두 배가 되어 회복 안 함."""
    import numpy as np

    T, Nn, dt, p = 300, 4, 0.02, 100
    alive, dones = np.ones((T, Nn), bool), np.zeros((T, Nn), bool)
    vx, vy, xy = np.ones((T, Nn)), np.zeros((T, Nn)), np.zeros((T, Nn, 2))
    k = np.arange(T)
    xy[:, :, 0] = k[:, None] * dt
    vy[p:p + 50, 0] = 0.5
    xy[p:p + 50, 0, 1] = np.arange(1, 51) * 0.5 * dt
    xy[p + 50:, 0, 1] = 0.5
    dones[p + 20, 1] = True
    alive[p + 20:, 1] = False
    vx[p:, 1] = 0.0
    dones[50, 2] = True
    alive[50:, 2] = False
    vx[p:, 3] = 2.0
    xy[p:, 3, 0] = p * dt + (k[p:] - p) * 2.0 * dt
    return alive, dones, vx, vy, xy, dt, p


def test_recovery_metrics_on_a_known_rollout():
    alive, dones, vx, vy, xy, dt, p = synthetic_rollout()
    out = M.recovery_metrics(alive, dones, vx, vy, xy, dt, p)
    assert out["defined"] and out["push_step"] == 100 and out["push_t_s"] == 2.0 and out["envs_in_population"] == 3
    assert out["fell_envs"] == 1 and out["fell_fraction"] == pytest.approx(1 / 3) and out["fall_time_s_median"] == pytest.approx(0.42)
    assert out["path_deviation_m_median"] == pytest.approx(0.5) and out["path_deviation_m_max"] == pytest.approx(3.98)
    assert out["recovered_envs"] == 1 and out["recovered_fraction"] == pytest.approx(1 / 3) and out["recovery_time_s_median"] == pytest.approx(1.02)
    assert out["definition"]["band_mps"] == 0.1 and out["definition"]["hold_s"] == 0.2
    json.dumps(out, allow_nan=False)
    assert M.recovery_metrics(alive, dones, vx, vy, xy, dt, None)["defined"] is False
    assert M.recovery_metrics(alive, dones, vx, vy, xy, dt, 0)["defined"] is False
    with pytest.raises(RuntimeError, match="모양"):
        M.recovery_metrics(alive, dones, vx, vy, xy[:, :, :1], dt, p)


def test_check_fired_scale_zero_requires_neutral_and_no_delay():
    r = ranges()
    ok = M.check_fired(summary(0.0), 0.0, r, 0.015, num_envs=N, pushes=1)
    assert ok["delay_max_substeps"] == 0 and ok["reset_sample_counts"] == {k: N for k in M.RESET_SAMPLE_KEYS}
    assert ok["fired"] == fired(0.0)
    with pytest.raises(RuntimeError, match="벗어났다|명목값"):
        M.check_fired(summary(0.0, com=(0.0, 0.01)), 0.0, r, 0.015, num_envs=N, pushes=1)
    with pytest.raises(RuntimeError, match="명목값"):
        M.check_fired(summary(0.0, push=(0.0, 1e-6)), 0.0, r, 0.015, num_envs=N, pushes=1)   # 배율 0 의 밀기는 속도 차 0
    with pytest.raises(RuntimeError, match="지연 상한"):
        M.check_fired(summary(0.0, allowed=1), 0.0, r, 0.015, num_envs=N, pushes=1)


def test_check_fired_scale_one_requires_full_range_samples_and_three_substeps():
    r = ranges()
    ok = M.check_fired(summary(1.0, observed=3), 1.0, r, 0.015, num_envs=N, pushes=1)
    assert ok["delay_max_substeps"] == 3 and ok["delay_observed_max_substeps"] == 3 and ok["fired"] == fired(1.0, 3)
    with pytest.raises(RuntimeError, match="벗어났다"):
        M.check_fired(summary(1.0, motor=(0.9, 1.11)), 1.0, r, 0.015, num_envs=N, pushes=1)
    with pytest.raises(RuntimeError, match="벗어났다"):
        M.check_fired(summary(1.0, push=(-1.0, 1.01)), 1.0, r, 0.015, num_envs=N, pushes=1)
    with pytest.raises(RuntimeError, match="표본이 없다"):
        M.check_fired(summary(1.0, counts=0), 1.0, r, 0.015, num_envs=N, pushes=1)
    with pytest.raises(RuntimeError, match="지연 상한"):
        M.check_fired(summary(1.0, allowed=2), 1.0, r, 0.015, num_envs=N, pushes=1)
    with pytest.raises(RuntimeError, match="지연 상한"):
        M.check_fired(summary(1.0, observed=4), 1.0, r, 0.015, num_envs=N, pushes=1)
    with pytest.raises(RuntimeError, match="readback 이 없다"):
        M.check_fired(summary(1.0, delay=False), 1.0, r, 0.015, num_envs=N, pushes=1)


def test_check_fired_counts_every_event_against_all_envs():
    r = ranges()
    with pytest.raises(RuntimeError, match="env 전부에 닿지 않았다"):
        M.check_fired(summary(1.0, envs=N - 1), 1.0, r, 0.015, num_envs=N, pushes=1)           # reset 이벤트가 한 env 빠짐
    with pytest.raises(RuntimeError, match="밀기 횟수"):
        M.check_fired(summary(1.0), 1.0, r, 0.015, num_envs=N, pushes=0)                       # 밀기가 안 불림(B1 의 원래 구멍)
    with pytest.raises(RuntimeError, match="밀기 횟수"):
        M.check_fired(summary(1.0), 1.0, r, 0.015, num_envs=N, pushes=2)
    with pytest.raises(RuntimeError, match="밀기 표본"):
        M.check_fired(summary(1.0, push_envs=N - 1), 1.0, r, 0.015, num_envs=N, pushes=1)      # 불렸다는데 env 하나 안 밀림
    with pytest.raises(RuntimeError, match="밀기 표본"):
        M.check_fired(summary(1.0, push_count=N * 5), 1.0, r, 0.015, num_envs=N, pushes=1)     # 성분 수가 다름
    with pytest.raises(RuntimeError, match="지연 행동 reset 표본"):
        M.check_fired(summary(1.0, delay_resets=N - 1), 1.0, r, 0.015, num_envs=N, pushes=1)
    ok = M.check_fired(summary(1.0, push_envs=0, push_count=0), 1.0, r, 0.015, num_envs=N, pushes=0, expected_pushes=0)
    assert ok["fired"]["push"] == 0 and ok["fired"]["push_events"] == 0                       # 길이 0 롤아웃만 0 번이 맞다
    with pytest.raises(RuntimeError, match="밀기 일정이 0 번"):
        M.check_fired(summary(1.0), 1.0, r, 0.015, num_envs=N, pushes=0, expected_pushes=0)
    with pytest.raises(RuntimeError, match="env 수"):
        M.check_fired(summary(1.0), 1.0, r, 0.015, num_envs=0, pushes=1)


def test_check_fired_half_scale_bounds_fold_linearly():
    r = ranges()
    assert M.sample_bounds(r, 0.5) == {"base_com_offset_m": (-0.025, 0.025), "actuator_gains": (0.95, 1.05),
                                       "motor_strength_multiplier": (0.95, 1.05), M.PUSH_SAMPLE_KEY: (-0.5, 0.5)}
    assert M.check_fired(summary(0.5, observed=1), 0.5, r, 0.015, num_envs=N, pushes=1)["delay_max_substeps"] == 1
    with pytest.raises(RuntimeError, match="벗어났다"):
        M.check_fired(summary(0.5, gains=(0.9, 1.1)), 0.5, r, 0.015, num_envs=N, pushes=1)
    with pytest.raises(RuntimeError, match="벗어났다"):
        M.check_fired(summary(0.5, push=(-1.0, 0.5)), 0.5, r, 0.015, num_envs=N, pushes=1)


def test_collect_writes_readback_and_score_row_and_refuses_changed_scale(capsys):
    dr, raw, _, _ = on_mode(1.0)
    dr.readback = SimpleNamespace(scale=1.0, summary=lambda: summary(1.0, observed=2))
    dr.begin(raw, "eval_gt/fwd1.0", 300, N, 0.02)
    assert dr.step(raw, 100)
    alive, dones, vx, vy, xy, dt, p = synthetic_rollout()
    res, row = {"dr": dr.record}, {"alive_envs_at_end": 60}
    out = dr.collect(raw, "eval_gt/fwd1.0", res, row, arrays={"alive": alive, "dones": dones, "vx": vx, "vy": vy, "xy": xy})
    assert res["dr"]["readback"]["eval_gt/fwd1.0"] is out and out["scale"] == 1.0
    assert out["rollout"] == {"key": "eval_gt/fwd1.0", "total_steps": 300, "dt": 0.02, "push_step": 100, "push_t_s": 2.0, "expected_pushes": 1,
                              "num_envs": N, "push_seed": M.push_seed(42, "eval_gt/fwd1.0"), "pushed": 1}
    assert len(out["push_events"]) == 1 and len(out["push_events"][0]["dv_xyz_w_mps"]) == N          # G18: 영상용 env 별 Δv
    assert out["recovery"]["fell_envs"] == 1 and out["recovery"]["recovery_time_s_median"] == pytest.approx(1.02)
    assert row["dr_scale"] == 1.0 and row["dr_fired"] == fired(1.0, 2)                   # B2: 점수 행에 배율 · 이벤트별 발화 수
    assert row["dr_push"] == {"step": 100, "t_s": 2.0, "seed": M.push_seed(42, "eval_gt/fwd1.0"), "envs": N,
                              "dv_xy_norm_mps_median": pytest.approx(1.0), "dv_xy_norm_mps_max": pytest.approx(1.0)}
    assert row["dr_recovery"] is out["recovery"] and row["alive_envs_at_end"] == 60
    assert "MAPMODE_DR eval_gt/fwd1.0" in capsys.readouterr().out
    json.dumps(res, allow_nan=False)
    dr.begin(raw, "eval_gt/side+0.5", 300, N, 0.02)                                     # 밀기 없이 끝내면 collect 가 막는다
    with pytest.raises(RuntimeError, match="밀기 횟수"):
        dr.collect(raw, "eval_gt/side+0.5", res, {})
    dr.begin(raw, "eval_gt/side+0.5", 300, N, 0.02)
    with pytest.raises(RuntimeError, match="다르다"):
        dr.collect(raw, "eval_gt/side-0.5", res)                                          # begin 과 다른 롤아웃 이름
    raw._ex40_dr_scale = 0.5
    with pytest.raises(RuntimeError, match="배율이 바뀌었"):
        dr.collect(raw, "eval_gt/side+0.5", res)
    dr4, raw4, _, _ = on_mode(1.0)                                                       # 시퀀스(배열 없음): 회복 지표 None, 밀기 기록은 있음
    dr4.readback = SimpleNamespace(scale=1.0, summary=lambda: summary(1.0, observed=2))
    dr4.begin(raw4, "eval_gt/seq/walk_turn", 300, N, 0.02)
    dr4.step(raw4, 100)
    seq_row = {"total_steps": 300}
    out4 = dr4.collect(raw4, "eval_gt/seq/walk_turn", {"dr": dr4.record}, seq_row)
    assert out4["recovery"] is None and seq_row["dr_recovery"] is None and seq_row["dr_push"]["step"] == 100


def test_real_m6000_off_output_has_the_literal_dr_off_list_and_no_dr_keys():
    if not REAL_M6000.is_file():
        pytest.skip("실측 m6000 map_modes.json 없음")
    doc = json.loads(REAL_M6000.read_text(encoding="utf-8-sig"))
    assert doc["dr_off"] == ["physics_material", "add_base_mass"] and "dr" not in doc
    rows = [row for mode in doc["modes"].values() for row in mode.values()]
    assert rows and all(not any(k in row for k in ("dr_scale", "dr_fired", "dr_push", "dr_recovery")) for row in rows)   # 끔 점수 행은 그대로
