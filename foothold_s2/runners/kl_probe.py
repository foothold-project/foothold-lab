"""조건부 policy KL 기록 (SONNET-X11 X6). Kit 없이 시험된다. scheduler 에 연결하지 않는다(기록만).

두 값을 따로 잰다. 둘 다 «같은 저장 history · 같은 hidden · 같은 epsilon» 에서 행동 분포 pi(a | o, est) 의 대각 가우시안 KL(전 || 후), 12 차원 합.
(a) PPO 전후: actor 입력(저장된 rollout)은 그대로, theta(actor)만 PPO update 로 바뀐다.
(b) 지각 phi 전후: theta 는 고정(PPO 가 끝난 값), phi(지각 모듈)만 update_perception 으로 바뀌어 같은 history · hidden · epsilon 으로 다시 계산한 est 가 달라진다.
    est mask(EX-11)가 켜져 있으면 actor 입력의 est 가 0 이라 (b) 는 정확히 0 이다.
z 를 두 번 새로 뽑지 않는다: epsilon 은 이 iteration 의 고정 시드로 한 번 정하고 전 · 후에 같은 것을 쓴다. 조건부 가우시안 KL 이며 잠재변수를 섞은 정책의 marginal KL 이 아니다.
hidden: 재생 버퍼에 저장된 rollout 시작 hidden(옛 값)에서 시퀀스를 다시 계산한다(phi 전 · 후 모두 같은 시작 hidden).
"""

from __future__ import annotations

import torch

BRANCHES = ("walk", "spin", "stand")


def gaussian_kl(mu0, std0, mu1, std1):
    """KL( N(mu0, std0^2) || N(mu1, std1^2) ) 을 마지막 차원(12)에서 합. 입력 (..., 12)."""
    return (torch.log(std1 / std0) + (std0 ** 2 + (mu0 - mu1) ** 2) / (2.0 * std1 ** 2) - 0.5).sum(dim=-1)


def command_branch(cmd: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    """명령 (…,3) 을 가지 번호로: 0 walk(vx>0) · 1 spin(vx=0 이고 wz != 0) · 2 stand(셋 모두 0)."""
    # Side and diagonal EX-39 commands are locomotion, not stand.
    walk = (cmd[..., :2].abs() > eps).any(dim=-1)
    spin = (~walk) & (cmd[..., 2].abs() > eps)

    return torch.where(walk, torch.zeros_like(walk, dtype=torch.long), torch.where(spin, torch.ones_like(walk, dtype=torch.long), torch.full_like(walk, 2, dtype=torch.long)))


def summarize(kl: torch.Tensor, branch: torch.Tensor) -> dict:
    """전체와 가지별 평균 · p95 · max · 표본 수."""
    def one(x):
        if x.numel() == 0:
            return {"n": 0, "mean": None, "p95": None, "max": None}

        return {"n": int(x.numel()), "mean": float(x.mean()), "p95": float(torch.quantile(x.flatten().float(), 0.95)), "max": float(x.max())}

    flat, br = kl.flatten().float(), branch.flatten()
    out = {"all": one(flat)}

    for i, name in enumerate(BRANCHES):
        out[name] = one(flat[br == i])

    return out


def policy_dist(policy, actor_obs_td):
    """정책(StartActorCritic · ActorCritic)의 행동 분포 (mean, std) 를 샘플링 없이. policy.distribution 을 덮어쓰지만 PPO 는 매 스텝 다시 만든다."""
    with torch.no_grad():
        x = policy.actor_obs_normalizer(policy.get_actor_obs(actor_obs_td))
        policy._update_distribution(x)

        return policy.distribution.mean.clone(), policy.distribution.stddev.clone()
