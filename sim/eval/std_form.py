# -*- coding: utf-8 -*-
"""체크포인트의 «표준편차 형식» 을 읽어 agent 설정을 맞춘다.

분류: 평가
작성: 오흥재 · 2026-09-26
근거: `AUDIT9-approve.md` 3 절 (astra) · `rsl_rl/modules/actor_critic.py:31,93,95`
      · `nvidia_pretrained.pt` 실측 (`std` shape (12,))
요지: 두 평가 하네스가 `scalar` 와 `log` 체크포인트를 **둘 다** 부를 수 있게 한다.
상태: 초안
판: v1.0

왜 필요한가 `확인됨`
    두 하네스가 레지스트리의 agent 설정으로 `OnPolicyRunner` 를 만든다.
    그 설정의 `noise_std_type` 기본값은 `scalar` 다 (`actor_critic.py:31`).
    그래서 정책이 `self.std` 를 가진 형태로 만들어진다.

    `noise_std_type="log"` 로 학습한 체크포인트는 열쇠가 `log_std` 다.
    `actor_critic.py:186~198` 이 기본 `strict=True` 로 부르므로
    **열쇠가 안 맞아 죽는다.** 반대 방향도 마찬가지다.

무엇을 «안» 하나
    - `strict=False` 로 «덮지 않는다». 그러면 누락을 조용히 넘긴다.
    - 열쇠를 «바꿔치지» 않는다. 값의 좌표가 다르다 (`std` 대 `log(std)`).
    - 둘 다 있거나 둘 다 없으면 **오류로 처리한다.** 추측하지 않는다.

돌리는 법 (하네스 안에서)
    from std_form import apply_std_form
    apply_std_form(agent_cfg, checkpoint_path)   # 설정을 «제자리에서» 고친다
"""

from __future__ import annotations

import os

_HAVE_TORCH = True
try:
    import torch
except Exception:                                              # noqa: BLE001
    _HAVE_TORCH = False


def read_std_form(checkpoint_path: str) -> str:
    """체크포인트가 어느 형식인지. `"scalar"` 또는 `"log"`.

    **둘 다 있거나 둘 다 없으면 오류다.** 조용히 고르지 않는다.
    """
    if not _HAVE_TORCH:
        raise RuntimeError("torch 를 못 불렀다. 표준편차 형식을 읽을 수 없다")
    if not os.path.isfile(checkpoint_path):
        raise FileNotFoundError("체크포인트가 없다: %s" % checkpoint_path)

    d = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    sd = d.get("model_state_dict")
    if not isinstance(sd, dict):
        raise RuntimeError("model_state_dict 가 없다: %s" % checkpoint_path)

    has_scalar = "std" in sd
    has_log = "log_std" in sd
    if has_scalar and has_log:
        raise RuntimeError(
            "체크포인트에 `std` 와 `log_std` 가 «둘 다» 있다. "
            "어느 쪽인지 정할 수 없다: %s" % checkpoint_path)
    if has_scalar:
        return "scalar"
    if has_log:
        return "log"
    # 상태 의존 std 를 쓰는 판일 수 있다. 그 경우도 «말하고» 죽는다.
    keys = [k for k in sd if "std" in k.lower()]
    raise RuntimeError(
        "표준편차 열쇠를 못 찾았다 (`std` 도 `log_std` 도 없다). "
        "std 가 든 열쇠: %r · %s" % (keys, checkpoint_path))


def apply_std_form(agent_cfg, checkpoint_path: str, log=print) -> str:
    """`agent_cfg` 의 `policy.noise_std_type` 을 체크포인트에 맞춘다.

    `agent_cfg` 는 dict 이거나 속성을 가진 객체 둘 다 받는다.
    맞춘 형식을 돌려준다. **못 맞추면 예외를 던진다.** 조용히 넘어가지 않는다.
    """
    form = read_std_form(checkpoint_path)

    # dict 인 경우
    if isinstance(agent_cfg, dict):
        pol = agent_cfg.get("policy")
        if not isinstance(pol, dict):
            raise RuntimeError("agent_cfg['policy'] 가 dict 가 아니다: %r" % type(pol))
        prev = pol.get("noise_std_type", "scalar")
        pol["noise_std_type"] = form
    else:
        pol = getattr(agent_cfg, "policy", None)
        if pol is None:
            raise RuntimeError("agent_cfg 에 policy 가 없다")
        prev = getattr(pol, "noise_std_type", "scalar")
        setattr(pol, "noise_std_type", form)

    if prev != form:
        log("[표준편차 형식] 체크포인트가 «%s» 이라 agent 설정을 %s -> %s 로 "
            "맞췄다 · %s" % (form, prev, form, os.path.basename(checkpoint_path)))
    else:
        log("[표준편차 형식] «%s» · 설정과 같다" % form)
    return form
