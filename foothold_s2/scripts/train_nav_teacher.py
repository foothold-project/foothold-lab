"""HiPAN 모드 2 teacher PPO 실행기 (설계 §3 N3). 지금은 `--print` 예행만 한다: 시작 영수증을 찍고 끝난다.

영수증: 하위 저장본 sha · 방 메시 sha (room_manifest.json) · plan sha · 하위 b 값 · 관측 차원 대조 · PPO 설정 (가정 이름 표시) · 저장 간격 · 이어 받기 경로.
학습 루프 (Kit 환경 위에 rsl-rl) 는 N1 Kit 확인이 끝나기 전에는 붙이지 않았다: `--print` 없이 부르면 거절한다 (조용히 다른 길로 가지 않음).
쓰는 법: python -m foothold_s2.scripts.train_nav_teacher --print --lower-checkpoint <pt> --lower-sha256 <sha> --room-manifest <json> --plan <yaml> --vx-corr-b 0.009
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

FORMAT = "foothold-hipan-teacher-start-receipt/1"


def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_receipt(*, lower_checkpoint, lower_sha256, room_manifests, plan, vx_corr_b, resume=None, num_envs=None) -> dict:
    from foothold_s2.nav import hl_ppo_cfg as cfg
    from foothold_s2.nav.teacher_obs import TeacherObsLayout

    ckpt = Path(lower_checkpoint).resolve(strict=True)
    digest = _sha(ckpt)
    if digest != str(lower_sha256).lower():
        raise ValueError(f"lower checkpoint sha256 {digest[:8]} differs from the registered {str(lower_sha256)[:8]}")
    rooms = []
    for path in room_manifests:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
        if manifest.get("format") != "hipan-room/1" or not isinstance(manifest.get("mesh_sha256"), str):
            raise ValueError(f"{path} is not a hipan room manifest")
        rooms.append({"manifest": str(Path(path).resolve()), "manifest_sha256": _sha(path), "mesh_sha256": manifest["mesh_sha256"]})
    if not rooms:
        raise ValueError("at least one room manifest is required")
    plan_path = Path(plan).resolve(strict=True)
    ppo = cfg.TeacherPPO(**({"num_envs": int(num_envs)} if num_envs else {}))
    layout = TeacherObsLayout()
    encoder = cfg.build_encoder(ppo, layout)
    import torch
    probe = encoder(torch.zeros(2, layout.total))                       # 관측 차원 대조: 인코더가 layout 전체를 받아 latent 로 나온다
    if tuple(probe.shape) != (2, ppo.latent):
        raise ValueError(f"encoder output {tuple(probe.shape)} is not (2, {ppo.latent})")
    resume_row = None
    if resume:
        resume_path = Path(resume).resolve(strict=True)
        resume_row = {"path": str(resume_path), "sha256": _sha(resume_path)}
    return {"format": FORMAT, "lower": {"checkpoint": str(ckpt), "sha256": digest},
            "rooms": rooms, "plan": {"path": str(plan_path), "sha256": _sha(plan_path)}, "lower_vx_corr_b": float(vx_corr_b),
            "observation": {"total": layout.total, "sizes": layout.sizes, "latent": ppo.latent},
            "ppo": ppo.as_dict(), "assumed_ppo_fields": list(cfg.ASSUMED), "action_dim": cfg.ACTION_DIM,
            "save_interval": ppo.save_interval, "resume": resume_row, "lower_map_mode": "eval_gt", "training_started": False}


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
    p.add_argument("--receipt-out", default=None, help="also write the receipt here (never overwritten)")
    a = p.parse_args(argv)
    if not a.dry:
        print("refused: the teacher training loop is not attached yet (N1 Kit check first); run with --print", file=sys.stderr)
        return 2
    receipt = build_receipt(lower_checkpoint=a.lower_checkpoint, lower_sha256=a.lower_sha256, room_manifests=a.room_manifest, plan=a.plan,
                            vx_corr_b=a.vx_corr_b, resume=a.resume, num_envs=a.num_envs)
    text = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True)
    if a.receipt_out:
        with open(a.receipt_out, "x", encoding="utf-8") as stream:
            stream.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
