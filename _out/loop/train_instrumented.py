# -*- coding: utf-8 -*-
"""계측을 켠 학습 · **rsl_rl 패키지를 고치지 않는다.**

분류: 운영
작성: 오흥재 · 2026-09-24
근거: `rsl_rl/algorithms/ppo.py` 의 `update()` · 2026-09-23 seed 43 발산
요지: 매 판 value/return/advantage/gradient 의 «극값» 만 CSV 로 남기고,
      비유한수가 처음 나오면 그 minibatch 를 통째로 덤프한 뒤 멈춘다.
상태: 초안
판: v1.0

왜 필요한가
    seed 43 이 step 1578 에서 발산했는데 `tfevents` 가 100 판 «평균» 만
    저장해서 어느 env·어느 minibatch 가 먼저 터졌는지 알 수 없었다.

왜 resume 이 아니라 처음부터인가
    checkpoint 에 «난수 생성기 상태가 없다**. `model_1550` 에서 이어받으면
    난수가 시드부터 다시 시작해 다른 궤적을 간다. 1578 에서 안 터진다.
    처음부터 돌리면 결정론이라 «반드시» 같은 자리에서 터진다.

무엇을 남기나
    매 판    _out/instr/<run>/per_iter.csv   (몇 KB. 학습 속도에 거의 영향 없음)
    터질 때  _out/instr/<run>/dump_<it>.pt   (그 minibatch 전체)

돌리는 법
    python train_instrumented.py --task ... --seed 43 --device cuda:1 agent.device=cuda:1
    (train_go2_win.py 와 같은 인자를 받는다)
"""

import csv
import math
import os
import runpy
import sys

# Windows 우회 · Kit 로드 전에 네이티브 확장 패키지를 선점 import
import torch                        # noqa: F401
from tensordict import TensorDict   # noqa: F401,E402
import rsl_rl.runners               # noqa: F401,E402
import h5py                         # noqa: F401,E402

from rsl_rl.algorithms import PPO

OUT_ROOT = r"C:\isaac\IsaacLab\_out\instr"
_state = {"it": 0, "rows": [], "dumped": False, "dir": None, "mb": 0}


def _fin(t):
    """(최소, 최대, 비유한수 개수). 텐서가 아니면 None."""
    if not torch.is_tensor(t):
        return (None, None, None)
    bad = int((~torch.isfinite(t)).sum().item())
    if bad == t.numel():
        return (float("nan"), float("nan"), bad)
    ok = t[torch.isfinite(t)]
    return (float(ok.min()), float(ok.max()), bad)


def _effective_std(policy):
    """scalar 든 log 든 **유효 표준편차** 를 돌려준다. 못 찾으면 None.

    scalar   policy.std          그대로
    log      exp(policy.log_std)  지수를 취한다
    """
    t = getattr(policy, "std", None)
    if t is not None and torch.is_tensor(t):
        return t.detach()
    t = getattr(policy, "log_std", None)
    if t is not None and torch.is_tensor(t):
        return torch.exp(t.detach())
    return None


_orig_update = PPO.update


def update(self, *a, **kw):
    """`update()` 를 감싸 극값을 기록한다. **계산은 안 바꾼다.**"""
    _state["it"] += 1
    it = _state["it"]
    _state["mb"] = 0

    # minibatch 단위로 보려고 loss 계산 지점을 후킹하는 대신,
    # update 전후의 파라미터와 gradient 를 본다. 가볍고 충분하다.
    before_bad = sum(int((~torch.isfinite(p)).sum().item())
                     for p in self.policy.parameters())

    out = _orig_update(self, *a, **kw)

    gnorm = None
    try:
        gs = [p.grad for p in self.policy.parameters() if p.grad is not None]
        if gs:
            gnorm = float(torch.norm(torch.stack(
                [torch.norm(g.detach(), 2) for g in gs]), 2))
    except Exception:                                          # noqa: BLE001
        gnorm = None

    after_bad = sum(int((~torch.isfinite(p)).sum().item())
                    for p in self.policy.parameters())
    # **두 형식을 다 읽는다 (2026-09-26 · astra AUDIT9 3 절).**
    # noise_std_type='log' 면 policy.std 가 «없고» log_std 만 있다.
    # 전에는 policy.std 를 직접 읽어 AttributeError 로 죽었다.
    std = _effective_std(self.policy)
    smin, smax, sbad = _fin(std)

    # **dict 반환을 읽는다 (2026-09-26 · astra AUDIT9 1 절).**
    # ppo.py:408 이 {'value_function': ...} 를 준다. 전에는 tuple/list 만
    # 읽어서 CSV 1671 행의 value_loss 가 «전부 비어 있었다».
    vloss = None
    if isinstance(out, dict):
        for k in ("value_function", "value_loss", "mean_value_loss"):
            if k in out:
                vloss = out[k]
                break
    elif isinstance(out, (tuple, list)) and out:
        vloss = out[0]
    if torch.is_tensor(vloss):
        vloss = float(vloss.detach())
    row = {
        "it": it,
        "value_loss": vloss if isinstance(vloss, (int, float)) else "",
        "grad_norm": gnorm if gnorm is not None else "",
        "grad_norm_finite": "" if gnorm is None else int(math.isfinite(gnorm)),
        "std_min": smin, "std_max": smax, "std_nonfinite": sbad,
        "param_nonfinite_before": before_bad,
        "param_nonfinite_after": after_bad,
    }
    _state["rows"].append(row)

    # **처음 이상이 보이면 그 자리에서 덤프하고 멈춘다.**
    trouble = (after_bad > 0 or sbad > 0
               or (gnorm is not None and not math.isfinite(gnorm))
               or (isinstance(vloss, float) and not math.isfinite(vloss)))
    if trouble and not _state["dumped"]:
        _state["dumped"] = True
        d = _state["dir"] or OUT_ROOT
        os.makedirs(d, exist_ok=True)
        torch.save({
            "iter": it,
            "model_state_dict": self.policy.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "grads": {n: (p.grad.detach().cpu() if p.grad is not None else None)
                      for n, p in self.policy.named_parameters()},
            "row": row,
        }, os.path.join(d, "dump_%d.pt" % it))
        _flush()
        print("\n[계측] iteration %d 에서 «비유한수» 를 처음 봤다. "
              "덤프를 남겼다: %s\n" % (it, d), flush=True)

    if it % 25 == 0:
        _flush()
    return out


def _flush():
    d = _state["dir"] or OUT_ROOT
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "per_iter.csv")
    if not _state["rows"]:
        return
    new = not os.path.isfile(p)
    with open(p, "a", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(_state["rows"][0]))
        if new:
            w.writeheader()
        w.writerows(_state["rows"])
    _state["rows"] = []


PPO.update = update

# 실행 이름을 받아 출력 폴더를 정한다
_run = "run"
for i, a in enumerate(sys.argv):
    if a == "--run_name" and i + 1 < len(sys.argv):
        _run = sys.argv[i + 1]
_state["dir"] = os.path.join(OUT_ROOT, _run)
os.makedirs(_state["dir"], exist_ok=True)
print("[계측] 켜짐. 출력: %s" % _state["dir"], flush=True)

SCRIPT = os.path.join("scripts", "reinforcement_learning", "rsl_rl", "train.py")
sys.path.insert(0, os.path.dirname(os.path.abspath(SCRIPT)))
sys.argv = [SCRIPT] + sys.argv[1:]
try:
    runpy.run_path(SCRIPT, run_name="__main__")
finally:
    _flush()
