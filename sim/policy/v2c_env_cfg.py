# -*- coding: utf-8 -*-
"""v2c · v2a 에서 **높이 격자 잡음 모델만** 바꾼 판.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-21
근거: 리드 지각 조사 · IsaacLab `ray_caster.py` 실측 · 돌아간 v2a 의 `params/env.yaml`
요지: 상관 드리프트를 켜고 셀별 백색 잡음을 줄인다. 논문들이 쓰는 모양으로 맞춘다
상태: 구현 · **학습 전 · 팀장 승인 전이라 안 걸었다**
판: v1.0

## 무엇을 바꾸나 · 두 칸

```
ray_cast_drift_range   x·y·z  (0,0)  ->  (-0.05, 0.05)     켠다
height_scan 잡음              ±0.10  ->  ±0.02             줄인다
```

**나머지는 v2a 를 그대로 물려받는다.** 지형 · 명령 · `rel_standing` ·
격자 위치 · 보상 · 관측 차원(235) 전부 안 건드린다.

## 두 잡음은 «주기» 가 다르다 `확인됨`

소비 지점을 읽어 확인했다.

| | 언제 다시 뽑히나 | 근거 |
|---|---|---|
| `ray_cast_drift` | **에피소드마다 · 환경마다** | `ray_caster.py:129~137` 이 `reset(env_ids)` 안에 있고, `step()` 이 끝난 환경만 골라 `_reset_idx` -> `scene.reset` 으로 부른다 (`manager_based_rl_env.py:221 · 358`) |
| `height_scan` 잡음 | **매 정책 스텝** | 관측 손상은 관측을 만들 때마다 걸린다 |

우리 설정은 정책 스텝 0.02 s · 에피소드 20 s 라 **한 에피소드가 1000
스텝**이다. 곧 드리프트 한 번에 백색 잡음 **1000 번**이다.

**AME-1 원문은 "at the beginning of training"** 이라 «학습 전체에 한 번»
인데, IsaacLab 기구는 «에피소드마다» 다. **둘은 다르다.** 다만 MARG ·
AME-2 · Zhang · Hwang 이 쓰는 「에피소드 단위 상관 드리프트」와는 맞는다.
**이 판은 후자를 따른다** · 전자는 IsaacLab 기구로 바로 안 된다.

## 적용되는 자리

`ray_cast_drift` 는 세 갈래로 걸린다 (`ray_caster.py`).

```
x·y   268 · 276 · 283 행   광선 출발점을 수평으로 민다
z     308 행               맞은 점의 높이에 더한다
```

**셀별로 다른 값이 아니라 그 환경의 격자 «전체» 가 같이 움직인다.** 그것이
「상관」이라는 말의 뜻이고, 지금 우리 백색 잡음과 다른 점이다.

## 안 바꾼 것을 적어 둔다

`drift_range` (센서 몸체 위치 드리프트) 는 **그대로 (0,0)** 이다. 조사에서
나온 것은 `ray_cast_drift_range` 쪽이고, 둘을 같이 켜면 한 판에 손잡이가
둘이 된다.
"""

from __future__ import annotations

from isaaclab.utils import configclass

from .v2a_env_cfg import UnitreeGo2V2aEnvCfg


SCANNER_DRIFT_RANGE = {
    "x": (-0.05, 0.05), "y": (-0.05, 0.05), "z": (-0.05, 0.05),
}
HEIGHT_SCAN_NOISE = (-0.02, 0.02)


@configclass
class UnitreeGo2V2cEnvCfg(UnitreeGo2V2aEnvCfg):
    """v2a 와 **잡음 모델 두 칸만** 다르다."""

    def scanner_drift_range(self):
        return SCANNER_DRIFT_RANGE

    def height_scan_noise(self):
        return HEIGHT_SCAN_NOISE
