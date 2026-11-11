"""CPU-only E0 comparison against the pinned five-repeat parent baseline."""
from __future__ import annotations

import json
import math
from pathlib import Path


def load_baseline(root: Path, cfg: dict, digest) -> dict:
    pin = cfg["baseline"]
    path = root / pin["path"]
    if digest(path) != pin["sha256"]:
        raise ValueError("EX-42 E0 baseline bytes differ from score config")
    base = json.loads(path.read_text(encoding="utf-8"))
    if (base.get("format") != "foothold-ex42-e0-baseline/1" or
            base.get("calibration_sha256") != pin["calibration_sha256"] or
            len(base.get("seeds", [])) != 5 or base.get("eval_cols") != 23):
        raise ValueError("EX-42 E0 baseline provenance differs")
    return base


def validate_measured_q4(baseline: dict, measured: dict, assumed: dict) -> None:
    if (measured.get("calibration_sha256") != baseline["calibration_sha256"] or
            measured.get("parent_checkpoint_sha256") != baseline["checkpoint_sha256"] or
            measured.get("eval_cols") != baseline["eval_cols"] or
            measured.get("seeds") != baseline["seeds"] or
            assumed.get("foot_drag_frac") != 0.25):
        raise ValueError("EX-42 E0 q4 provenance or approved assumptions differ")
    rules = (("survival_drop_envs", "survival"),
             ("error_rise_vx_vy_mps", "tracking_vx_vy"),
             ("error_rise_wz_radps", "tracking_wz"))
    for key, item in rules:
        widths = [baseline["metrics"][p]["repeat_width"] for p in baseline["items"][item]["metric_paths"]]
        expected = max(assumed[key], 2 * max(widths))
        if measured.get(key) != expected:
            raise ValueError(f"EX-42 E0 q4 {key} differs from approved max rule")
    drag = [v for k, v in baseline["metrics"].items() if "/foot_drag_proxy_m_by_foot_median/" in k]
    if (measured.get("foot_drag_m") != "per_cell_max_0.25_parent_or_2_repeat_width" or
            measured.get("foot_drag_metric_count") != len(drag) or
            any(v["rise_limit_m"] != max(.25 * v["parent_median"], 2 * v["repeat_width"])
                for v in drag)):
        raise ValueError("EX-42 E0 foot drag per-cell limits differ")


def judge(score: dict, baseline: dict, measured: dict) -> dict:
    """Return a new score; record-only items never change the 26-cell verdict."""
    if measured["baseline_sha256"] != baseline["_sha256"] or measured["calibration_sha256"] != baseline["calibration_sha256"]:
        raise ValueError("EX-42 measured q4 and baseline pin differ")
    if score["conditions"]["envs"] != 64 or set(score["map64"]) != {"eval_gt", "eval_pred", "probe_prop_only"}:
        raise ValueError("EX-42 E0 map conditions differ")
    limits = {"alive_at_end": measured["survival_drop_envs"],
              "vx_abs_error_median_mps": measured["error_rise_vx_vy_mps"],
              "vy_abs_error_median_mps": measured["error_rise_vx_vy_mps"],
              "wz_abs_error_median_radps": measured["error_rise_wz_radps"]}
    result = dict(score)
    result["baseline"] = {"sha256": baseline["_sha256"],
                          "calibration_sha256": baseline["calibration_sha256"],
                          "parent_checkpoint_sha256": baseline["checkpoint_sha256"],
                          "repeat_count": 5}
    cells = {}
    for mode, cases in score["map64"].items():
        cells[mode] = {}
        for case, row in cases.items():
            checks = {}
            for metric, limit in limits.items():
                path = f"map64/{mode}/{case}/{metric}"
                reference = baseline["metrics"].get(path)
                value = row.get(metric)
                if reference is None or type(value) not in (int, float) or not math.isfinite(value):
                    checks[metric] = {"judgment": "HOLD", "reason": "metric or parent baseline missing"}
                    continue
                parent = reference["parent_median"]
                adverse = parent - value if metric == "alive_at_end" else value - parent
                checks[metric] = {"judgment": "FAIL" if adverse > limit else "PASS",
                                  "parent_median": parent, "measured": value,
                                  "adverse_delta": adverse, "limit": limit}
            judgments = {value["judgment"] for value in checks.values()}
            verdict = "FAIL" if "FAIL" in judgments else "HOLD" if "HOLD" in judgments else "PASS"
            record_only = mode == "probe_prop_only"
            cells[mode][case] = {"role": "record_only" if record_only else "judge",
                                 "judgment": "HOLD" if record_only else verdict,
                                 "reason": "E0 record-only map mode" if record_only else None,
                                 "comparison_judgment": verdict if record_only else None,
                                 "metrics": checks}
    result["cell_judgments"] = cells
    judged = [row["judgment"] for mode in ("eval_gt", "eval_pred") for row in cells[mode].values()]
    if len(judged) != 26:
        raise ValueError("EX-42 E0 judge cell count differs")
    result["judgement"] = "FAIL" if "FAIL" in judged else "HOLD" if "HOLD" in judged else "PASS"
    result["reason"] = "E0 parent median from five A23 repeats; q4 measured limits; 26 judge cells"
    items = {name: dict(row) for name, row in score["maintenance_items"].items()}
    for name, row in items.items():
        if name == "calibration_repeat_width":
            row.update(state="pinned_five_repeats", judgement="PASS",
                       evidence=baseline["calibration_sha256"])
        elif name == "parent_cumulative_drop":
            row.update(state="awaiting_second_window", judgement="HOLD")
        elif name in ("survival", "tracking_vx_vy", "tracking_wz", "W57_spin_survival"):
            fields = {"survival": ("alive_at_end",), "tracking_vx_vy": (
                "vx_abs_error_median_mps", "vy_abs_error_median_mps"),
                "tracking_wz": ("wz_abs_error_median_radps",),
                "W57_spin_survival": ("alive_at_end",)}[name]
            values = [cell["metrics"][field]["judgment"] for mode in ("eval_gt", "eval_pred")
                      for case, cell in cells[mode].items()
                      if name != "W57_spin_survival" or case in ("spin+1.2", "spin-1.2")
                      for field in fields]
            row.update(state="judged", judgement="FAIL" if "FAIL" in values else
                       "HOLD" if "HOLD" in values else "PASS")
        else:
            row.update(state="baseline_pinned_record_only", judgement="HOLD",
                       baseline_metric_count=len(baseline["items"][name]["metric_paths"]))
    result["maintenance_items"] = items
    return result
