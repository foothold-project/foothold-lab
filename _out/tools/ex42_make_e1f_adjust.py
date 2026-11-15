"""Write the E1F start adjust file (policy_std_cap) bound to stage E1F and the plan sha, and read it back with the training reader.

The file is handed to the segment by EX42_UPDATE_ADJUST (the launcher passes it through). It is read at update 1 only.
  python _out/tools/ex42_make_e1f_adjust.py --plan <E1F plan> --out <file> [--std-cap 0.48] --decided-by <who> --evidence <text>
"""
import argparse
import json
import sys
from pathlib import Path

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.ex42_live_adjust import limits_from_plan, read_request


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--std-cap", type=float, default=0.48)
    ap.add_argument("--decided-by", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--decided-at", required=True)
    a = ap.parse_args(argv)
    plan = EX42Plan.load(a.plan)
    row = next(s for s in plan.document["stages"] if s["id"] == "E1F")
    limits = limits_from_plan(row["live_adjustment"])
    doc = {"schema": "ex42-update-adjust/1", "stage_id": "E1F", "plan_sha256": plan.sha256,
           "changes": {"1": {"decided_by": a.decided_by, "decided_at": a.decided_at, "evidence": a.evidence,
                             "runtime": {"policy_std_cap": a.std_cap}}}}
    raw = json.dumps(doc, indent=1, sort_keys=True).encode()
    read_request(raw, stage_id="E1F", plan_sha256=plan.sha256, iteration=1, limits=limits)
    out = Path(a.out)
    if out.exists():
        print(f"refused: {out} exists", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    print(json.dumps({"file": str(out), "plan_sha256": plan.sha256, "std_cap": a.std_cap}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
