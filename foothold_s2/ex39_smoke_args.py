"""EX-39 Kit smoke argv boundary, checked before the training child starts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPECTED = {"--smoke-updates": "2", "--basic-stage": "smoke", "--max_iterations": "3004"}


def check_args(argv: list[str]) -> dict:
    observed = {}
    for flag, expected in EXPECTED.items():
        if argv.count(flag) != 1:
            raise ValueError(f"EX-39 smoke launch needs exactly one {flag}")
        pos = argv.index(flag) + 1
        if pos >= len(argv) or argv[pos] != expected:
            raise ValueError(f"EX-39 smoke launch has {flag}={argv[pos] if pos < len(argv) else None!r}, expected {expected!r}")
        observed[flag] = argv[pos]
    return {"state": "PASS", "expected": EXPECTED, "observed": observed}


def check_file(path: Path) -> dict:
    return check_args(path.read_text(encoding="utf-8-sig").splitlines())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("args_file", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(check_file(args.args_file), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
