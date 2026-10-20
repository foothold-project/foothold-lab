# -*- coding: utf-8 -*-
"""`std` 체크포인트를 `log_std` 로 바꾼 **새 출발 체크포인트**를 만든다.

분류: 운영
작성: 오흥재 · 2026-09-26
근거: `AUDIT9-approve.md` 3 절 (astra) · `actor_critic.py:93,95,140,142` ·
      `nvidia_pretrained.pt` 실측 (`std` shape (12,) · 0.4433~0.8099)
요지: 학습을 걸기 «전에» 필요한 호환성 조각을 만든다. **GPU 를 안 쓴다.**
상태: 초안
판: v1.0

왜 이것이 필요한가 `확인됨`
    `noise_std_type="log"` 로 바꾸면 policy 의 저장 열쇠가 `std` -> `log_std` 다.
    `actor_critic.py:186~198` 이 기본 `strict=True` 로 부르므로
    **기존 NVIDIA 체크포인트에서 resume 이 «안 된다»** (열쇠가 없다).

왜 0 으로 초기화하면 «안» 되나 `확인됨`
    `init_noise_std=1.0` 은 `std=1` 곧 `log_std=0` 에 대응한다.
    그런데 우리는 새 초기화가 아니라 **NVIDIA 체크포인트에서 시작한다.**
    그 `std` 는 0.4433 ~ 0.8099 다. `log_std=0` 으로 두면 **탐색 잡음을
    두 배 가까이 키운다.** 출발 분포를 유지하는 변환은 `log_std = log(std)` 다.

optimizer 를 어떻게 하나 `확인됨`
    **그대로 못 옮긴다.** Adam moment 는 `std` 좌표에서 쌓인 것이고
    `log_std` 좌표에서는 뜻이 다르다. 과거 gradient 마다 당시 sigma 가 달라
    현재 sigma 하나로 곱해 복원할 수도 없다 (astra AUDIT9 3 절).

    그래서 이 파일은 **optimizer 를 «버리는» 판과 «남기는» 판을 둘 다 만들지
    않는다.** 버린다. 그리고 **scalar 대조군도 optimizer 를 버려야** 공정하다.
    그 대조군을 만드는 것이 `--also-scalar` 다.

돌리는 법
    python _out/loop/std_to_log.py --dry-run
    python _out/loop/std_to_log.py
    python _out/loop/std_to_log.py --verify <만든파일>
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import math
import os
import sys

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import torch  # noqa: E402

ROOT = "C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia"
SRC_GLOB = ROOT + "/**/nvidia_pretrained.pt"
OUT_LOG = ROOT + "/nvidia_pretrained_logstd/nvidia_pretrained.pt"
OUT_SCALAR = ROOT + "/nvidia_pretrained_noopt/nvidia_pretrained.pt"


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def find_src():
    hits = glob.glob(SRC_GLOB, recursive=True)
    return hits[0].replace("\\", "/") if hits else None


def convert(dry: bool, also_scalar: bool) -> int:
    src = find_src()
    if not src:
        print("원본을 못 찾는다:", SRC_GLOB)
        return 1
    print("원본      :", src)
    print("원본 SHA  :", sha(src)[:16], "...")

    d = torch.load(src, map_location="cpu", weights_only=False)
    sd = d["model_state_dict"]

    if "std" not in sd:
        print("«std» 열쇠가 없다. 이미 log 판이거나 다른 구조다:", list(sd)[:4])
        return 1
    if "log_std" in sd:
        print("«log_std» 가 이미 있다. 건드리지 않는다")
        return 1

    std = sd["std"]
    bad = int((~torch.isfinite(std)).sum())
    nonpos = int((std <= 0).sum())
    print()
    print("std       : shape %s  min %.10f  max %.10f" %
          (tuple(std.shape), float(std.min()), float(std.max())))
    print("  비유한수 %d 개 · 0 이하 %d 개" % (bad, nonpos))
    if bad or nonpos:
        # **양수가 아니면 log 를 못 취한다. 여기서 «멈춘다».**
        print("** 양수·유한이 아닌 값이 있다. 변환하지 «않는다» **")
        return 2

    log_std = torch.log(std)
    print("log_std   : min %.6f  max %.6f" % (float(log_std.min()),
                                              float(log_std.max())))
    # 되읽기 · exp 로 돌려 원본과 같은가
    back = torch.exp(log_std)
    err = float((back - std).abs().max())
    print("되읽기 오차 exp(log(std)) 대 std 의 최대 절대차 : %.3e" % err)
    if err > 1e-6:
        print("** 되읽기 오차가 크다. 변환하지 «않는다» **")
        return 2

    if dry:
        print()
        print("«--dry-run 이라 아무것도 안 썼다»")
        print("만들 파일:")
        print("  ", OUT_LOG, "   (log_std · optimizer 버림)")
        if also_scalar:
            print("  ", OUT_SCALAR, "(std 그대로 · optimizer 버림 · 공정한 대조군)")
        return 0

    # ---- log 판 ----
    nl = dict(sd)
    del nl["std"]
    nl["log_std"] = log_std
    # **optimizer 를 버린다.** 좌표가 달라 뜻이 없다 (위 docstring).
    out = {"model_state_dict": nl, "iter": d.get("iter", 0),
           "infos": d.get("infos"),
           "converted_from": src,
           "converted_from_sha256": sha(src),
           "conversion": "log_std = log(std) · optimizer_state_dict «버림»",
           "why_no_optimizer": ("Adam moment 는 std 좌표에서 쌓였고 log_std "
                                "좌표에서는 뜻이 다르다 (AUDIT9 3 절)")}
    os.makedirs(os.path.dirname(OUT_LOG), exist_ok=True)
    torch.save(out, OUT_LOG)
    print()
    print("만들었다 :", OUT_LOG)
    print("  SHA    :", sha(OUT_LOG)[:16], "...")

    # ---- scalar 대조군 (optimizer 만 버린 것) ----
    if also_scalar:
        ns = {"model_state_dict": dict(sd), "iter": d.get("iter", 0),
              "infos": d.get("infos"),
              "converted_from": src,
              "converted_from_sha256": sha(src),
              "conversion": "std 그대로 · optimizer_state_dict «버림»",
              "why": ("log 판이 optimizer 를 버리므로 scalar 대조군도 버려야 "
                      "공정하다 (AUDIT9 3 절의 「가장 명료한 첫 대조」)")}
        os.makedirs(os.path.dirname(OUT_SCALAR), exist_ok=True)
        torch.save(ns, OUT_SCALAR)
        print("만들었다 :", OUT_SCALAR)
        print("  SHA    :", sha(OUT_SCALAR)[:16], "...")

    print()
    print("**아직 학습을 걸지 않았다.** 다음에 확인할 것")
    print("  1  평가 하네스 둘이 «새» 체크포인트를 부를 수 있나 (지금은 «못 한다»)")
    print("  2  train_instrumented.py:86 이 policy.std 를 직접 읽는다 (AttributeError)")
    print("  3  agent cfg 에 noise_std_type='log' 를 «어떻게» 넣나")
    return 0


def verify(path: str) -> int:
    if not os.path.isfile(path):
        print("없다:", path)
        return 1
    d = torch.load(path, map_location="cpu", weights_only=False)
    sd = d["model_state_dict"]
    print("파일    :", path)
    print("SHA     :", sha(path)[:16], "...")
    print("최상위  :", list(d))
    keys = [k for k in sd if "std" in k.lower()]
    print("std 열쇠:", keys)
    for k in keys:
        t = sd[k]
        print("  %-10s shape %-8s min %.10f max %.10f"
              % (k, tuple(t.shape), float(t.min()), float(t.max())))
        if k == "log_std":
            e = torch.exp(t)
            print("     exp -> min %.10f max %.10f  (원본 std 와 같아야 한다)"
                  % (float(e.min()), float(e.max())))
    print("optimizer 있나:", "optimizer_state_dict" in d, "(log 판은 «없어야» 한다)")
    print("변환 기록:", d.get("conversion"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--also-scalar", action="store_true", default=True,
                    help="공정한 scalar 대조군도 만든다 (기본 켜짐)")
    ap.add_argument("--verify", default=None)
    a = ap.parse_args()
    if a.verify:
        return verify(a.verify)
    return convert(a.dry_run, a.also_scalar)


if __name__ == "__main__":
    sys.exit(main())
