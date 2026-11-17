"""복원 지도 오프라인 가르기 (설계 DESIGN-MAP-EDGE-1117 2.2 · 2.3 ㄱ · 3 절): 기록 npz (ex42_mapfit_record_child) 로 TRNet 만 맞추는 스크립트. Kit · 정책 없음 · CPU.
판: base (정본 3 의 TRNet 그대로, 맞추지 않음 = 기준) · ctrl (같은 길이로 맞추되 가중 1 = 「더 맞췄을 뿐」 대조, 설계 밖 덧붙임) · A (모서리 · 구멍 칸 손실 x weight) ·
B1 (GRU · rough MLP 폭 width · CNN · prop_mlp · U-Net 은 이어받음) · A+B1. 체크포인트 파일은 읽기만 한다 (정책 · 나머지 지각은 건드리지 않고, 이 스크립트는 어디에도 체크포인트를 쓰지 않는다).
판정표 (3 절 미리 적은 줄): 모서리 칸 오차 (cm) · 이웃 차 5 cm 넘는 칸 비율 (복원 대 정답) · 평평한 칸 오차 · 없는 구멍 · 구멍 놓침 % (기록) · rough (U-Net 앞) 모서리 오차.
평가 묶음은 학습 시드와 다른 폴더 (--eval-dirs). 기록의 깊이는 평가 환경이 낸 그대로 (그 안에 증강이 켜져 있었는지는 미확인: 오프라인에서 다시 증강하지 않는다).
쓰는 법: python -m foothold_s2.eval.ex42_mapfit_offline --checkpoint <model.pt> --train-dirs d1,d2 --eval-dirs d3 --out <폴더> [--variants base,ctrl,A,B1,A+B1] [--weight 4 --width 512 --epochs 8]"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch

from foothold_s2.eval import ex42_axes as ax
from foothold_s2.models import map_weights as mw
from foothold_s2.models import start_perception as sp

MIN_SEGMENT_TICKS = 4
JUDGE = {"edge_err_cm": (2.0, 2.9), "edge_frac_pred": (0.06, 0.03), "flat_err_cm": 0.9, "false_hole_frac": 0.005}      # 설계 3 절: (통과 아래, 실패 위) · (통과 위, 실패 아래) · 넘으면 가중 내림 · 아래면 통과


def load_segments(patterns) -> list[dict]:
    """mapfit.npz 들 -> env 마다 first 에서 끊은 구간 목록 (각 구간 = depth (T, 2, 60, 60) · z_prop (T, 128) · gt (T, 32, 16) float32)."""
    files = sorted({f for pat in patterns for f in glob.glob(str(pat))})
    if not files:
        raise FileNotFoundError(f"no mapfit.npz for {patterns}")
    segs = []
    for f in files:
        d = np.load(f)
        order = np.lexsort((d["call"], d["env"]))
        env, first = d["env"][order], d["first"][order]
        cut = np.nonzero(first | (np.diff(env, prepend=env[0] - 1) != 0))[0]
        for a, b in zip(cut, list(cut[1:]) + [len(env)]):
            if b - a >= MIN_SEGMENT_TICKS and bool(first[a]):               # 리셋 첫 스텝으로 시작하는 구간만 (h 0 에서 시작이 맞는 것)
                idx = order[a:b]
                segs.append({"depth": d["depth2"][idx].astype(np.float32), "z_prop": d["z_prop"][idx].astype(np.float32), "gt": d["gt"][idx].astype(np.float32), "src": f})
    return segs


def pad_batch(segs: list[dict]):
    t = max(len(s["gt"]) for s in segs)
    b = len(segs)
    depth = torch.zeros(b, t, 2, 60, 60); zp = torch.zeros(b, t, 128); gt = torch.zeros(b, t, sp.MAP_X, sp.MAP_Y); valid = torch.zeros(b, t, dtype=torch.bool)
    for i, s in enumerate(segs):
        n = len(s["gt"])
        depth[i, :n] = torch.from_numpy(s["depth"]); zp[i, :n] = torch.from_numpy(s["z_prop"]); gt[i, :n] = torch.from_numpy(s["gt"]); valid[i, :n] = True
    return depth, zp, gt, valid


def forward_segments(net: sp.TRNet, depth, zp, valid):
    """구간 묶음 (B, T, ...) -> rough · refined (B, T, 32, 16). 구간 시작 h = 0 · 한 구간 안에서 BPTT. 유효하지 않은 칸은 h 를 그대로 둔다."""
    b, t = valid.shape
    h = torch.zeros(b, net.width)
    roughs, refs = [], []
    for k in range(t):
        h_new = net.step(depth[:, k], zp[:, k], h)
        h = torch.where(valid[:, k, None], h_new, h)
        r, f = net.decode(h)
        roughs.append(r); refs.append(f)
    return torch.stack(roughs, 1), torch.stack(refs, 1)


def load_trnet(checkpoint: str, width: int = 128) -> tuple[sp.TRNet, dict]:
    """체크포인트의 perception_state_dict 에서 TRNet 만 읽는다 (읽기 전용). 모양이 다른 칸 (B1 의 GRU · rough) 은 새로 두고 건너뛴 이름을 돌려준다."""
    ck = torch.load(checkpoint, map_location="cpu", weights_only=False)
    sd = {k[len("trnet."):]: v for k, v in ck["perception_state_dict"].items() if k.startswith("trnet.")}
    net = sp.TRNet(width=width)
    own = net.state_dict()
    take = {k: v for k, v in sd.items() if k in own and own[k].shape == v.shape}
    skipped = sorted(k for k in own if k not in take)
    net.load_state_dict({**own, **take})
    return net, {"loaded": len(take), "new_keys": skipped}


def fit(net: sp.TRNet, train: list[dict], *, w_edge: float, w_hole: float, epochs: int, batch: int, lr: float, seed: int = 0, log=print) -> list[float]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    hist = []
    for ep in range(epochs):
        order = rng.permutation(len(train))
        tot, cnt = 0.0, 0
        for i in range(0, len(order), batch):
            depth, zp, gt, valid = pad_batch([train[j] for j in order[i:i + batch]])
            rough, ref = forward_segments(net, depth, zp, valid)
            g = gt[valid]
            loss = sp.loss_tr(rough[valid], ref[valid], g, mw.weight_map(g, w_edge, w_hole))
            opt.zero_grad(); loss.backward(); opt.step()
            tot += float(loss); cnt += 1
        hist.append(tot / max(cnt, 1))
        log(f"  epoch {ep + 1}/{epochs} loss {hist[-1]:.5f}")
    return hist


@torch.no_grad()
def evaluate(net: sp.TRNet, segs: list[dict], batch: int = 16) -> dict:
    """평가 묶음에서 판정표의 값. 모든 칸 합쳐 센다 (구간 · 틱 구분 없이 칸 단위)."""
    err_e, err_e_rough, n_flat, s_flat = [], [], 0, 0.0
    cnt = {"cells": 0, "edge_gt": 0, "edge_pred": 0}
    hole = np.zeros(len(ax.HOLE_COLUMNS))
    for i in range(0, len(segs), batch):
        depth, zp, gt, valid = pad_batch(segs[i:i + batch])
        rough, ref = forward_segments(net, depth, zp, valid)
        g = gt[valid].numpy().astype(np.float64); r = ref[valid].numpy().astype(np.float64); ro = rough[valid].numpy().astype(np.float64)
        eg, er = ax.edge_mask(g), ax.edge_mask(r)
        e, e_ro = np.abs(r - g), np.abs(ro - g)
        err_e.append(e[eg]); err_e_rough.append(e_ro[eg])
        n_flat += int((~eg).sum()); s_flat += float(e[~eg].sum())
        cnt["cells"] += g.size; cnt["edge_gt"] += int(eg.sum()); cnt["edge_pred"] += int(er.sum())
        hole += ax.hole_stats(r, g).sum(0)
    ee, eo = np.concatenate(err_e), np.concatenate(err_e_rough)
    return {"ticks": int(sum(len(s["gt"]) for s in segs)), "edge_err_cm": float(ee.mean() * 100) if ee.size else None,
            "edge_err_p90_cm": float(np.percentile(ee, 90) * 100) if ee.size else None, "rough_edge_err_cm": float(eo.mean() * 100) if eo.size else None,
            "edge_frac_gt": cnt["edge_gt"] / cnt["cells"], "edge_frac_pred": cnt["edge_pred"] / cnt["cells"], "flat_err_cm": s_flat / max(n_flat, 1) * 100,
            "hole_cells": int(hole[0]), "hole_missed_frac": float(hole[1] / hole[0]) if hole[0] > 0 else None,
            "false_hole_frac": float(hole[3] / hole[2]) if hole[2] > 0 else None}


def judge(m: dict) -> dict:
    """설계 3 절 줄 (결과 전에 고정): 통과 / 실패 / 사이 (표시만). ㄱ 은 자료가 적어 숫자 통과를 엄격히 읽지 않는다 (방향만 보라는 설계 문장)."""
    out = {}
    e = m["edge_err_cm"]
    out["edge_err"] = None if e is None else ("PASS" if e < JUDGE["edge_err_cm"][0] else "FAIL" if e > JUDGE["edge_err_cm"][1] else "mid")
    f = m["edge_frac_pred"]
    out["edge_frac"] = "PASS" if f > JUDGE["edge_frac_pred"][0] else "FAIL" if f < JUDGE["edge_frac_pred"][1] else "mid"
    out["flat_err"] = "OK" if m["flat_err_cm"] <= JUDGE["flat_err_cm"] else "lower-weight"
    fh = m["false_hole_frac"]
    out["false_hole"] = None if fh is None else ("PASS" if fh < JUDGE["false_hole_frac"] else "too-strong")
    return out


def table(rows: dict) -> str:
    f = lambda v, n=2: "-" if v is None else f"{v:.{n}f}"                      # noqa: E731
    out = ["판       모서리 cm (p90)    5cm 단차 칸 비율 복원/정답   평평한 칸 cm   없는 구멍 %   구멍 놓침 %   rough 모서리 cm   판정 (모서리 · 단차 · 평평 · 없는 구멍)"]
    for name, r in rows.items():
        m, j = r["metrics"], r["judge"]
        out.append(f"{name:<8} {f(m['edge_err_cm'])} ({f(m['edge_err_p90_cm'])})      {f(m['edge_frac_pred'] * 100)} / {f(m['edge_frac_gt'] * 100)}              "
                   f"{f(m['flat_err_cm'])}          {f(None if m['false_hole_frac'] is None else m['false_hole_frac'] * 100, 3)}       "
                   f"{f(None if m['hole_missed_frac'] is None else m['hole_missed_frac'] * 100, 1)}         {f(m['rough_edge_err_cm'])}            "
                   f"{j['edge_err']} · {j['edge_frac']} · {j['flat_err']} · {j['false_hole']}")
    return "\n".join(out)


def run(args, log=print) -> dict:
    train, held = load_segments([p for p in args.train_dirs.split(",")]), load_segments([p for p in args.eval_dirs.split(",")])
    sha = hashlib.sha256(Path(args.checkpoint).read_bytes()).hexdigest()
    log(f"train segments {len(train)} ({sum(len(s['gt']) for s in train)} ticks) · eval segments {len(held)} ({sum(len(s['gt']) for s in held)} ticks)")
    spec = {"base": (128, 1.0, False), "ctrl": (128, 1.0, True), "A": (128, args.weight, True), "B1": (args.width, 1.0, True), "A+B1": (args.width, args.weight, True)}
    rows = {}
    for name in args.variants.split(","):
        width, w, trained = spec[name]
        net, info = load_trnet(args.checkpoint, width)
        t0 = time.time()
        hist = fit(net, train, w_edge=w, w_hole=w, epochs=args.epochs, batch=args.batch, lr=args.lr, log=log) if trained else []
        m = evaluate(net, held)
        rows[name] = {"metrics": m, "judge": judge(m), "width": width, "weight": w, "trained": trained, "loss_by_epoch": hist, "load": info, "seconds": round(time.time() - t0, 1)}
        log(f"[{name}] edge {m['edge_err_cm']} cm · flat {m['flat_err_cm']:.2f} cm · {rows[name]['seconds']} s")
    res = {"checkpoint": args.checkpoint, "checkpoint_sha256": sha, "checkpoint_sha256_after": hashlib.sha256(Path(args.checkpoint).read_bytes()).hexdigest(),
           "train_dirs": args.train_dirs, "eval_dirs": args.eval_dirs, "judge_lines": JUDGE, "rows": rows, "table": table(rows),
           "note": "ㄱ 단계: 방향 (정본 3 보다 모서리 오차가 내려갔는가) 과 세 판의 순서만 읽는다. 숫자 통과는 ㄴ (본 맞춤) 에서 판정 (설계 3 절)."}
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    (out / "mapfit_offline.json").write_text(json.dumps(res, ensure_ascii=False, indent=2))
    (out / "mapfit_offline_table.txt").write_text(res["table"] + "\n")
    log(res["table"])
    return res


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--checkpoint", required=True); p.add_argument("--train-dirs", required=True, help="mapfit.npz 경로 (glob 가능, 쉼표로 여럿)")
    p.add_argument("--eval-dirs", required=True); p.add_argument("--out", required=True)
    p.add_argument("--variants", default="base,ctrl,A,B1,A+B1"); p.add_argument("--weight", type=float, default=4.0, help="설계 2.2: 먼저 4 (가정)")
    p.add_argument("--width", type=int, default=512); p.add_argument("--epochs", type=int, default=8); p.add_argument("--batch", type=int, default=8)
    p.add_argument("--lr", type=float, default=3e-4); p.add_argument("--threads", type=int, default=4)
    a = p.parse_args(argv)
    torch.set_num_threads(a.threads)
    run(a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
