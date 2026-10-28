"""One W15 evaluation unit for a saved basic-gait checkpoint.

This module only runs when the operator starts the approved W28 GPU queue.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from foothold_s2.basic_gait_kit import KIT_CACHE_ARG
from foothold_s2.eval.map_mode_cells import commands, SEQUENCES


MODES = ("eval_gt", "eval_pred", "probe_prop_only")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(out: Path, checkpoint: Path, expected_iter: int) -> dict:
    row = json.loads((out / "map64" / "map_modes.json").read_text(encoding="utf-8"))
    if row.get("checkpoint_iter") != expected_iter or row.get("checkpoint_sha256") != sha256_file(checkpoint):
        raise ValueError("checkpoint identity mismatch")
    if row.get("command_suite") != "extended" or set(row.get("commands", {})) != set(commands("extended")):
        raise ValueError("W15 command suite incomplete")
    if set(row.get("modes", {})) != set(MODES) or set(row.get("sequences", {})) != set(MODES):
        raise ValueError("W15 map modes or sequences incomplete")
    if len(row.get("terrain_tiles", [])) != 64:
        raise ValueError("W15 terrain receipt must contain 64 envs")
    for mode in MODES:
        if set(row["modes"][mode]) != set(commands("extended")) or set(row["sequences"][mode]) != set(SEQUENCES):
            raise ValueError("W15 command or reversal receipt incomplete")
        log = (out / f"turn16_{mode}" / "run.log").read_text(encoding="utf-8", errors="replace")
        if "TURNPROBE_DONE" not in log:
            raise ValueError("turn16 completion marker missing")
    rc_lines = (out / "rc.txt").read_text(encoding="utf-8", errors="replace").splitlines()
    expected = {f"turn16_{mode} rc=0" for mode in MODES} | {"map64 rc=0"}
    if not expected <= set(rc_lines):
        raise ValueError("evaluation child rc missing or nonzero")
    return {"checkpoint": str(checkpoint), "checkpoint_sha256": row["checkpoint_sha256"],
            "checkpoint_iter": expected_iter, "modes": list(MODES),
            "commands": sorted(commands("extended")), "sequences": sorted(SEQUENCES),
            "terrain_tiles": len(row.get("terrain_tiles", [])), "source_sha256": row.get("source_sha256")}


def run(device: str, checkpoint: Path, expected_iter: int, out: Path) -> dict:
    if device not in ("cuda:0", "cuda:1") or not checkpoint.is_file() or out.exists():
        raise ValueError("invalid device, missing checkpoint, or existing output")
    before = sha256_file(checkpoint)
    root = Path(__file__).resolve().parents[1]
    shell = Path(os.environ.get("BASIC_GAIT_BASH", "C:/Program Files/Git/bin/bash.exe"))
    if not shell.is_file():
        raise FileNotFoundError(shell)
    env = os.environ.copy()
    env["MODES"] = " ".join(MODES)
    env["COMMAND_SUITE"] = "extended"
    env["PYTHONUTF8"] = "1"
    env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    env["BASIC_GAIT_KIT_ARG"] = KIT_CACHE_ARG
    child = subprocess.run([str(shell), str(root / "foothold_s2/eval/run_sb_eval.sh"), device,
                            str(checkpoint), str(out)], cwd=root, env=env, check=False)
    if child.returncode != 0 or sha256_file(checkpoint) != before:
        raise RuntimeError("evaluation failed or checkpoint changed during evaluation")
    result = verify(out, checkpoint, expected_iter)
    (out / "w15_verified.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cuda:0", "cuda:1"), required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--expected-iter", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    a = parser.parse_args(argv)
    result = verify(a.out, a.checkpoint, a.expected_iter) if a.verify_only else run(a.device, a.checkpoint, a.expected_iter, a.out)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
