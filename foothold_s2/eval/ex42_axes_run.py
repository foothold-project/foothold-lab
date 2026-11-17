"""EX-42 새 학습 축 실행기: 저장본 하나 -> CPU 자식 (차례로 하나씩) -> 한 줄 표 (설계 DESIGN-E2E5-LEARNING-AXES-1117 v0.1).
자식 1 (가-1 · 가-2): 평탄 L0 느린 걸음 탐침 (planner run_est_f.sh 와 같은 인자) · 자식 2 (가-3 + 다): 연속 지형 한 열 · 자식 3.. (나 + 다): 그 단계가 연 종 (checkpoint 의 노출 영수증) 가운데 n 개.
학습 코드 · 평가기는 안 바꾼다. CPU 만 (CUDA_VISIBLE_DEVICES 비움) · taskset 코어 제한 · 자식마다 시간 제한 (멈추면 시드를 바꿔 한 번 더 · 그래도 안 되면 값 없음).
쓰는 법 (set -a; . ~/mai/foothold-linux.env; set +a 뒤 isaac311 python):
  python -B -m foothold_s2.eval.ex42_axes_run --checkpoint <run>/model_50.pt --plan <materialized_E2>/ex42-prep.yaml --stage E2 --mesh-dir <E2 mesh> --out <폴더> [--only flat,cont,kinds] [--dry]"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from foothold_s2.eval import ex42_axes as ax

TASK = "FootholdS2-Go2-S2-SB-v0"
FLAT_CASES = "0.1/0;0/0.2;0/-0.2;0.3/0;0.1/0"            # run_est_f.sh 와 같은 칸 순서 (planner)
FLAT_CMDS = "fwd0.1,fwd0.2,side+0.2,side-0.2,side+0.4"
KEEP_SLOTS = (("fwd0.1", 4), ("side+0.2", 1), ("side-0.2", 2), ("fwd0.3", 3))   # line50.py 와 같은 칸 번호 (정답 | 복원 = n | n+5)
PLANNER_PLAN = "/home/jay/mai/tmp/lead/E1_v28_20261114_131028/eval_policy/ex42-prep.yaml"
PLANNER_MESH = "/home/jay/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333"
KIND_STEPS = 600                                          # 12 초 (정책 dt 0.02 가정: 실제 dt 는 npz 에서 읽음)
CONT_STEPS = 300                                          # 6 초
MODES = ("eval_gt", "eval_pred")


def build_flat(a, out: Path, seed: int) -> list[str]:
    return ["--ex42-evaluation-plan", a.flat_plan, "--task", TASK, "--checkpoint", a.checkpoint, "--envs", "32", "--steps", "300",
            "--modes", ",".join(MODES), "--fixed-terrain", "--fixed-level", "0", "--eval-seed", str(seed), "--command-suite", "e1_v2",
            "--commands", FLAT_CMDS, "--mesh-dir", a.flat_mesh, "--out", str(out), "--device", "cpu", "--headless"]


def build_kind(a, out: Path, seed: int, kind: str, level: int, steps: int, yaw0: bool, envs: int = 32) -> list[str]:
    family, name = kind.split("/", 1)
    return ["--task", TASK, "--checkpoint", a.checkpoint, "--envs", str(envs), "--steps", str(steps), "--modes", ",".join(MODES),
            "--command-suite", "core", "--commands", "fwd0.5", "--fixed-terrain", "--fixed-level", str(level), "--mesh-dir", a.mesh_dir,
            "--ex42-kind-family", family, "--ex42-kind-name", name, "--eval-seed", str(seed), "--out", str(out), "--device", "cpu", "--headless",
            *(["--start-yaw-zero"] if yaw0 else [])]


def run_child(a, name: str, argv: list[str], cases: str, out: Path, seed: int) -> dict:
    """자식 하나. 시간 제한을 넘기거나 비정상 종료면 시드를 바꿔 한 번 더 (설계 4-5). 돌려주는 값: 상태 · 초 · 쓴 시드."""
    rec = {"name": name, "attempts": []}
    done = out / name
    if a.reuse and (done / "map_modes.json").is_file() and (done / "extra_1.npz").is_file():
        return {"name": name, "folder": str(done), "reused": True, "attempts": []}
    for attempt, s in enumerate((seed, seed + 1)):
        folder = out / (name if attempt == 0 else f"{name}_s{s}")
        folder.mkdir(parents=True, exist_ok=True)
        full = [("--eval-seed" if x == "--eval-seed" else x) for x in argv]
        full[full.index("--eval-seed") + 1] = str(s)
        full[full.index("--out") + 1] = str(folder)
        env = dict(os.environ, CUDA_VISIBLE_DEVICES="", PYTHONDONTWRITEBYTECODE="1", PROBE_CASES=cases, PROBE_EXTRA=str(folder / "extra"))
        cmd = ["taskset", "-c", a.cpus, "timeout", "-s", "KILL", str(a.timeout), a.python, "-B", "-m", "foothold_s2.eval.ex42_axes_child", *full]
        t0 = time.time()
        if a.dry:
            print("DRY", " ".join(cmd)); rec["attempts"].append({"seed": s, "dry": True}); return rec
        with open(folder / "stdout.log", "wb") as so, open(folder / "stderr.log", "wb") as se:
            r = subprocess.run(cmd, stdout=so, stderr=se, stdin=subprocess.DEVNULL, env=env, cwd=a.copy)
        secs = int(time.time() - t0)
        have = (folder / "map_modes.json").is_file() and (folder / "extra_1.npz").is_file()
        rec["attempts"].append({"seed": s, "rc": r.returncode, "seconds": secs, "folder": str(folder), "ok": have})
        print(f"child {name} seed {s} rc={r.returncode} {secs}s ok={have}", flush=True)
        if have:
            rec["folder"], rec["seed"] = str(folder), s
            return rec
    rec["folder"] = None
    return rec


# ---------------------------------------------------------------- 읽기
def _npz(folder: str, name: str) -> dict:
    with np.load(Path(folder) / name, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


SLOPE_SLOTS = ((0, 0), (4, 0), (1, 1), (2, 1))           # 옛 판 (참고 칸 전용): 앞 0.1 두 칸 + 옆 +-0.2 를 섞어 환경 평균으로 맞춤. 판정에 쓰지 않는다
FWD01_SLOT = 4                                            # 앞 0.1 칸 번호 (line50.py 와 같음 · 정답 n | 복원 n + 5)


def read_flat(folder: str) -> dict:
    keep = {}
    for name, n in KEEP_SLOTS:
        cell = {}
        for mode, idx in (("gt", n), ("pred", n + 5)):
            z = _npz(folder, f"extra_{idx}.npz")
            cell[mode] = ax.keep_cell(z["true"], z["command"])
        keep[name] = cell
    slope = {}
    ref = {}
    for mode, off in (("gt", 0), ("pred", 5)):
        ts, es = [], []                                    # 판정 칸: 앞 0.1 (x 만) 한 칸 · 25 step 창 평균 점
        for n in (FWD01_SLOT,):                            # 칸 0 은 정답 쪽이 1 step 짜리 껍데기 (복원 쪽 칸 5 는 301 step) 라 둘 다 못 쓴다 · 정답 | 복원 같은 칸 (4 | 9)
            z = _npz(folder, f"extra_{n + off}.npz")
            c = np.asarray(z["command"], dtype=np.float64)
            if abs(c[0] - 0.1) > 1e-6 or abs(c[1]) > 1e-6:
                raise ValueError(f"slot {n + off} is not the forward 0.1 command: {c.tolist()}")
            ts.append(z["true"][..., 0]); es.append(z["est"][..., 16])
        slope[mode] = ax.slope_windows(ts, es)
        old_t, old_e = [], []
        for n, axis in SLOPE_SLOTS:
            z = _npz(folder, f"extra_{n + off}.npz")
            old_t.append(z["true"][..., axis]); old_e.append(z["est"][..., 16 + axis])
        ref[mode] = ax.slope_fit(old_t, old_e)
    slope["ref"] = ref
    return {"keep": keep, "slope": slope}


def read_kind_cell(folder: str, mode_index: int, mode: str, anchor, settle_s: float, *, continuous: bool) -> dict:
    arr = _npz(folder, f"env_arrays_{mode}_fwd0.5.npz")
    ex = _npz(folder, f"extra_{mode_index}.npz")
    envs = int(arr["alive"].shape[1])
    counts = ax.continuous_counts(arr, envs=envs) if continuous else ax.kind_counts(arr, anchor, settle_s=settle_s, envs=envs)
    alive = arr["alive"].astype(bool)
    holes = ex.get("holes")
    if holes is not None:
        n = alive.shape[0]
        counts["hole_rows_vs_steps"] = [int(holes.shape[0]), int(n)]
        try:
            counts.update(ax.hole_summary(holes[:n], alive) if holes.shape[0] >= n else {"hole_error": "fewer hole rows than steps"})
            rough = ex.get("holes_rough")
            if rough is not None and rough.shape[0] >= n and np.isfinite(rough[:n]).any():      # U-Net 앞 rough 지도의 같은 칸 (구조 대 U-Net 가름용)
                counts["rough"] = ax.hole_summary(rough[:n], alive)
        except ValueError as err:                                  # 옛 판 (구멍 6 열) 로 저장된 자식을 --reuse 로 읽은 경우: 값 없음으로 두고 이유를 남김
            counts["hole_error"] = str(err)
    e = arr.get("map_err_inrange_mean_cm")
    if e is not None:
        counts["err_mean_cm"] = float(np.nanmean(e)) if np.isfinite(e).any() else None
        counts["err_p90_cm"] = ax.percentile_or_none(e, 0.9)
    return counts


def pick_kinds(opened: dict[str, int], it: int, n: int, interval: int = 50) -> dict[str, int]:
    """열린 종 가운데 이 저장본에서 잴 n 개: 종 이름 순으로 놓고 저장본 번호 (it/interval) 마다 n 개씩 돌려 가며 (설계 5 절 · 종이 n 보다 많은 단계용)."""
    names = sorted(opened)
    if not names or n <= 0:
        return {}
    n = min(n, len(names))
    start = ((max(it, interval) // interval - 1) * n) % len(names)
    chosen = [names[(start + i) % len(names)] for i in range(n)]
    return {k: opened[k] for k in chosen}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--checkpoint", required=True); p.add_argument("--plan", required=True); p.add_argument("--stage", required=True)
    p.add_argument("--mesh-dir", required=True, help="종 칸용 (그 단계의 mesh)"); p.add_argument("--out", required=True)
    p.add_argument("--flat-plan", default=PLANNER_PLAN); p.add_argument("--flat-mesh", default=PLANNER_MESH)
    p.add_argument("--copy", default=os.getcwd()); p.add_argument("--python", default=sys.executable)
    p.add_argument("--cpus", default="0-3"); p.add_argument("--timeout", type=int, default=540); p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n-kinds", type=int, default=2); p.add_argument("--continuous-kind", default="A/random_rough")
    p.add_argument("--kind-steps", type=int, default=KIND_STEPS); p.add_argument("--kind-envs", type=int, default=32)
    p.add_argument("--only", default="flat,cont,kinds")
    p.add_argument("--reuse", action="store_true", help="이미 끝난 flat · cont 자식 폴더를 다시 돌리지 않고 읽는다"); p.add_argument("--dry", action="store_true")
    a = p.parse_args(argv)
    it = int(Path(a.checkpoint).stem.split("_")[-1])
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.eval.ex42_mesh_eval import preflight
    from foothold_s2.ex42_kind_stage_judge import _spec, finish_anchor, opened_kinds
    from foothold_s2.eval.ex42_kind_completion import finish_anchor_for_kind

    plan = EX42Plan.load(Path(a.plan))
    spec = _spec(plan.document)
    opened = opened_kinds(Path(a.checkpoint), stage_id=a.stage, plan_sha256=plan.sha256, plan=plan.document)
    mesh = preflight(a.mesh_dir)
    cont_kind = a.continuous_kind if a.continuous_kind in opened else sorted(opened)[0]
    cont_level = opened[cont_kind]
    todo = set(a.only.split(","))
    row: dict = {"opened_kinds": opened, "timing": {}}
    t_all = time.time()
    if "flat" in todo:
        rec = ({"folder": str(out / "flat"), "reused": True} if a.reuse and (out / "flat" / "extra_9.npz").is_file()
               else run_child(a, "flat", build_flat(a, out / "flat", a.seed), FLAT_CASES, out, a.seed))
        row["timing"]["flat"] = rec
        if rec.get("folder"):
            row.update(read_flat(rec["folder"]))
    if "cont" in todo:
        yaw0 = bool((spec["completion"].get(cont_kind) or {}).get("start_yaw_zero", cont_kind.split("/")[0] != "A" and cont_kind in spec["completion"]))
        rec = ({"folder": str(out / "cont"), "reused": True} if a.reuse and (out / "cont" / "extra_1.npz").is_file()
               else run_child(a, "cont", build_kind(a, out / "cont", a.seed, cont_kind, cont_level, CONT_STEPS, yaw0), "0.5/0;0.5/0", out, a.seed))
        row["timing"]["cont"] = rec
        if rec.get("folder"):
            cells = {m: read_kind_cell(rec["folder"], i, m, None, spec["completion_settle_s"], continuous=True) for i, m in enumerate(MODES)}
            row["continuous"] = {"kind": cont_kind, "level": cont_level, "gt": cells["eval_gt"], "pred": cells["eval_pred"]}
            row.setdefault("map", {})[cont_kind + f"@L{cont_level}"] = cells
    if "kinds" in todo:
        row["kinds"] = {}
        row.setdefault("map", {})
        for kind, level in pick_kinds(opened, it, a.n_kinds).items():
            family, name = kind.split("/", 1)
            try:                                                                 # A 종류는 메시에서 잰 끝 발판, 나머지는 계획에 등록된 규칙
                anchor = (finish_anchor_for_kind(mesh, family=family, kind=name, level=level) if family == "A"
                          else finish_anchor(mesh, family=family, kind=name, level=level, completion=spec["completion"]))
            except (KeyError, ValueError) as e:                                   # 기준선을 못 재는 종: 도달은 값 없음 (생존 · 넘어짐은 그대로 센다)
                anchor = None
                row.setdefault("anchor_missing", {})[kind] = repr(e)[:120]
            yaw0 = bool((anchor or {}).get("start_yaw_zero"))
            rec = run_child(a, "kind_" + kind.replace("/", "__"), build_kind(a, out / ("kind_" + kind.replace("/", "__")), a.seed, kind, level, a.kind_steps, yaw0, a.kind_envs),
                            "0.5/0;0.5/0", out, a.seed)
            row["timing"]["kind_" + kind] = rec
            if rec.get("folder"):
                cells = {m: read_kind_cell(rec["folder"], i, m, anchor, spec["completion_settle_s"], continuous=False) for i, m in enumerate(MODES)}
                row["kinds"][kind + f"@L{level}"] = cells
                row["map"][kind + f"@L{level}"] = cells
    row["timing"]["total_seconds"] = int(time.time() - t_all)
    if a.dry:
        return 0
    row["tool"] = ax.tool_version(a.copy)
    line = ax.write_table(out / f"axes_m{it}.json", it, row)
    print(line)
    with open(out / "axes_table.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
