"""Draft of the plan pin for a candidate training mesh (B/beam splice): a NEW file, ex42-prep.yaml is never written.

    python -m foothold_s2.tools.ex42_beam_pin_draft --mesh-dir <folder> --out <draft plan yaml> [--profile e2_easy10_beam_edge]

The draft adds one training_mesh_profiles entry (directory, geometry sha256 and the three file sha256 of the folder) and points every stage that
named the old profile (e2_easy10_edge) at it. Nothing else in the plan changes, so the plan sha256 differs by exactly these lines.
The draft is then checked with the same reader a launch uses (EX42Plan.load, pinned_stage_mesh on every stage that has the profile).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OLD_PROFILE = "e2_easy10_edge"
FILES = ("terrain_mesh.npz", "mesh_manifest.json", "terrain_manifest.json")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def profile_block(mesh_dir: Path, name: str, note: str) -> str:
    mesh_dir = Path(mesh_dir).resolve(strict=True)
    geometry = json.loads((mesh_dir / "mesh_manifest.json").read_text(encoding="utf-8-sig"))["mesh_sha256"]
    lines = [f"  # {note}", f"  {name}:", f"    directory: {mesh_dir}", f"    geometry_sha256: {geometry}", "    files:"]
    lines += [f"      {f}: {_sha(mesh_dir / f)}" for f in FILES]
    return "\n".join(lines) + "\n"


def draft(table_text: str, mesh_dir: Path, name: str, note: str) -> str:
    if re.search(rf"^  {re.escape(name)}:\s*$", table_text, re.M):
        raise ValueError(f"profile {name} already exists in the plan")
    head = re.search(rf"^  {OLD_PROFILE}:\s*$", table_text, re.M)
    end = re.search(r"^environment:\s*$", table_text, re.M)
    if head is None or end is None or end.start() < head.start():
        raise ValueError(f"plan has no {OLD_PROFILE} profile followed by `environment:`")
    stages = len(re.findall(rf"^  training_mesh_profile: {OLD_PROFILE}\s*$", table_text, re.M))
    if not stages:
        raise ValueError(f"no stage names {OLD_PROFILE}")
    out = table_text[:end.start()] + profile_block(mesh_dir, name, note) + table_text[end.start():]
    return re.sub(rf"^(  training_mesh_profile: ){OLD_PROFILE}(\s*)$", rf"\g<1>{name}\g<2>", out, flags=re.M)


def check(path: Path, name: str) -> dict:
    """The launch-side reader on the draft: loads the plan and verifies the profile (files, sha, flags) for every stage that uses it."""
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_stage_mesh import pinned_stage_mesh
    plan = EX42Plan.load(path)
    stage_ids = [row["id"] for row in plan.document["stages"] if row.get("training_mesh_profile") == name]
    receipts = {sid: pinned_stage_mesh(plan.document, sid) for sid in stage_ids}
    return {"plan_sha256": plan.sha256, "stages": stage_ids, "geometry_sha256": next(iter(receipts.values()))["geometry_sha256"],
            "flag_cells": next(iter(receipts.values()))["flag_cells"]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--table", type=Path, default=REPO / "foothold_s2/curriculum/ex42-prep.yaml")
    p.add_argument("--mesh-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--profile", default="e2_easy10_beam_edge")
    p.add_argument("--note", default="e2_easy10_edge with the B/beam rows 0..9 replaced (ex42_beam_splice_mesh: short beam, level-scaled tilt). DRAFT: not in the plan until lead pins it.")
    a = p.parse_args(argv)
    if a.out.resolve() == a.table.resolve():
        raise SystemExit("refusing to overwrite the plan table")
    if a.out.exists():
        raise SystemExit(f"{a.out} exists")
    text = draft(a.table.read_text(encoding="utf-8"), a.mesh_dir, a.profile, a.note)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    for sibling in a.table.parent.glob("*.yaml"):           # EX42Plan.load reads the files that sit next to the plan (ex41-fixed5000.yaml, ...)
        target = a.out.parent / sibling.name
        if sibling.resolve() != a.table.resolve() and not target.exists():
            target.write_bytes(sibling.read_bytes())
    a.out.write_text(text, encoding="utf-8")
    print(json.dumps({"draft": str(a.out), "draft_file_sha256": _sha(a.out), **check(a.out, a.profile)}, indent=1))


if __name__ == "__main__":
    main()
