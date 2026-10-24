"""창 3 처방 축 1(종아리 펴짐 한계 띠 벌점)을 켤 때의 재개 관문 (SONNET-X25 W3-T2, 설계 초안 DESIGN-W3 §3.1 · §6). isaaclab 을 import 하지 않는다(CPU 시험).

- ENV_ALLOWED: 부모(창 2 자식) 대비 자식(창 3)의 env.yaml 에서 허용하는 경로. 설계에 적힌 칸 하나뿐이다. 이 밖의 차이는 기존대로 학습 전에 멈춘다.
- prescription_receipt: 창 3 영수증에 적을 «처방 축 1 · 식 · m · w · 잎 해시».
- check_pair_same: 두 판(EX-30 · EX-31)이 같은 처방 잎을 가졌는지(한 판만 넣으면 거절).
"""

from __future__ import annotations

import hashlib
import json

from foothold_s2.runners.stage_transfer import load_dumped_yaml

TERM = "calf_ext_limit_band"
PREFIX = f"rewards.{TERM}"
ENV_ALLOWED = (f"{PREFIX}.*",)
FORMULA = "r = - w * sum_{j in calf 네 관절} max(0, q_j - (hard_hi_j - m)),  hard_hi 는 시뮬레이터 data.joint_pos_limits 에서"


def _leaves(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _leaves(v, f"{prefix}.{k}" if prefix else str(k))
    else:
        yield prefix, obj


def prescription_leaves(env_yaml_path) -> dict:
    """env.yaml 에서 처방 항(rewards.calf_ext_limit_band) 아래 모든 잎. 항이 없으면 빈 dict."""
    leaves = dict(_leaves(load_dumped_yaml(env_yaml_path)))

    return {k: v for k, v in leaves.items() if k.startswith(PREFIX + ".")}


def prescription_receipt(env_yaml_path) -> dict:
    leaves = prescription_leaves(env_yaml_path)
    if not leaves:
        raise ValueError(f"{env_yaml_path}: {PREFIX} 항이 없다(처방을 켜지 않은 판)")
    weight = leaves.get(f"{PREFIX}.weight")
    if weight is None or float(weight) == 0.0:
        raise ValueError(f"{PREFIX}.weight 가 없거나 0 이다(꺼져 있다): {weight!r}")
    margin = leaves.get(f"{PREFIX}.params.margin")
    blob = json.dumps({k: leaves[k] for k in sorted(leaves)}, ensure_ascii=False, default=str, sort_keys=True)

    return {"axis": 1, "term": TERM, "formula": FORMULA, "weight": float(weight), "margin": None if margin is None else float(margin), "leaves": len(leaves),
            "leaves_sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest()}


def check_pair_same(env_yaml_a, env_yaml_b) -> dict:
    """두 판의 처방 영수증이 같아야 한다(가중치 · 띠 폭 · 모든 잎). 한 판에만 있거나 다르면 ValueError."""
    ra, rb = prescription_receipt(env_yaml_a), prescription_receipt(env_yaml_b)
    if ra != rb:
        raise ValueError(f"두 판의 처방이 다르다: {ra} 대 {rb}")

    return ra
