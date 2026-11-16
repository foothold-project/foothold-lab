"""HiPAN 모드 2 주행 평가 (설계 §3 N4 · §8): 에피소드마다 SR · SPL (0.2 m 문턱) · 충돌 수를 `nav_score` 로 센다.
`evaluate` 는 환경 (`TeacherVecEnv` 꼴: n · task · state · step) 과 `act(o) -> (n,3)` 정책을 받는다. env 마다 첫 에피소드 하나씩 (끝남 · 목표 모두 도달 · 최대 틱) 을 재고 끝낸다.
CLI: `--env-factory 모듈:함수` 가 (env, act) 를 돌려준다. 결과 json 은 덮어쓰지 않는다. GPU 평가라 승인 불필요 (학습 아님).
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np


def evaluate(env, act, o, *, max_ticks: int = 600) -> dict:
    """o = env.reset() 의 첫 관측. 돌려주는 값: `nav_score.aggregate` 결과 + 에피소드 수."""
    from foothold_s2.nav import nav_score, teacher_obs

    n = env.n
    task = env.task
    def pos():
        org = None if task.origin_xy is None else np.asarray(task.origin_xy)
        return teacher_obs.to_room_frame(env.state.pos_local, org)[:, :2]
    start, goal, rid = pos().copy(), task.goal.copy(), task.room_id.copy()
    traj = [[start[i]] for i in range(n)]
    finished = np.zeros(n, bool)
    collisions = np.zeros(n, int)
    for _ in range(max_ticks):
        a = act(o)
        o = env.step(a)
        o = o[0] if isinstance(o, tuple) else o
        p, st = pos(), env.state
        done = np.asarray(st.done, bool)
        reached = np.array([q.all_reached for q in task.pgcl])
        for i in np.flatnonzero(~finished):
            if not done[i]:                                  # 끝난 틱의 위치는 새 에피소드 값이라 궤적에 넣지 않는다
                traj[i].append(p[i])
            collisions[i] += int(bool(st.collision[i]))
        finished |= done | reached
        if finished.all():
            break
    eps = []
    for i in range(n):
        g = task.assets[rid[i]].grade
        eps.append(nav_score.score_episode(np.array(traj[i]), goal[i], nav_score.shortest_length(g, start[i], goal[i]), int(collisions[i])))
    return {**nav_score.aggregate(eps), "episodes": n}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--env-factory", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--max-ticks", type=int, default=600)
    a = p.parse_args(argv)
    import importlib
    mod, _, fn = a.env_factory.partition(":")
    env, act = getattr(importlib.import_module(mod), fn)()
    result = evaluate(env, act, env.reset(), max_ticks=a.max_ticks)
    with open(a.out, "x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
