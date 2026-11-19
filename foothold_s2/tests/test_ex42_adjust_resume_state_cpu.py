"""An adjustment resume must carry the last live state: keys at or below the start update never fire again (2026-11-19 21:3x).

The E2 m500 / m750 resumes printed EX42_SEGMENT_REWARDS_READBACK slow_progress 0.4 (the plan value, written before
LiveAdjustment exists) and no LIVE_ADJUST line, which read as a lost 0.6. This pins the real order with the real
LiveAdjustment: construct (restore from the last receipt) after the plan value is laid, then read the live cell. No Kit."""
import json

from foothold_s2.ex42_live_adjust import SCHEMA
from foothold_s2.tests.test_ex42_live_adjust_cpu import _entry, _setup, Manager


def _file(path, keys):
    doc = {"schema": SCHEMA, "stage_id": "E1", "plan_sha256": "a" * 64,
           "changes": {str(k): _entry(rewards={"slow_progress": .6}) for k in keys}}
    path.write_text(json.dumps(doc))


def _resume(tmp_path, file, keys):
    """A new process on the same folder: the plan value 0.4 laid first, then LiveAdjustment restores."""
    _file(file, keys)
    from foothold_s2.ex42_live_adjust import LiveAdjustment
    import hashlib
    from foothold_s2.commands.ex42_segment_adjust import REWARD_LIMITS
    ctl, runtime, _ = _setup(tmp_path / "scratch", iteration=1)             # only to borrow a runtime shell + config
    runtime.env.reward_manager = Manager()
    runtime.env.reward_manager.terms["ex42_slow_progress"].weight = 0.4      # the segment readback value (plan)
    seg = tmp_path / "segment.yaml"
    seg.write_bytes(REWARD_LIMITS.read_bytes())
    cfg = {"segment_reward_limits_sha256": hashlib.sha256(seg.read_bytes()).hexdigest(),
           "extra_reward_limits": {"zero_yaw": [-2, -.5], "feet_air_time_threshold": [.04, .5], "slow_track": [0, .3],
                                   "slow_track_sigma": [.5, .5], "slow_track_speed_min": [.1, .1], "slow_track_speed_max": [.3, .3], "slow_progress": [0, .6]},
           "command_limits": {"low_forward_fraction": [.2, .5]},
           "runtime_limits": {"policy_std_cap": [0, 2], "terrain_level_cap": [5, 9]}, "runtime_start": {"policy_std_cap": 0.0}}
    ctl = LiveAdjustment(runtime, cfg, plan_sha256="a" * 64, path=file, log_dir=tmp_path, segment_limits_path=seg)
    return ctl, runtime


def _live(runtime):
    return runtime.env.reward_manager.get_term_cfg("ex42_slow_progress").weight


def test_resume_after_keys_1_270_930_still_has_slow_progress_06_on_the_first_update(tmp_path):
    file = tmp_path / "adjust.json"
    ctl, runtime = _resume(tmp_path, file, [1])                  # fresh: plan 0.4, key 1 fires at update 1
    assert _live(runtime) == .4
    assert ctl.on_update_start(1)["after"]["rewards"]["slow_progress"] == .6 and _live(runtime) == .6
    for resume_at, keys in ((270, [1, 270]), (930, [1, 270, 930])):
        ctl, runtime = _resume(tmp_path, file, keys)             # a new process: plan 0.4 again, restore from the last receipt
        assert _live(runtime) == .6, f"restore must beat the plan value at resume {resume_at}"
        assert ctl.on_update_start(resume_at)["after"]["rewards"]["slow_progress"] == .6   # the key at the start update is a no-op change
    ctl, runtime = _resume(tmp_path, file, [1, 270, 930, 1001])  # resume 1000
    assert _live(runtime) == .6
    assert ctl.on_update_start(1000) is None                     # no key, nothing to do, and the live cell was not re-opened
    assert _live(runtime) == .6
    assert ctl.on_update_start(1001)["after"]["rewards"]["slow_progress"] == .6


def test_restore_prints_the_live_state_line(tmp_path, capsys):
    file = tmp_path / "adjust.json"
    ctl, runtime = _resume(tmp_path, file, [1])
    ctl.on_update_start(1)
    capsys.readouterr()
    _resume(tmp_path, file, [1])
    line = [x for x in capsys.readouterr().out.splitlines() if x.startswith("EX42_LIVE_RESTORE ")]
    assert len(line) == 1 and json.loads(line[0].split(" ", 1)[1])["values"]["rewards"]["slow_progress"] == .6


def _tool():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("adj_check", Path(__file__).resolve().parents[2] / "_out/tools/ex42_adjust_state_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_state_check_passes_on_the_folded_file_and_flags_a_cell_the_live_state_lacks(tmp_path, capsys):
    file = tmp_path / "adjust.json"
    ctl, _ = _resume(tmp_path, file, [1])
    ctl.on_update_start(1)
    tool = _tool()
    _file(file, [1, 270, 930])                                              # keys past the last receipt (270 930 never ran)
    assert tool.main(["--adjust", str(file), "--out", str(tmp_path), "--start-iter", "1000"]) == 0   # same value: still equal
    doc = json.loads(file.read_text())
    doc["changes"]["500"] = _entry(rewards={"slow_track": .2})              # a change the live state never took
    file.write_text(json.dumps(doc))
    assert tool.main(["--adjust", str(file), "--out", str(tmp_path), "--start-iter", "1000"]) == 1
    assert "rewards.slow_track file 0.2 live" in capsys.readouterr().out
    assert tool.main(["--adjust", str(file), "--out", str(tmp_path), "--start-iter", "400"]) == 0    # key 500 is after the start
    assert tool.main(["--adjust", str(tmp_path / "none.json"), "--out", str(tmp_path), "--start-iter", "1"]) == 2
