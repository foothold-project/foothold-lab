"""벌점 켜짐 비율 기록 (16 §7: 12 충돌 · 13 걸려 넘어짐 · 14 발 가장자리). Kit 없이 시험한다.

보상 함수가 매 스텝 `record(env, 이름, 값)` 으로 «값이 0 이 아닌 env 의 비율» 을 쌓고, 반복(PPO update) 이 바뀔 때마다
지난 반복의 평균 비율을 `roll` 이 내놓는다. 곡선으로 «벌점이 얼마나 자주 켜지나» 를 보려는 것이다(한 항이 항상 켜져 있거나 항상 꺼져 있으면 걸린다).
"""

import torch

NAMES = ("collision", "stumble", "foot_edge")


class PenaltyLog:
    def __init__(self, steps_per_iter=24):
        self.steps_per_iter = steps_per_iter
        self.sum = {n: None for n in NAMES}
        self.count = {n: 0 for n in NAMES}
        self.last = {n: 0.0 for n in NAMES}
        self.iteration = -1

    def add(self, name, value):
        frac = (value != 0).float().mean()
        self.sum[name] = frac if self.sum[name] is None else self.sum[name] + frac
        self.count[name] += 1

    def roll(self, iteration):
        """반복이 바뀌었으면 지난 반복의 평균 켜짐 비율을 확정한다. 돌려주는 값은 가장 최근 확정값."""
        if iteration != self.iteration:
            for n in NAMES:
                if self.count[n] > 0:
                    self.last[n] = float(self.sum[n] / self.count[n])

                self.sum[n] = None
                self.count[n] = 0

            self.iteration = iteration

        return dict(self.last)


def record(env, name, value):
    log = getattr(env, "_penalty_log", None)

    if log is None:
        log = env._penalty_log = PenaltyLog()

    log.add(name, value)

    return value


def penalty_activation(env, env_ids, steps_per_iter: int = 24):
    """curriculum term 모양: Curriculum/penalty_on/<이름> 으로 로그에 찍힌다."""
    log = getattr(env, "_penalty_log", None)

    if log is None:
        return {n: 0.0 for n in NAMES}

    return log.roll(int(env.common_step_counter // steps_per_iter))
