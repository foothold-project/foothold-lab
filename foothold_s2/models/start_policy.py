"""START 정책 (13-POLICY): 비대칭 actor-critic. actor 96 = o_t 45 + 지각 추정 51, critic 664 = o_t 45 + 특권 619.

설치 rsl_rl 3.1.2 의 `ActorCritic`(MLP) 를 그대로 물려받는다. 두 GRU 는 지각(start_perception) 안에 있고, actor 는 runner 가
수집 때 만든 96 차원 입력만 본다. 그래서 PPO 재평가는 rollout 버퍼에 저장된 그 입력으로만 ratio 를 낸다(12 §6.1 PPO 입력
고정). 지각 파라미터는 이 모듈에 없으므로 PPO optimizer 와 gradient 가 지각에 닿을 길이 구조적으로 없다(12 §6).

설치 `ActorCriticRecurrent` 는 1 차원 관측만 받고 actor · critic 에 GRU 를 붙이므로 쓰지 않는다(VERIFY-astra-final 5).
"""

from __future__ import annotations

from rsl_rl.modules import ActorCritic

from foothold_s2.models.start_perception import ACTOR_IN, FOOT_CELLS, MAP_CELLS, OBS_DIM

CRITIC_IN = OBS_DIM + 3 + 4 + MAP_CELLS + FOOT_CELLS  # 13 §2: o_t · v · 발 접촉 · H^b · H^f = 664
ACTOR_KEY = "actor_in"
CRITIC_KEY = "critic_in"
OBS_GROUPS = {"policy": [ACTOR_KEY], "critic": [CRITIC_KEY]}


class StartActorCritic(ActorCritic):
    def __init__(self, obs, obs_groups, num_actions, **kwargs) -> None:
        kwargs.setdefault("actor_hidden_dims", [512, 256, 128])  # 선행 Table V 353 행 · Isaac Lab Go2 cfg
        kwargs.setdefault("critic_hidden_dims", [512, 256, 128])
        kwargs.setdefault("activation", "elu")
        super().__init__(obs, obs_groups, num_actions, **kwargs)
        a = sum(obs[g].shape[-1] for g in obs_groups["policy"])
        c = sum(obs[g].shape[-1] for g in obs_groups["critic"])
        if a != ACTOR_IN or c != CRITIC_IN:
            raise ValueError(f"actor {a} · critic {c} 이 계약값 {ACTOR_IN} · {CRITIC_IN} 과 다르다")
