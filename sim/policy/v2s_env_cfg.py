# -*- coding: utf-8 -*-
"""v2s · 훈련 지형에 `stepping_stones` 를 **10 %** 넣은 혼합 판.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-25
근거: inbox/jay/20260923-lineage/AUDIT9-approve.md 6·7·8·9 절 (astra) ·
      sim/eval/generalization_env_cfg.py:75 의 평가용 생성기 설정 ·
      v2b_env_cfg.py · 2026-09-25 판정 (세 판 모두 최저 칸이 stones 0 %)
요지: `boxes` 와 `random_rough` 에서 각각 5 %p 를 떼 `stepping_stones` 0.10 을
      만든다. 아홉 종 합계 1.00.
상태: 구현 · 학습 전
판: v1.0

## 왜 이것인가

2026-09-25 판정에서 `v2b-r` · `v2g-feetair1` · `v2n-noise02` **세 판 모두**
네 체크포인트 전부의 **절대 최저 칸이 `stepping_stones` 난이도 0.5 에서
0 %** 였다. 보상을 100 배로 키워도, 노이즈를 5 분의 1 로 줄여도 안 움직였다.
**훈련 분포에 그 지형족이 아예 없다는 것**이 남은 설명이다.

## 가설은 「이 혼합」이다 · 「stones 추가 효과」가 아니다 `확인됨`

| 지형 | 대조군 (v2b) | 이 판 |
|---|---:|---:|
| pyramid_stairs | 0.15 | 0.15 |
| pyramid_stairs_inv | 0.15 | 0.15 |
| boxes | 0.15 | **0.10** |
| random_rough | 0.15 | **0.10** |
| hf_pyramid_slope | 0.10 | 0.10 |
| hf_pyramid_slope_inv | 0.10 | 0.10 |
| omni_gap | 0.10 | 0.10 |
| rails | 0.10 | 0.10 |
| **stepping_stones** | 0 | **0.10** |
| 합계 | 1.00 | 1.00 |

성적 변화에는 **줄인 두 지형의 노출 감소 효과가 같이 들어간다.**
「stones 를 넣은 효과만 독립 측정했다」고 적지 않는다 (AUDIT9 7 절).

## 평가 집합과의 관계 · 판정은 48 칸 그대로 `확인됨`

`stepping_stones` 는 `sim/eval/terrains.py` 의 `unseen10` 안에 있다.
이 판에서 그 지형은 **「미경험」이 아니다.** 그래도 판정은 바꾸지 않는다.
`CRITERIA.md` v1.4 2 절이 **「정책의 학습 지형에 따라 경험 분류를 다시 하고
판정은 전체 48 칸으로 유지」** 를 이미 규정한다. 이미 v2a·v2b 가 그 묶음의
`rails` 를 학습한다.

    경험 계열     21 칸 -> 24 칸
    도랑이 닿는   3 칸  -> 3 칸
    학습에 없던   24 칸 -> 21 칸
    판정 합계     48 칸 (그대로)

주장할 수 있는 것은 **「경험한 stones 계열의 새 인스턴스 성능」** 이다.
**「미경험 stones 일반화」가 아니다** (AUDIT9 9 절).

## 생성기는 평가용과 **같게** 둔다

`sim/eval/generalization_env_cfg.py:75` 의 값을 그대로 쓴다. 돌 크기·높이·
간격을 동시에 바꾸면 「노출」과 「기하 변경」이 섞인다. 물음을 하나로 둔다 ·
**「이 기하를 훈련에 노출하면 현재의 약점을 배울 수 있는가」**.

## 난이도 0.1 에는 틈이 «없다» `확인됨`

`hf_terrains.py:373~385` 이 간격 `0.08 + 0.12d` 를 구한 뒤 `horizontal_scale`
0.1 로 나누고 **정수로 자른다.**

    d=0.1   명목 0.092 m -> 0 셀      틈이 «없다»
    d=0.5   명목 0.140 m -> 1 셀
    d=0.9   명목 0.188 m -> 1 셀

그래서 「난이도 0.1 에서 성공한다」는 능력의 근거가 아니다. 이 판은 10 행
curriculum 을 물려받고 초기 레벨이 최대 2 라서 **초반에는 틈이 없는 구간에만
머무를 수 있다.** 그러므로 stones 전용 레벨과 **실제 틈 노출을 따로 본다.**
전 지형 평균 레벨로 대신하지 않는다 (AUDIT9 9 절).

## 왜 `v2b` 를 상속하는가 `확인됨`

대조군이 `v2b-r` 이므로 `v2b`(정지 비율 0.10)를 물려받는 것이 의도를 가장 잘
드러낸다. `v2a`(0.02) 를 물려받고 손으로 맞추면 누락 위험이 크다.

## 검사를 «완성 뒤» 에 한 번 더 하는 까닭 `확인됨`

부모 `v2a_env_cfg.py:125` 는 자기 `__post_init__` **끝에서**
`self._verify_overrides()` 를 부른다. 검사 함수만 갈아끼우면 **stones 를 아직
넣지 않은 시점에** 아홉 칸을 기대하는 검사가 돈다.

그래서 이 판은 **부모 검사를 여덟 칸 상태로 통과시킨 뒤** stones 혼합을
적용하고 **자기 최종 검사를 따로** 돈다 (AUDIT9 8 절).

## 모듈 전역 비중 표를 «건드리지 않는다» `확인됨`

`TERRAIN_PROPORTIONS` 는 `v2a_env_cfg.py` 의 모듈 전역이고 `v2a` 도 `v2b` 도
그것을 **부를 때** 읽는다. 실행 중에 바꾸면 **v2a·v2b 까지 같이 바뀌고
오류가 안 난다.** 이 파일은 지역 표만 쓴다.
"""

from __future__ import annotations

import isaaclab.terrains as terrain_gen
from isaaclab.utils import configclass

from .v2b_env_cfg import UnitreeGo2V2bEnvCfg


# **이 파일의 지역 표다.** v2a 의 모듈 전역을 건드리지 않는다.
MIXED_PROPORTIONS = {
    "pyramid_stairs": 0.15,
    "pyramid_stairs_inv": 0.15,
    "boxes": 0.10,            # 0.15 에서 5 %p
    "random_rough": 0.10,     # 0.15 에서 5 %p
    "hf_pyramid_slope": 0.10,
    "hf_pyramid_slope_inv": 0.10,
    "omni_gap": 0.10,
    "rails": 0.10,
    "stepping_stones": 0.10,  # 떼어 온 10 %p
}

# `sim/eval/generalization_env_cfg.py:75` 와 **같은 값**이다.
STONES = dict(
    stone_height_max=0.12,
    stone_width_range=(0.35, 0.65),
    stone_distance_range=(0.08, 0.20),
    holes_depth=-1.0,
    platform_width=1.5,
    border_width=0.25,
)


@configclass
class UnitreeGo2V2sEnvCfg(UnitreeGo2V2bEnvCfg):
    """v2b 와 **훈련 지형 혼합 하나만** 다르다."""

    def __post_init__(self):
        # 1) 부모를 «여덟 칸 상태로» 끝까지 돌린다. 부모 검사가 여기서 돈다.
        super().__post_init__()

        # 2) 그 «뒤에» 혼합을 적용한다.
        terrains = self.scene.terrain.terrain_generator.sub_terrains
        terrains["stepping_stones"] = terrain_gen.HfSteppingStonesTerrainCfg(
            proportion=MIXED_PROPORTIONS["stepping_stones"], **STONES)
        for name, want in MIXED_PROPORTIONS.items():
            terrains[name].proportion = want

        # 3) 그리고 «내» 최종 검사를 돈다.
        self._verify_mixture()

    def _verify_mixture(self):
        """아홉 키 · 각 비중 · 합계를 되읽는다. 어긋나면 학습을 시작하지 않는다."""
        problems = []
        terrains = self.scene.terrain.terrain_generator.sub_terrains

        if set(terrains) != set(MIXED_PROPORTIONS):
            problems.append("지형 키가 아홉이 아니다: %r" % sorted(terrains))
        for name, want in MIXED_PROPORTIONS.items():
            got = getattr(terrains.get(name), "proportion", None)
            if got != want:
                problems.append("비중 %s: %r (기대값 %r)" % (name, got, want))

        # **합을 따로 센다.** 아홉 칸이 각각 맞아도 합이 1 이 아니면 표본이 밀린다.
        total = sum(getattr(terrains[n], "proportion", 0.0) for n in terrains)
        if abs(total - 1.0) > 1e-9:
            problems.append("비중 합이 1 이 아니다: %r" % total)

        # 생성기 «종류» 와 기하까지 본다. 이름만 맞고 다른 지형일 수 있다.
        st = terrains.get("stepping_stones")
        if not isinstance(st, terrain_gen.HfSteppingStonesTerrainCfg):
            problems.append("stepping_stones 가 HfSteppingStonesTerrainCfg 가 아니다")
        else:
            for key, want in STONES.items():
                got = getattr(st, key, None)
                if isinstance(want, tuple):
                    bad = got is None or tuple(got) != tuple(want)
                else:
                    bad = got != want
                if bad:
                    problems.append("stones %s: %r (기대값 %r)" % (key, got, want))

        # **대조군과 같아야 하는 것들을 여기서 한 번 더 본다.**
        # 이 판의 주장이 「지형 혼합 하나만 다르다」이기 때문이다.
        command = self.commands.base_velocity
        noise = self.observations.policy.height_scan.noise
        scanner = self.scene.height_scanner
        same = (
            ("rel_standing_envs", command.rel_standing_envs, 0.10),
            ("lin_vel_x", command.ranges.lin_vel_x, (0.4, 1.5)),
            ("ang_vel_z", command.ranges.ang_vel_z, (-1.0, 1.0)),
            ("height_scan noise", (noise.n_min, noise.n_max), (-0.1, 0.1)),
            ("ray_cast_drift_range", tuple(scanner.ray_cast_drift_range.values()),
             ((0.0, 0.0), (0.0, 0.0), (0.0, 0.0))),
            ("scanner offset", tuple(scanner.offset.pos), (0.0, 0.0, 20.0)),
            ("enable_corruption", self.observations.policy.enable_corruption, True),
            ("max_init_terrain_level", self.scene.terrain.max_init_terrain_level, 2),
        )
        for name, got, want in same:
            if got != want:
                problems.append("대조군과 달라졌다 · %s: %r (기대값 %r)"
                                % (name, got, want))

        if problems:
            raise ValueError(
                "v2s 혼합 검사 실패 · 학습을 시작하지 «않는다»:\n  - "
                + "\n  - ".join(problems))
