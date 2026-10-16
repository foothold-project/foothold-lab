"""Seal an S2 case list from the 1043 Q evaluator's terrain and command vocabulary.

No simulator is imported. Physical mesh and initial state fingerprints are checked
by the driver at execution time; a seed alone never proves paired equivalence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class CaseError(ValueError):
    pass


FAMILIES = ("gap", "stepping_stones", "flat", "stairs_up")
COUNTS = ("gap", "stepping_stones", "flat", "stairs_up")
COMMANDS = {
    "fwd03": {"name": "fwd03", "kind": "lin", "cmd": [0.3, 0.0, 0.0], "duration_s": 20.0, "switch_s": None},
    "fwd10": {"name": "fwd10", "kind": "lin", "cmd": [1.0, 0.0, 0.0], "duration_s": 20.0, "switch_s": None},
}
SOURCE_SHA = {
    "candidate_manifest_s1043.json": "837fbe07b4240b80dcc9bbb269534ed2f076eff0899c325b77eaa00843909413",
    "q_eval_cmdr.py": "24aeaf6358ef79096911e3dcb220212ac715775012da96bf14e438c331dba4bc",
    "cmdr_post_v10.py": "dea9ca7bfe01b92b634aa85048ff0cb4128b4eaa3b7943030a9a9b5660332dc2",
    "unseen_post.py": "880ca17c469c3ff79a66afc631f49db420fd7c3cc71ff240ec096e960a41975e",
    "terrains.py": "3e0d47185f110a5fb6aa3550ba61ea7edd0fa1e89bd6a275f9377fae283a72ae",
    "q_metrics.py": "c9930f8d327efd04df51440da519fefab2585490ae45b4a6ffbd39466138a794",
    "paired_ci.py": "3056f6b364d8f4499a52d23839a901931d9ef0496dbdbb9e49e13da5665cdc2d",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _sha_ok(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def seal(*, phase, counts, eval_seeds, learning_seeds, command, difficulty,
         terrain_source_sha256, terrain_source, geometry_sha256, friction,
         physics_dt=0.005, policy_dt=0.02):
    if (phase not in ("smoke", "full") or set(counts) != set(COUNTS) or
        any(type(counts[f]) is not int or counts[f] < 0 for f in COUNTS) or
        (phase == "smoke" and counts != {"gap": 2, "stepping_stones": 2, "flat": 0, "stairs_up": 0}) or
        (phase == "full" and any(counts[f] < 1 for f in COUNTS))):
        raise CaseError("counts: explicit four layers required; smoke=2/2/0/0, full all positive; UNDECIDED rejected")
    if command not in COMMANDS:
        raise CaseError("command must be a pinned 1043 Q cell")
    if type(difficulty) not in (float, int) or not 0 <= difficulty <= 1:
        raise CaseError("difficulty")
    if type(friction) not in (float, int) or friction <= 0:
        raise CaseError("friction")
    if physics_dt != 0.005 or policy_dt != 0.02:
        raise CaseError("1043 dt contract")
    if not all(_sha_ok(x) for x in (terrain_source_sha256, geometry_sha256)) or not terrain_source:
        raise CaseError("terrain and geometry source SHA required")
    n = sum(counts.values())
    if (len(eval_seeds) != n or len(set(eval_seeds)) != n or
        any(type(x) is not int or x < 0 for x in eval_seeds) or
        any(type(x) is not int or x < 0 for x in learning_seeds) or
        set(eval_seeds) & (set(learning_seeds) | {11, 7})):
        raise CaseError("eval seeds must be unique, count-matched and disjoint from learning seeds 11/7")
    if not {11, 7}.issubset(set(learning_seeds)):
        raise CaseError("learning seed set must include 11 and 7")
    cases = []
    idx = 0
    for family in FAMILIES:
        for ordinal in range(counts[family]):
            seed = eval_seeds[idx]
            cases.append({
                "case_id": f"{family}-{ordinal:03d}-s{seed}",
                "family": family, "eval_seed": seed, "terrain_seed": seed,
                "terrain_set": "unseen10" if family in ("gap", "stepping_stones") else "train",
                "terrain_source": terrain_source, "terrain_source_sha256": terrain_source_sha256,
                "geometry_sha256": geometry_sha256, "difficulty": float(difficulty),
                "command": COMMANDS[command], "friction": float(friction),
                "reset": {"origin_xy_m": [-0.5, 0.5], "origin_z_m": [0.0, 0.2],
                          "joints": "default pose scale 1.0", "body_velocity": [0.0] * 6,
                          "yaw": "fixed per command; linear points world +x"},
                "physics_dt": physics_dt, "policy_dt": policy_dt,
                "episode_length_s": 30.0,
                "score_contract": {"fall": "q_metrics.fall_index span", "command_pass": "span_q1_pass",
                                   "crossed": "unseen_post obstacle_zone_m end while alive",
                                   "stuck": "alive without zone crossing at duration"},
            })
            idx += 1
    payload = {"schema": "s2-eval-cases-v1", "phase": phase, "source": "1043 Q evaluator",
               "source_sha256": SOURCE_SHA, "counts": counts, "learning_seeds": sorted(set(learning_seeds)),
               "cases": cases}
    payload["cases_sha256"] = digest({k: v for k, v in payload.items() if k != "cases_sha256"})
    return payload


def verify(payload):
    if not isinstance(payload, dict) or payload.get("schema") != "s2-eval-cases-v1":
        raise CaseError("case schema")
    want = digest({k: v for k, v in payload.items() if k != "cases_sha256"})
    if payload.get("cases_sha256") != want:
        raise CaseError("case list SHA")
    if payload.get("source_sha256") != SOURCE_SHA:
        raise CaseError("1043 source pin")
    counts = payload.get("counts", {})
    cases = payload.get("cases", [])
    if (set(counts) != set(COUNTS) or len(cases) != sum(counts.values()) or
        len({c["case_id"] for c in cases}) != len(cases) or
        len({c["eval_seed"] for c in cases}) != len(cases) or
        {c["family"] for c in cases} != {f for f in FAMILIES if counts[f]} or
        any(sum(c["family"] == f for c in cases) != counts[f] for f in FAMILIES) or
        {c["eval_seed"] for c in cases} & set(payload.get("learning_seeds", []))):
        raise CaseError("case count, identity or seed")
    return want


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--phase", required=True, choices=("smoke", "full"))
    for f in COUNTS:
        p.add_argument("--" + f + "-pairs", required=True, type=int)
    p.add_argument("--eval-seeds", required=True, help="comma separated, one per case")
    p.add_argument("--learning-seeds", required=True, help="comma separated, include 11,7")
    p.add_argument("--command", required=True, choices=tuple(COMMANDS))
    p.add_argument("--difficulty", required=True, type=float)
    p.add_argument("--friction", required=True, type=float)
    p.add_argument("--terrain-source", required=True)
    p.add_argument("--terrain-source-sha256", required=True)
    p.add_argument("--geometry-sha256", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    counts = {f: getattr(a, f + "_pairs") for f in COUNTS}
    x = seal(phase=a.phase, counts=counts, eval_seeds=[int(v) for v in a.eval_seeds.split(",")],
             learning_seeds=[int(v) for v in a.learning_seeds.split(",")], command=a.command,
             difficulty=a.difficulty, friction=a.friction, terrain_source=a.terrain_source,
             terrain_source_sha256=a.terrain_source_sha256, geometry_sha256=a.geometry_sha256)
    Path(a.out).write_bytes(canonical(x) + b"\n")
    print(x["cases_sha256"])


if __name__ == "__main__":
    main()
