"""START 지각 (12-PERCEPTION): TR-Net · I-E Estimator · AdaSmpl. torch 만 쓰고 Kit 없이 CPU 로 시험한다.

공개 코드를 옮기지 않았다(START 코드 없음 · MGDP 라이선스 없음). PyTorch 기본 층으로 새로 짓는다.
수치의 등급(논문 · 선행 · 가정)은 12 문서 표를 따르고, 문서에 없는 것을 여기서 정한 곳은 주석에 «가정(rl)» 으로 적는다.

자료 흐름(12 §2):
    o^H1 (10 x 45) -> Prop encoder (MLP 256,128 -> GRU 128) -> z_prop
    depth (2, 60, 60) -> Depth CNN -> 1024 ┐
    z_prop.detach() -> MLP 64,64 ----------┴-> GRU 128 (10 Hz 틱에만 진행) -> Rough MLP -> H_rough 32x16 -> U-Net -> H_refined
    AdaSmpl: env 마다 정답 H^b 또는 H_refined.detach() -> Map CNN -> 토큰 128 x 64 ┐
    z_prop -> Linear 64 (prop 토큰) --------------------------------------------┴-> Self-attention -> z 16 · v 3 · zb 16 · zf 16

gradient 경계(12 §6): PPO 는 이 모듈의 출력을 detach 해서 받는다(actor 입력은 수집 때 고정, runner). TR-Net 은 z_prop 을
detach 해서 받고, I-E 는 TR-Net 지도를 detach 해서 받는다. 그래서 L_TR 은 TR-Net 만, L_IE 는 I-E 만 움직인다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import torch
import torch.nn as nn
import torch.nn.functional as F

# 12 §3 지도 규격 (논문 START 127 행 · 셀 배치는 가정 SPEC 53 행)
MAP_X = 32  # 뒤 0.5 ~ 앞 1.1 m, 5 cm
MAP_Y = 16  # 폭 0.8 m, 5 cm
MAP_CELLS = MAP_X * MAP_Y  # 512
FOOT_CELLS = 4 * 5 * 5  # 발마다 5 x 5 · 5 cm (가정 12 §4)
OBS_DIM = 45  # 13 §2 o_t
HIST_LEN = 10  # H1 (선행 2409 95 행)
DEPTH_HW = 60
DEPTH_FRAMES = 2  # H2 (논문 127 행)
Z_DIM = 16
V_DIM = 3
ZB_DIM = 16
ZF_DIM = 16
EST_DIM = Z_DIM + V_DIM + ZF_DIM + ZB_DIM  # 51
ACTOR_IN = OBS_DIM + EST_DIM  # 96 (13 §2)
TOKEN = 64


def mlp(in_dim: int, hidden: list[int], out_dim: int | None) -> nn.Sequential:
    layers: list[nn.Module] = []
    d = in_dim
    for h in hidden:
        layers += [nn.Linear(d, h), nn.ELU()]
        d = h
    if out_dim is not None:
        layers.append(nn.Linear(d, out_dim))
    return nn.Sequential(*layers)


@dataclass
class PerceptionCfg:
    fast_gt_only: bool = False
    map_input: str = "reconstruction"  # "reconstruction"(G1 · G3) · "none"(G0 · 지도 토큰 0)
    force_gt: bool = False  # G0-gt: p_smpl = 1 고정 (13 §4)
    attn_layers: int = 2  # 가정 (12 §4: 층 수 · FF 근거 부족)
    attn_ff: int = 256
    p_smpl_init: float = 1.0  # 가정(rl): 첫 통계가 쌓이기 전에는 정답 지도로 시작
    cv_eps: float = 1e-6  # 12 §5 가정
    depth_tick: int = 5  # 10 Hz 깊이 = 50 Hz 의 5 스텝마다 (11 §4)
    depth_delay_ticks: int = 1  # 1 프레임(0.1 s) 지연 (11 §2.1 · JEPLO cfg)
    sample_latent_in_rollout: bool = True  # 가정(rl): 수집 때 z 를 표집, 배포(act_inference)는 평균


class DepthCNN(nn.Module):
    """12 §3 우리 선택(가정): (32,k7,s4,p3) · (64,k3,s2,p1) · (64,k3,s2,p1). 60x60 -> 15 -> 8 -> 4, 1024."""

    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(DEPTH_FRAMES, 32, 7, 4, 3), nn.ELU(),
            nn.Conv2d(32, 64, 3, 2, 1), nn.ELU(),
            nn.Conv2d(64, 64, 3, 2, 1), nn.ELU(),
        )  # 활성화 ELU 는 가정(rl): 선행 Table V 가 MLP 에 ELU 를 쓴 것을 따른다

    def forward(self, d: torch.Tensor) -> torch.Tensor:
        if d.shape[-3:] != (DEPTH_FRAMES, DEPTH_HW, DEPTH_HW):
            raise ValueError(f"depth 는 (..., {DEPTH_FRAMES}, {DEPTH_HW}, {DEPTH_HW}) 여야 한다: {tuple(d.shape)}")
        return self.net(d).flatten(1)


class UNetRefine(nn.Module):
    """선행 Fig. 8: 16,16 / 32,32 / 64,64 / concat 64->32,32 / concat 32->16,16 -> 1. 마지막 활성화 없음(가정)."""

    def __init__(self) -> None:
        super().__init__()

        def block(i: int, o: int) -> nn.Sequential:
            return nn.Sequential(nn.Conv2d(i, o, 3, 1, 1), nn.ReLU(), nn.Conv2d(o, o, 3, 1, 1), nn.ReLU())

        self.e1 = block(1, 16)
        self.e2 = block(16, 32)
        self.mid = block(32, 64)
        self.u2 = nn.ConvTranspose2d(64, 32, 2, 2)
        self.d2 = block(64, 32)
        self.u1 = nn.ConvTranspose2d(32, 16, 2, 2)
        self.d1 = block(32, 16)
        self.out = nn.Conv2d(16, 1, 3, 1, 1)  # 3x3 · 활성화 없음: fable 20s 가 START 원문과 대조해 채택 (12 §3 · §12, 37ed3ada)

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        x = h.unsqueeze(1)
        e1 = self.e1(x)
        e2 = self.e2(F.max_pool2d(e1, 2))
        m = self.mid(F.max_pool2d(e2, 2))
        d2 = self.d2(torch.cat([self.u2(m), e2], 1))
        d1 = self.d1(torch.cat([self.u1(d2), e1], 1))
        return self.out(d1).squeeze(1)


class TRNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.depth_cnn = DepthCNN()
        self.prop_mlp = mlp(128, [64, 64], None)
        self.gru = nn.GRUCell(1024 + 64, 128)
        self.rough = mlp(128, [128, 256], MAP_CELLS)
        self.refine = UNetRefine()

    def step(self, depth: torch.Tensor, z_prop: torch.Tensor, h: torch.Tensor) -> torch.Tensor:
        """한 틱 진행한 새 hidden. z_prop 은 detach 해서 받는다(12 §6 가정)."""
        x = torch.cat([self.depth_cnn(depth), self.prop_mlp(z_prop.detach())], -1)
        return self.gru(x, h)

    def decode(self, h: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        rough = self.rough(h).view(-1, MAP_X, MAP_Y)
        return rough, self.refine(rough)


class IEEstimator(nn.Module):
    def __init__(self, cfg: PerceptionCfg) -> None:
        super().__init__()
        self.use_map = cfg.map_input != "none"
        self.prop_mlp = mlp(OBS_DIM * HIST_LEN, [256, 128], None)
        self.prop_gru = nn.GRUCell(128, 128)
        self.prop_token = nn.Linear(128, TOKEN)
        if self.use_map:
            # 12 §4 우리 선택(가정): (32,k7,s2,p3) · (64,k3,s1,p1). 32x16 -> 16x8 = 128 토큰
            self.map_cnn = nn.Sequential(nn.Conv2d(1, 32, 7, 2, 3), nn.ELU(), nn.Conv2d(32, TOKEN, 3, 1, 1))
            # 위치 임베딩은 가정(rl): attention 은 순서를 모르므로 칸 위치를 따로 준다
            self.map_pos = nn.Parameter(torch.zeros(1, (MAP_X // 2) * (MAP_Y // 2), TOKEN))
        layer = nn.TransformerEncoderLayer(TOKEN, 1, cfg.attn_ff, dropout=0.0, batch_first=True)
        self.attn = nn.TransformerEncoder(layer, cfg.attn_layers, enable_nested_tensor=False)
        self.heads = nn.Linear(TOKEN, 2 * Z_DIM + V_DIM + ZB_DIM + ZF_DIM)
        self.dec_b = mlp(ZB_DIM, [64, 128], MAP_CELLS)
        self.dec_f = mlp(ZF_DIM, [64, 128], FOOT_CELLS)
        self.dec_o = mlp(EST_DIM, [64, 128], OBS_DIM)

    def prop_step(self, hist: torch.Tensor, h: torch.Tensor) -> torch.Tensor:
        return self.prop_gru(self.prop_mlp(hist.flatten(1)), h)

    def estimate(self, z_prop: torch.Tensor, hmap: torch.Tensor | None, map_off: torch.Tensor | None = None) -> dict[str, torch.Tensor]:
        """map_off (B,) bool: 참인 행은 지도 토큰을 attention 키에서 뺀다(EX-33 S-B · 평가 probe_prop_only 와 같은 방식, 지도를 0 높이로 바꿔 넣지 않는다). None 이거나 모두 거짓이면 마스크 인자 없이 B 와 같은 호출이다."""
        tokens = [self.prop_token(z_prop).unsqueeze(1)]
        if self.use_map:
            if hmap is None:
                raise ValueError("map_input 이 none 이 아니면 지도가 있어야 한다")
            m = self.map_cnn(hmap.detach().unsqueeze(1))  # (B, 64, 16, 8)
            tokens.append(m.flatten(2).transpose(1, 2) + self.map_pos)
        seq = torch.cat(tokens, 1)
        self.last_num_map_tokens = seq.shape[1] - 1  # 시험용: G0 이면 0
        pad = None
        if self.use_map and getattr(self, "mask_map_tokens", False):  # 진단 전용(probe_prop_only): 지도 토큰을 모든 행에서 attention 키에서 뺀다. 0 높이 지도로 바꿔 넣지 않는다
            pad = torch.zeros(seq.shape[:2], dtype=torch.bool, device=seq.device)
            pad[:, 1:] = True
        elif self.use_map and map_off is not None and bool(map_off.any()):  # 행마다 끔(지도 비율 M-T1): 참인 행만
            pad = torch.zeros(seq.shape[:2], dtype=torch.bool, device=seq.device)
            pad[:, 1:] = map_off.bool()[:, None]
        out = self.attn(seq) if pad is None else self.attn(seq, src_key_padding_mask=pad)
        out = out[:, 0]  # prop 토큰 자리의 출력을 쓴다: 가정(rl)
        if getattr(self, "heads_fp32", False) and torch.is_autocast_enabled(out.device.type):
            with torch.autocast(out.device.type, enabled=False):  # bf16 에서 logvar · KL 정밀도를 지킨다(RL-3 B)
                h = self.heads(out.float())
        else:
            h = self.heads(out)
        mu, logvar, v, zb, zf = torch.split(h, [Z_DIM, Z_DIM, V_DIM, ZB_DIM, ZF_DIM], -1)
        return {"mu": mu, "logvar": logvar, "v": v, "zb": zb, "zf": zf}


def kl_standard_normal(mu: torch.Tensor, logvar: torch.Tensor) -> torch.Tensor:
    """KL(N(mu, var) || N(0, 1)), 차원 합 · 배치 평균 (가정(rl): 합 · 평균의 축)."""
    mu, logvar = mu.float(), logvar.float()
    return (-0.5 * (1 + logvar - mu.pow(2) - logvar.exp()).sum(-1)).mean()


def loss_tr(rough: torch.Tensor, refined: torch.Tensor, hb: torch.Tensor) -> torch.Tensor:
    """식 4: MSE(H_rough, H^b) + L1(H_refined, H^b). 칸 평균."""
    return F.mse_loss(rough, hb) + F.l1_loss(refined, hb)


class AdaSmpl:
    """p_smpl = tanh(CV(R)) (논문 193 행). 창 · 분모 · 표본 단위는 12 §5 가정.

    통계는 지난 1 회 iteration 에 끝난 에피소드 보상의 count · sum · sumsq. 분산 학습에서는 이 셋을 전 rank 합산(18 §5.1).
    """

    def __init__(self, p_init: float = 1.0, eps: float = 1e-6, force_gt: bool = False) -> None:
        self.p = float(p_init)
        self.eps = eps
        self.force_gt = force_gt
        self.reset_stats()

    def reset_stats(self) -> None:
        self.count = 0.0
        self.sum = 0.0
        self.sumsq = 0.0

    def add(self, rewards: torch.Tensor) -> None:
        r = rewards.detach().double().flatten()
        self.count += float(r.numel())
        self.sum += float(r.sum())
        self.sumsq += float((r * r).sum())

    @staticmethod
    def cv(count: float, s: float, ss: float, eps: float) -> float:
        mean = s / count
        var = max(ss / count - mean * mean, 0.0)  # 모분산: 가정(rl), 12 §9 기대값(R = [0, 2] -> 0.76)과 맞는 쪽
        return math.sqrt(var) / (abs(mean) + eps)

    def update(self) -> float:
        """iteration 끝에 부른다. 끝난 에피소드가 2 개 미만이면 p 를 그대로 둔다(가정(rl))."""
        if self.force_gt:
            self.p = 1.0
        elif self.count >= 2:
            self.p = math.tanh(self.cv(self.count, self.sum, self.sumsq, self.eps))
        self.reset_stats()
        return self.p

    def sample(self, n: int, device, generator: torch.Generator | None = None) -> torch.Tensor:
        if self.force_gt:
            return torch.ones(n, dtype=torch.bool, device=device)
        return torch.rand(n, device=device, generator=generator) < self.p

    def state_dict(self) -> dict:
        return {"p": self.p, "count": self.count, "sum": self.sum, "sumsq": self.sumsq, "force_gt": self.force_gt}

    def load_state_dict(self, sd: dict) -> None:
        self.p, self.count, self.sum, self.sumsq = float(sd["p"]), float(sd["count"]), float(sd["sum"]), float(sd["sumsq"])
        self.force_gt = bool(sd["force_gt"])


@dataclass
class PerceptionState:
    """수집 중 env 마다 들고 가는 상태. 저장하지 않는다(재개하면 env 를 리셋한다)."""

    h_prop: torch.Tensor
    h_terr: torch.Tensor
    hist: torch.Tensor  # (N, 10, 45)
    frames: torch.Tensor  # (N, 2 + delay, 60, 60) 최근 프레임, 0 이 가장 새것
    steps_since_reset: torch.Tensor  # (N,) long
    use_gt: torch.Tensor  # (N,) bool AdaSmpl 플래그
    extra: dict = field(default_factory=dict)
    map_off: torch.Tensor | None = None  # (N,) bool: 이 에피소드는 지도 토큰을 끈다(EX-33 S-B). None = 항상 켬(B)


class StartPerception(nn.Module):
    """TR-Net + I-E 를 묶고, 50 Hz 한 스텝(step) 과 재생 손실(sequence_loss) 두 경로를 둔다.

    두 경로는 같은 함수(_advance)를 지나므로 같은 입력에 같은 값이 나온다. 이것이 «재생 = 수집» 의 근거다.
    """

    def __init__(self, cfg: PerceptionCfg | None = None) -> None:
        super().__init__()
        self.cfg = cfg or PerceptionCfg()
        self.trnet = TRNet() if self.cfg.map_input != "none" else None
        self.ie = IEEstimator(self.cfg)

    # ---------------- 상태 ----------------
    def init_state(self, n: int, device) -> PerceptionState:
        k = DEPTH_FRAMES + self.cfg.depth_delay_ticks
        return PerceptionState(
            h_prop=torch.zeros(n, 128, device=device),
            h_terr=torch.zeros(n, 128, device=device),
            hist=torch.zeros(n, HIST_LEN, OBS_DIM, device=device),
            frames=torch.zeros(n, k, DEPTH_HW, DEPTH_HW, device=device),
            steps_since_reset=torch.zeros(n, dtype=torch.long, device=device),
            use_gt=torch.ones(n, dtype=torch.bool, device=device),
            map_off=torch.zeros(n, dtype=torch.bool, device=device),
        )

    @torch.no_grad()
    def reset_envs(self, st: PerceptionState, mask: torch.Tensor, new_flags: torch.Tensor, new_map_off: torch.Tensor | None = None) -> None:
        """env 리셋: 두 GRU 0 (12 §6.1), 이력 · 프레임은 다음 관측으로 채우도록 표시, AdaSmpl 플래그 새로 뽑음."""
        m = mask.bool()
        st.h_prop[m] = 0
        st.h_terr[m] = 0
        st.steps_since_reset[m] = 0
        st.use_gt[m] = new_flags[m]
        if new_map_off is not None:
            st.map_off[m] = new_map_off[m]  # 에피소드 시작 때만 새로 뽑는다: 에피소드 안에서는 유지

    @torch.no_grad()
    def ingest(self, st: PerceptionState, obs: torch.Tensor, depth: torch.Tensor) -> dict[str, torch.Tensor]:
        """새 관측을 상태에 넣고 이번 스텝의 입력(이력 · 깊이 2 프레임 · 틱 · 첫 스텝)을 만든다. 재생 버퍼가 이것을 저장한다.

        첫 스텝(리셋 직후)에는 이력과 프레임을 현재 값으로 모두 채운다: 가정(rl), Isaac Lab CircularBuffer 와 같은 꼴.
        """
        first = st.steps_since_reset == 0
        st.hist = torch.where(first[:, None, None], obs[:, None, :].expand_as(st.hist), torch.roll(st.hist, 1, 1))
        st.hist[:, 0] = obs
        tick = (st.steps_since_reset % self.cfg.depth_tick) == 0
        rolled = torch.roll(st.frames, 1, 1)
        rolled[:, 0] = depth
        new_frames = torch.where(first[:, None, None, None], depth[:, None].expand_as(st.frames), rolled)
        st.frames = torch.where(tick[:, None, None, None], new_frames, st.frames)
        d = self.cfg.depth_delay_ticks
        d2 = st.frames[:, d : d + DEPTH_FRAMES]
        st.steps_since_reset += 1
        return {"hist": st.hist.clone(), "depth2": d2.clone(), "tick": tick.clone(), "first": first.clone()}

    # ---------------- 한 스텝 계산 (수집 · 재생 공용) ----------------
    def _advance(self, h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, map_off=None):
        keep = (~first).float()[:, None]
        h_prop = self.ie.prop_step(hist, h_prop * keep)
        h_terr = h_terr * keep
        out: dict[str, torch.Tensor] = {}
        if self.cfg.fast_gt_only:
            if not self.cfg.force_gt or not bool(use_gt.all()):
                raise ValueError("fast_gt_only requires the GT map for every environment")
            hmap = gt_map
        elif self.trnet is not None:
            h_new = self.trnet.step(depth2, h_prop, h_terr)
            h_terr = torch.where(tick[:, None], h_new, h_terr)  # 틱이 아니면 step mask 0 (12 §6.1)
            rough, refined = self.trnet.decode(h_terr)
            out["rough"], out["refined"] = rough, refined
            hmap = torch.where(use_gt[:, None, None], gt_map, refined.detach())
        else:
            hmap = None
        est = self.ie.estimate(h_prop, hmap) if map_off is None else self.ie.estimate(h_prop, hmap, map_off)
        out.update(est)
        return h_prop, h_terr, out

    @staticmethod
    def _off_args(map_off, t: int | None = None) -> tuple:
        """_advance 의 마지막 인자. 끌 env 가 하나도 없으면 인자를 아예 안 넘긴다: 그러면 호출이 B 와 글자까지 같고, _advance 를 감싼 기록기(8 인자 고정)도 그대로 돈다."""
        if map_off is None:
            return ()
        m = map_off if t is None else map_off[t]

        return (m,) if bool(m.any()) else ()

    @torch.no_grad()
    def step(self, st: PerceptionState, inp: dict[str, torch.Tensor], gt_map: torch.Tensor, deterministic: bool = False) -> torch.Tensor:
        """수집 · 배포용. 51 차원 추정(z · v · zf · zb)을 돌려준다. 배포(deterministic)는 z 평균."""
        st.h_prop, st.h_terr, out = self._advance(
            st.h_prop, st.h_terr, inp["hist"], inp["depth2"], inp["tick"], inp["first"], st.use_gt, gt_map, *self._off_args(st.map_off)
        )
        if deterministic or not self.cfg.sample_latent_in_rollout:
            z = out["mu"]
        else:
            z = out["mu"] + torch.randn_like(out["mu"]) * torch.exp(0.5 * out["logvar"])
        return torch.cat([z, out["v"], out["zf"], out["zb"]], -1)

    @torch.no_grad()
    def est_sequence(self, batch: dict[str, torch.Tensor], eps: torch.Tensor) -> torch.Tensor:
        """저장된 rollout 시퀀스에서 est (T, B, 51) 를 다시 계산한다(gradient 없음). 고정된 eps 로 z 를 표집하므로 phi 전 · 후를 같은 잡음으로 견줄 수 있다.
        sequence_loss(loop) 와 같은 _advance 경로를 지난다 (X6 KL 기록용)."""
        T = batch["obs"].shape[0]
        h_prop, h_terr = batch["h_prop0"], batch["h_terr0"]
        outs = []
        for t in range(T):
            h_prop, h_terr, out = self._advance(
                h_prop, h_terr, batch["hist"][t], batch["depth2"][t].float(), batch["tick"][t], batch["first"][t],
                batch["use_gt"][t], batch["gt_map"][t], *self._off_args(batch.get("map_off"), t),
            )
            z = out["mu"] + eps[t] * torch.exp(0.5 * out["logvar"])
            outs.append(torch.cat([z, out["v"], out["zf"], out["zb"]], -1))
        return torch.stack(outs)

    # ---------------- 재생 손실 (gradient 켬) ----------------
    def sequence_loss(self, batch: dict[str, torch.Tensor], eps: torch.Tensor | None = None,
                      impl: str = "loop") -> dict[str, torch.Tensor]:
        """batch 는 (T, B, ...) 순서. 시작 hidden 은 버퍼 값, first 에서 0 으로 다시 시작(BPTT 는 한 rollout).

        ô_{t+1} 항은 done_t = 1 인 전이를 뺀다(terminal 마스크, 12 §6.1). 나머지 항은 모든 스텝.
        eps 는 VAE 표집 잡음 (T, B, 16). 구현(loop · a1 · a2 · a3)끼리 같은 잡음을 쓰게 밖에서 줄 수 있다.
        impl: loop = 스텝마다 전부(기준) · a1 = 순환 없는 모듈을 T x B 로 한 번에 · a2 = GRU 를 cuDNN 한 번 · a3 = 둘 다
        (models/replay_fast.py, RL-3). 학습 내용은 같고 계산 순서만 다르다.
        """
        T = batch["obs"].shape[0]
        if eps is None:
            eps = torch.randn(T, batch["obs"].shape[1], Z_DIM, device=batch["obs"].device)
        if impl != "loop":
            from foothold_s2.models.replay_fast import sequence_loss_fast

            return sequence_loss_fast(self, batch, eps, impl)
        h_prop, h_terr = batch["h_prop0"], batch["h_terr0"]
        sums = {k: 0.0 for k in ("tr", "kl", "o_next", "v", "hf", "hb")}
        o_valid_total = 0.0
        for t in range(T):
            h_prop, h_terr, out = self._advance(
                h_prop, h_terr, batch["hist"][t], batch["depth2"][t].float(), batch["tick"][t], batch["first"][t],
                batch["use_gt"][t], batch["gt_map"][t], *self._off_args(batch.get("map_off"), t),
            )
            if self.trnet is not None:
                sums["tr"] = sums["tr"] + loss_tr(out["rough"], out["refined"], batch["gt_map"][t])
            z = out["mu"] + eps[t] * torch.exp(0.5 * out["logvar"])
            sums["kl"] = sums["kl"] + kl_standard_normal(out["mu"], out["logvar"])
            sums["v"] = sums["v"] + F.mse_loss(out["v"], batch["base_vel"][t])
            sums["hb"] = sums["hb"] + F.mse_loss(self.ie.dec_b(out["zb"]), batch["gt_map"][t].flatten(1))
            sums["hf"] = sums["hf"] + F.mse_loss(self.ie.dec_f(out["zf"]), batch["gt_feet"][t])
            o_hat = self.ie.dec_o(torch.cat([z, out["v"], out["zf"], out["zb"]], -1))
            valid = (~batch["done"][t]).float()
            per = ((o_hat - batch["next_obs"][t]) ** 2).mean(-1)
            sums["o_next"] = sums["o_next"] + (per * valid).sum()
            o_valid_total += float(valid.sum())
        res = {k: (v / T if k != "o_next" else v / max(o_valid_total, 1.0)) for k, v in sums.items()}
        res["l_ie"] = res["kl"] + res["o_next"] + res["v"] + res["hf"] + res["hb"]  # 식 3, 계수 1
        res["l_tr"] = res["tr"] if self.trnet is not None else torch.zeros(())
        res["loss"] = res["l_tr"] + res["l_ie"]
        return res
