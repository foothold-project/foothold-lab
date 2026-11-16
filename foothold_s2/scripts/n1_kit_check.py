"""N1 Kit 확인 (설계 §3.1 · 팀장 11/16 결정 3): 방 하나 · 같은 무작위 명령 열로 정답 지도 (eval_gt) 와 복원 지도 (eval_pred) 를 한 번씩 굴려 추종 오차 95 분위를 비교한다.
Kit 는 한 프로세스에 환경 하나라 모드마다 따로 부른다: `run --map-mode eval_gt` · `run --map-mode eval_pred` · `compare`. GPU 평가라 승인 불필요 (학습 아님).
`run`: 방 메시를 쓰고 (`--room-seed`) NavEnv 를 만들어 `--ticks` 상위 틱 (기본 200) 을 같은 시드 명령으로 돌리고 `<out>/<map_mode>.npz` 를 쓴다 (덮어쓰지 않음).
`compare`: 두 npz 의 명령 sha 가 같은지 보고 `n1_check.compare_maps` 결과를 `<out>/n1_check.json` 에 쓴다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

TICKS, ENVS, HIGH = 200, 64, np.array([1.0, 0.5, 1.0])      # 명령은 [-HIGH, HIGH] 균등 (하위 범위 안 · 가정)


def command_sequence(ticks: int, n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).uniform(-1.0, 1.0, (ticks, n, 3)) * HIGH


def run(args) -> Path:
    from foothold_s2.nav import room_generator as rg
    from foothold_s2.tasks.nav_env_cfg import build_nav_env

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{args.map_mode}.npz"
    if target.exists():
        raise FileExistsError(f"{target} exists (never overwritten)")
    _spec, room = rg.make_room(args.room_seed)
    manifest = rg.write_room(room, out / f"room_{args.room_seed}", n_starts=args.envs, start_seed=args.room_seed)
    mesh = out / f"room_{args.room_seed}" / "terrain_mesh.npz"
    env, summary = build_nav_env(checkpoint=args.lower_checkpoint, expected_sha256=args.lower_sha256, room_mesh_npz=mesh,
                                 room_mesh_sha256=manifest["mesh_sha256"], num_envs=args.envs, device=args.device, seed=args.seed,
                                 map_mode=args.map_mode)
    cmds = command_sequence(args.ticks, args.envs, args.seed)
    env.reset()
    errs, dsteps, touts = [], [], []
    for t in range(args.ticks):
        s = env.step(cmds[t])
        errs.append(s.track_err); dsteps.append(s.done_step); touts.append(s.timed_out)
    np.savez_compressed(target, track_err=np.stack(errs), done_step=np.stack(dsteps), timed_out=np.stack(touts),
                        commands_sha256=hashlib.sha256(cmds.tobytes()).hexdigest(), map_mode=args.map_mode,
                        summary=json.dumps(summary, default=str))
    return target


def compare(out) -> dict:
    from foothold_s2.nav import n1_check

    d = {m: np.load(Path(out) / f"{m}.npz") for m in ("eval_gt", "eval_pred")}
    if str(d["eval_gt"]["commands_sha256"]) != str(d["eval_pred"]["commands_sha256"]):
        raise ValueError("the two runs used different command sequences")
    p = {m: n1_check.p95(d[m]["track_err"], d[m]["done_step"]) for m in d}
    f = {m: n1_check.fall_counts(d[m]["done_step"], d[m]["timed_out"]) for m in d}
    result = n1_check.compare_maps(p["eval_gt"], p["eval_pred"], commands_sha256=str(d["eval_gt"]["commands_sha256"]),
                                   falls_gt=f["eval_gt"], falls_pred=f["eval_pred"])
    path = Path(out) / "n1_check.json"
    with open(path, "x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    return result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--map-mode", choices=("eval_gt", "eval_pred"), required=True)
    r.add_argument("--lower-checkpoint", required=True)
    r.add_argument("--lower-sha256", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--room-seed", type=int, default=0)
    r.add_argument("--envs", type=int, default=ENVS)
    r.add_argument("--ticks", type=int, default=TICKS)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--device", default="cuda:0")
    c = sub.add_parser("compare")
    c.add_argument("--out", required=True)
    a, _unknown = p.parse_known_args(argv)
    if a.cmd == "compare":
        print(json.dumps(compare(a.out), ensure_ascii=False, indent=2))
        return 0
    from isaaclab.app import AppLauncher

    app = AppLauncher(headless=True, device=a.device).app
    try:
        print(run(a))
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
