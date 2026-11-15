"""Generate one W28 P1 evaluation job per 250-update basic-gait checkpoint.

This command writes proposed specs only. It never registers jobs or starts GPU work.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PYTHON = "C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe"


def iterations(kind: str) -> tuple[int, ...]:
    if kind == "parent":
        return tuple(range(1750, 3001, 250))
    if kind == "scratch":
        return tuple(range(250, 1501, 250))
    raise ValueError("kind must be parent or scratch")


def spec(kind: str, iteration: int, run_dir: Path, out_root: Path,
         gpu: int, uuid: str, authorization_ref: str) -> dict:
    if iteration not in iterations(kind) or gpu not in (0, 1) or not uuid.startswith("GPU-"):
        raise ValueError("checkpoint, GPU, or UUID outside proposed pair")
    if not authorization_ref or authorization_ref.startswith("PENDING"):
        raise ValueError("approval reference required before registration")
    root = Path(__file__).resolve().parents[1]
    checkpoint = (run_dir / f"model_{iteration}.pt").resolve()
    out = (out_root / kind / f"m{iteration}").resolve()
    argv = [PYTHON, "-m", "foothold_s2.basic_gait_eval_once", "--device", f"cuda:{gpu}",
            "--checkpoint", str(checkpoint), "--expected-iter", str(iteration), "--out", str(out)]
    job = {"id": f"basic-gait-{kind}-m{iteration}-w15", "kind": "judge", "priority": 1,
           "gpu": gpu, "gpu_uuid": uuid, "owner": "lead", "authorization_ref": authorization_ref,
           "output": str(out_root.resolve()), "cwd": str(root), "argv": argv,
           "ready_file": str(checkpoint),
           "units": [{"id": "w15-extended", "args": [],
                      "verify_argv": argv + ["--verify-only"]}]}
    module_dir = root / "_out/tools/gpu_jobs"
    sys.path.insert(0, str(module_dir))
    try:
        from queue_w28 import validate

        validate(job)
    finally:
        sys.path.remove(str(module_dir))
    return job


def write_specs(kind: str, run_dir: Path, out_root: Path, spec_dir: Path,
                gpu: int, uuid: str, authorization_ref: str) -> list[Path]:
    if spec_dir.exists():
        raise FileExistsError(spec_dir)
    jobs = [spec(kind, it, run_dir, out_root, gpu, uuid, authorization_ref)
            for it in iterations(kind)]
    spec_dir.mkdir(parents=True)
    files = []
    for row in jobs:
        path = spec_dir / (row["id"] + ".json")
        path.write_text(json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        files.append(path)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("parent", "scratch"))
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--spec-dir", type=Path, required=True)
    parser.add_argument("--gpu", type=int, choices=(0, 1), required=True)
    parser.add_argument("--gpu-uuid", required=True)
    parser.add_argument("--authorization-ref", required=True)
    a = parser.parse_args(argv)
    for path in write_specs(a.kind, a.run_dir, a.out_root, a.spec_dir,
                            a.gpu, a.gpu_uuid, a.authorization_ref):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
