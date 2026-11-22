"""HiPAN 모드 2 teacher PPO 실행기 (설계 §3 N3). `--print` = 시작 영수증만 찍고 끝 · 없이 부르면 학습 루프 (`nav/hl_train.py`).

영수증: 하위 저장본 sha · 방 메시 sha (room_manifest.json) · plan sha · 하위 b 값 · 관측 차원 대조 · PPO 설정 (가정 이름 표시) · 저장 간격 · 이어 받기 경로.
학습 루프: `--env-factory 모듈:함수` 가 (NavEnv, NavTask) 를 돌려준다 (Kit 기동은 그 함수 몫 · N1 Kit 확인 뒤). 없으면 · `--out-dir` 가 없으면 · `--iterations` 가 없으면 거절 (조용히 다른 길로 가지 않음).
영수증은 out-dir 에 먼저 써 두고 (덮어쓰지 않음) 그 sha256 이 체크포인트에 들어간다: 이어 받기는 같은 영수증 · 같은 PPO 설정일 때만. 저장 50 회마다 `model_<회>.pt`. 실제 학습은 팀장 승인 뒤 lead 가 띄운다.
쓰는 법: python -m foothold_s2.scripts.train_nav_teacher --print --lower-checkpoint <pt> --lower-sha256 <sha> --room-manifest <json> --plan <yaml> --vx-corr-b 0.009
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

FORMAT = "foothold-hipan-teacher-start-receipt/1"


def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ppo_kwargs(num_envs=None, save_interval=None) -> dict:
    return {**({"num_envs": int(num_envs)} if num_envs else {}), **({"save_interval": int(save_interval)} if save_interval else {})}


def identity_text(receipt: dict) -> str:
    """이어 받기 대조에 쓰는 글: `resume` 칸을 뺀 영수증 (하위 · 방 · plan · b · 관측 · PPO). 첫 실행과 이어 받기가 같은 글을 낸다 (reviewer 04:15)."""
    return json.dumps({k: v for k, v in receipt.items() if k != "resume"}, ensure_ascii=False, indent=2, sort_keys=True)


def build_receipt(*, lower_checkpoint, lower_sha256, room_manifests, plan, vx_corr_b, resume=None, num_envs=None, save_interval=None, resume_levels=None) -> dict:
    from foothold_s2.nav import hl_ppo_cfg as cfg
    from foothold_s2.nav.teacher_obs import TeacherObsLayout

    ckpt = Path(lower_checkpoint).resolve(strict=True)
    digest = _sha(ckpt)
    if digest != str(lower_sha256).lower():
        raise ValueError(f"lower checkpoint sha256 {digest[:8]} differs from the registered {str(lower_sha256)[:8]}")
    rooms = []
    for path in room_manifests:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
        if manifest.get("format") not in ("hipan-room/1", "hipan-rooms/1") or not isinstance(manifest.get("mesh_sha256"), str):
            raise ValueError(f"{path} is not a hipan room manifest")
        rooms.append({"manifest": str(Path(path).resolve()), "manifest_sha256": _sha(path), "mesh_sha256": manifest["mesh_sha256"]})
    if not rooms:
        raise ValueError("at least one room manifest is required")
    plan_path = Path(plan).resolve(strict=True)
    ppo = cfg.TeacherPPO(**ppo_kwargs(num_envs, save_interval))
    layout = TeacherObsLayout()
    encoder = cfg.build_encoder(ppo, layout)
    import torch
    probe = encoder(torch.zeros(2, layout.total))                       # 관측 차원 대조: 인코더가 layout 전체를 받아 latent 로 나온다
    if tuple(probe.shape) != (2, ppo.latent):
        raise ValueError(f"encoder output {tuple(probe.shape)} is not (2, {ppo.latent})")
    resume_row = None
    if resume:
        resume_path = Path(resume).resolve(strict=True)
        resume_row = {"path": str(resume_path), "sha256": _sha(resume_path), **({"levels": str(resume_levels)} if resume_levels else {})}     # 칸 levels 는 켰을 때만 (끄면 옛 영수증과 같다)
    from foothold_s2.runners.start_runner import VX_CORR_RAMP, vx_corr_params
    on, b_applied, band = vx_corr_params()               # lead 11/22 10:36: the correction the lower policy actually applies (environment)
    if not on or float(vx_corr_b) != float(b_applied):
        raise ValueError(f"--vx-corr-b {vx_corr_b} is not what the lower policy applies (on={on} b={b_applied}): set EX42_PERCEPTION_VX_CORR_B "
                         f"to the lower run's value, or pass that value")
    return {"format": FORMAT, "lower": {"checkpoint": str(ckpt), "sha256": digest},
            "lower_vx_corr_applied": {"on": bool(on), "b": float(b_applied), "band": float(band), "ramp": float(VX_CORR_RAMP)},
            "rooms": rooms, "plan": {"path": str(plan_path), "sha256": _sha(plan_path)}, "lower_vx_corr_b": float(vx_corr_b),
            "observation": {"total": layout.total, "sizes": layout.sizes, "latent": ppo.latent},
            "ppo": ppo.as_dict(), "assumed_ppo_fields": list(cfg.ASSUMED), "action_dim": cfg.ACTION_DIM,
            "save_interval": ppo.save_interval, "resume": resume_row, "lower_map_mode": "eval_gt", "training_started": False}


def _register_stack_dump() -> None:
    """Pod 는 ptrace 가 막혀 py-spy dump 가 안 된다: `kill -USR1 <학습 python PID>` 로 모든 스레드의 파이썬 스택을 stderr (= train.log) 에 찍는다 (G3 Pod 느림 조사 · lead 00:51)."""
    import faulthandler
    import signal

    if hasattr(signal, "SIGUSR1"):
        try:
            faulthandler.register(signal.SIGUSR1, all_threads=True, chain=False)
        except (OSError, ValueError, AttributeError):          # stderr 가 파일 서술자가 없는 곳 (pytest 가로채기 등): 스택 덤프만 못 쓴다
            pass


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--print", dest="dry", action="store_true", help="print the start receipt and exit (the only mode so far)")
    p.add_argument("--lower-checkpoint", required=True)
    p.add_argument("--lower-sha256", required=True)
    p.add_argument("--room-manifest", action="append", required=True, help="room_manifest.json of each training room (repeat)")
    p.add_argument("--plan", required=True)
    p.add_argument("--vx-corr-b", type=float, required=True)
    p.add_argument("--resume", default=None)
    p.add_argument("--num-envs", type=int, default=None)
    p.add_argument("--save-interval", type=int, default=None, help="default 50 (design); a different value is part of the PPO identity")
    p.add_argument("--env-factory", default=None, help="module:function returning (NavEnv, NavTask) for the real loop")
    p.add_argument("--out-dir", default=None)
    p.add_argument("--iterations", type=int, default=None)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--noise-std-min", type=float, default=None, help="policy std floor (default off; env HIPAN_NOISE_STD_MIN when the flag is absent). Not part of the PPO identity: a resume may change it")
    p.add_argument("--resume-levels", default=None, help="with --resume: carry the PGCL level distribution over (default off = every env restarts at level 1; env HIPAN_RESUME_LEVELS when the flag is absent). 'checkpoint' = the state saved in the checkpoint, or 1:0.4,2:0.1,3:0.5 = level:fraction")
    p.add_argument("--receipt-out", default=None, help="also write the receipt here (never overwritten)")
    a = p.parse_args(argv)
    a.resume_levels = a.resume_levels or os.environ.get("HIPAN_RESUME_LEVELS") or None
    if a.resume_levels and not a.resume:
        raise SystemExit("refused: --resume-levels (or HIPAN_RESUME_LEVELS) needs --resume")
    if not a.dry:
        _register_stack_dump()
    if not a.dry and not (a.env_factory and a.out_dir and a.iterations):
        print("refused: training needs --env-factory, --out-dir and --iterations (or use --print)", file=sys.stderr)
        return 2
    receipt = build_receipt(lower_checkpoint=a.lower_checkpoint, lower_sha256=a.lower_sha256, room_manifests=a.room_manifest, plan=a.plan,
                            vx_corr_b=a.vx_corr_b, resume=a.resume, num_envs=a.num_envs, save_interval=a.save_interval, resume_levels=a.resume_levels)
    text = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True)
    if a.receipt_out:
        with open(a.receipt_out, "x", encoding="utf-8") as stream:
            stream.write(text + "\n")
    print(text)
    if a.dry:
        return 0
    import importlib
    from foothold_s2.nav import hl_ppo_cfg as cfg, hl_train

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ident = identity_text(receipt)
    rpath = out / "start_receipt.json"
    if rpath.exists():
        if rpath.read_text(encoding="utf-8").strip() != ident:
            raise SystemExit("refused: out-dir already holds a different start receipt")
    else:
        rpath.write_text(ident + "\n", encoding="utf-8")
    if a.resume:                                   # 이어 받기 기록은 영수증과 따로 덧붙인다
        with open(out / "resume_log.jsonl", "a", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt["resume"], ensure_ascii=False) + "\n")
    receipt["receipt_sha256"] = hashlib.sha256(ident.encode("utf-8")).hexdigest()
    rc = 0
    try:
        mod, _, fn = a.env_factory.partition(":")
        nav_env, task = getattr(importlib.import_module(mod), fn)()
        ppo = cfg.TeacherPPO(**ppo_kwargs(a.num_envs, a.save_interval))
        env = hl_train.TeacherVecEnv(nav_env, task, device="cuda:0" if _cuda() else "cpu")
        env.heading_selfcheck()                          # 쿼터니언 순서 · 몸 틀 속도 해석이 틀리면 여기서 멈춘다 (Pod 돈 아낌)
        floor = a.noise_std_min if a.noise_std_min is not None else (float(os.environ["HIPAN_NOISE_STD_MIN"]) if os.environ.get("HIPAN_NOISE_STD_MIN") else None)
        last, saved = hl_train.train(env, ppo, out_dir=out, iterations=a.iterations, receipt=receipt, resume=a.resume, seed=a.seed,
                                     device=env.device, noise_std_min=floor, resume_levels=a.resume_levels)
        print(json.dumps({"last_iteration": last, "saved": saved}), flush=True)
    except BaseException:
        import traceback

        text = traceback.format_exc()                   # Kit 종료 (app.close) 가 예외 Traceback 과 종료 코드를 지우므로 먼저 stderr 와 파일에 남긴다
        print(text, file=sys.stderr, flush=True)
        try:
            (out / "FAILED.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
        rc = 1
    finally:
        from foothold_s2.nav import kit_factories

        kit_factories.finish(rc)
    return rc


def _cuda() -> bool:
    import torch
    return torch.cuda.is_available()


if __name__ == "__main__":
    raise SystemExit(main())
