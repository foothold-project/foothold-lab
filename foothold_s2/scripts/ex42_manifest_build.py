"""CPU assembler for receipts produced by queued EX-42 Kit family probes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.curriculum.ex42_manifest import assemble_manifest


def _read_json(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON receipt must contain an object: {path}")
    return value


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, action="append", required=True)
    parser.add_argument("--aggregate-measurements", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan = EX42Plan.load(args.table)
    receipts = [_read_json(path) for path in args.receipt]
    aggregate = _read_json(args.aggregate_measurements) if args.aggregate_measurements else None
    manifest = assemble_manifest(plan, receipts, aggregate_measurements=aggregate)
    _write_json(args.output, manifest)
    summary = {
        "state": manifest["status"],
        "family_counts_observed": manifest["family_counts_observed"],
        "family_counts_expected": manifest["family_counts_expected"],
        "receipt_ids": manifest["receipt_ids"],
        "output": str(args.output),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if manifest["status"] == "measured" else 2


if __name__ == "__main__":
    raise SystemExit(main())
