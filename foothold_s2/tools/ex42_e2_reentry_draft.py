"""Draft plan + approvals for a NEW E2 run seeded from this E2 run's own boundary checkpoint (lead-lx 11/19 07:1x).

    python -m foothold_s2.tools.ex42_e2_reentry_draft --source-dir <materialized_E2> --run-dir <E2 run> --iteration 750 \
        --mesh-dir <beam mesh folder> --out <new folder>

A same-run resume cannot change the mesh pin or the level-up rule (both are plan edits, the saved state binds the plan sha256), so the
change goes in through the entry the first E2 used: a new OUT whose parent is a checkpoint. The stage id stays E2. The draft copies the
materialized plan folder and changes only:
  * stages[E2].parent  -> source_stage_id E2, manifest_local_update N, checkpoint_key model_N.pt, sha256 of that file, cumulative_update
                          = the old parent's cumulative + N (the origin does not move: the count of updates stays the lineage's);
  * training_mesh_profiles + every stage that named the old profile -> the new mesh folder (ex42_beam_pin_draft.profile_block rules);
  * terrain_promotion (optional cell, ex41.terrain_promotion_cell);
  * kind level caps (optional, lead 11/19 13:19): --bake-caps-run <run> --bake-boundaries k writes the caps the run had after k boundaries (the plan
                          start values advanced by `raise_kind_caps` from the run's ladder evidence) into the new plan's start block, because a
                          new OUT counts its own boundaries from 0; --kind-cap <family/kind>=<n> then LOWERS single kinds (never raises). At the
                          start the exposure layer clips every env to min(level, cap of its column), so envs above a lowered cap come down;
  * the approval cell's scope.parent_sha256 and the plan's stage_zero.approval_sha256 (the approvals file bytes changed).
The `materialization` declaration and transition.json are NOT carried over: they describe E1F -> E2 with a gate receipt, and a plan
that still carried them would be re-derived from that gate (validate_materialized_transition) and refused. The draft writes its own
`reentry.json` (what was changed, the old and new plan sha256, the parent pin) instead. Nothing here starts training.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import yaml

OLD_PROFILE = "e2_easy10_edge"
FILES = ("terrain_mesh.npz", "mesh_manifest.json", "terrain_manifest.json")
STAGE = "E2"
DEFAULT_KINDS = ["A/gaps", "B/gap", "C/gap", "B/beam", "A/balance_beams", "B/pallets", "A/stepping_beams",
                 "A/stepping_stones_low", "A/stepping_stones_high", "B/stones"]
REENTRY_FORMAT = "foothold-ex42-e2-reentry/1"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _dump(doc) -> bytes:
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True).encode()


def mesh_profile(mesh_dir: Path) -> dict:
    mesh_dir = Path(mesh_dir).resolve(strict=True)
    geometry = json.loads((mesh_dir / "mesh_manifest.json").read_text(encoding="utf-8-sig"))["mesh_sha256"]
    return {"directory": str(mesh_dir), "geometry_sha256": geometry, "files": {f: _sha(mesh_dir / f) for f in FILES}}


def parent_pin(source_row: dict, run_dir: Path, iteration: int) -> dict:
    """The pin of the new run's parent: this E2 run's own model_<iteration>.pt, read from its manifest (the published checkpoint)."""
    run_dir = Path(run_dir).resolve(strict=True)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    key = f"model_{iteration}.pt"
    done = (manifest.get("progress") or {}).get("completed_updates")
    if type(done) is not int or done < iteration or key not in (manifest.get("checkpoints") or {}):
        raise ValueError(f"the run manifest has not published {key}")
    sha = _sha(run_dir / key)
    if not str(manifest["checkpoints"][key]).startswith(sha[:10]) and manifest["checkpoints"][key] != sha:
        raise ValueError(f"{key} differs from the manifest inventory")
    base = (source_row.get("parent") or {}).get("cumulative_update")
    if type(base) is not int:
        raise ValueError("the source E2 row has no parent cumulative_update")
    return {"source_stage_id": STAGE, "manifest_local_update": iteration, "checkpoint_key": key, "sha256": sha,
            "cumulative_update": base + iteration}


def rule_caps(terrain: dict) -> dict:
    """{family/kind: level_cap} of the single-kind share rules of the stage's start block."""
    rules = (terrain.get(f"exposure_at_{STAGE}") or {}).get("positive") or []
    return {f"{r['family']}/{r['kind']}": int(r["level_cap"]) for r in rules if "kind" in r and "share" in r}


def set_kind_caps(terrain: dict, run_dir: Path | None, boundaries: int, overrides: dict | None) -> tuple[dict, dict]:
    """(terrain, report). Bake the caps after `boundaries` boundaries of `run_dir` (ladder evidence
    eval/scores/m<boundaries*250>/ladder_outcomes_list.json, replayed by raise_kind_caps) and lower the named kinds. Anything else of the
    terrain cell stays. Raising a kind above its baked value is refused (this is a way down only)."""
    from foothold_s2.terrains.ex42_exposure import raise_kind_caps
    report = {"start": rule_caps(terrain), "boundaries": 0, "moves": [], "lowered": {}}
    if run_dir is not None:
        listing = Path(run_dir) / "eval" / "scores" / f"m{boundaries * 250}" / "ladder_outcomes_list.json"
        outcomes = json.loads(listing.read_text(encoding="utf-8-sig"))
        if len(outcomes) < boundaries:
            raise ValueError(f"{listing} has {len(outcomes)} boundary entries, need {boundaries}")
        terrain, moves = raise_kind_caps(terrain, STAGE, boundaries, outcomes)
        report.update(boundaries=boundaries, moves=moves, evidence=str(listing))
    baked = rule_caps(terrain)
    report["baked"] = dict(baked)
    for kind, cap in (overrides or {}).items():
        if kind not in baked:
            raise ValueError(f"--kind-cap {kind}: no such single-kind share rule (have {sorted(baked)})")
        if type(cap) is not int or not 0 <= cap <= baked[kind]:
            raise ValueError(f"--kind-cap {kind}={cap}: must be an integer 0..{baked[kind]} (lowering only)")
        report["lowered"][kind] = {"from": baked[kind], "to": cap}
    if overrides:
        block = terrain[f"exposure_at_{STAGE}"]
        rules = [dict(r, level_cap=overrides[f"{r['family']}/{r['kind']}"]) if "kind" in r and "share" in r and f"{r['family']}/{r['kind']}" in overrides else r
                 for r in block["positive"]]
        terrain = {**terrain, f"exposure_at_{STAGE}": {**block, "positive": rules}}
    report["final"] = rule_caps(terrain)
    return terrain, report


def draft(source_dir: Path, run_dir: Path, iteration: int, mesh_dir: Path, out: Path, *, profile: str = "e2_easy10_beam_edge",
          promotion: dict | None = None, adjust_from: Path | None = None, keep_mesh: bool = False,
          bake_caps_run: Path | None = None, bake_boundaries: int = 0, kind_caps: dict | None = None) -> dict:
    source_dir, out = Path(source_dir).resolve(strict=True), Path(out).absolute()
    if out.exists():
        raise FileExistsError(f"{out} exists (a draft folder is never reused)")
    plan = yaml.safe_load((source_dir / "ex42-prep.yaml").read_text(encoding="utf-8-sig"))
    approvals = yaml.safe_load((source_dir / "ex42-approvals.yaml").read_text(encoding="utf-8-sig"))
    old_plan_sha = _sha(source_dir / "ex42-prep.yaml")
    if profile in plan["training_mesh_profiles"] and not keep_mesh:
        raise ValueError(f"profile {profile} already exists in the plan")
    row = next(r for r in plan["stages"] if r["id"] == STAGE)
    pin = parent_pin(row, run_dir, iteration)
    row["parent"] = pin
    moved = []
    if not keep_mesh:       # keep_mesh: the same weights on the plan's own mesh (the way back when the new mesh or rule fails its first-update check)
        moved = [r["id"] for r in plan["stages"] if r.get("training_mesh_profile") == OLD_PROFILE]
        if not moved:
            raise ValueError(f"no stage names {OLD_PROFILE}")
        plan["training_mesh_profiles"][profile] = mesh_profile(mesh_dir)
        for r in plan["stages"]:
            if r.get("training_mesh_profile") == OLD_PROFILE:
                r["training_mesh_profile"] = profile
    caps_report = None
    if bake_caps_run is not None or kind_caps:
        row["terrain"], caps_report = set_kind_caps(row["terrain"], bake_caps_run, bake_boundaries, kind_caps)
    if promotion is not None:
        plan["terrain_promotion"] = promotion
    plan.pop("materialization", None)
    cell = approvals[f"stage_{STAGE.lower()}_authorization"]
    cell["scope"]["parent_sha256"] = pin["sha256"]
    approval_bytes = _dump(approvals)
    plan["stage_zero"]["approval_sha256"] = hashlib.sha256(approval_bytes).hexdigest()
    plan_bytes = _dump(plan)
    out.mkdir(parents=True)
    for path in source_dir.rglob("*"):
        rel = path.relative_to(source_dir)
        if path.is_file() and "provenance" not in rel.parts and ".git" not in rel.parts and path.name not in ("transition.json", "ex42-prep.yaml", "ex42-approvals.yaml"):
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, out / rel)
    (out / "ex42-prep.yaml").write_bytes(plan_bytes)
    (out / "ex42-approvals.yaml").write_bytes(approval_bytes)
    record = {"format": REENTRY_FORMAT, "stage": STAGE, "source_dir": str(source_dir), "source_plan_sha256": old_plan_sha,
              "new_plan_sha256": hashlib.sha256(plan_bytes).hexdigest(), "approval_sha256": plan["stage_zero"]["approval_sha256"],
              "parent": pin, "run_dir": str(Path(run_dir).resolve()), "mesh_profile": None if keep_mesh else profile, "mesh_stages": moved, "keep_mesh": keep_mesh,
              "terrain_promotion": promotion, "kind_caps": caps_report, "training_started": False}
    if adjust_from is not None:
        # the live (per update) adjustment file binds the plan sha256: the same decisions, re-bound to the new plan. Nothing is added or decided here.
        adjust = json.loads(Path(adjust_from).read_text(encoding="utf-8-sig"))
        if adjust.get("schema") != "ex42-update-adjust/1" or adjust.get("stage_id") != STAGE:
            raise ValueError("--adjust-from is not an E2 ex42-update-adjust/1 file")
        adjust["plan_sha256"] = record["new_plan_sha256"]
        (out / "e2-update-adjust.json").write_text(json.dumps(adjust, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        record["update_adjust"] = {"from": str(Path(adjust_from).resolve()), "old_plan_sha256": old_plan_sha}
    (out / "reentry.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return record


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source-dir", type=Path, required=True)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--iteration", type=int, required=True)
    p.add_argument("--mesh-dir", type=Path, required=True, help="ignored with --keep-mesh (but must exist)")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--profile", default="e2_easy10_beam_edge")
    p.add_argument("--keep-mesh", action="store_true", help="do not change the mesh pin (rollback draft: same weights, old mesh)")
    p.add_argument("--no-promotion", action="store_true", help="leave the level-up rule as it is (no terrain_promotion cell)")
    p.add_argument("--x-fraction", type=float, default=0.5)
    p.add_argument("--adjust-from", type=Path, help="an e2 ex42-update-adjust/1 file to copy with the new plan sha256")
    p.add_argument("--kinds", nargs="*", default=DEFAULT_KINDS)
    p.add_argument("--bake-caps-run", type=Path, help="a run whose kind level caps after --bake-boundaries boundaries become the new plan's start caps")
    p.add_argument("--bake-boundaries", type=int, default=0)
    p.add_argument("--kind-cap", action="append", default=[], metavar="FAMILY/KIND=N", help="lower one kind's level cap (repeatable)")
    a = p.parse_args(argv)
    caps = {k: int(v) for k, v in (item.split("=", 1) for item in a.kind_cap)}
    cell = None if a.no_promotion else {"x_progress_kinds": a.kinds, "x_progress_fraction": a.x_fraction, "forward_only": True}
    print(json.dumps(draft(a.source_dir, a.run_dir, a.iteration, a.mesh_dir, a.out, profile=a.profile, promotion=cell,
                                          adjust_from=a.adjust_from, keep_mesh=a.keep_mesh,
                                          bake_caps_run=a.bake_caps_run, bake_boundaries=a.bake_boundaries, kind_caps=caps or None), indent=1))


if __name__ == "__main__":
    main()
