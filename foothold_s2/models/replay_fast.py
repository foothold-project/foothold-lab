"""지각 재생 손실의 빠른 구현 (RL-3). 학습 내용(식 · 마스크 · gradient 경계)은 start_perception.sequence_loss(loop) 와 같고
계산 순서만 바꾼다. loop 와 같은 입력 · 같은 잡음에서 손실 · 지도가 1e-4 안으로 같은지를 시험이 본다.

    a1  순환이 없는 모듈(prop MLP · depth CNN · TR 의 prop MLP · rough · U-Net · I-E attention · 디코더 · 손실)을 T x B 로 한 번에.
        순환은 GRUCell 두 개만 24 스텝 Python 순환에 남긴다.
    a2  GRU 두 개를 cuDNN 한 번 호출로(리셋에서 자른 구간 · 10 Hz 틱만 모아 pack). 나머지는 loop 처럼 스텝마다.
    a3  a1 + a2.

마스크 규칙은 loop 와 같다: first 에서 hidden 0, 지형 GRU 는 tick 에서만 진행하고 그 사이는 유지(step mask 0).
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.func import functional_call
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

from foothold_s2.models.start_perception import MAP_X, MAP_Y, kl_standard_normal, loss_tr

_GRU_CACHE: dict = {}


def _gru_for(cell: nn.GRUCell) -> tuple[nn.GRU, dict]:
    """GRUCell 과 같은 가중치를 쓰는 nn.GRU (functional_call 로 cell 의 파라미터를 그대로 넘긴다 · gradient 는 cell 로)."""
    key = (cell.input_size, cell.hidden_size, cell.weight_ih.device)
    if key not in _GRU_CACHE:
        _GRU_CACHE[key] = nn.GRU(cell.input_size, cell.hidden_size, batch_first=True).to(cell.weight_ih.device)
    params = {"weight_ih_l0": cell.weight_ih, "weight_hh_l0": cell.weight_hh, "bias_ih_l0": cell.bias_ih, "bias_hh_l0": cell.bias_hh}
    return _GRU_CACHE[key], params


def scan_loop(cell: nn.GRUCell, x: torch.Tensor, h0: torch.Tensor, advance: torch.Tensor, reset: torch.Tensor) -> torch.Tensor:
    """(T, B, D) -> (T, B, H). 매 스텝 h = h * (1 - reset); advance 면 h = cell(x, h)."""
    h, out = h0, []
    for t in range(x.shape[0]):
        h = h * (~reset[t]).float()[:, None]
        h = torch.where(advance[t][:, None], cell(x[t], h), h)
        out.append(h)
    return torch.stack(out)


def scan_cudnn(cell: nn.GRUCell, x: torch.Tensor, h0: torch.Tensor, advance: torch.Tensor, reset: torch.Tensor) -> torch.Tensor:
    """scan_loop 와 같은 값을 cuDNN GRU 한 번으로. 리셋에서 env 별 구간으로 자르고, 구간 안의 advance 스텝만 모아 pack 한다."""
    T, B, D = x.shape
    Hd = cell.hidden_size
    dev = x.device
    seg = torch.cumsum(reset.long(), 0)  # (T, B) env 안 구간 번호
    nseg = seg[-1] + 1
    offs = torch.cumsum(nseg, 0) - nseg
    gid = seg + offs[None]  # (T, B) 전체 구간 번호
    S = int(nseg.sum())
    init = torch.zeros(S, Hd, device=dev, dtype=x.dtype)
    keep0 = ~reset[0]
    init = init.index_put((offs[keep0],), h0[keep0])  # 첫 구간이 리셋으로 시작하지 않으면 버퍼의 시작 hidden

    ib, it = advance.t().nonzero(as_tuple=True)  # env 순 · 시간 순
    g = gid[it, ib]
    lengths = torch.bincount(g, minlength=S)
    start = torch.cumsum(lengths, 0) - lengths
    pos = torch.arange(g.numel(), device=dev) - start[g]
    L = int(lengths.max()) if g.numel() else 0
    outs = torch.zeros(S, max(L, 1), Hd, device=dev, dtype=x.dtype)
    nz = lengths > 0
    if L > 0:
        padded = torch.zeros(S, L, D, device=dev, dtype=x.dtype).index_put((g, pos), x[it, ib])
        gru, params = _gru_for(cell)
        packed = pack_padded_sequence(padded[nz], lengths[nz].cpu(), batch_first=True, enforce_sorted=False)
        y, _ = functional_call(gru, params, (packed, init[nz].unsqueeze(0)))
        y, _ = pad_packed_sequence(y, batch_first=True, total_length=L)
        outs = outs.index_put((nz.nonzero(as_tuple=True)[0],), y)

    # 각 (t, b) 에서 구간 안 advance 누적 수 k: k = 0 이면 구간 시작 hidden, 아니면 k 번째 출력
    A = torch.cumsum(advance.long(), 0)
    tt = torch.arange(T, device=dev)[:, None].expand(T, B)
    startflag = reset.clone()
    startflag[0] = True
    s_t = torch.cummax(torch.where(startflag, tt, torch.zeros_like(tt)), 0).values
    before = torch.where(s_t > 0, torch.gather(A, 0, (s_t - 1).clamp(min=0)), torch.zeros_like(A))
    k = A - before
    h_from_out = outs[gid, (k - 1).clamp(min=0)]
    return torch.where((k == 0)[..., None], init[gid], h_from_out)


def _gru_states(p, b, scan):
    T, B = b["obs"].shape[:2]
    first = b["first"]
    xp = p.ie.prop_mlp(b["hist"].flatten(2))  # (T, B, 128)
    H_prop = scan(p.ie.prop_gru, xp, b["h_prop0"], torch.ones_like(first), first)
    H_terr = None
    if p.trnet is not None:
        d = p.trnet.depth_cnn(b["depth2"].float().flatten(0, 1)).view(T, B, -1)
        zp = p.trnet.prop_mlp(H_prop.detach())  # z_prop 은 detach 해서 TR-Net 에 (12 §6)
        H_terr = scan(p.trnet.gru, torch.cat([d, zp], -1), b["h_terr0"], b["tick"], first)
    return H_prop, H_terr


def _losses_flat(p, b, eps, H_prop, H_terr):
    """(T*B) 로 한 번에 계산. loop 의 스텝 평균의 평균 = T*B 평균 (B 가 스텝마다 같으므로)."""
    T, B = b["obs"].shape[:2]
    gt = b["gt_map"].flatten(0, 1)
    res = {}
    if p.trnet is not None:
        rough = p.trnet.rough(H_terr.flatten(0, 1)).view(-1, MAP_X, MAP_Y)
        refined = p.trnet.refine(rough)
        res["tr"] = loss_tr(rough, refined, gt)
        hmap = torch.where(b["use_gt"].flatten()[:, None, None], gt, refined.detach())
    else:
        res["tr"] = torch.zeros((), device=gt.device)
        hmap = None
    out = p.ie.estimate(H_prop.flatten(0, 1), hmap)
    z = out["mu"] + eps.flatten(0, 1) * torch.exp(0.5 * out["logvar"])
    res["kl"] = kl_standard_normal(out["mu"], out["logvar"])
    res["v"] = F.mse_loss(out["v"], b["base_vel"].flatten(0, 1))
    res["hb"] = F.mse_loss(p.ie.dec_b(out["zb"]), gt.flatten(1))
    res["hf"] = F.mse_loss(p.ie.dec_f(out["zf"]), b["gt_feet"].flatten(0, 1))
    o_hat = p.ie.dec_o(torch.cat([z, out["v"], out["zf"], out["zb"]], -1))
    valid = (~b["done"]).flatten().float()
    per = ((o_hat - b["next_obs"].flatten(0, 1)) ** 2).mean(-1)
    res["o_next"] = (per * valid).sum() / valid.sum().clamp(min=1.0)
    res["_refined"] = refined if p.trnet is not None else None
    return res


def _losses_stepwise(p, b, eps, H_prop, H_terr):
    """a2: GRU 상태는 미리 구하고 나머지는 loop 처럼 스텝마다."""
    T = b["obs"].shape[0]
    sums = {k: 0.0 for k in ("tr", "kl", "v", "hb", "hf")}
    o_sum, o_cnt, refs = 0.0, 0.0, []
    for t in range(T):
        gt = b["gt_map"][t]
        if p.trnet is not None:
            rough, refined = p.trnet.decode(H_terr[t])
            sums["tr"] = sums["tr"] + loss_tr(rough, refined, gt)
            hmap = torch.where(b["use_gt"][t][:, None, None], gt, refined.detach())
            refs.append(refined)
        else:
            hmap = None
        out = p.ie.estimate(H_prop[t], hmap)
        z = out["mu"] + eps[t] * torch.exp(0.5 * out["logvar"])
        sums["kl"] = sums["kl"] + kl_standard_normal(out["mu"], out["logvar"])
        sums["v"] = sums["v"] + F.mse_loss(out["v"], b["base_vel"][t])
        sums["hb"] = sums["hb"] + F.mse_loss(p.ie.dec_b(out["zb"]), gt.flatten(1))
        sums["hf"] = sums["hf"] + F.mse_loss(p.ie.dec_f(out["zf"]), b["gt_feet"][t])
        o_hat = p.ie.dec_o(torch.cat([z, out["v"], out["zf"], out["zb"]], -1))
        valid = (~b["done"][t]).float()
        o_sum = o_sum + (((o_hat - b["next_obs"][t]) ** 2).mean(-1) * valid).sum()
        o_cnt = o_cnt + valid.sum()
    res = {k: v / T for k, v in sums.items()}
    if p.trnet is None:
        res["tr"] = torch.zeros((), device=b["obs"].device)
    res["o_next"] = o_sum / torch.clamp(torch.as_tensor(o_cnt, device=b["obs"].device), min=1.0)
    res["_refined"] = torch.cat(refs) if refs else None
    return res


def sequence_loss_fast(p, b: dict, eps: torch.Tensor, impl: str) -> dict:
    if impl not in ("a1", "a2", "a3"):
        raise ValueError(f"모르는 구현: {impl}")
    scan = scan_cudnn if impl in ("a2", "a3") else scan_loop
    H_prop, H_terr = _gru_states(p, b, scan)
    res = (_losses_flat if impl in ("a1", "a3") else _losses_stepwise)(p, b, eps, H_prop, H_terr)
    res["l_ie"] = res["kl"] + res["o_next"] + res["v"] + res["hf"] + res["hb"]
    res["l_tr"] = res["tr"]
    res["loss"] = res["l_tr"] + res["l_ie"]
    return res
