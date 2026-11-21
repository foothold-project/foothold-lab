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
  * kind shares (optional, lead 11/20 18:08): --add-kind <family/kind>=<cap> opens a new single-kind row at share 0 (the second door, C/box) and
                          --kind-share <family/kind>=<value> (repeatable) sets the share of single kinds. The sum of the single-kind shares must
                          stay what the source plan had (the 0.44 bundle), so a share freed by one kind (a graduated kind goes to 0.03) has to be
                          named on another in the same call; otherwise the draft is refused and nothing is written. The sum is checked against the bundle total 0.44
                          itself (not only against the source), and a single-kind row at share 0 is refused;
  * the E2 exit judge (optional, lead 11/20 18:08 (B), reviewer 18:25): --exit-judge <adapter> sets stages[E2].exit_judge, the E3 row's entry_gate_adapter (the gate that
                          leaves E2) and the approvals file's stage_e3_authorization.later_stage_entry_gate_adapter, which the repo keeps equal to it (stage_e2's cell is the
                          gate INTO E2 and is not touched). A gate swap needs a ledger line: --ledger-pin <json> {commit, path, line, line_text, line_sha256, decision_id}
                          is checked like the cap handoff approval (commit is an ancestor of the published ledger ref, the line is in the ledger at that commit, its sha
                          matches) and the line has to carry EXIT_JUDGE_LINE_TAG, the decision id and the adapter name. mapgain_two_boundary_e2 = graduation by map gain in two boundaries;
  * the approval cell's scope.parent_sha256 and the plan's stage_zero.approval_sha256 (the approvals file bytes changed).
  * --parent-from-source (lead 11/21 20:24, rx2pz: a new E2-stage OUT from the canonical lower 3 = E1F m250): the source row's own parent pin is kept
                          (it must name another stage, E1F); --run-dir is that parent's run and --iteration its local update, and the file must have the
                          pinned sha256. The training entry then reads the run as a first E2 (previous stage E1F), as the first E2 did;
  * --no-flags (same order, "깃발 env 0"): stages[E2].shares.flag -> 0 and the free command slots scaled by 1 / (1 - flag) (the sum stays 1).
The `materialization` declaration and transition.json are NOT carried over: they describe E1F -> E2 with a gate receipt, and a plan
that still carried them would be re-derived from that gate (validate_materialized_transition) and refused. The draft writes its own
`reentry.json` (what was changed, the old and new plan sha256, the parent pin) instead. Nothing here starts training.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

import yaml

OLD_PROFILE = "e2_easy10_edge"
FILES = ("terrain_mesh.npz", "mesh_manifest.json", "terrain_manifest.json")
STAGE = "E2"
DEFAULT_KINDS = ["A/gaps", "B/gap", "C/gap", "B/beam", "A/balance_beams", "B/pallets", "A/stepping_beams",
                 "A/stepping_stones_low", "A/stepping_stones_high", "B/stones"]
REENTRY_FORMAT = "foothold-ex42-e2-reentry/1"
BUNDLE_TOTAL = 0.44      # the sparse bundle share of every E2..E4 start (test_ex42_stage_exposure_cpu SPARSE)
EXIT_JUDGE_LINE_TAG = "[E2 졸업 관문 교체 승인 줄 · exit_judge]"


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


def source_parent_pin(source_row: dict, run_dir: Path, iteration: int) -> dict:
    """--parent-from-source: keep the source row's parent pin (another stage's checkpoint, the canonical E1F m250), after checking that
    run_dir/model_<iteration>.pt is that file (manifest inventory and sha256)."""
    pin = dict(source_row.get("parent") or {})
    if pin.get("source_stage_id") in (None, STAGE):
        raise ValueError("--parent-from-source needs a source row whose parent is another stage (the first E2 plan, parent E1F)")
    if pin.get("manifest_local_update") != iteration or pin.get("checkpoint_key") != f"model_{iteration}.pt":
        raise ValueError(f"--parent-from-source: the source parent is {pin.get('checkpoint_key')}, not model_{iteration}.pt")
    run_dir = Path(run_dir).resolve(strict=True)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    key = pin["checkpoint_key"]
    if key not in (manifest.get("checkpoints") or {}):
        raise ValueError(f"the run manifest has not published {key}")
    sha = _sha(run_dir / key)
    if sha != pin.get("sha256"):
        raise ValueError(f"{run_dir / key} sha256 {sha[:12]} is not the source parent pin {str(pin.get('sha256'))[:12]}")
    return pin


def drop_flag_share(shares: dict) -> tuple[dict, dict]:
    """--no-flags: the flag slot to 0 and the free slots scaled so the command shares still add up to 1."""
    flag = float(shares.get("flag", 0.0))
    if not 0.0 < flag < 1.0:
        raise ValueError(f"--no-flags: the source flag share is {flag} (nothing to take out)")
    out = {k: (0.0 if k == "flag" else round(float(v) / (1.0 - flag), 10)) for k, v in shares.items()}
    total = sum(out.values())
    if abs(total - 1.0) > 1e-8:
        raise ValueError(f"--no-flags: the scaled shares add up to {total}")
    return out, {"flag_before": flag, "before": dict(shares), "after": out}


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


def rule_shares(terrain: dict) -> dict:
    """{family/kind: share} of the single-kind share rules of the stage's start block."""
    rules = (terrain.get(f"exposure_at_{STAGE}") or {}).get("positive") or []
    return {f"{r['family']}/{r['kind']}": float(r["share"]) for r in rules if "kind" in r and "share" in r}


def set_kind_shares(terrain: dict, shares: dict | None, add: dict | None, drop: list | None = None, shrink: bool = False) -> tuple[dict, dict]:
    """(terrain, report). `add` {family/kind: level_cap} appends single-kind rows at share 0; `shares` {family/kind: value} sets shares.
    `drop` [family/kind] takes the rows out of the plan (a share-0 row is refused, so a kind that is to get no envs has no row; the freed share goes to the
    weight rules, the continuous columns, by the exposure rule: they take 1 - sum(share)). The sum must then equal the bundle total minus the dropped shares.
    The sum of the single-kind shares must equal the sum before (the bundle total), to 1e-6. Raises before anything is written.
    `shrink` (--shrink-to-continuous, lead 2026-11-21 13:28): the named --kind-share values may only go down, and what they give up goes to the
    continuous columns the same way a dropped row does (the sum may then be below the bundle total). Without it the rule above is unchanged."""
    block = terrain[f"exposure_at_{STAGE}"]
    rules = [dict(r) for r in block["positive"]]
    before = rule_shares(terrain)
    report = {"before": dict(before), "added": {}, "set": {}, "dropped": {}}
    for kind in (drop or []):
        if kind not in before:
            raise ValueError(f"--drop-kind {kind}: no such single-kind share row (have {sorted(before)})")
        if kind in (add or {}) or kind in (shares or {}):
            raise ValueError(f"--drop-kind {kind}: cannot also be added or given a share")
        report["dropped"][kind] = before[kind]
    rules = [r for r in rules if not ("kind" in r and "share" in r and f"{r['family']}/{r['kind']}" in report["dropped"])]
    # A source plan that already had rows dropped (a re-entry from a re-entry: sparse total 0.28, not 0.44) and gets more rows dropped keeps its own total as the base;
    # without a drop, or from a full 0.44 source, nothing changes (the bundle must still be 0.44).
    base_total = sum(before.values()) if report["dropped"] and abs(sum(before.values()) - BUNDLE_TOTAL) > 1e-6 else BUNDLE_TOTAL
    allowed_total = base_total - sum(report["dropped"].values())
    for kind, cap in (add or {}).items():
        family, _, name = kind.partition("/")
        if not family or not name or kind in before:
            raise ValueError(f"--add-kind {kind}: needs family/kind and must not be a row already (have {sorted(before)})")
        if type(cap) is not int or not 0 <= cap <= 12:
            raise ValueError(f"--add-kind {kind}={cap}: the level cap must be an integer")
        rules.append({"family": family, "kind": name, "share": 0.0, "level_cap": cap})
        report["added"][kind] = cap
    have = {f"{r['family']}/{r['kind']}" for r in rules if "kind" in r and "share" in r}
    for kind, value in (shares or {}).items():
        if kind not in have:
            raise ValueError(f"--kind-share {kind}: no such single-kind share rule (have {sorted(have)})")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 0.44:
            raise ValueError(f"--kind-share {kind}={value}: a share between 0 and 0.44")
        report["set"][kind] = value
    rules = [dict(r, share=float(shares[f"{r['family']}/{r['kind']}"])) if "kind" in r and "share" in r and f"{r['family']}/{r['kind']}" in (shares or {}) else r
             for r in rules]
    terrain = {**terrain, f"exposure_at_{STAGE}": {**block, "positive": rules}}
    after = rule_shares(terrain)
    total_after = sum(after.values())
    zero = sorted(k for k, v in after.items() if v <= 0)
    if zero:
        raise ValueError(f"single-kind rows at share 0: {zero} (give them a share with --kind-share or do not add them)")
    if shrink:
        if not shares or drop:
            raise ValueError("--shrink-to-continuous needs --kind-share values (no --drop-kind)")
        up = sorted(k for k, v in shares.items() if k in before and v > before[k] + 1e-12)
        if up:
            raise ValueError(f"--shrink-to-continuous only lowers the shares of existing rows: raised {up}")
        if add:
            # lead 2026-11-21 20:17: open new rows (D/crawl) at a small share in the same call. Their share comes from the continuous columns
            # (or from the existing rows lowered in the same call); the single-kind sum may not pass the 0.44 bundle.
            unshared = sorted(k for k in add if k not in shares)
            if unshared:
                raise ValueError(f"--shrink-to-continuous with --add-kind: give the new rows a share ({unshared})")
            if total_after > BUNDLE_TOTAL + 1e-9:
                raise ValueError(f"--shrink-to-continuous with --add-kind: the single-kind sum {total_after:.6f} passes the {BUNDLE_TOTAL} bundle")
            report["from_continuous"] = round(total_after - sum(before.values()), 9)
        elif not total_after < sum(before.values()) - 1e-9:                  # against the source's own sparse total (0.28 here), not the 0.44 bundle
            raise ValueError(f"--shrink-to-continuous only lowers shares: raised {up}, sum {total_after:.6f} vs the source's {sum(before.values()):.6f}")
        else:
            report["shrunk_to_continuous"] = round(sum(before.values()) - total_after, 9)
    elif abs(allowed_total - total_after) > 1e-6:
        raise ValueError(f"the single-kind shares add up to {total_after:.6f}, the bundle is {allowed_total:.6f}: name the receiving kind in the same call "
                         f"(before {before}, after {after})")
    report.update(after=after, total=total_after)
    return terrain, report


def check_ledger_pin(pin: dict, repo, adapter: str) -> dict:
    """The ledger line that approves swapping the E2 exit gate to `adapter` (same pin shape and rules as ex42_e1_cap_handoff._check_approval):
    the commit is an ancestor of the published ledger ref, the line text hashes to line_sha256 and is a line of the ledger at that commit, and it
    carries the tag, the decision id and the adapter name. Returns the pin."""
    import os
    import subprocess
    from foothold_s2.ex42_e1_cap_handoff import LEDGER_PATH, LEDGER_REMOTE_REF, LEDGER_REPO_ENV, _ledger_lines
    if not isinstance(pin, dict) or set(pin) != {"commit", "path", "line", "line_text", "line_sha256", "decision_id"}:
        raise ValueError("--ledger-pin needs exactly commit, path, line, line_text, line_sha256, decision_id")
    repo = repo or os.environ.get(LEDGER_REPO_ENV)
    if not repo:
        raise ValueError(f"--exit-judge needs the ledger repository ({LEDGER_REPO_ENV} or --ledger-repo)")
    if pin["path"] != LEDGER_PATH:
        raise ValueError("ledger path is not the registered decisions file")
    if subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", str(pin["commit"]), LEDGER_REMOTE_REF], capture_output=True, check=False).returncode != 0:
        raise ValueError(f"the ledger commit is not on {LEDGER_REMOTE_REF} (a local commit is not an approval)")
    text = pin["line_text"]
    if not isinstance(text, str) or hashlib.sha256(text.encode("utf-8")).hexdigest() != pin["line_sha256"]:
        raise ValueError("ledger line text differs from its sha256")
    lines = _ledger_lines(repo, pin["commit"], pin["path"])
    number = pin["line"]
    if type(number) is not int or not 1 <= number <= len(lines) or lines[number - 1] != text.encode("utf-8"):
        raise ValueError("the ledger line is not at the pinned line number of the ledger at that commit")
    if not pin["decision_id"] or any(n not in text for n in (EXIT_JUDGE_LINE_TAG, pin["decision_id"])):
        raise ValueError(f"the ledger line must carry {EXIT_JUDGE_LINE_TAG} and the decision id")
    # the adapter is a named field of the line (exact name, not a substring: a line that mentions the old adapter in its reason must not approve the old one)
    named = re.findall(r"어댑터 ([A-Za-z0-9_]+)", text)
    if named != [adapter]:
        raise ValueError(f"the ledger line must name exactly one adapter field ('어댑터 <name>') and it must be {adapter} (found {named})")
    ids = re.findall(r"결정 id ([A-Za-z0-9_.\-]+)", text)
    if ids != [pin["decision_id"]]:
        raise ValueError(f"the ledger line's decision id field ('결정 id <id>') must be exactly {pin['decision_id']} (found {ids})")
    return pin


def draft(source_dir: Path, run_dir: Path, iteration: int, mesh_dir: Path, out: Path, *, profile: str = "e2_easy10_beam_edge",
          promotion: dict | None = None, adjust_from: Path | None = None, keep_mesh: bool = False,
          bake_caps_run: Path | None = None, bake_boundaries: int = 0, kind_caps: dict | None = None,
          kind_shares: dict | None = None, add_kinds: dict | None = None, drop_kinds: list | None = None, shrink_to_continuous: bool = False, exit_judge: str | None = None, ledger_pin: dict | None = None, ledger_repo=None,
          parent_from_source: bool = False, no_flags: bool = False) -> dict:
    source_dir, out = Path(source_dir).resolve(strict=True), Path(out).absolute()
    if out.exists():
        raise FileExistsError(f"{out} exists (a draft folder is never reused)")
    plan = yaml.safe_load((source_dir / "ex42-prep.yaml").read_text(encoding="utf-8-sig"))
    approvals = yaml.safe_load((source_dir / "ex42-approvals.yaml").read_text(encoding="utf-8-sig"))
    old_plan_sha = _sha(source_dir / "ex42-prep.yaml")
    if profile in plan["training_mesh_profiles"] and not keep_mesh:
        raise ValueError(f"profile {profile} already exists in the plan")
    row = next(r for r in plan["stages"] if r["id"] == STAGE)
    pin = source_parent_pin(row, run_dir, iteration) if parent_from_source else parent_pin(row, run_dir, iteration)
    row["parent"] = pin
    flags_report = None
    if no_flags:
        row["shares"], flags_report = drop_flag_share(row["shares"])
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
    shares_report = None
    if kind_shares or add_kinds or drop_kinds:
        row["terrain"], shares_report = set_kind_shares(row["terrain"], kind_shares, add_kinds, drop_kinds, shrink=shrink_to_continuous)
    if promotion is not None:
        plan["terrain_promotion"] = promotion
    plan.pop("materialization", None)
    cell = approvals[f"stage_{STAGE.lower()}_authorization"]
    judge_report = None
    if exit_judge is not None:
        from foothold_s2.ex42_stage_judges import ADAPTERS
        if exit_judge not in ADAPTERS:
            raise ValueError(f"--exit-judge {exit_judge}: not a registered adapter (have {sorted(ADAPTERS)})")
        check_ledger_pin(ledger_pin, ledger_repo, exit_judge)
        nxt = next(r for r in plan["stages"] if r["id"] == "E3")
        gate_cell = approvals["stage_e3_authorization"]          # the gate that leaves E2 is the E3 row's entry gate and E3's approval cell, kept equal by the repo tests
        judge_report = {"E2.exit_judge": [row.get("exit_judge"), exit_judge],
                        "E3.entry_gate_adapter": [nxt["authorization_contract"]["entry_gate_adapter"], exit_judge],
                        "approvals.stage_e3.later_stage_entry_gate_adapter": [gate_cell.get("later_stage_entry_gate_adapter"), exit_judge],
                        "ledger_pin": ledger_pin}
        row["exit_judge"] = nxt["authorization_contract"]["entry_gate_adapter"] = gate_cell["later_stage_entry_gate_adapter"] = exit_judge
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
              "terrain_promotion": promotion, "kind_caps": caps_report, "kind_shares": shares_report, "exit_judge": judge_report,
              "parent_from_source": parent_from_source, "command_shares": flags_report, "training_started": False}
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
    p.add_argument("--x-fall-down", action="store_true", help="terrain_promotion x_fall_down: a fall short of the x fraction steps the env down (needs a copy with that rule)")
    p.add_argument("--adjust-from", type=Path, help="an e2 ex42-update-adjust/1 file to copy with the new plan sha256")
    p.add_argument("--kinds", nargs="*", default=DEFAULT_KINDS)
    p.add_argument("--bake-caps-run", type=Path, help="a run whose kind level caps after --bake-boundaries boundaries become the new plan's start caps")
    p.add_argument("--bake-boundaries", type=int, default=0)
    p.add_argument("--kind-cap", action="append", default=[], metavar="FAMILY/KIND=N", help="lower one kind's level cap (repeatable)")
    p.add_argument("--kind-share", action="append", default=[], metavar="FAMILY/KIND=VALUE", help="set one single kind's share (repeatable); the sum must stay the bundle total")
    p.add_argument("--add-kind", action="append", default=[], metavar="FAMILY/KIND=CAP", help="add a single-kind row at share 0 with this level cap (the second door C/box=4); give it a share with --kind-share")
    p.add_argument("--drop-kind", action="append", default=[], metavar="FAMILY/KIND", help="take a single-kind row out of the plan (repeatable); its share goes to the continuous columns and the bundle total falls by it")
    p.add_argument("--shrink-to-continuous", action="store_true", help="with --kind-share: lower those shares and give the rest to the continuous columns (the sum may fall below the bundle total)")
    p.add_argument("--exit-judge", default=None, help="E2 stage exit adapter for the new OUT (and the E3 entry gate that names it), e.g. mapgain_two_boundary_e2")
    p.add_argument("--ledger-pin", type=Path, help="json file with the ledger line that approves the --exit-judge swap (required with it)")
    p.add_argument("--ledger-repo", type=Path, help="the ledger checkout (default: EX42_LEDGER_REPO)")
    p.add_argument("--parent-from-source", action="store_true", help="keep the source row's parent pin (another stage, E1F m250); --run-dir / --iteration name that file")
    p.add_argument("--no-flags", action="store_true", help="stages[E2].shares.flag -> 0, the free slots scaled to add up to 1")
    a = p.parse_args(argv)
    caps = {k: int(v) for k, v in (item.split("=", 1) for item in a.kind_cap)}
    shares = {k: float(v) for k, v in (item.split("=", 1) for item in a.kind_share)}
    adds = {k: int(v) for k, v in (item.split("=", 1) for item in a.add_kind)}
    cell = None if a.no_promotion else {"x_progress_kinds": a.kinds, "x_progress_fraction": a.x_fraction, "forward_only": True, **({"x_fall_down": True} if a.x_fall_down else {})}
    print(json.dumps(draft(a.source_dir, a.run_dir, a.iteration, a.mesh_dir, a.out, profile=a.profile, promotion=cell,
                                          adjust_from=a.adjust_from, keep_mesh=a.keep_mesh,
                                          bake_caps_run=a.bake_caps_run, bake_boundaries=a.bake_boundaries, kind_caps=caps or None,
                                          kind_shares=shares or None, add_kinds=adds or None, drop_kinds=a.drop_kind or None, shrink_to_continuous=a.shrink_to_continuous, exit_judge=a.exit_judge,
                                          ledger_pin=json.loads(a.ledger_pin.read_text(encoding="utf-8")) if a.ledger_pin else None, ledger_repo=a.ledger_repo,
                                          parent_from_source=a.parent_from_source, no_flags=a.no_flags), indent=1))


if __name__ == "__main__":
    main()
