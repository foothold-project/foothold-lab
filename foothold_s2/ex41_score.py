"""Add the numeric EX-41 maintenance contract to an evaluator score draft."""
from __future__ import annotations

import argparse

from foothold_s2.scripts.ex41_startup import enrich_score_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score-draft", required=True)
    parser.add_argument("--map-modes", required=True)
    parser.add_argument("--stand-eval-gt", required=True)
    parser.add_argument("--stand-probe-prop-only", required=True)
    parser.add_argument("--stand-eval-pred", required=True)
    parser.add_argument("--table", default="foothold_s2/curriculum/ex41-fixed5000.yaml")
    parser.add_argument("--out", required=True)
    parser.add_argument("--w86-metrics", required=True,
                        help="same-run foothold_s2/rewards/ex41_w86.jsonl")
    args = parser.parse_args(argv)
    stand_paths = {
        "eval_gt": args.stand_eval_gt,
        "probe_prop_only": args.stand_probe_prop_only,
        "eval_pred": args.stand_eval_pred,
    }
    out = enrich_score_file(args.score_draft, args.map_modes, stand_paths,
                            args.table, args.out, args.w86_metrics)
    print(f"EX41_MAINTENANCE_SCORE {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
