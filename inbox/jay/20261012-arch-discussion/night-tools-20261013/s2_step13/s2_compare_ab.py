"""CPU only exploratory S2 encounter comparison. A frozen criteria receipt is mandatory."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path
MATCH_FIELDS=("parent","agent_yaml","encoder_mode","schedule","seed",
              "num_envs","rollout_steps","epochs","minibatches","map_init_seed",
              "gap_proportion","stones_proportion","step_height_m","step_width_m",
              "geometry_tolerance_m","lr","clip_param","gamma","lam",
              "value_loss_coef","entropy_coef","max_grad_norm","desired_kl",
              "use_clipped_value_loss")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required(criteria: dict) -> None:
    keys = ("terrains", "arms", "final_checkpoint", "window_updates", "min_assigned",
            "min_approach", "min_blocks", "bootstrap_reps", "bootstrap_seed", "z",
            "min_mean_delta", "min_delta_lower")
    if any(k not in criteria for k in keys):
        raise ValueError("criteria_missing")
    allowed = (["A", "B-mlp"], ["A", "B-mlp", "B-attn"],
               ["A-mlp", "B-mlp", "A-attn", "B-attn"])
    if criteria["arms"] not in allowed or not criteria["terrains"]:
        raise ValueError("criteria_arms_or_terrains")
    for k in ("final_checkpoint", "window_updates", "min_assigned", "min_approach",
              "min_blocks", "bootstrap_reps"):
        if type(criteria[k]) is not int or criteria[k] <= 0:
            raise ValueError("criteria_positive_" + k)
    if type(criteria["bootstrap_seed"]) is not int:
        raise ValueError("criteria_seed")
    for k in ("z", "min_mean_delta", "min_delta_lower"):
        if type(criteria[k]) not in (float, int) or not math.isfinite(criteria[k]):
            raise ValueError("criteria_finite_" + k)
    if criteria["z"] <= 0 or not -1 <= criteria["min_delta_lower"] <= 1 or not -1 <= criteria["min_mean_delta"] <= 1:
        raise ValueError("criteria_range")


def freeze(criteria_path: Path, ledger_path: Path) -> dict:
    """Exclusive creation. This must precede opening result data."""
    criteria = json.loads(criteria_path.read_text(encoding="utf-8"))
    _required(criteria)
    receipt = {"criteria_sha256": sha(criteria_path), "criteria_path": str(criteria_path.resolve())}
    with ledger_path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, sort_keys=True)
    return receipt


def _load_frozen(criteria_path: Path, ledger_path: Path) -> tuple[dict, str]:
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if ledger.get("criteria_path") != str(criteria_path.resolve()) or ledger.get("criteria_sha256") != sha(criteria_path):
        raise ValueError("criteria_digest_mismatch")
    criteria = json.loads(criteria_path.read_text(encoding="utf-8"))
    _required(criteria)
    return criteria, ledger["criteria_sha256"]


def wilson(success: int, n: int, z: float) -> tuple[float, float] | None:
    if n == 0:
        return None
    if not 0 <= success <= n:
        raise ValueError("bad_binomial")
    p = success / n
    den = 1 + z*z/n
    center = (p + z*z/(2*n))/den
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return center-half, center+half


def _counts(events: list[dict]) -> dict:
    out = {k: 0 for k in ("assigned", "approach", "pass", "avoid", "fall", "stall", "ongoing", "unknown", "censored")}
    for event in events:
        out["assigned"] += 1
        if event["approach"]:
            out["approach"] += 1
        out[event["outcome"]] += 1
    return out


def _rate(events: list[dict], denominator: str) -> float:
    c = _counts(events)
    return c["pass"] / c[denominator] if c[denominator] else float("nan")


def _paired_interval(a_events: list[dict], b_events: list[dict], denominator: str,
                     reps: int, seed: int, min_blocks: int) -> tuple[float, float] | None:
    a_blocks, b_blocks = {}, {}
    for event in a_events:
        a_blocks.setdefault(event["block"], []).append(event)
    for event in b_events:
        b_blocks.setdefault(event["block"], []).append(event)
    blocks = sorted(set(a_blocks) & set(b_blocks))
    if len(blocks) < min_blocks:
        return None
    rng = random.Random(seed)
    deltas = []
    for _ in range(reps):
        picked = [rng.choice(blocks) for _ in blocks]
        ae = [e for block in picked for e in a_blocks[block]]
        be = [e for block in picked for e in b_blocks[block]]
        ar, br = _rate(ae, denominator), _rate(be, denominator)
        if math.isfinite(ar) and math.isfinite(br):
            deltas.append(br-ar)
    if len(deltas) != reps:
        return None
    deltas.sort()
    return deltas[max(0, math.floor(.025*reps)-1)], deltas[min(reps-1, math.ceil(.975*reps)-1)]


def compare(data_path: Path, criteria_path: Path, ledger_path: Path) -> dict:
    criteria, digest = _load_frozen(criteria_path, ledger_path)
    data = json.loads(data_path.read_text(encoding="utf-8"))
    events = data["events"]
    stages = data["stages"]
    seen = set()
    block_meta = {}
    for e in events:
        key = tuple(e[k] for k in ("arm", "terrain_instance", "terrain_seed", "difficulty", "env", "episode", "obstacle_id"))
        if key in seen:
            raise ValueError("duplicate_encounter")
        seen.add(key)
        if e["arm"] not in criteria["arms"] or e["terrain"] not in criteria["terrains"]:
            raise ValueError("unknown_arm_or_terrain")
        if e["outcome"] not in ("pass", "avoid", "fall", "stall", "ongoing", "unknown", "censored"):
            raise ValueError("bad_outcome")
        if type(e["approach"]) is not bool or (e["outcome"] == "pass" and not e["approach"]):
            raise ValueError("bad_approach")
        if type(e["update"]) is not int or e["update"] < 0 or not e["block"]:
            raise ValueError("bad_update_or_block")
        if not e.get("command_bin") or e.get("difficulty") is None:
            raise ValueError("stratum_missing")
        identity = (e["terrain"], e["terrain_seed"], e["env"], e["difficulty"],
                    e["command_bin"], (e["update"] - 1)//criteria["window_updates"])
        old = block_meta.setdefault(e["block"], identity)
        if old != identity:
            raise ValueError("block_identity_mismatch")
    checkpoints = list(range(criteria["window_updates"], criteria["final_checkpoint"]+1, criteria["window_updates"]))
    if checkpoints[-1] != criteria["final_checkpoint"]:
        checkpoints.append(criteria["final_checkpoint"])
    rows = []
    strata_rows = []
    final = []
    for cp in checkpoints:
        if stages.get(str(cp)) != "PASS":
            raise ValueError("stage_not_pass")
        start = cp - criteria["window_updates"]
        for terrain in criteria["terrains"]:
            selected = {arm: [e for e in events if e["arm"] == arm and e["terrain"] == terrain and start < e["update"] <= cp]
                        for arm in criteria["arms"]}
            cumulative = {arm: [e for e in events if e["arm"] == arm and e["terrain"] == terrain and e["update"] <= cp]
                          for arm in criteria["arms"]}
            baseline = "A" if "A" in criteria["arms"] else "A-mlp"
            base = _counts(selected[baseline])
            strata = sorted({(e["difficulty"], e["command_bin"]) for arm in criteria["arms"]
                             for e in selected[arm]}, key=lambda x: (str(x[0]), str(x[1])))
            for difficulty, command_bin in strata:
                counts = {arm: _counts([e for e in selected[arm]
                                       if e["difficulty"] == difficulty and e["command_bin"] == command_bin])
                          for arm in criteria["arms"]}
                strata_rows.append({"checkpoint": cp, "window": [start+1, cp], "terrain": terrain,
                                    "difficulty": difficulty, "command_bin": command_bin,
                                    "counts_by_arm": counts,
                                    "assignment_or_approach_mismatch":
                                    any(counts[arm]["assigned"] != counts[baseline]["assigned"] or
                                        counts[arm]["approach"] != counts[baseline]["approach"]
                                        for arm in criteria["arms"] if arm != baseline)})
            for arm in criteria["arms"]:
                c = _counts(selected[arm])
                cum = _counts(cumulative[arm])
                row = {"checkpoint": cp, "window": [start+1, cp], "terrain": terrain, "arm": arm,
                       "window_counts": c, "cumulative_counts": cum,
                       "assigned_pass_rate": c["pass"]/c["assigned"] if c["assigned"] else None,
                       "approach_pass_rate": c["pass"]/c["approach"] if c["approach"] else None,
                       "assigned_wilson": wilson(c["pass"], c["assigned"], criteria["z"]),
                       "approach_wilson": wilson(c["pass"], c["approach"], criteria["z"]),
                       "selection_changed": c["assigned"] != base["assigned"] or c["approach"] != base["approach"]}
                if arm != baseline:
                    eligible = min(c["assigned"], base["assigned"]) >= criteria["min_assigned"] and min(c["approach"], base["approach"]) >= criteria["min_approach"]
                    interval = _paired_interval(selected[baseline], selected[arm], "assigned", criteria["bootstrap_reps"],
                                                criteria["bootstrap_seed"]+cp, criteria["min_blocks"]) if eligible else None
                    row["delta_vs_A"] = row["assigned_pass_rate"] - base["pass"]/base["assigned"] if eligible else None
                    row["delta_interval_exploratory"] = interval
                    row["direction"] = "판정 불가" if interval is None else ("탐색 하한 충족" if interval[0] > criteria["min_delta_lower"] else "탐색 하한 미충족")
                    if cp == criteria["final_checkpoint"]:
                        final.append(row)
                rows.append(row)
    def final_direction(arm):
        arm_rows = [r for r in final if r["arm"] == arm]
        if len(arm_rows) != len(criteria["terrains"]) or any(r["direction"] == "판정 불가" for r in arm_rows):
            return "판정 불가"
        if all(r["direction"] == "탐색 하한 충족" for r in arm_rows) and sum(r["delta_vs_A"] for r in arm_rows)/len(arm_rows) >= criteria["min_mean_delta"]:
            return "탐색 기준 충족"
        return "탐색 기준 미충족"
    return {"status": "학습 중 방향 관찰, 독립 평가 아님", "criteria_sha256": digest,
            "data_sha256": sha(data_path), "rows": rows, "strata_rows": strata_rows,
            "design": "first A/B MLP" if criteria["arms"] == ["A", "B-mlp"] else
                      "exploratory structural comparison; no isolated map effect",
            "final_boundary": criteria["final_checkpoint"],
            "final_only": {arm: final_direction(arm) for arm in criteria["arms"]
                           if arm != ("A" if "A" in criteria["arms"] else "A-mlp")}}


def compare_short(data_path: Path, criteria_path: Path, ledger_path: Path,
                  manifests: dict[str, Path], receipts: dict[str, Path]) -> dict:
    """Read both sealed runs and all 0..2000 checkpoint bytes before comparing."""
    if set(manifests)!={"A","B"} or set(receipts)!={"A","B"}:
        raise ValueError("short_arm_pair_missing")
    criteria,digest=_load_frozen(criteria_path,ledger_path)
    if criteria["arms"]!=["A","B-mlp"] or criteria["final_checkpoint"]!=2000 or criteria["window_updates"]!=200:
        raise ValueError("short_evaluation_conditions")
    loaded={arm:(json.loads(manifests[arm].read_text(encoding="utf-8")),
                 json.loads(receipts[arm].read_text(encoding="utf-8"))) for arm in ("A","B")}
    a=loaded["A"][0]
    expected={f"checkpoint_{n:06d}.pt" for n in range(0,2001,200)}
    for arm in ("A","B"):
        m,r=loaded[arm]
        plan=m.get("plan") or {}
        manifest_digest=hashlib.sha256(json.dumps(m,sort_keys=True,
                                    separators=(",",":"),allow_nan=False).encode()).hexdigest()
        if (m.get("chain_id")!=a.get("chain_id") or m.get("gpu_uuid")!=a.get("gpu_uuid") or
            m.get("evaluation_criteria_sha256")!=digest or
            m.get("extension_disabled") is not True or
            m.get("checkpoint_boundaries")!=list(range(0,2001,200)) or
            plan.get("extension_disabled") is not True or
            plan.get("arm")!=arm or plan.get("stage")!="short" or
            plan.get("updates")!=2000 or plan.get("checkpoint_interval")!=200):
            raise ValueError("short_manifest_conditions_mismatch")
        if any(plan.get(k)!=a.get("plan",{}).get(k) for k in MATCH_FIELDS):
            raise ValueError("short_training_conditions_mismatch")
        if (r.get("chain_id")!=m["chain_id"] or r.get("arm")!=arm or
            r.get("stage")!="short" or r.get("manifest_sha256")!=manifest_digest or
            r.get("verdict")!="RUN_COMPLETE_UNVERIFIED" or r.get("boundary_ok") is not True or
            r.get("family_active_count")!=0 or
            r.get("parent_sha256_before")!=plan.get("parent_sha256") or
            r.get("parent_sha256_after")!=plan.get("parent_sha256") or
            type(r.get("executed_updates")) is not int or r["executed_updates"]!=2000 or
            r.get("extension_disabled") is not True or
            r.get("family_cleanup_confirmed") is not True or
            r.get("gpu_lease_released") is not True or
            r.get("usd_lock_released") is not True):
            raise ValueError("short_receipt_unverified")
        hashes=r.get("checkpoint_sha256") or {}
        if not expected.issubset(hashes):raise ValueError("short_checkpoint_boundary_missing")
        root=Path(r.get("out_root") or "missing")
        if root.resolve()!=Path(plan.get("out_root") or "missing").resolve():
            raise ValueError("short_output_identity")
        for name in sorted(expected):
            path=root/name
            if not path.is_file() or path.stat().st_size==0 or sha(path)!=hashes[name]:
                raise ValueError("short_checkpoint_hash_mismatch")
    data=json.loads(data_path.read_text(encoding="utf-8"))
    if (data.get("chain_id")!=a.get("chain_id") or data.get("criteria_sha256")!=digest or
        data.get("source_receipts")!={arm:sha(receipts[arm]) for arm in ("A","B")}):
        raise ValueError("short_evaluation_provenance_mismatch")
    result=compare(data_path,criteria_path,ledger_path)
    stage0=all(loaded[arm][1].get("stage0_passed") is True for arm in ("A","B"))
    result["status"]="잠정 · 0단계 통과" if stage0 else "잠정 · 0단계 미통과"
    result["stage0_passed"]=stage0
    result["receipt_sha256"]={arm:sha(receipts[arm]) for arm in ("A","B")}
    result["checkpoint_boundaries"]=list(range(0,2001,200))
    result["performance_verified"]=False
    if any(loaded[arm][0].get("map_contract_verified") is not True for arm in ("A","B")):
        result["status"]="잠정 · 지도 계약 미확인"
        result["final_only"]={arm:"판정 보류 · 지도 계약 미확인" for arm in result["final_only"]}
        result["comparison_ready"]=False
    else:result["comparison_ready"]=True
    return result


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="action", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--criteria", type=Path, required=True)
    f.add_argument("--ledger", type=Path, required=True)
    c = sub.add_parser("compare")
    c.add_argument("--criteria", type=Path, required=True)
    c.add_argument("--ledger", type=Path, required=True)
    c.add_argument("--data", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("compare-short")
    for name in ("criteria","ledger","data","manifest-a","manifest-b",
                 "receipt-a","receipt-b","out"):
        s.add_argument("--"+name,type=Path,required=True)
    a = ap.parse_args(argv)
    if a.action == "freeze":
        print(json.dumps(freeze(a.criteria, a.ledger), ensure_ascii=False))
    elif a.action == "compare":
        a.out.write_text(json.dumps(compare(a.data, a.criteria, a.ledger), ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        result=compare_short(a.data,a.criteria,a.ledger,
                             {"A":a.manifest_a,"B":a.manifest_b},
                             {"A":a.receipt_a,"B":a.receipt_b})
        a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
