# -*- coding: utf-8 -*-
"""v2n · v2b 에서 `height_scan` 백색 잡음 **한 칸만** 줄인 판.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-24
근거: inbox/jay/20260921-perception-research/SYNTHESIS.md 6 절 1 순위 ·
      inbox/jay/20260923-lineage/AUDIT8-plan.md v1.1 「다음 관측 시험은
      백색잡음만 줄이는 N 이 명료하다」 · v2b_env_cfg.py
요지: 셀별 백색 잡음 진폭을 ±0.10 -> ±0.02. 그 밖에는 v2b 와 같다.
상태: 구현 · 학습 전
판: v1.0

## 무엇을 묻는가

**「매 정책 스텝 셀마다 다시 뽑히는 높이 오차가 학습을 방해했는가」** 하나다.

돌 하나가 옆 구멍보다 0.12 m 높다고 하자. 지금 잡음은 ±0.10 m 라서
돌은 0.02~0.22 로, 구멍은 -0.10~+0.10 으로 읽힌다. **두 구간이 겹친다.**
어느 순간에는 구멍이 돌보다 높게 읽힌다. ±0.02 로 줄이면 돌은
0.10~0.14, 구멍은 -0.02~+0.02 로 **겹치지 않는다.**

대칭 균일분포 U(-a, a) 의 표준편차는 a/√3 이므로 0.0577 -> 0.0115 m,
분산으로 25 분의 1 이다 (AUDIT8 v1.1).

## 왜 «v2c 가 아니라» v2b 를 물려받는가 `확인됨`

`sim/policy/v2c_env_cfg.py` 는 **v2a** 를 물려받는다. v2a 의 정지 비율은
0.02 이고 기준선 r 이 쓰는 v2b 는 0.10 이다. v2c 는 그 칸을 안 덮어쓴다.
**v2c 를 r 과 비교하면 잡음 말고 정지 비율도 같이 바뀐다.** 한 실험에
가설 하나라는 규칙이 깨진다. 그래서 새로 만든다 (AUDIT8 v1.1).

## 무엇을 «안» 바꾸는가

    ray_cast_drift_range   (0,0) 그대로. 드리프트는 **다른 물음** 이다.
    offset.pos             (0,0,20) 그대로. 격자 이동은 **다른 물음** 이다.
    enable_corruption      True 그대로. 통째로 끄면 고유수용 잡음까지
                           달라져 height_scan 만의 시험이 아니게 된다.
    나머지 전부            v2b 상속 · 덮어쓸 자리가 이 파일에 없다.

## 대조

    R0  기준선          v2b · 잡음 ±0.10        = v2b-r / v2b-p11
    N   이 파일         v2b · 잡음 ±0.02        <- 이 한 칸만 다르다
"""

from __future__ import annotations

from isaaclab.utils import configclass

from .v2b_env_cfg import UnitreeGo2V2bEnvCfg


HEIGHT_SCAN_NOISE = (-0.02, 0.02)


@configclass
class UnitreeGo2V2nEnvCfg(UnitreeGo2V2bEnvCfg):
    """v2b 와 **셀별 백색 잡음 진폭 하나만** 다르다."""

    def height_scan_noise(self):
        return HEIGHT_SCAN_NOISE
