"""PGCL 부목표 (PLAN-HIPAN-V2 §5.4 · M6 · 22-NAV-ENV §4). numpy 만.

경로 (m 점 열) 에서 d 간격 부목표를 뽑고, 듬성한 지형 띠 (SPARSE) 입구마다 진입 방향 부목표 둘 (입구 앞 0.5 m 와 입구, 경로 방향) 을 끼운다.
수준 k 의 d = d0 + (k - 1) * step (논문: 1 m 에서 시작, 수준마다 +1 m). 수준 올림: 그 수준의 부목표를 순서대로 모두 닿아야 (0.1 m 안).
마지막 수준: d 가 경로 길이 이상이면 목표만 남고, 거기서 연속 final_successes (가정 3) 회 성공하면 새 시작 · 목표를 요청한다.
teacher 만 본다 (student 는 최종 목표만).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from foothold_s2.nav import grade_map as gm

REACH_M = 0.1
ENTRY_BEFORE_M = 0.5


@dataclass(frozen=True)
class Subgoal:
    point: tuple
    kind: str        # "path" | "entry_before" | "entry" | "goal"
    s: float         # 경로 위 호흡 길이 m


def _arc(points):
    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(seg)])


def _at(points, arc, s):
    s = float(np.clip(s, 0.0, arc[-1]))
    i = int(np.searchsorted(arc, s, side="right") - 1)
    i = min(i, len(points) - 2)
    t = 0.0 if arc[i + 1] == arc[i] else (s - arc[i]) / (arc[i + 1] - arc[i])
    return points[i] + t * (points[i + 1] - points[i])


def path_subgoals(points, d: float, g: gm.GradeMap | None = None) -> list:
    """d 간격 부목표 ceil(L / d) 개 (마지막은 목표) + 진입 방향 부목표. g 가 없으면 진입 부목표 없음."""
    P = np.asarray(points, dtype=float)
    if P.ndim != 2 or P.shape[1] != 2 or len(P) < 2 or d <= 0:
        raise ValueError("points must be (K>=2, 2) and d > 0")
    arc = _arc(P)
    L = float(arc[-1])
    n = int(np.ceil(L / d - 1e-9))
    out = [Subgoal(tuple(_at(P, arc, min(d * (k + 1), L))), "path", min(d * (k + 1), L)) for k in range(n)]
    out[-1] = Subgoal(tuple(P[-1]), "goal", L)
    if g is not None:
        fine = np.arange(0.0, L, g.res / 2)
        samples = np.array([_at(P, arc, s) for s in fine])
        cells = (samples / g.res).astype(int)
        sparse = g.grade[cells[:, 0], cells[:, 1]] == gm.SPARSE
        enter = np.nonzero(sparse[1:] & ~sparse[:-1])[0] + 1
        for i in enter:
            a, b = samples[max(i - 3, 0)], samples[min(i + 3, len(samples) - 1)]
            u = (b - a) / max(np.linalg.norm(b - a), 1e-9)
            e = samples[i]
            s_e = float(fine[i])
            out.append(Subgoal(tuple(e - ENTRY_BEFORE_M * u), "entry_before", max(s_e - ENTRY_BEFORE_M, 0.0)))
            out.append(Subgoal(tuple(e), "entry", s_e))
        out.sort(key=lambda sg: (sg.s, 0 if sg.kind != "goal" else 1))
    return out


class PGCL:
    def __init__(self, d0: float = 1.0, step: float = 1.0, reach_m: float = REACH_M, final_successes: int = 3):
        if d0 <= 0 or step <= 0 or reach_m <= 0 or final_successes < 1:
            raise ValueError("d0, step, reach_m > 0 and final_successes >= 1 required")
        self.d0, self.step, self.reach_m, self.final_successes = d0, step, reach_m, final_successes
        self.level = 1
        self.streak = 0
        self.needs_new_task = False
        self._sub: list = []
        self._i = 0
        self._length = 0.0

    @property
    def d(self) -> float:
        return self.d0 + (self.level - 1) * self.step

    @property
    def is_final(self) -> bool:
        return bool(self._sub) and self.d >= self._length

    def start_episode(self, points, g: gm.GradeMap | None = None) -> list:
        P = np.asarray(points, dtype=float)
        self._length = float(_arc(P)[-1])
        self._sub = path_subgoals(P, self.d, g)
        if self.is_final:                                  # 마지막 수준: 목표만
            self._sub = [sg for sg in self._sub if sg.kind == "goal"]
        self._i = 0
        self.needs_new_task = False
        return list(self._sub)

    @property
    def target(self):
        return self._sub[self._i] if self._i < len(self._sub) else None

    @property
    def all_reached(self) -> bool:
        return bool(self._sub) and self._i >= len(self._sub)

    def update(self, pos_xy):
        """현재 위치로 순서대로 도달 판정. 앞 부목표를 건너뛴 도달은 세지 않는다. 지금 목표 (없으면 None) 를 돌려준다."""
        p = np.asarray(pos_xy, dtype=float)
        while self._i < len(self._sub) and np.linalg.norm(p - np.asarray(self._sub[self._i].point)) <= self.reach_m:
            self._i += 1
        return self.target

    def end_episode(self) -> str:
        """에피소드 끝. 모두 닿았으면 성공: 중간 수준은 +1, 마지막 수준은 연속 성공 횟수 +1 (가득 차면 새 과제 요청). 아니면 수준 유지, 연속 횟수 0."""
        if not self.all_reached:
            self.streak = 0
            return "hold"
        if self.is_final:
            self.streak += 1
            if self.streak >= self.final_successes:
                self.needs_new_task, self.streak = True, 0
                return "new_task"
            return "final_success"
        self.level += 1
        return "level_up"
