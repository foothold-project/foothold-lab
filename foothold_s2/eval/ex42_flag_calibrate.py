"""CPU-only five-repeat width for the E1F flag cells; never starts Isaac."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml

from foothold_s2.eval.ex42_flag_cells import summarize_repeats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--repeat-root", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv=None) -> dict:
    args = build_parser().parse_args(argv)
    if len(args.repeat_root) != 5 or args.out.exists():
        raise ValueError("E1F flag calibration needs five roots and a fresh output")
    raw_plan = args.plan.read_bytes()
    plan = yaml.safe_load(raw_plan.decode("utf-8-sig"))
    checkpoint_sha = hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
    result = summarize_repeats(args.repeat_root, plan=plan,
                               plan_sha256=hashlib.sha256(raw_plan).hexdigest(),
                               checkpoint_sha256=checkpoint_sha)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                        encoding="utf-8")
    return result


if __name__ == "__main__":
    main()
