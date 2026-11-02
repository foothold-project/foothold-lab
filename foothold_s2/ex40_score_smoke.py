"""Lead-only EX-40 score evaluator Kit smoke with the completed v5 model_14."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from foothold_s2.ex40_eval_once import evaluate
from foothold_s2.ex40_score import sha256


def check(out: Path, checkpoint: Path) -> dict:
    receipt = json.loads((out / "eval_receipt.json").read_text(encoding="utf-8-sig"))
    row = json.loads((out / "map64/map_modes.json").read_text(encoding="utf-8-sig"))
    stand = json.loads((out / "stand_eval_gt/stand.json").read_text(encoding="utf-8-sig"))
    if (receipt.get("state") != "done" or not receipt.get("smoke")
            or set(receipt.get("steps", {})) != {"map64", "stand_eval_gt"}
            or any(step["rc"] != 0 for step in receipt["steps"].values())
            or row.get("checkpoint_sha256") != sha256(checkpoint)
            or stand.get("checkpoint_sha256") != sha256(checkpoint)
            or row.get("envs") != 64 or stand.get("envs") != 64
            or set(row.get("modes", {})) != {"eval_gt"}
            or set(row["modes"]["eval_gt"]) != {"fwd0.5"}
            or len(row["modes"]["eval_gt"]["fwd0.5"].get("per_env", [])) != 64
            or len(stand.get("per_env", [])) != 64
            or sha256(out / "stand_eval_gt/stand_raw.npz") != stand.get("raw_sha256")):
        raise ValueError("EX-40 64-env score smoke missing or mismatched")
    return {"state": "PASS", "checkpoint_sha256": sha256(checkpoint),
            "map64": str(out / "map64/map_modes.json"),
            "stand": str(out / "stand_eval_gt/stand.json"),
            "evaluation_seconds": receipt["elapsed_seconds"]}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--verify-only", action="store_true")
    args = p.parse_args(argv)
    args.checkpoint = args.checkpoint.resolve()
    args.out = args.out.resolve()
    if args.checkpoint.name != "model_14.pt":
        p.error("the first score smoke uses the completed v5 model_14.pt")
    if not args.verify_only:
        result = evaluate(args.checkpoint, args.out, stage="B0", arm="B", smoke=True)
        if result["state"] != "done":
            print(json.dumps(result, ensure_ascii=False))
            return 5
    result = check(args.out, args.checkpoint)
    (args.out / "smoke_check.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
