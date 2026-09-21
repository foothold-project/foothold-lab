# -*- coding: utf-8 -*-
"""v2b · v2a 에서 `rel_standing_envs` **한 칸만** 바꾼 판.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-21
근거: inbox/jay/20260921-v2-design.md v1.0 (커밋 c766f97) 1 절 · 1-1 절
요지: 정지를 «하한 없이» 살 수 있는지 가른다. 0.02 -> 0.10 · 4096 중 410 개
상태: 구현 · 학습 전
판: v1.0

## 왜 «복사» 가 아니라 «상속» 인가

H 를 만들 때는 F 를 통째로 복사했다. 여기서는 **물려받는다.**

이 두 판의 주장이 **「`rel_standing_envs` 하나만 다르다」**인데, 복사해 두면
그 주장이 **사람이 두 파일을 눈으로 맞춰 본 결과**가 된다. 물려받으면
**구조가 보증한다** · `standing_envs()` 말고는 덮어쓸 자리가 없다.

되읽기(`_verify_overrides`)도 v2a 것을 그대로 쓴다. 그 안의
`rel_standing_envs` 검사가 `self.standing_envs()` 를 부르므로 **v2b 에서는
0.10 을 기대하며 검사한다.**

## 대가

**주행 학습이 8 %p 줄어든다.** 4096 중 328 개가 더 서 있게 된다.
축 1 이 그만큼 나빠질 수 있고, 그것이 v2a 와 나란히 거는 이유다
(설계 1-2 절).
"""

from __future__ import annotations

from isaaclab.utils import configclass

from .v2a_env_cfg import UnitreeGo2V2aEnvCfg


REL_STANDING_ENVS = 0.10


@configclass
class UnitreeGo2V2bEnvCfg(UnitreeGo2V2aEnvCfg):
    """v2a 와 **정지 환경 비율 하나만** 다르다."""

    def standing_envs(self):
        return REL_STANDING_ENVS
