"""Known-answer and mutation tests for the CPU result generator."""
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("generate_result26a.py")
SPEC = importlib.util.spec_from_file_location("result26a", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def run() -> None:
    mod.self_test()
    root = Path("C:/mai/wt/foothold-lab")
    base = root / "impl-turncases/logs/six_cases/b1500"
    known = {
        "indep_left": (+1.01, 0.40),
        "indep_right": (-0.25, 0.80),
        "left_then_right": (-0.23, 0.90),
        "right_then_left": (+1.04, 0.46),
        "fwd_then_left": (+0.89, 0.44),
        "fwd_then_right": (-0.49, 0.61),
    }
    for case, (yaw_expected, four_expected) in known.items():
        yaw, four, _alive = mod.case_metrics(base / f"arrays_{case}.npz", 1.0)
        assert round(yaw, 2) == yaw_expected, (case, yaw)
        assert round(four, 2) == four_expected, (case, four)
    print("PASS B1500 six-case known-answer 6/6")

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        missing, source = mod.map_rows(folder / "missing.json", "S-B", 1500,
                                       ("eval_gt", "probe_prop_only"))
        assert source is None and len(missing) == 8
        assert all(r["status"] == "평가 전" for r in missing)
        print("PASS missing evaluation stays pending")
        value = {"body_vx_integral_median_m": 5.0, "yaw_follow_median": 0.4,
                 "alive_envs_at_end": 64, "stalled_fraction_2to4s": 0.0,
                 "tilt_rad_mean_alive": 0.1, "gt_used": 0}
        meta = {"envs": 64, "steps": 300, "fixed_terrain": {"assignment_sha256": mod.MAP_SHA},
                "checkpoint_sha256": "a" * 64,
                "modes": {mode: {case: value for case in ("fwd0.5", "fwd1.0", "spin+1.2", "spin-1.2")}
                          for mode in ("eval_gt", "probe_prop_only")}}
        path = folder / "two_modes.json"
        path.write_text(json.dumps(meta), encoding="utf-8")
        rows, source = mod.map_rows(path, "S-B", 1500, ("eval_gt", "probe_prop_only"))
        assert source and len(rows) == 8 and {r["mode"] for r in rows} == {"eval_gt", "probe_prop_only"}
        print("PASS S-B two evaluation modes")
        meta["fixed_terrain"]["assignment_sha256"] = "b" * 64
        path.write_text(json.dumps(meta), encoding="utf-8")
        try:
            mod.map_rows(path, "S-B", 1500, ("eval_gt", "probe_prop_only"))
        except ValueError as exc:
            assert "assignment changed" in str(exc)
        else:
            raise AssertionError("mutated terrain SHA was accepted")
        print("CAUGHT terrain assignment mutation")
        switch = folder / "map_switch.jsonl"
        item = {"it": 50, "off_frac_steps": 0.5, "p_off": 0.5}
        branch = {"env_steps": 100, "episodes_ended": 3, "ep_reward_mean": 1.0,
                  "ep_length_mean": 20, "terrain_level_mean": 2,
                  "track_lin_vel_per_s": 0.4, "track_ang_vel_per_s": 0.2}
        item.update(on=branch, off={**branch, "ep_reward_mean": 2.0})
        switch.write_text(json.dumps(item) + "\n", encoding="utf-8")
        rows = mod.map_switch_rows(switch)
        assert [(r["mode"], r["ep_reward_mean"]) for r in rows] == [("on", 1.0), ("off", 2.0)]
        print("PASS S-B map on/off separation")


if __name__ == "__main__":
    run()
