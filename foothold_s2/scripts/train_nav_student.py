"""HiPAN 모드 2 student DAgger 실행기 (설계 §3 N4). `--print` = 시작 영수증만. 없이 부르면 `--env-factory` · `--out-dir` · `--iterations` 가 모두 있어야 돈다 (없으면 rc 2).
`--env-factory 모듈:함수` 는 (TeacherVecEnv, depth_fn) 을 돌려준다 (Kit 기동 · RayCasterCamera 는 그 함수 몫). 영수증은 out-dir 에 먼저 쓰고 (다른 영수증이 있으면 거절) 50 회마다 `student_<회>.pt`.
이어 받기는 같은 teacher sha · 같은 student 설정일 때만. 실제 학습은 팀장 승인 뒤 lead 가 띄운다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

FORMAT = "foothold-hipan-student-start-receipt/1"
CKPT_FORMAT = "foothold-hipan-student-ckpt/1"
SAVE_INTERVAL = 50


def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def identity_text(receipt: dict) -> str:
    """이어 받기 대조용 글: `resume` 칸을 뺀 영수증 (reviewer 04:15 와 같은 결함을 student 에도 미리 막음)."""
    return json.dumps({k: v for k, v in receipt.items() if k != "resume"}, ensure_ascii=False, indent=2, sort_keys=True)


def build_receipt(*, teacher_checkpoint, teacher_sha256, cfg=None, resume=None, save_interval=SAVE_INTERVAL) -> dict:
    import torch
    from foothold_s2.nav import hl_student as hs

    cfg = cfg or hs.StudentCfg()
    ck = Path(teacher_checkpoint).resolve(strict=True)
    digest = _sha(ck)
    if digest != str(teacher_sha256).lower():
        raise ValueError(f"teacher checkpoint sha256 {digest[:8]} differs from the registered {str(teacher_sha256)[:8]}")
    net = hs.build_student(cfg)
    a, z, xm, _h = net(torch.zeros(2, 1, hs.DEPTH_H, hs.DEPTH_W), torch.zeros(2, cfg.o_p + cfg.goal_dim), net.init_hidden(2))
    if (tuple(a.shape), tuple(z.shape), tuple(xm.shape)) != ((2, 3), (2, cfg.latent), (2, cfg.x_m)):
        raise ValueError("student output shapes do not match the teacher labels")
    row = None
    if resume:
        rp = Path(resume).resolve(strict=True)
        row = {"path": str(rp), "sha256": _sha(rp)}
    return {"format": FORMAT, "teacher": {"checkpoint": str(ck), "sha256": digest}, "student": cfg.as_dict(), "assumed_fields": list(hs.ASSUMED),
            "depth": [hs.DEPTH_H, hs.DEPTH_W], "camera_pitch_deg": hs.CAMERA_PITCH_DEG, "save_interval": int(save_interval), "resume": row, "training_started": False}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--print", dest="dry", action="store_true")
    p.add_argument("--teacher-checkpoint", required=True)
    p.add_argument("--teacher-sha256", required=True)
    p.add_argument("--teacher-num-envs", type=int, default=None, help="PPO num_envs the teacher was trained with (must match its checkpoint)")
    p.add_argument("--env-factory", default=None)
    p.add_argument("--out-dir", default=None)
    p.add_argument("--iterations", type=int, default=None)
    p.add_argument("--resume", default=None)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--save-interval", type=int, default=SAVE_INTERVAL)
    p.add_argument("--receipt-out", default=None)
    a = p.parse_args(argv)
    if not a.dry and not (a.env_factory and a.out_dir and a.iterations):
        print("refused: training needs --env-factory, --out-dir and --iterations (or use --print)", file=sys.stderr)
        return 2
    receipt = build_receipt(teacher_checkpoint=a.teacher_checkpoint, teacher_sha256=a.teacher_sha256, resume=a.resume, save_interval=a.save_interval)
    text = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True)
    if a.receipt_out:
        with open(a.receipt_out, "x", encoding="utf-8") as stream:
            stream.write(text + "\n")
    print(text)
    if a.dry:
        return 0
    import importlib
    import torch
    from foothold_s2.nav import hl_ppo_cfg, hl_student as hs

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ident = identity_text(receipt)
    rpath = out / "start_receipt.json"
    if rpath.exists():
        if rpath.read_text(encoding="utf-8").strip() != ident:
            raise SystemExit("refused: out-dir already holds a different start receipt")
    else:
        rpath.write_text(ident + "\n", encoding="utf-8")
    if a.resume:
        with open(out / "resume_log.jsonl", "a", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt["resume"], ensure_ascii=False) + "\n")
    sha = hashlib.sha256(ident.encode("utf-8")).hexdigest()
    cfg = hs.StudentCfg()
    mod, _, fn = a.env_factory.partition(":")
    vec, depth_fn = getattr(importlib.import_module(mod), fn)()
    device = vec.device
    ppo = hl_ppo_cfg.TeacherPPO(**({"num_envs": a.teacher_num_envs} if a.teacher_num_envs else {}))
    teacher = hs.teacher_from_checkpoint(a.teacher_checkpoint, ppo, device)
    student = opt = None
    it0 = 0
    if a.resume:
        ck = torch.load(a.resume, map_location=device, weights_only=False)
        if ck.get("format") != CKPT_FORMAT or ck["receipt_sha256"] != sha or ck["student"] != cfg.as_dict():
            raise SystemExit("refused: resume checkpoint is not from this start receipt and student configuration")
        student = hs.build_student(cfg).to(device); student.load_state_dict(ck["model"])
        opt = torch.optim.Adam(student.parameters(), lr=cfg.lr); opt.load_state_dict(ck["optimizer"])
        it0 = int(ck["iteration"])
    saved = []

    def after(it, net, optimizer):
        if it % a.save_interval == 0:
            path = out / f"student_{it}.pt"
            if path.exists():
                raise FileExistsError(f"{path} exists (never overwritten)")
            torch.save({"format": CKPT_FORMAT, "iteration": it, "receipt_sha256": sha, "student": cfg.as_dict(), "model": net.state_dict(),
                        "optimizer": optimizer.state_dict()}, path)
            saved.append(str(path))

    env = hs.StudentEnv(vec, depth_fn, cfg)
    _s, _o, last = hs.dagger(env, teacher, cfg, iterations=a.iterations, seed=a.seed, device=device, student=student, opt=opt, start_iteration=it0, after=after)
    print(json.dumps({"last_iteration": last, "saved": saved}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
