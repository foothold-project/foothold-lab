"""E2 fixed-evaluation comparison with the immediately preceding boundary.

The parent comparison is a separate gate. This gate records a regression outside
the calibrated width as HOLD, so training may continue without opening exposure.
"""
from __future__ import annotations

import math


def compare(now: dict, previous: dict | None, *, measured: dict,
            baseline: dict, kind_now: dict, kind_previous: dict | None,
            stage_id: str | None = None, kind_score_key: str = "e2_kind",
            kind_subcells: tuple[str, ...] = ("forward", "flag_four")) -> dict:
    if (stage_id is not None and (not isinstance(stage_id, str) or not stage_id) or
            not isinstance(kind_score_key, str) or not kind_score_key or
            not isinstance(kind_subcells, tuple) or not kind_subcells or
            len(set(kind_subcells)) != len(kind_subcells) or
            any(not isinstance(cell, str) or not cell for cell in kind_subcells)):
        raise ValueError("EX-42 exchange watch stage or kind identity invalid")
    if previous is None:
        return {"role": "judge", "judgement": "HOLD", "source": "fixed_eval",
                "reason": "직전 경계 평가 없음", "violations": [], "missing": ["previous_boundary"]}
    if (now.get("conditions", {}).get("eval_seed") != previous.get("conditions", {}).get("eval_seed") or
            now.get("score_config_sha256") != previous.get("score_config_sha256") or
            now.get("stage_id") != previous.get("stage_id") or
            (stage_id is not None and now.get("stage_id") != stage_id) or
            (stage_id is not None and (kind_score_key not in now or kind_score_key not in previous)) or
            now.get(kind_score_key, {}).get("mesh_sha256") != previous.get(kind_score_key, {}).get("mesh_sha256")):
        return {"role": "judge", "judgement": "HOLD", "source": "fixed_eval",
                "reason": "직전 경계 시드·설정·단계·메시가 다름", "violations": [], "missing": ["identity"]}
    limits = {"alive_at_end": measured["survival_drop_envs"],
              "vx_abs_error_median_mps": measured["error_rise_vx_vy_mps"],
              "vy_abs_error_median_mps": measured["error_rise_vx_vy_mps"],
              "wz_abs_error_median_radps": measured["error_rise_wz_radps"]}
    violations, missing, compared, record_only = [], [], 0, {}

    def check(path, old, new, allowance, *, larger_is_better=False, record=False):
        nonlocal compared
        if (type(old) not in (int, float) or type(new) not in (int, float) or
                type(allowance) not in (int, float) or
                not all(math.isfinite(float(x)) for x in (old, new, allowance)) or allowance < 0):
            missing.append(path)
            return
        adverse = old - new if larger_is_better else new - old
        if record:
            record_only[path] = {"previous": old, "current": new, "adverse": adverse}
            return
        compared += 1
        if adverse > allowance:
            violations.append({"cell": path, "previous": old, "current": new,
                               "adverse": adverse, "limit": allowance})

    for mode in ("eval_gt", "eval_pred", "probe_prop_only"):
        new_cases = now.get("map64", {}).get(mode, {})
        old_cases = previous.get("map64", {}).get(mode, {})
        if set(new_cases) != set(old_cases) or len(new_cases) != 13:
            missing.append(f"map64/{mode}/coverage")
            continue
        for case, new_row in new_cases.items():
            old_row = old_cases[case]
            for metric, allowance in limits.items():
                check(f"map64/{mode}/{case}/{metric}", old_row.get(metric), new_row.get(metric),
                      allowance, larger_is_better=metric == "alive_at_end",
                      record=mode == "probe_prop_only")
            path = f"map64/{mode}/{case}/command_projection_median_m"
            parent = baseline.get("metrics", {}).get(path, {}).get("parent_median")
            check(path, old_row.get("command_projection_median_m"),
                  new_row.get("command_projection_median_m"),
                  .1 * abs(parent) if type(parent) in (int, float) else None,
                  larger_is_better=True, record=mode == "probe_prop_only")
    for mode in ("eval_gt", "eval_pred", "probe_prop_only"):
        new_row, old_row = kind_now.get(mode), (kind_previous or {}).get(mode)
        if not isinstance(new_row, dict) or not isinstance(old_row, dict):
            missing.append(f"kind/{mode}")
            continue
        for subcell in kind_subcells:
            newer, older = new_row.get(subcell, {}), old_row.get(subcell, {})
            valid_new, valid_old = newer.get("valid_count"), older.get("valid_count")
            for metric in ("success_count", "survival_count"):
                path = f"kind/{mode}/{subcell}/{metric}"
                if (type(valid_new) is not int or type(valid_old) is not int or
                        not 0 < valid_new <= 64 or not 0 < valid_old <= 64 or
                        type(newer.get(metric)) is not int or type(older.get(metric)) is not int):
                    missing.append(path)
                    continue
                old_scaled = math.ceil(older[metric] * valid_new / valid_old)
                check(path, old_scaled, newer[metric], measured["survival_drop_envs"],
                      larger_is_better=True, record=mode == "probe_prop_only")
    for mode in ("eval_gt", "eval_pred", "probe_prop_only"):
        new_axis = now.get("axis_v2", {}).get(mode, {})
        old_axis = previous.get("axis_v2", {}).get(mode, {})
        if set(new_axis) != set(old_axis) or not new_axis:
            missing.append(f"axis_v2/{mode}/coverage")
            continue
        for case, new_row in new_axis.items():
            old_row = old_axis[case]
            newer = new_row.get("foot_drag_proxy_m_by_foot_median", [])
            older = old_row.get("foot_drag_proxy_m_by_foot_median", [])
            if len(newer) != 4 or len(older) != 4:
                missing.append(f"axis_v2/{mode}/{case}/foot_drag/coverage")
                continue
            for foot in range(4):
                path = f"axis_v2/{mode}/{case}/foot_drag_proxy_m_by_foot_median/{foot}"
                allowance = baseline.get("metrics", {}).get(path, {}).get("rise_limit_m")
                check(path, older[foot], newer[foot], allowance,
                      record=mode == "probe_prop_only")
    for mode in ("eval_gt", "eval_pred", "probe_prop_only"):
        feet_now = now.get("stand", {}).get(mode, {}).get("per_foot_contact_fraction_median", {})
        feet_old = previous.get("stand", {}).get(mode, {}).get("per_foot_contact_fraction_median", {})
        if set(feet_now) != set(feet_old) or len(feet_now) != 4:
            missing.append(f"stand/{mode}/coverage")
            continue
        for foot in feet_now:
            check(f"stand/{mode}/{foot}/contact", feet_old[foot], feet_now[foot], 0,
                  record=True)
    for source in ("d44_cells", "flag_cells"):
        latest = now.get(source) or {}
        earlier = previous.get(source) or {}
        if not latest or set(latest) != set(earlier):
            missing.append(source)
            continue
        for case, new_row in latest.items():
            old_row = earlier[case]
            valid_new, valid_old = new_row.get("valid_count"), old_row.get("valid_count")
            for metric in ("success_count", "survival_count"):
                path = f"{source}/{case}/{metric}"
                if (type(valid_new) is not int or type(valid_old) is not int or
                        not 0 < valid_new <= 64 or not 0 < valid_old <= 64 or
                        type(new_row.get(metric)) is not int or type(old_row.get(metric)) is not int):
                    missing.append(path)
                    continue
                old_scaled = math.ceil(old_row[metric] * valid_new / valid_old)
                check(path, old_scaled, new_row[metric], measured["survival_drop_envs"],
                      larger_is_better=True,
                      record="probe_prop_only" in case)
    return {"role": "judge", "judgement": "HOLD" if missing or violations else "PASS",
            "source": "fixed_eval", "compared": compared, "limits": limits,
            "violations": violations, "missing": sorted(set(missing)),
            "record_only_deltas": record_only,
            **({"reason": "교환 감시 원자료 결측 또는 반복 폭 밖 하락"} if missing or violations else {})}
