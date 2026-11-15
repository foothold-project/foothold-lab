"""Next-run W15 evaluation chain with a first-attempt command gate.

No work starts at import. The operator supplies completed checkpoints and an unused
output root; this module never touches the currently running v2 chain.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from foothold_s2.basic_gait_eval_once import MODES, run as run_once
from foothold_s2.eval.map_mode_cells import commands


EXPECTED_COMMANDS = 13


def source_head(root: Path) -> str:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                          capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "foothold_s2"], cwd=root,
                           capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        raise ValueError("evaluation code changed outside pinned commit")
    return head


def command_gate(map_path: Path, configured_count: int = EXPECTED_COMMANDS) -> dict:
    expected = set(commands("extended"))
    if configured_count != EXPECTED_COMMANDS or len(expected) != configured_count:
        raise ValueError("configured W15 command count differs from source suite")
    row = json.loads(map_path.read_text(encoding="utf-8"))
    top = set(row.get("commands", {}))
    modes = {name: set((row.get("modes") or {}).get(name, {})) for name in MODES}
    if top != expected or any(actual != expected for actual in modes.values()):
        raise ValueError("first map_modes.json lacks configured commands: " +
                         json.dumps({"top": len(top), "modes": {k: len(v) for k, v in modes.items()},
                                     "expected": configured_count}, sort_keys=True))
    return {"map_modes_path": str(map_path.resolve()), "commands": configured_count,
            "modes": list(MODES)}


def write_status(path: Path, row: dict) -> None:
    if row.get("done") and (not row.get("output_path") or not Path(row["output_path"]).exists()):
        raise ValueError("done requires output_path")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def run_chain(device: str, checkpoints: list[Path], out: Path) -> dict:
    if device not in ("cuda:0", "cuda:1") or not checkpoints or out.exists():
        raise ValueError("device, checkpoints or unused output root invalid")
    source = Path(__file__).resolve().parents[1]
    head = source_head(source)
    if len(commands("extended")) != EXPECTED_COMMANDS:
        raise ValueError("W15 source command count changed")
    out.mkdir(parents=True)
    status_path = out / "chain_status.json"
    row = {"state": "running", "source_commit": head,
           "configured_commands": EXPECTED_COMMANDS, "started": time.time(),
           "first_evidence": None, "done": None, "output_path": None, "attempts": []}
    write_status(status_path, row)
    for index, checkpoint in enumerate(checkpoints):
        if not checkpoint.is_file() or not checkpoint.stem.startswith("model_"):
            row.update(state="hold", reason="checkpoint_missing_or_wrong_name")
            write_status(status_path, row)
            break
        iteration = int(checkpoint.stem.removeprefix("model_"))
        attempt = out / f"m{iteration}" / f"attempt_{time.time_ns()}"
        attempt.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = run_once(device, checkpoint, iteration, attempt)
            if not (attempt / "w15_verified.json").is_file():
                raise ValueError("verified output artifact missing")
            if source_head(source) != head:
                raise ValueError("evaluation source commit changed during chain")
            map_path = attempt / "map64" / "map_modes.json"
            if index == 0:
                row["first_evidence"] = command_gate(map_path)
            if result.get("commands") is None or len(result["commands"]) != EXPECTED_COMMANDS:
                raise ValueError("verified evaluation command count differs")
            row["attempts"].append({"checkpoint": str(checkpoint), "output_path": str(attempt),
                                    "verified_commands": len(result["commands"])})
            row["output_path"] = str(attempt)
            write_status(status_path, row)
        except Exception as exc:
            map_path = attempt / "map64" / "map_modes.json"
            if index == 0 and map_path.is_file():
                row["first_evidence"] = {"map_modes_path": str(map_path), "gate": "failed"}
                try:
                    command_gate(map_path)
                except ValueError as gate_exc:
                    exc = gate_exc
            row.update(state="hold", reason=f"{type(exc).__name__}: {exc}")
            write_status(status_path, row)
            print("W50 HOLD " + row["reason"], file=sys.stderr, flush=True)
            break
    else:
        row.update(state="done", done=time.time())
        write_status(status_path, row)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cuda:0", "cuda:1"), required=True)
    parser.add_argument("--checkpoint", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    row = run_chain(args.device, args.checkpoint, args.out)
    print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return 0 if row["state"] == "done" else 4


if __name__ == "__main__":
    raise SystemExit(main())
