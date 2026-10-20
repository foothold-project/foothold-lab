"""명령 정리기 (31 §5, D39 · 팀장 결정 2 · 5). 순수 파이썬. 시계는 호출 쪽이 `dt` 로 준다(시험 가능).

이어진 지형: 학습 범위 clip 만 (vx ±1.5 · vy ±1.0 · wz ±2.0, 14 §4).
듬성한 지형: vy ±0.2(가정), 후진 -0.3 까지 + 연속 2 s · 누적 0.6 m 넘으면 vx 0, 이동 중 wz ±1.0 · 제자리(|vx|<0.3) wz ±1.2,
전진은 깃발 방식 학습 속도 상한 1.0 으로 자른다(문서에 없음: 가정).
"""

from dataclasses import dataclass, field

CONTINUOUS = "continuous"
SPARSE = "sparse"


@dataclass
class FilterParams:
    cont_vx: float = 1.5
    cont_vy: float = 1.0
    cont_wz: float = 2.0
    sparse_vx_fwd: float = 1.0
    sparse_vx_back: float = 0.3
    sparse_vy: float = 0.2
    sparse_wz_moving: float = 1.0
    sparse_wz_standing: float = 1.2
    moving_threshold: float = 0.3
    back_max_s: float = 2.0
    back_max_m: float = 0.6


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


@dataclass
class CommandFilter:
    params: FilterParams = field(default_factory=FilterParams)
    back_time: float = 0.0
    back_dist: float = 0.0
    warnings: list = field(default_factory=list)

    def reset(self):
        self.back_time = 0.0
        self.back_dist = 0.0
        self.warnings = []

    def step(self, cmd, terrain_class, dt):
        """(vx, vy, wz) -> 정리된 (vx, vy, wz). `warnings` 에 이번 스텝의 경고 이름이 쌓인다."""
        p = self.params
        vx, vy, wz = (float(c) for c in cmd)
        self.warnings = []

        if terrain_class == CONTINUOUS:
            self.back_time = 0.0
            self.back_dist = 0.0

            return (_clip(vx, -p.cont_vx, p.cont_vx), _clip(vy, -p.cont_vy, p.cont_vy), _clip(wz, -p.cont_wz, p.cont_wz))

        if terrain_class != SPARSE:
            raise ValueError("지형 등급은 continuous 또는 sparse: %r" % (terrain_class,))

        vx_c = _clip(vx, -p.sparse_vx_back, p.sparse_vx_fwd)
        vy_c = _clip(vy, -p.sparse_vy, p.sparse_vy)

        if vx_c != vx or vy_c != vy:
            self.warnings.append("sparse_range")

        if vx_c < 0.0:
            self.back_time += dt
            self.back_dist += -vx_c * dt

            if self.back_time > p.back_max_s + 1e-9 or self.back_dist > p.back_max_m + 1e-9:
                vx_c = 0.0
                self.warnings.append("back_limit")
        else:
            self.back_time = 0.0
            self.back_dist = 0.0

        limit = p.sparse_wz_moving if abs(vx_c) >= p.moving_threshold else p.sparse_wz_standing

        return (vx_c, vy_c, _clip(wz, -limit, limit))
