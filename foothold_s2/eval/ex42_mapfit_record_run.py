"""복원 지도 오프라인 가르기 기록 실행기 (설계 2.3 ㄱ): (종 · 레벨 · 시드) 칸마다 CPU 자식 하나 (한 번에 하나 · taskset · 540 초 제한) 로 TRNet 입력 · 정답을 기록한다.
쓰는 법: python -m foothold_s2.eval.ex42_mapfit_record_run --checkpoint <model_*.pt> --plan <ex42-prep.yaml> --mesh-dir <메시 폴더> --out <폴더> \\
          --cells "A/boxes:5,A/random_rough:5" --seeds 42,43,44 [--dry]
한 칸의 출력 = <out>/<종>_L<레벨>_s<시드>/mapfit.npz · 전체 요약 = <out>/record_manifest.json (체크포인트 sha256 · 칸별 상태 · 초). 학습 · 평가 코드는 안 바뀐다."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

TASK = "FootholdS2-Go2-S2-SB-v0"


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def build_argv(a, folder: Path, kind: str, level: int, seed: int) -> list[str]:
    family, name = kind.split("/", 1)
    return ["--ex42-evaluation-plan", a.plan, "--task", TASK, "--checkpoint", a.checkpoint, "--envs", str(a.envs), "--steps", str(a.steps),
            "--modes", "eval_gt", "--command-suite", "core", "--commands", a.commands, "--fixed-terrain", "--fixed-level", str(level),
            "--mesh-dir", a.mesh_dir, "--ex42-kind-family", family, "--ex42-kind-name", name, "--eval-seed", str(seed),
            "--out", str(folder), "--device", "cpu", "--headless"]


def parse_cells(text: str) -> list[tuple[str, int]]:
    out = []
    for item in text.split(","):
        kind, _, level = item.strip().rpartition(":")
        if "/" not in kind or not level.isdigit():
            raise ValueError(f"cell must look like family/kind:level, got {item!r}")
        out.append((kind, int(level)))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--checkpoint", required=True); p.add_argument("--plan", required=True); p.add_argument("--mesh-dir", required=True); p.add_argument("--out", required=True)
    p.add_argument("--cells", default="A/boxes:5,A/random_rough:5"); p.add_argument("--seeds", default="42,43,44")
    p.add_argument("--envs", type=int, default=32); p.add_argument("--steps", type=int, default=600); p.add_argument("--commands", default="fwd0.5")
    p.add_argument("--copy", default=os.getcwd()); p.add_argument("--python", default=sys.executable)
    p.add_argument("--cpus", default="0-3"); p.add_argument("--timeout", type=int, default=540); p.add_argument("--dry", action="store_true")
    a = p.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    seeds = [int(s) for s in a.seeds.split(",")]
    manifest = {"checkpoint": a.checkpoint, "checkpoint_sha256": None if a.dry else sha256_file(a.checkpoint), "plan": a.plan, "mesh_dir": a.mesh_dir,
                "envs": a.envs, "steps": a.steps, "commands": a.commands, "cells": []}
    for kind, level in parse_cells(a.cells):
        for seed in seeds:
            name = f"{kind.replace('/', '_')}_L{level}_s{seed}"
            folder = out / name
            row = {"name": name, "kind": kind, "level": level, "seed": seed}
            if (folder / "mapfit.npz").is_file():
                row["status"] = "reused"; manifest["cells"].append(row); continue
            folder.mkdir(parents=True, exist_ok=True)
            env = dict(os.environ, CUDA_VISIBLE_DEVICES="", PYTHONDONTWRITEBYTECODE="1", MAPFIT_OUT=str(folder / "mapfit.npz"))
            cmd = ["taskset", "-c", a.cpus, "timeout", "-s", "KILL", str(a.timeout), a.python, "-B", "-m", "foothold_s2.eval.ex42_mapfit_record_child",
                   *build_argv(a, folder, kind, level, seed)]
            if a.dry:
                print("DRY", " ".join(cmd)); row["status"] = "dry"; manifest["cells"].append(row); continue
            t0 = time.time()
            with open(folder / "stdout.log", "wb") as so, open(folder / "stderr.log", "wb") as se:
                r = subprocess.run(cmd, stdout=so, stderr=se, stdin=subprocess.DEVNULL, env=env, cwd=a.copy)
            row.update(rc=r.returncode, seconds=int(time.time() - t0), status="ok" if (folder / "mapfit.npz").is_file() else "missing")
            print(f"child {name} rc={r.returncode} {row['seconds']}s {row['status']}", flush=True)
            manifest["cells"].append(row)
            (out / "record_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    (out / "record_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
