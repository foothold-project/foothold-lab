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
import traceback
from pathlib import Path

import numpy as np

TICKS, ENVS, HIGH = 200, 64, np.array([1.0, 0.5, 1.0])      # 명령은 [-HIGH, HIGH] 균등 (하위 범위 안 · 가정)


def command_sequence(ticks: int, n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).uniform(-1.0, 1.0, (ticks, n, 3)) * HIGH


def run(args) -> Path:
    from foothold_s2.nav import room_generator as rg
    from foothold_s2.tasks.nav_env_cfg import build_nav_env

    from foothold_s2.lab_compat import require_declared_major

    require_declared_major()                           # FOOTHOLD_LAB_MAJOR 없으면 거절 (쿼터니언 순서가 조용히 틀리는 것을 막음)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.camera_probe:
        return run_camera_probe(args, out)
    if args.env_diff:
        return run_env_diff(args, out)
    target = out / f"{args.map_mode}.npz"
    if target.exists():
        raise FileExistsError(f"{target} exists (never overwritten)")
    _spec, room = rg.make_room(args.room_seed)
    manifest = rg.write_room(room, out / f"room_{args.room_seed}", n_starts=args.envs, start_seed=args.room_seed)
    mesh = out / f"room_{args.room_seed}" / "terrain_mesh.npz"
    env, summary = build_nav_env(checkpoint=args.lower_checkpoint, expected_sha256=args.lower_sha256, room_mesh_npz=mesh,
                                 room_mesh_sha256=manifest["mesh_sha256"], num_envs=args.envs, device=args.device, seed=args.seed,
                                 map_mode=args.map_mode)
    report_physics(env, out)
    if not args.no_obs_probe:                       # 3.0 이식 확인: 관측 45 칸의 뜻 (쿼터니언 순서 포함). 틀려도 본 확인은 계속 돌고 결과만 파일로 남긴다
        from foothold_s2.nav import lower_obs_probe

        probe = lower_obs_probe.kit_probe(env)
        with open(out / f"obs_probe_{args.map_mode}.json", "w", encoding="utf-8") as stream:
            json.dump(probe, stream, ensure_ascii=False, indent=2)
        print("OBS_PROBE", json.dumps(probe, ensure_ascii=False), flush=True)
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


def report_physics(env, out: Path) -> dict:
    """PhysX 가 아니면 (newton 등) 예외로 시작하지 않는다 (팀장 11/17: 3.0 도 PhysX). 아니면 PHYSICS_BACKEND 줄과 physics_backend.json 을 남긴다."""
    from foothold_s2.lab_compat import require_physx

    rep = require_physx(env.raw)
    with open(out / "physics_backend.json", "w", encoding="utf-8") as stream:
        json.dump(rep, stream, ensure_ascii=False, indent=2)
    print("PHYSICS_BACKEND", json.dumps(rep, ensure_ascii=False), flush=True)
    return rep


def run_env_diff(args, out: Path) -> Path:
    """OPS v0.2 5.1 절 환경 차이 확인: 평지 방 하나 · 명령 다섯 칸 · 6 초 · env 32. 같은 판에서 정본 3 가 걷는 RGB 영상과 35 도 깊이 npz 를 저장 (VIDEO_CASE 칸)."""
    from foothold_s2.nav import env_diff, hl_student
    from foothold_s2.nav import room_generator as rg
    from foothold_s2.tasks.nav_env_cfg import build_nav_env

    room = rg.build_room(env_diff.flat_room_spec(args.room_seed))
    manifest = rg.write_room(room, out / f"room_flat_{args.room_seed}", n_starts=args.envs, start_seed=args.room_seed)
    mesh = out / f"room_flat_{args.room_seed}" / "terrain_mesh.npz"

    def extra(env_cfg):
        if not args.no_depth:
            env_cfg.scene.depth_camera = hl_student.depth_camera_cfg()
        if not args.no_rgb:
            env_cfg.scene.rgb_camera = env_diff.rgb_camera_cfg()
    env, _summary = build_nav_env(checkpoint=args.lower_checkpoint, expected_sha256=args.lower_sha256, room_mesh_npz=mesh,
                                  room_mesh_sha256=manifest["mesh_sha256"], num_envs=args.envs, device=args.device, seed=args.seed,
                                  map_mode=args.map_mode, extra_scene=extra)
    phys = report_physics(env, out)
    rec = env_diff.Recorder(env.raw, rgb=not args.no_rgb, depth=not args.no_depth)
    result = env_diff.run_cases(env, on_tick=rec)
    res = {"physics": phys, "cases": result, "verdict": env_diff.verdict(result), "recorded": rec.save(out), "envs": args.envs, "seed": args.seed, "room_seed": args.room_seed,
           "lower_sha256": args.lower_sha256, "note": "평지 · 6 초 · 상위 틱 0.1 s · 성공 식은 env_diff.py 머리 글 참조 (OPS v0.2 원문 미확인)"}
    path = out / "env_diff.json"
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(res, stream, ensure_ascii=False, indent=2)
    print("ENV_DIFF", json.dumps({k: v for k, v in res.items() if k != "recorded"}, ensure_ascii=False), flush=True)
    print("ENV_DIFF_RECORDED", json.dumps(res["recorded"], ensure_ascii=False), flush=True)
    return path


def run_camera_probe(args, out: Path) -> Path:
    """깊이 카메라 방향 확인 (따로 한 번): 카메라를 단 환경으로 중심 화소 깊이 대 계산한 지면 거리. 결과 camera_probe.json."""
    from foothold_s2.nav import hl_student, lower_obs_probe
    from foothold_s2.nav import room_generator as rg
    from foothold_s2.tasks.nav_env_cfg import build_nav_env

    _spec, room = rg.make_room(args.room_seed)
    manifest = rg.write_room(room, out / f"room_{args.room_seed}", n_starts=args.envs, start_seed=args.room_seed)
    mesh = out / f"room_{args.room_seed}" / "terrain_mesh.npz"

    def extra(env_cfg):
        env_cfg.scene.depth_camera = hl_student.depth_camera_cfg()
    env, _summary = build_nav_env(checkpoint=args.lower_checkpoint, expected_sha256=args.lower_sha256, room_mesh_npz=mesh,
                                  room_mesh_sha256=manifest["mesh_sha256"], num_envs=args.envs, device=args.device, seed=args.seed,
                                  map_mode=args.map_mode, extra_scene=extra)
    from foothold_s2.lab_compat import th

    report_physics(env, out)
    raw = env.raw
    origins = th(raw.scene.env_origins).detach().cpu().numpy()
    res = lower_obs_probe.kit_camera_probe(env, lambda: raw.scene["depth_camera"].data.output["distance_to_image_plane"], lambda i: float(origins[i, 2]))
    path = out / "camera_probe.json"
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(res, stream, ensure_ascii=False, indent=2)
    print("CAMERA_PROBE", json.dumps(res, ensure_ascii=False), flush=True)
    return path


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
    r.add_argument("--no-obs-probe", action="store_true")
    r.add_argument("--camera-probe", action="store_true", help="깊이 카메라 방향만 확인하고 끝낸다 (camera_probe.json · npz 안 씀)")
    r.add_argument("--env-diff", action="store_true", help="평지에서 명령 다섯 칸 (OPS v0.2 5.1) + 걷는 RGB 영상 · 35 도 깊이 저장 (env_diff.json · npz 안 씀)")
    r.add_argument("--no-rgb", action="store_true"); r.add_argument("--no-depth", action="store_true")
    c = sub.add_parser("compare")
    c.add_argument("--out", required=True)
    a, _unknown = p.parse_known_args(argv)
    if a.cmd == "compare":
        print(json.dumps(compare(a.out), ensure_ascii=False, indent=2))
        return 0
    from isaaclab.app import AppLauncher

    app = AppLauncher(headless=True, device=a.device, enable_cameras=bool(getattr(a, "env_diff", False) and not a.no_rgb)).app
    return guarded_run(a, app)


def guarded_run(a, app, runner=None) -> int:
    """Isaac 의 app.close() 는 프로세스를 바로 끝내 예외 Traceback 이 사라지고 종료 코드도 0 이다 (11/17 05:06 결과 파일 없이 rc 0).
    그래서 닫기 전에 Traceback 을 stderr 와 `<out>/<map_mode>.FAILED.txt` 에 먼저 남긴다."""
    rc = 0
    try:
        print((runner or run)(a), flush=True)
    except BaseException:
        text = traceback.format_exc()
        print(text, file=sys.stderr, flush=True)
        try:
            Path(a.out).mkdir(parents=True, exist_ok=True)
            (Path(a.out) / f"{a.map_mode}.FAILED.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
        rc = 1
    finally:
        app.close()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
