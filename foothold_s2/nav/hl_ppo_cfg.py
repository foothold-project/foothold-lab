"""HiPAN 모드 2 teacher 의 PPO 설정과 관측 인코더 모양 (설계 §3 N3 · PLAN-HIPAN-V2 M10). CPU 에서 모양 · 차원만 시험한다 (학습 루프는 Kit 환경이 필요).

논문이 값을 적지 않은 칸은 ASSUMED 에 이름을 모았다: 영수증에 그대로 찍혀 「가정」 임이 보인다. 근거 있는 값: env 1,024 · latent 32 · 저장 50 회마다 (설계 §3 · §5 · §8).
teacher 관측 = `teacher_obs.TeacherObsLayout` 의 한 줄 벡터 (o_p 45 · c_prev 3 · x_m 6 · 부목표 2 · 3D 점유 14x11x11 · 2.5D 고도 31x21 = 2,401 칸).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from foothold_s2.nav.teacher_obs import TeacherObsLayout

NUM_ENVS = 1024                 # 설계 §3 (가정 · 메모리 실측 뒤 확정)
LATENT = 32                     # 설계 §3 (논문)
SAVE_INTERVAL = 50              # 설계 §3 · §8: 50 회마다 저장
ACTION_DIM = 3                  # 상위 출력 (vx vy wz) · 설계 결정 1

ASSUMED = ("learning_rate", "gamma", "lam", "clip_param", "num_learning_epochs", "num_mini_batches", "desired_kl",
           "entropy_coef", "num_steps_per_env", "hidden", "conv_channels", "max_grad_norm", "init_noise_std")


@dataclass(frozen=True)
class TeacherPPO:
    num_envs: int = NUM_ENVS
    save_interval: int = SAVE_INTERVAL
    latent: int = LATENT
    learning_rate: float = 3.0e-4
    gamma: float = 0.99
    lam: float = 0.95
    clip_param: float = 0.2
    num_learning_epochs: int = 5
    num_mini_batches: int = 4
    desired_kl: float = 0.01
    entropy_coef: float = 0.005
    num_steps_per_env: int = 24
    hidden: tuple = (256, 128)
    conv_channels: tuple = (16, 32)
    max_grad_norm: float = 1.0
    init_noise_std: float = 0.5

    def as_dict(self) -> dict:
        row = asdict(self)
        row["hidden"], row["conv_channels"] = list(self.hidden), list(self.conv_channels)
        return row


def build_encoder(cfg: TeacherPPO | None = None, layout: TeacherObsLayout | None = None):
    """3D 점유 -> Conv3d · 2.5D 고도 -> Conv2d · 나머지 고유감각 -> 한 줄로 이어 latent 32. torch 는 여기서만 import."""
    import torch
    from torch import nn

    cfg, layout = cfg or TeacherPPO(), layout or TeacherObsLayout()
    c1, c2 = cfg.conv_channels
    off = layout.offsets

    class Encoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.layout, self.off = layout, off
            self.occ = nn.Sequential(nn.Conv3d(1, c1, 3, stride=2, padding=1), nn.ELU(), nn.Conv3d(c1, c2, 3, stride=2, padding=1), nn.ELU(),
                                     nn.AdaptiveAvgPool3d(1), nn.Flatten())
            self.elev = nn.Sequential(nn.Conv2d(1, c1, 3, stride=2, padding=1), nn.ELU(), nn.Conv2d(c1, c2, 3, stride=2, padding=1), nn.ELU(),
                                      nn.AdaptiveAvgPool2d(1), nn.Flatten())
            prop = layout.o_p + layout.c_prev + layout.x_m + layout.subgoal
            self.mix = nn.Sequential(nn.Linear(prop + 2 * c2, cfg.hidden[0]), nn.ELU(), nn.Linear(cfg.hidden[0], cfg.latent), nn.ELU())

        def forward(self, obs):
            if obs.shape[-1] != layout.total:
                raise ValueError(f"teacher observation has {obs.shape[-1]} columns, layout wants {layout.total}")
            a, b = off["occ"]
            occ = obs[:, a:b].reshape(-1, 1, *layout.occ)
            a, b = off["elev"]
            elev = obs[:, a:b].reshape(-1, 1, *layout.elev)
            prop = torch.cat([obs[:, off[k][0]:off[k][1]] for k in ("o_p", "c_prev", "x_m", "subgoal")], dim=1)
            return self.mix(torch.cat([prop, self.occ(occ), self.elev(elev)], dim=1))

    return Encoder()


def build_actor_critic(cfg: TeacherPPO | None = None, layout: TeacherObsLayout | None = None):
    """(actor, critic): 둘 다 같은 꼴의 인코더 + MLP. actor 출력 3 칸 (평균), critic 출력 1 칸. rsl-rl 에 붙이는 일은 Kit 쪽 실행기 몫."""
    from torch import nn

    cfg = cfg or TeacherPPO()
    out = []
    for dim in (ACTION_DIM, 1):
        out.append(nn.Sequential(build_encoder(cfg, layout), nn.Linear(cfg.latent, cfg.hidden[1]), nn.ELU(), nn.Linear(cfg.hidden[1], dim)))
    return tuple(out)
