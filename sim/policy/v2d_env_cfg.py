# -*- coding: utf-8 -*-
"""v2d · v2a 에서 **높이 격자 위치만** 앞으로 민 판.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-21
근거: 리드 지각 조사 · IsaacLab `ray_caster.py:224` · 돌아간 v2a 의 `params/env.yaml`
요지: 격자를 0.2 m 앞으로 민다. 광선 수 · 관측 차원 · 가중치가 그대로다
상태: 구현 · **학습 전 · 팀장 승인 전이라 안 걸었다**
판: v1.0

## 무엇을 바꾸나 · 한 칸

```
height_scanner.offset.pos   (0.0, 0.0, 20.0)  ->  (0.2, 0.0, 20.0)
```

**그것 하나다.** 지형 · 명령 · `rel_standing` · 잡음 모델 · 보상 전부
v2a 그대로다.

## 왜 차원이 안 바뀌나 `확인됨`

`ray_caster.py:224` 가 `self.ray_starts += offset_pos` 다. **격자를 통째로
옮길 뿐 광선을 더하거나 빼지 않는다.** 그래서 187 개 · 235 차원이 그대로다.

```
격자      resolution 0.1 · size (1.6, 1.0)  ->  17 x 11 = 187
offset x  0.0  ->  몸통 기준 -0.8 ~ +0.8 m
offset x  0.2  ->  몸통 기준 -0.6 ~ +1.0 m
```

**앞을 0.2 m 더 보고 뒤를 0.2 m 덜 본다.** 지금은 광선의 절반을 몸통
«뒤» 에 쓰고 있다.

## 근거의 한계 · 숨기지 않는다

START (arXiv 2512.13153 p.3 II-B) 가 뒤 0.5 m ~ 앞 1.1 m 를 쓴다는 것이
근거인데, **그 논문은 전방 깊이 카메라를 쓰고 우리는 아래로 쏘는
레이캐스트**다. 격자 범위를 그대로 옮겨 쓸 수 있다는 보장이 없다.

그리고 **MARG (T-RO 2025) 는 우리와 «한 자리도 안 다른» 격자**
(187 개 · 1.6 x 1.0 m · 몸통 중심) 로 실기에서 65 cm 갭을 건넌다.
**곧 「뒤를 절반 본다」가 그 자체로 결함이라는 근거는 없다.** 이 판은
「앞을 더 보면 나아지나」를 **재 보는 것**이지 고치는 것이 아니다.

`0.2` 를 고른 까닭도 논문이 아니라 **작게 밀어 본다** 는 것뿐이다
`미확인`. 뒤 0.6 m 는 남겨 둔다.
"""

from __future__ import annotations

from isaaclab.utils import configclass

from .v2a_env_cfg import UnitreeGo2V2aEnvCfg


SCANNER_OFFSET_POS = (0.2, 0.0, 20.0)


@configclass
class UnitreeGo2V2dEnvCfg(UnitreeGo2V2aEnvCfg):
    """v2a 와 **격자 위치 한 칸만** 다르다."""

    def scanner_offset_pos(self):
        return SCANNER_OFFSET_POS
