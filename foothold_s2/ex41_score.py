"""Add the numeric EX-41 maintenance contract to an evaluator score draft."""
from __future__ import annotations

import argparse

from foothold_s2.scripts.ex41_startup import enrich_score_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score-draft", required=True)
    parser.add_argument("--map-modes", required=True)
    parser.add_argument("--table", default="foothold_s2/curriculum/ex41-fixed5000.yaml")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = enrich_score_file(args.score_draft, args.map_modes, args.table, args.out)
    print(f"EX41_MAINTENANCE_SCORE {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
