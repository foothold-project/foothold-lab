"""D94 · D125 DR 켠 평가 모드의 답 아는 CPU 시험. Kit · CUDA 없음.

끝점: 끔 모드는 아무것도 설치 · 기록하지 않고(출력 키 불변), 켠 모드는 시동 DR 둘을 지우지 않고 런타임 DR 다섯을
학습과 같은 설치 함수 서명으로 설치하며, 배율 0 에서는 표본이 명목값 · 배율 1.0 에서는 표본이 전체 범위 안일 때만 통과한다.
"""

from __future__ import annotations

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


def args(**over):
    base = dict(dr_mode="off", dr_scale=1.0, dr_table=str(M.DEFAULT_TABLE), axis_v2=False)
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
        env_cfg.events.ex40_push = SimpleNamespace(func=lambda *a, **k: None, mode="interval")
        env_cfg.actions.joint_pos = SimpleNamespace(max_delay_s=delay_max_s, dr_scale_from_env=True)
        return {"reset_terms": list(M.RUNTIME_RESET_TERMS), "interval_terms": ["ex40_push"], "delay_max_s": delay_max_s}
    return install


def summary(scale, *, com=None, gains=None, motor=None, allowed=None, observed=None, counts=64, delay=True, dt=0.005):
    full = {"base_com_offset_m": (-0.05 * scale, 0.05 * scale), "actuator_gains": (1 - 0.1 * scale, 1 + 0.1 * scale),
            "motor_strength_multiplier": (1 - 0.1 * scale, 1 + 0.1 * scale)}
    given = {"base_com_offset_m": com, "actuator_gains": gains, "motor_strength_multiplier": motor}
    samples = {}
    for key, default in full.items():
        lo, hi = given[key] or default
        samples[key] = {"count": counts, "min": lo, "max": hi, "mean": (lo + hi) / 2, "target_envs": counts}
    expected = int(math.floor(0.015 * scale / dt + 1e-9))
    row = {"actual_samples": samples, "scale": scale}
    if delay:
        row["delay_readback"] = {"count": 64, "physics_dt_seconds": dt,
                                 "max_allowed_substeps": expected if allowed is None else allowed,
                                 "observed_max_substeps": observed}
    return row


def test_default_table_is_ex41_and_matches_ex40_training_ranges():
    table = M.load_table(M.DEFAULT_TABLE)
    ex40 = yaml.safe_load(EX40.read_text(encoding="utf-8"))["domain_randomization"]
    assert table["full_ranges"] == ex40["full_ranges"]
    assert table["push_interval_s"] == tuple(float(v) for v in ex40["push_interval_s"]) == (10.0, 15.0)
    assert table["delay_max_s"] == 0.015
    assert table["sha256"] == hashlib.sha256(M.DEFAULT_TABLE.read_bytes()).hexdigest()


def test_installer_signature_is_the_training_one():
    from foothold_s2.curriculum.ex40_dr_runtime import install_runtime_events

    assert list(inspect.signature(install_runtime_events).parameters) == ["env_cfg", "ranges", "push_interval_s", "delay_max_s"]
    assert list(inspect.signature(M._default_installer).parameters) == ["env_cfg", "ranges", "push_interval_s", "delay_max_s"]


def test_off_mode_is_a_no_op_and_records_nothing():
    cfg = b_env_cfg()
    dr = M.DRMode.from_args(args(), cfg)
    assert dr.mode == "off" and dr.record is None
    assert cfg.events.physics_material is not None and cfg.events.add_base_mass is not None   # 끔은 eval 본문이 한다
    assert not hasattr(cfg.events, "ex40_base_com")
    raw = SimpleNamespace()
    assert dr.after_make(raw) is None and not hasattr(raw, "_ex40_dr_scale")
    res = {"envs": 64}
    assert dr.collect(raw, "eval_gt/fwd1.0", res) is None and res == {"envs": 64}


def test_eval_script_keeps_off_path_and_gates_on_path_before_kit():
    src = EVAL.read_text(encoding="utf-8")
    assert 'EXPECTED_DR_OFF = ["physics_material", "add_base_mass"]' in src
    assert 'if args.dr_mode == "off" and sorted(dr_off) != sorted(EXPECTED_DR_OFF):' in src
    assert 'if args.dr_mode == "off":' in src and src.index('if args.dr_mode == "off":') < src.index('for name in ("actuator_gains"')
    assert src.index("eval_dr_mode.validate_args(args)") < src.index("app = AppLauncher(args).app")
    assert src.index("DR = eval_dr_mode.DRMode.from_args(args, env_cfg)") < src.index("gym.make(")
    assert src.index("_made = gym.make(") < src.index("DR.after_make(_made.unwrapped)") < src.index("RslRlVecEnvWrapper(_made")
    assert src.count('res["dr"] = DR.record') == 1 and src.index("if DR.record is not None:") < src.index('res["dr"] = DR.record')
    assert src.count("DR.collect(raw, ") == 2
    assert "runner.perception.ie.mask_map_tokens = False" in src


def test_on_mode_keeps_startup_events_installs_runtime_dr_and_pins_scale():
    cfg = b_env_cfg()
    calls = []
    dr = M.DRMode.from_args(args(dr_mode="on", dr_scale=1.0), cfg, installer=fake_installer(calls))
    table = M.load_table(M.DEFAULT_TABLE)
    assert calls == [(table["full_ranges"], (10.0, 15.0), 0.015)]
    assert cfg.events.physics_material is not None and cfg.events.add_base_mass is not None
    assert dr.startup_events_kept == ["physics_material", "add_base_mass"]
    assert dr.record["mode"] == "on" and dr.record["scale"] == 1.0 and dr.record["table_sha256"] == table["sha256"]
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


def test_on_mode_refuses_installer_that_leaves_delay_or_reset_terms_out():
    def no_delay(env_cfg, ranges, push_interval_s, *, delay_max_s):
        for name in M.RUNTIME_RESET_TERMS:
            setattr(env_cfg.events, name, SimpleNamespace(func=lambda *a, **k: None))
        return {}

    with pytest.raises(RuntimeError, match="지연 행동"):
        M.DRMode.from_args(args(dr_mode="on"), b_env_cfg(), installer=no_delay)

    def no_terms(env_cfg, ranges, push_interval_s, *, delay_max_s):
        env_cfg.actions.joint_pos = SimpleNamespace(max_delay_s=delay_max_s, dr_scale_from_env=True)
        return {}

    with pytest.raises(RuntimeError, match="reset 이벤트"):
        M.DRMode.from_args(args(dr_mode="on"), b_env_cfg(), installer=no_terms)


def test_validate_args_rejects_axis_v2_bad_scale_and_missing_table_before_kit(tmp_path):
    assert M.validate_args(args()) is None
    assert M.validate_args(args(dr_mode="on")) is None
    assert M.validate_args(args(dr_mode="on", dr_scale=0.0)) is None
    assert "axis-v2" in M.validate_args(args(dr_mode="on", axis_v2=True))
    for bad in (1.5, -0.1, float("nan"), float("inf")):
        assert "dr-scale" in M.validate_args(args(dr_mode="on", dr_scale=bad))
    assert "dr-table" in M.validate_args(args(dr_mode="on", dr_table=str(tmp_path / "none.yaml")))
    assert M.validate_args(args(dr_scale=7.0)) is None            # off 는 배율을 쓰지 않는다


def test_check_fired_scale_zero_requires_neutral_and_no_delay():
    ranges = M.load_table(M.DEFAULT_TABLE)["full_ranges"]
    ok = M.check_fired(summary(0.0), 0.0, ranges, 0.015)
    assert ok["delay_max_substeps"] == 0 and ok["reset_sample_counts"] == {k: 64 for k in M.RESET_SAMPLE_KEYS}
    with pytest.raises(RuntimeError, match="벗어났다|명목값"):
        M.check_fired(summary(0.0, com=(0.0, 0.01)), 0.0, ranges, 0.015)
    with pytest.raises(RuntimeError, match="지연 상한"):
        M.check_fired(summary(0.0, allowed=1), 0.0, ranges, 0.015)


def test_check_fired_scale_one_requires_full_range_samples_and_three_substeps():
    ranges = M.load_table(M.DEFAULT_TABLE)["full_ranges"]
    ok = M.check_fired(summary(1.0, observed=3), 1.0, ranges, 0.015)
    assert ok["delay_max_substeps"] == 3 and ok["delay_observed_max_substeps"] == 3
    with pytest.raises(RuntimeError, match="벗어났다"):
        M.check_fired(summary(1.0, motor=(0.9, 1.11)), 1.0, ranges, 0.015)
    with pytest.raises(RuntimeError, match="표본이 없다"):
        M.check_fired(summary(1.0, counts=0), 1.0, ranges, 0.015)
    with pytest.raises(RuntimeError, match="지연 상한"):
        M.check_fired(summary(1.0, allowed=2), 1.0, ranges, 0.015)
    with pytest.raises(RuntimeError, match="지연 상한"):
        M.check_fired(summary(1.0, observed=4), 1.0, ranges, 0.015)
    with pytest.raises(RuntimeError, match="readback 이 없다"):
        M.check_fired(summary(1.0, delay=False), 1.0, ranges, 0.015)


def test_check_fired_half_scale_bounds_fold_linearly():
    ranges = M.load_table(M.DEFAULT_TABLE)["full_ranges"]
    assert M.sample_bounds(ranges, 0.5) == {"base_com_offset_m": (-0.025, 0.025), "actuator_gains": (0.95, 1.05),
                                            "motor_strength_multiplier": (0.95, 1.05)}
    assert M.check_fired(summary(0.5, observed=1), 0.5, ranges, 0.015)["delay_max_substeps"] == 1
    with pytest.raises(RuntimeError, match="벗어났다"):
        M.check_fired(summary(0.5, gains=(0.9, 1.1)), 0.5, ranges, 0.015)


def test_collect_writes_readback_under_dr_block_and_refuses_changed_scale(capsys):
    cfg = b_env_cfg()
    dr = M.DRMode.from_args(args(dr_mode="on", dr_scale=1.0), cfg, installer=fake_installer([]))
    raw = SimpleNamespace(scene=SimpleNamespace(), action_manager=SimpleNamespace())
    dr.after_make(raw)
    dr.readback = SimpleNamespace(scale=1.0, summary=lambda: summary(1.0, observed=2))
    res = {"dr": dr.record}
    out = dr.collect(raw, "eval_gt/fwd1.0", res)
    assert res["dr"]["readback"]["eval_gt/fwd1.0"] is out and out["scale"] == 1.0
    assert "MAPMODE_DR eval_gt/fwd1.0" in capsys.readouterr().out
    raw._ex40_dr_scale = 0.5
    with pytest.raises(RuntimeError, match="배율이 바뀌었"):
        dr.collect(raw, "eval_gt/side+0.5", res)


def test_real_m6000_off_output_has_the_literal_dr_off_list_and_no_dr_block():
    if not REAL_M6000.is_file():
        pytest.skip("실측 m6000 map_modes.json 없음")
    doc = json.loads(REAL_M6000.read_text(encoding="utf-8-sig"))
    assert doc["dr_off"] == ["physics_material", "add_base_mass"] and "dr" not in doc
