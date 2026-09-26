"""B 조건 · 연습 틈을 평가 틈만큼 넓힌 학습 환경.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-11
근거: sim/eval/generalization_env_cfg.py 의 MeshGapTerrainCfg.gap_width_range 실측
요지: A 와 딱 한 줄 다르다. 연습 틈 폭을 0.05~0.20 에서 0.15~0.40 으로 넓힌다
상태: 확정

왜 새 파일로 분리했는가
    A(UnitreeGo2GapEnvCfg)를 그 자리에서 고치면 A 를 다시 재현할 수 없다.
    두 조건이 각자 파일로 남아 있어야 「무엇을 바꿔서 무엇이 달라졌는가」를
    나중에 코드로 되짚을 수 있다.

무엇을 맞췄는가
    평가 하네스는 MeshGapTerrainCfg(gap_width_range=(0.15, 0.40)) 로 잰다.
    학습은 ForwardGapTerrainCfg(gap_width_range=(0.05, 0.20)) 로 했다.
    난이도 0.5 에서 평가 틈은 0.275 m 인데 학습이 본 최대 틈은 0.20 m 였다.
    한 번도 못 본 폭을 시험에서 만난 셈이다. 이 파일은 그 범위를 맞춘다.

    지형의 «모양»은 일부러 그대로 둔다. 학습은 앞쪽 슬래브 하나, 평가는 사방
    도랑이다. 모양까지 베끼면 연습을 시험지에 맞추는 것이라 일반화가 아니다.
"""

from __future__ import annotations

from isaaclab.utils import configclass

from .gap_env_cfg import UnitreeGo2GapEnvCfg

# 평가 하네스와 같은 값. 여기 하나만 고치면 된다.
EVAL_GAP_WIDTH_RANGE = (0.15, 0.40)


@configclass
class UnitreeGo2GapWideEnvCfg(UnitreeGo2GapEnvCfg):
    """A 와 동일하되 forward_gap 의 폭 범위만 평가 규격에 맞춘다."""

    def __post_init__(self):
        super().__post_init__()

        gap = self.scene.terrain.terrain_generator.sub_terrains["forward_gap"]
        gap.gap_width_range = EVAL_GAP_WIDTH_RANGE

        # 조용한 실패를 막는다. 상위 클래스가 구조를 바꾸면 여기서 바로 터진다.
        if tuple(gap.gap_width_range) != EVAL_GAP_WIDTH_RANGE:
            raise RuntimeError(
                "forward_gap 폭이 안 바뀌었다: %r" % (gap.gap_width_range,)
            )
