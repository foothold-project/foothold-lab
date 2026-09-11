# -*- coding: utf-8 -*-
"""바닥 없는 지형에서 빗나간 광선을 다루는 높이 스캔.

분류: 운영
작성: 오흥재 · 2026-09-11 15:10
근거: IsaacLab 의 `gap_training/gap_observations.py` 와 기본 `mdp.height_scan` 을 직접 읽고 옮김
요지: 평가 하네스가 저장소 «밖» 코드에 기대지 않게, 같은 계산을 여기에 둔다
상태: 확정

왜 여기 있나
    2026-09-11 까지 `generalization_env_cfg.apply_gap_aware_scan` 은 이 함수를
    IsaacLab 의 `isaaclab_tasks...gap_training.gap_observations` 에서 가져왔다.
    그건 **이 저장소 밖**이다.

    `git pull origin main` 만 받은 사람이 그 IsaacLab 판을 안 갖고 있으면
    **규격 2 로 평가할 수 없다.** 기본값이 규격 2 인데 기본 경로가 깨진다.
    검증에서 「공개 재현을 막는 누락 의존성」으로 걸렸다.

무엇을 하나
    높이 스캔은 몸통 아래로 광선을 쏘아 «내 몸통이 그 지점보다 얼마나 높은가» 를
    잰다. 계산은 IsaacLab 기본 함수와 **글자 그대로 같다**.

        height = 몸통높이 - 광선이 닿은 높이 - offset

    다른 것은 **광선이 아무것도 못 맞혔을 때** 하나뿐이다.

        기본 함수    닿은 높이가 inf 라 결과가 -inf 가 되고, 관측 클리핑이 -1 로 자른다
                     이 눈금에서 -1 은 「내 몸통보다 offset 만큼 넘게 솟은 것」, 곧 벽이다
        이 함수      그 자리에 `miss_value`(기본 +1.0)를 넣는다
                     양수는 「바닥이 아래로 멀다」는 뜻이라 구멍의 올바른 표현이다

    학습(`Isaac-Velocity-Gap-Unitree-Go2-v0`)이 쓰는 값과 같다. 임석헌의 원격 평가
    설정도 `miss_value=1.0` 이었다 (`lim-gap_stop_10-environment.yaml:532`).

    **기본 함수가 틀린 것이 아니다.** 바닥 없는 지형을 상정하고 만든 것이 아닐 뿐이다.
    험지에는 구멍이 없어 inf 가 들어올 일이 없다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch

# **이름표로만 쓴다.** 예전에는 그냥 import 라, 이 함수를 시험하려면 Isaac 을
# 통째로 띄워야 했다. 그래서 「빗나간 광선에 +1 이 들어가는가」를 시험 모음에
# 넣을 수가 없었고, 우리 평가의 핵심 한 줄이 관문 없이 남아 있었다
# `확인됨` (2026-09-11 · omni 없이 부르면 ModuleNotFoundError).
#
# 계산은 torch 뿐이다. 이제 Isaac 밖에서도 부를 수 있고, 시험이 돈다.
if TYPE_CHECKING:  # pragma: no cover
    from isaaclab.managers import SceneEntityCfg
    from isaaclab.sensors import RayCaster


def height_scan_with_gap(env, sensor_cfg: "SceneEntityCfg", offset: float = 0.5,
                         miss_value: float = 1.0) -> torch.Tensor:
    """빗나간 광선을 «깊은 낭떠러지» 로 읽는 높이 스캔.

    Args:
        env: 환경. `env.scene.sensors[sensor_cfg.name]` 로 센서를 찾는다
        sensor_cfg: 높이 스캐너. Go2 는 `height_scanner`
        offset: 기본 함수와 같은 값을 쓴다. 학습·평가 모두 0.5
        miss_value: 광선이 아무것도 못 맞혔을 때 넣을 값. 규격 2 는 +1.0

    Returns:
        `(환경 수, 광선 수)` 텐서. Go2 는 광선 187개다.
    """
    sensor: "RayCaster" = env.scene.sensors[sensor_cfg.name]
    ray_hit_z = sensor.data.ray_hits_w[..., 2]

    # 기본 함수(`isaaclab.envs.mdp.observations.height_scan`)와 같은 식이다.
    height = sensor.data.pos_w[:, 2].unsqueeze(1) - ray_hit_z - offset

    # **못 맞힌 광선을 가른다.** 맞힌 좌표의 초기값이 inf 라(`warp/ops.py`),
    # 못 맞히면 그대로 inf 가 남고 위 식이 -inf 가 된다. NaN 도 같이 잡는다.
    valid_hit = torch.isfinite(ray_hit_z) & torch.isfinite(height)

    # 양수로 포화된 값은 «로봇 한참 아래의 지형» 을 뜻하지, 높은 벽이 아니다.
    return torch.where(valid_hit, height, torch.full_like(height, float(miss_value)))
