"""EX-42 하위 자세 명령 (몸 높이 · roll) 을 배우는 최소 경로 (lead 2026-11-21 19:34 · 팀장 18:51 「하위가 자세를 배워 오고 상위는 원문 그대로」).
기본 꺼짐: EX42_POSTURE=1 일 때만 켜진다. 꺼짐이면 env 설정 · 관측 (자세 칸 0) · 보상 · runner 확인이 r3 와 같은 바이트다.

켜짐이면:
  - 명령: env 마다 [h, roll] 을 원문 범위에서 고르게 뽑는다. h ∈ [0.1, 0.4] m (지면 기준 몸 높이) · roll ∈ [-1.0, 1.0] rad (2604.26504.txt:635).
    속도 명령이 바뀌거나 새 에피소드면 다시 뽑는다 (heading 항과 같은 방식 · 명령 항 코드는 고치지 않는다).
  - 관측: actor 96:98 · critic 664:666 의 자세 칸 = [h - H0, roll] (D93 순서: 높이 변화 · roll). H0 = 공칭 몸 높이 (가정 0.31 m · EX42_POSTURE_H0).
  - 보상 (원문 Table III · 2604.26504.txt:597-605 · 627): 높이 w3 0.2 · exp(-|hc - hB| / 0.0025) · roll w4 0.2 · exp(-|θc - θ_roll| / 0.05).
    hB = 몸통 z - 높이 스캐너가 맞힌 바닥 z 평균 (스캐너가 없으면 env 원점 z).
  - runner: 자세 칸이 0 이 아니어도 받는다 (범위 · 유한성만 확인).
범위 · 가중은 env 값으로 바꿀 수 있다 (EX42_POSTURE_H_RANGE "lo,hi" · EX42_POSTURE_ROLL_RANGE · EX42_POSTURE_HEIGHT_W · EX42_POSTURE_ROLL_W).
CG C8a~C8c 의 단계 (높이 좁게 → 넓게 → roll) 를 따르려면 범위 env 값을 단계마다 바꿔 새 판을 띄운다 (실시간 칸은 둘째 단계).

rx2pz (lead 2026-11-21 20:24 · 원장 20:23 「자세 하위 따로 판」) 에서 더한 것 (둘 다 EX42_POSTURE=1 안에서만):
  - 적용 env: 평지 · 연속 지형 env 만 자세 명령을 받는다. 듬성 열 (A 의 듬성 종류 · A 가 아닌 족 B~E) 과 깃발 env 는 자세 0
    (관측 [0, 0] · 보상 목표 [H0, 0]). 열 표 (env._ex42_column_table) 가 없으면 열로는 가르지 않는다 (시작 줄에 적음).
  - 범위 커리큘럼 (EX42_POSTURE_CURRICULUM=1): 높이는 H0 ± EX42_POSTURE_H_START (기본 0.02 m) 에서, roll 은 ± EX42_POSTURE_ROLL_START
    (기본 0.1 rad) 에서 시작한다. EX42_POSTURE_CHECK_STEPS (기본 1200 step = 50 update x 24) 마다 그 사이의 적용 env 표본으로
    중앙 오차를 재고, 높이 중앙 오차 < min(EX42_POSTURE_H_TOL 0.02, 0.4 x 반폭) 이면 반폭을 EX42_POSTURE_H_STEP (0.02) 넓히고
    roll 중앙 오차 < min(EX42_POSTURE_ROLL_TOL 0.1, 0.4 x 반폭) 이면 EX42_POSTURE_ROLL_STEP (0.1) 넓힌다 (원문 범위에서 멈춤).
    0.4 x 반폭: 띠 안에서 늘 H0 로만 서 있으면 중앙 오차가 반폭의 0.5 쯤이라, 그보다 낫게 따라가야 넓힌다.
    상태는 EX42_POSTURE_STATE (json · rank 마다 .rank<r>) 에 쓰고 시작할 때 있으면 읽는다 (같은 OUT 이어 가기에서 띠가 처음으로 돌아가지 않게).
  - 점검 줄 (커리큘럼과 무관하게 켜짐이면 늘): EX42_POSTURE_CHECK step · 띠 · 표본 수 · 높이 추종 보상 평균 · 중앙 오차 (높이 · roll) ·
    명령 대 실제 기울기 (높이 · roll) · 넓힘 여부. 50 회 탐침 (꼬리표 rx2pz) 이 이 줄을 읽는다.
σ 풀림 (EX42_POSTURE_SIGMA_ANNEAL=1 · lead 11/22 06:28 · 원장 3a06f0724 · planner 06:25 rx2pf2 +250 slope_h · slope_roll 0.00): 원문 폭
exp(-|e|/0.0025) · exp(-|e|/0.05) 는 처음에 신호가 없음 → 높이 σ 0.05 m · roll σ 0.5 rad 로 넓게 시작하고 EX42_POSTURE_CHECK 의 slope 가 0.5 를
넘고 중앙 오차가 지금 σ 보다 작을 때마다 (planner 06:39 · 두 rank all-reduce 평균으로 판정) 그 축의 σ 를 절반 (06:31: 높이 시작 0.10 m) (끝값 = 원문 0.0025 · 0.05 에서 멈춤). 점검 줄 · 시작 줄에 σ 와 절반 사건. 켜면 EX42_POSTURE_CHECK_STEPS 를 커리큘럼 없이도
받는다 (짧은 Kit 기동용). 끔 (기본) = 원문 폭 고정 · 옛 동작 그대로. 두 rank 는 slope · 중앙 오차를 all-reduce 평균으로 같이 판정해 σ 가 같게 움직인다 (점검 줄의 judged_* = 판정에 쓴 평균).
No Kit import at module level.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import torch

ENV_SWITCH = "EX42_POSTURE"
PAPER_H = (0.1, 0.4)                 # 2604.26504.txt:635
PAPER_ROLL = (-1.0, 1.0)
PAPER_W = (0.2, 0.2)                 # 2604.26504.txt:627 w3L · w4L
H0_DEFAULT = 0.31                    # 공칭 몸 높이 (가정 · CG C8a 의 공칭 근처 U[0.28, 0.34] 의 가운데)
HEIGHT_TERM, ROLL_TERM = "ex42_posture_height", "ex42_posture_roll"
STATE = "_ex42_posture_state"
CURRICULUM_KEYS = ("EX42_POSTURE_CURRICULUM", "EX42_POSTURE_H_START", "EX42_POSTURE_ROLL_START", "EX42_POSTURE_H_STEP", "EX42_POSTURE_ROLL_STEP",
                   "EX42_POSTURE_H_TOL", "EX42_POSTURE_ROLL_TOL", "EX42_POSTURE_CHECK_STEPS", "EX42_POSTURE_STATE")
SIGMA_PAPER = (0.0025, 0.05)        # 원문 높이 · roll 폭 (2604.26504.txt:597-605)
SIGMA_START = (0.10, 0.5)            # σ 풀림 시작값 (lead 06:31 원장 7641d99ae: 높이 0.10 m · roll 0.5 rad)
SIGMA_SLOPE = 0.5                    # 이 slope 를 넘으면 그 축 σ 절반
# 자세 env 벌 낮춤 (EX42_POSTURE_PEN_MASK=1 · lead 06:31 원장 7641d99ae · planner 06:29 벌 합): 자세 명령 env 에서만 이 가중으로 (hip 듬성 열 가림과 같은 꼴:
# 항 함수 안에서 값 x 목표/지금 가중 · 실시간 칸은 항 전체 가중이라 함수 안에서 가린다). 다른 env 는 항 가중 그대로. collision 은 바꾸지 않고 기록만.
PEN_TARGETS = {"basic_hip_pos_penalty_l1": 0.0, "ex39_thigh_calf_pos_l1": -0.0025}
PEN_LOG_ONLY = ("collision",)
SAMPLE_EVERY = 24                    # 표본은 24 step (update 1 회) 마다 한 번
BEAT_FRACTION = 0.4                  # 넓힘 문턱 = min(tol, 0.4 x 반폭)


def enabled() -> bool:
    value = os.environ.get(ENV_SWITCH, "")
    if value not in ("", "0", "1"):
        raise ValueError(f"{ENV_SWITCH} must be 0 or 1 (got {value!r})")
    extra = [k for k in ("EX42_POSTURE_H_RANGE", "EX42_POSTURE_ROLL_RANGE", "EX42_POSTURE_H0", "EX42_POSTURE_HEIGHT_W", "EX42_POSTURE_ROLL_W", *CURRICULUM_KEYS)
             if os.environ.get(k, "") != ""]
    if value != "1" and extra:
        raise ValueError(f"{', '.join(extra)} set but {ENV_SWITCH} is not 1")
    return value == "1"


def _pair(name, default):
    raw = os.environ.get(name, "")
    if raw == "":
        return tuple(map(float, default))
    try:
        lo, hi = (float(v) for v in raw.split(","))
    except ValueError:
        raise ValueError(f"{name} must be 'lo,hi' (got {raw!r})") from None
    if not (math.isfinite(lo) and math.isfinite(hi) and lo <= hi):
        raise ValueError(f"{name} must be finite with lo <= hi (got {raw!r})")
    return lo, hi


def _num(name, default, lo=0.0):
    raw = os.environ.get(name, "")
    try:
        v = float(raw) if raw != "" else float(default)
    except ValueError:
        raise ValueError(f"{name} must be a number (got {raw!r})") from None
    if not math.isfinite(v) or v < lo:
        raise ValueError(f"{name} must be finite and >= {lo} (got {raw!r})")
    return v


def settings() -> dict:
    h, roll = _pair("EX42_POSTURE_H_RANGE", PAPER_H), _pair("EX42_POSTURE_ROLL_RANGE", PAPER_ROLL)
    if not (PAPER_H[0] <= h[0] and h[1] <= PAPER_H[1] and PAPER_ROLL[0] <= roll[0] and roll[1] <= PAPER_ROLL[1]):
        raise ValueError(f"posture ranges must stay inside the paper ranges h {PAPER_H} roll {PAPER_ROLL} (got {h} {roll})")
    h0 = _num("EX42_POSTURE_H0", H0_DEFAULT, 0.05)
    out = {"h": h, "roll": roll, "h0": h0,
           "height_w": _num("EX42_POSTURE_HEIGHT_W", PAPER_W[0]), "roll_w": _num("EX42_POSTURE_ROLL_W", PAPER_W[1])}
    cur = os.environ.get("EX42_POSTURE_CURRICULUM", "")
    if cur not in ("", "0", "1"):
        raise ValueError(f"EX42_POSTURE_CURRICULUM must be 0 or 1 (got {cur!r})")
    anneal = os.environ.get("EX42_POSTURE_SIGMA_ANNEAL", "")
    if anneal not in ("", "0", "1"):
        raise ValueError(f"EX42_POSTURE_SIGMA_ANNEAL must be 0 or 1 (got {anneal!r})")
    out["sigma_anneal"] = anneal == "1"
    pm = os.environ.get("EX42_POSTURE_PEN_MASK", "")
    if pm not in ("", "0", "1"):
        raise ValueError(f"EX42_POSTURE_PEN_MASK must be 0 or 1 (got {pm!r})")
    out["pen_mask"] = pm == "1"
    loose = [k for k in CURRICULUM_KEYS[1:] if os.environ.get(k, "") != "" and not (out["sigma_anneal"] and k == "EX42_POSTURE_CHECK_STEPS")]
    if cur != "1" and loose:
        raise ValueError(f"{', '.join(loose)} set but EX42_POSTURE_CURRICULUM is not 1")
    out["curriculum"] = cur == "1"
    if out["curriculum"]:
        if not h[0] <= h0 <= h[1]:
            raise ValueError(f"EX42_POSTURE_H0 {h0} must lie inside the height range {h}")
        out.update(h_start=_num("EX42_POSTURE_H_START", 0.02, 1e-4), roll_start=_num("EX42_POSTURE_ROLL_START", 0.1, 1e-4),
                   h_step=_num("EX42_POSTURE_H_STEP", 0.02, 1e-4), roll_step=_num("EX42_POSTURE_ROLL_STEP", 0.1, 1e-4),
                   h_tol=_num("EX42_POSTURE_H_TOL", 0.02, 1e-4), roll_tol=_num("EX42_POSTURE_ROLL_TOL", 0.1, 1e-4),
                   state_path=os.environ.get("EX42_POSTURE_STATE", ""))
        steps = _num("EX42_POSTURE_CHECK_STEPS", 1200, SAMPLE_EVERY)
        if steps != int(steps):
            raise ValueError("EX42_POSTURE_CHECK_STEPS must be a whole number")
    elif out["sigma_anneal"] and os.environ.get("EX42_POSTURE_CHECK_STEPS", "") != "":
        steps = _num("EX42_POSTURE_CHECK_STEPS", 1200, SAMPLE_EVERY)
        if steps != int(steps):
            raise ValueError("EX42_POSTURE_CHECK_STEPS must be a whole number")
    else:
        steps = 1200
    out["check_steps"] = int(steps)
    return out


def _rank() -> int:
    for k in ("RANK", "LOCAL_RANK"):
        if os.environ.get(k, "").isdigit():
            return int(os.environ[k])
    return 0


def band(cfg, h_half, roll_half):
    """지금 띠 ((h_lo, h_hi), (roll_lo, roll_hi)): 커리큘럼이면 H0 ± 반폭을 범위 안으로 자른 것, 아니면 범위 그대로."""
    if not cfg["curriculum"]:
        return cfg["h"], cfg["roll"]
    (hl, hh), (rl, rh) = cfg["h"], cfg["roll"]
    return (max(hl, cfg["h0"] - h_half), min(hh, cfg["h0"] + h_half)), (max(rl, -roll_half), min(rh, roll_half))


def _slope(x, y):
    x, y = x.double(), y.double()
    vx = ((x - x.mean()) ** 2).sum()
    return float(((x - x.mean()) * (y - y.mean())).sum() / vx) if vx > 1e-12 else float("nan")


def _ranks_mean(values, device):
    """Mean over ranks of each value (None or nan = that rank has no value for it); single process = the values themselves.
    Every rank calls check at the same step (the reward manager calls height_tracking once per env step on each rank)."""
    import torch.distributed as dist

    vals = [None if (v is None or (isinstance(v, float) and math.isnan(v))) else float(v) for v in values]
    if not (dist.is_available() and dist.is_initialized()) or dist.get_world_size() == 1:
        return vals
    t = torch.tensor([[0.0 if v is None else v for v in vals], [0.0 if v is None else 1.0 for v in vals]], dtype=torch.float64,
                     device=device if torch.device(device).type == "cuda" else "cpu")
    dist.all_reduce(t, op=dist.ReduceOp.SUM)
    t = t.cpu()
    return [None if float(t[1, k]) == 0 else round(float(t[0, k] / t[1, k]), 6) for k in range(len(vals))]


class PostureState:
    def __init__(self, n, device, cfg, seed=0):
        self.cfg = cfg
        self.target = torch.zeros((n, 2), device=device)        # [h (m), roll (rad)] (뽑힌 값 · 적용 env 가 아니면 effective 가 [H0, 0])
        self.target[:, 0] = cfg["h0"]
        self.command = torch.full((n, 3), float("nan"), device=device)
        self.active = torch.ones(n, dtype=torch.bool, device=device)
        self.gen = torch.Generator(device="cpu").manual_seed(int(seed) + 4243)
        self.h_half = cfg.get("h_start", 0.0)
        self.roll_half = cfg.get("roll_start", 0.0)
        self.steps = 0                   # height_tracking 이 불린 수 (보상 관리자가 step 마다 한 번)
        self.checks = 0
        self.samples = []                # [(target_h, h, target_roll, roll, reward_h)] 적용 env 만
        self.sigma = list(SIGMA_START) if cfg.get("sigma_anneal") else list(SIGMA_PAPER)   # [높이 m, roll rad]
        self.pen_sum = {}; self.pen_n = {}; self.pen_started = False   # 자세 env 의 벌 항 기여 (값 x 실제 가중) 합 · 횟수 (점검 사이)
        self.state_path = None
        if cfg["curriculum"] and cfg.get("state_path"):
            self.state_path = Path(f"{cfg['state_path']}.rank{_rank()}")
            if self.state_path.is_file():
                saved = json.loads(self.state_path.read_text(encoding="utf-8"))
                self.h_half, self.roll_half = float(saved["h_half"]), float(saved["roll_half"])
                self.steps, self.checks = int(saved.get("steps", 0)), int(saved.get("checks", 0))
                if cfg.get("sigma_anneal") and "sigma" in saved:
                    self.sigma = [float(v) for v in saved["sigma"]]
                print(f"EX42_POSTURE_CURRICULUM resumed {self.state_path} h_half={self.h_half} roll_half={self.roll_half} checks={self.checks}", flush=True)

    def update(self, command, new_episode):
        changed = ~(command == self.command).all(-1) | new_episode.bool()
        k = int(changed.sum())
        if k:
            u = torch.rand((k, 2), generator=self.gen).to(self.target.device)
            (hl, hh), (rl, rh) = band(self.cfg, self.h_half, self.roll_half)
            self.target[changed] = torch.stack([hl + (hh - hl) * u[:, 0], rl + (rh - rl) * u[:, 1]], 1).to(self.target.dtype)
            self.command[changed] = command[changed]
        return changed

    def effective(self):
        """보상 · 관측이 쓰는 목표: 적용 env 는 뽑힌 값, 아니면 [H0, 0] (자세 0)."""
        zero = torch.tensor([self.cfg["h0"], 0.0], device=self.target.device, dtype=self.target.dtype)
        return torch.where(self.active[:, None], self.target, zero)

    def record(self, h, roll, reward_h):
        self.steps += 1
        if self.steps % SAMPLE_EVERY == 0:
            a = self.active
            if bool(a.any()):
                self.samples.append(torch.stack([self.target[a, 0], h[a], self.target[a, 1], roll[a], reward_h[a]], 1).detach().float().cpu())
        if self.steps % self.cfg["check_steps"] == 0:
            return self.check()
        return None

    def check(self):
        self.checks += 1
        (hl, hh), (rl, rh) = band(self.cfg, self.h_half, self.roll_half)
        line = {"step": self.steps, "rank": _rank(), "h": [round(hl, 4), round(hh, 4)], "roll": [round(rl, 4), round(rh, 4)],
                "n": 0, "reward_h": None, "med_h_err": None, "med_roll_err": None, "slope_h": None, "slope_roll": None,
                "widen_h": False, "widen_roll": False}
        if self.samples:
            s = torch.cat(self.samples)
            self.samples = []
            eh, er = (s[:, 0] - s[:, 1]).abs(), (s[:, 2] - s[:, 3]).abs()
            line.update(n=int(len(s)), reward_h=round(float(s[:, 4].mean()), 5), med_h_err=round(float(eh.median()), 5),
                        med_roll_err=round(float(er.median()), 5), slope_h=round(_slope(s[:, 0], s[:, 1]), 4), slope_roll=round(_slope(s[:, 2], s[:, 3]), 4))
            if self.cfg["curriculum"]:
                (phl, phh), (prl, prh) = self.cfg["h"], self.cfg["roll"]
                h_full = self.cfg["h0"] - self.h_half <= phl and self.cfg["h0"] + self.h_half >= phh
                roll_full = -self.roll_half <= prl and self.roll_half >= prh
                if not h_full and line["med_h_err"] < min(self.cfg["h_tol"], BEAT_FRACTION * self.h_half):
                    self.h_half += self.cfg["h_step"]
                    line["widen_h"] = True
                if not roll_full and line["med_roll_err"] < min(self.cfg["roll_tol"], BEAT_FRACTION * self.roll_half):
                    self.roll_half += self.cfg["roll_step"]
                    line["widen_roll"] = True
        if self.pen_n:
            line["pen_posture_env_mean"] = {k: round(self.pen_sum[k] / self.pen_n[k], 7) for k in sorted(self.pen_n)}   # 자세 env 평균 · step 당 기여 (가중 곱함)
            self.pen_sum, self.pen_n = {}, {}
        if self.cfg.get("sigma_anneal"):
            line["sigma_h"], line["sigma_roll"] = self.sigma[0], self.sigma[1]
            judged = _ranks_mean([line.get("slope_h"), line.get("slope_roll"), line.get("med_h_err"), line.get("med_roll_err")], self.target.device)
            line["judged_slope_h"], line["judged_slope_roll"], line["judged_med_h_err"], line["judged_med_roll_err"] = judged
            halve = []
            for ax, slope, err in ((0, judged[0], judged[2]), (1, judged[1], judged[3])):
                # planner 06:39 · lead 06:40 (ledger b148fd9b2): slope > 0.5 AND median error < the current sigma, both as the two-rank mean
                if slope is not None and err is not None and slope > SIGMA_SLOPE and err < self.sigma[ax] and self.sigma[ax] > SIGMA_PAPER[ax]:
                    self.sigma[ax] = max(self.sigma[ax] / 2.0, SIGMA_PAPER[ax])
                    halve.append(("h", "roll")[ax])
            line["sigma_halved"] = halve
            line["next_sigma_h"], line["next_sigma_roll"] = self.sigma[0], self.sigma[1]
        if self.cfg["curriculum"]:
            (nhl, nhh), (nrl, nrh) = band(self.cfg, self.h_half, self.roll_half)
            line["next_h"], line["next_roll"] = [round(nhl, 4), round(nhh, 4)], [round(nrl, 4), round(nrh, 4)]
            if self.state_path is not None:
                tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
                tmp.write_text(json.dumps({"h_half": self.h_half, "roll_half": self.roll_half, "steps": self.steps, "checks": self.checks,
                                           "sigma": self.sigma, "last": line}), encoding="utf-8")
                os.replace(tmp, self.state_path)
        print("EX42_POSTURE_CHECK " + json.dumps(line), flush=True)
        return line


def _state(env):
    st = getattr(env, STATE, None)
    if st is None:
        cfg = settings()
        st = PostureState(env.num_envs, env.device, cfg)
        setattr(env, STATE, st)
        st.column_ok = _posture_columns(env)
        print(f"EX42_POSTURE_SCOPE columns={'all (no column table)' if st.column_ok is None else int(st.column_ok.sum())}"
              f" curriculum={cfg['curriculum']} band={band(cfg, st.h_half, st.roll_half)} check_steps={cfg['check_steps']}", flush=True)
    return st


def _posture_columns(env):
    """(columns,) bool: 자세 명령을 받는 열 = A 족의 연속 종류와 평지. 열 표가 없으면 None (열로는 가르지 않음)."""
    from foothold_s2.terrains import columns as cols
    table = getattr(getattr(env, "unwrapped", env), "_ex42_column_table", None)
    if table is None:
        return None
    ok = [row["family"] == "A" and (row["kind"] in cols.CONTINUOUS or row["kind"] == "flat") for row in table]
    return torch.tensor(ok, dtype=torch.bool, device=env.device)


def active_envs(env, st, command_name="base_velocity"):
    """(N,) bool: 평지 · 연속 열이고 깃발 env 가 아닌 env."""
    active = torch.ones(env.num_envs, dtype=torch.bool, device=env.device)
    if st.column_ok is not None:
        columns = env.scene.terrain.terrain_types.long().to(env.device)
        if bool(((columns < 0) | (columns >= len(st.column_ok))).any()):
            raise ValueError("EX-42 posture: a terrain column is outside the column table")
        active &= st.column_ok[columns]
    try:
        flag = env.command_manager.get_term(command_name).is_flag_env
    except (AttributeError, KeyError):
        flag = None
    if flag is not None:
        active &= ~flag.bool().to(env.device)
    return active


def posture_command_obs(env, command_name: str = "base_velocity"):
    """관측 칸 (N, 2) = [h - H0, roll]. 매 스텝 불리며 명령이 바뀐 env · 새 에피소드 env 의 목표를 다시 뽑는다. 적용 env 가 아니면 [0, 0]."""
    st = _state(env)
    command = env.command_manager.get_command(command_name)[:, :3]
    st.update(command, env.episode_length_buf <= 1)
    st.active = active_envs(env, st, command_name)
    out = st.effective()
    out[:, 0] -= st.cfg["h0"]
    return out


def body_roll(quat_wxyz):
    w, x, y, z = quat_wxyz.unbind(-1)
    return torch.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))


def body_height(env):
    root_z = env.scene["robot"].data.root_pos_w[:, 2]
    try:
        hits = env.scene["height_scanner"].data.ray_hits_w[..., 2]
    except (KeyError, AttributeError):
        return root_z - env.scene.env_origins[:, 2]
    hits = torch.where(torch.isfinite(hits), hits, torch.full_like(hits, float("nan")))
    ground = torch.nanmean(hits, dim=1)
    return root_z - torch.where(torch.isfinite(ground), ground, env.scene.env_origins[:, 2])


def height_tracking(env):
    """높이 보상 · 표본 · 점검 (보상 관리자가 step 마다 한 번 부른다). 목표는 effective (적용 env 가 아니면 H0)."""
    st = _state(env)
    target = st.effective()
    h = body_height(env)
    r = torch.exp(-(target[:, 0] - h).abs() / st.sigma[0])           # σ 풀림 끔이면 원문 0.0025 그대로
    st.record(h, body_roll(env.scene["robot"].data.root_quat_w), r)
    return r


def roll_tracking(env):
    st = _state(env)
    return torch.exp(-(st.effective()[:, 1] - body_roll(env.scene["robot"].data.root_quat_w)).abs() / st.sigma[1])   # 끔이면 0.05


def register_observation(obs_group) -> bool:
    """apply_ex41_pose_observation 이 만든 PoseCommandGroup 의 칸 함수를 바꾼다 (스위치가 켜졌을 때만)."""
    if not enabled():
        return False
    obs_group.pose_cmd.func = posture_command_obs
    obs_group.pose_cmd.params = {"command_name": "base_velocity"}
    return True


def register_rewards(env_cfg, term_cfg_class=None) -> bool:
    if not enabled() or hasattr(env_cfg.rewards, HEIGHT_TERM):
        return False
    cfg = settings()
    if term_cfg_class is None:
        from isaaclab.managers import RewardTermCfg as term_cfg_class
    setattr(env_cfg.rewards, HEIGHT_TERM, term_cfg_class(func=height_tracking, weight=cfg["height_w"], params={}))
    setattr(env_cfg.rewards, ROLL_TERM, term_cfg_class(func=roll_tracking, weight=cfg["roll_w"], params={}))
    register_pen_mask(env_cfg)                               # EX42_POSTURE_PEN_MASK=1 일 때만 (lead 06:31)
    orient = getattr(env_cfg.rewards, ORIENT_TERM, None)
    if orient is not None:
        orient.func = posture_orientation                    # 원문 r7 (pitch 만) · 적용 env 만 · 칸 가중은 그대로 (지킬 칸 보호 · 옛 식은 끈 env 에 남음)
        print(f"EX42_POSTURE_ORIENT where=start term={ORIENT_TERM} weight={orient.weight} active=pitch_only_paper_w={PAPER_PITCH_W} inactive=gxy_l2", flush=True)
    print(f"EX42_POSTURE where=start h={list(cfg['h'])} roll={list(cfg['roll'])} h0={cfg['h0']} height_w={cfg['height_w']} roll_w={cfg['roll_w']}"
          f" curriculum={cfg['curriculum']} check_steps={cfg['check_steps']}"
          + (f" h_start={cfg['h_start']} roll_start={cfg['roll_start']} h_step={cfg['h_step']} roll_step={cfg['roll_step']}"
             f" h_tol={cfg['h_tol']} roll_tol={cfg['roll_tol']} state={cfg['state_path'] or '-'}" if cfg["curriculum"] else "")
          + (f" sigma_anneal=1 sigma_start={list(SIGMA_START)} sigma_end={list(SIGMA_PAPER)} halve_when_slope>{SIGMA_SLOPE}" if cfg.get("sigma_anneal") else f" sigma={list(SIGMA_PAPER)}"), flush=True)
    return True


def _pen_wrap(term, func, target):
    """자세 env 벌 낮춤 · 기록. target None = 값을 안 바꾸고 기록만 (collision)."""
    def posture_pen_term(env, **params):
        value = func(env, **params)
        raw = getattr(env, "unwrapped", env)
        w = float(raw.reward_manager.get_term_cfg(term).weight)
        st = _state(env)
        act = st.active.to(value.device)
        if target is not None:
            factor = 0.0 if w == 0.0 else target / w
            value = torch.where(act, value * factor, value)
        if not st.pen_started and target is not None:
            st.pen_started = True
            print(f"EX42_POSTURE_PEN_MASK where=first_call masked_envs={int(act.sum())} of={int(act.numel())} "
                  + " ".join(f"{k}={raw.reward_manager.get_term_cfg(k).weight}->{v}" for k, v in PEN_TARGETS.items()
                             if k in raw.reward_manager.active_terms), flush=True)
        if bool(act.any()):
            st.pen_sum[term] = st.pen_sum.get(term, 0.0) + float((value[act] * w).mean())
            st.pen_n[term] = st.pen_n.get(term, 0) + 1
        return value
    posture_pen_term.ex42_posture_pen = target
    posture_pen_term.__wrapped__ = func
    return posture_pen_term


def register_pen_mask(env_cfg) -> bool:
    if not settings().get("pen_mask"):
        return False
    done = []
    for term, target in list(PEN_TARGETS.items()) + [(t, None) for t in PEN_LOG_ONLY]:
        cfg = getattr(env_cfg.rewards, term, None)
        if cfg is None:
            if target is not None:
                raise ValueError(f"EX42_POSTURE_PEN_MASK=1 but the env config has no {term} term")
            continue
        if getattr(cfg.func, "ex42_posture_pen", "unset") != "unset":
            continue
        if target is not None and cfg.weight < 0 and target < cfg.weight:
            raise ValueError(f"posture pen target {target} for {term} is stronger than its weight {cfg.weight} (this only lowers)")
        cfg.func = _pen_wrap(term, cfg.func, target); done.append(f"{term}:{cfg.weight}->{'log' if target is None else target}")
    print(f"EX42_POSTURE_PEN_MASK where=start posture_envs_only {' '.join(done)}", flush=True)
    return True


ORIENT_TERM = "flat_orientation"
PAPER_PITCH_W = -0.5                 # 원문 Table III r7 = w7L |θ_y| · w7L -0.5 (pitch 만 · lead 11/22 03:00 PDF 5 쪽 눈 확인)


def body_pitch(quat_wxyz):
    w, x, y, z = quat_wxyz.unbind(-1)
    return torch.asin(torch.clamp(2 * (w * y - z * x), -1.0, 1.0))


def posture_orientation(env, asset_cfg=None):
    """몸 자세 벌 (EX42_POSTURE 켬일 때 flat_orientation 칸의 함수를 이것으로 바꿈 · lead 11/22 03:00 · planner 02:59):
    자세 명령 적용 env 는 원문 r7 = |θ_y| (pitch 만 · 칸 가중을 곱해 PAPER_PITCH_W 가 되게 |PAPER_PITCH_W / 지금 가중| 배) · 아닌 env (듬성 열 · 깃발) 는 옛 g_x² + g_y² 그대로.
    옛 식은 roll 명령을 따를수록 깎였다 (roll 1.0 에서 -0.71 · 추종 보상 +0.2)."""
    name = getattr(asset_cfg, "name", "robot") if asset_cfg is not None else "robot"
    data = env.scene[name].data
    old = torch.sum(data.projected_gravity_b[:, :2] ** 2, dim=1)
    try:
        w = float(env.reward_manager.get_term_cfg(ORIENT_TERM).weight)
    except (AttributeError, ValueError, KeyError):
        w = -1.0
    new = body_pitch(data.root_quat_w).abs() * (abs(PAPER_PITCH_W) / abs(w)) if w != 0 else torch.zeros_like(old)
    return torch.where(_state(env).active, new, old)


def check_runner_pose(pose) -> None:
    """runner 의 자세 칸 확인 (스위치 켜짐): 유한 · 범위 안. 꺼짐은 runner 가 옛 0 확인을 그대로 한다."""
    cfg = settings()
    if not torch.isfinite(pose).all():
        raise ValueError("EX-42 posture pose_cmd must be finite")
    dh, roll = pose[:, 0], pose[:, 1]
    eps = 1e-5
    if (dh < cfg["h"][0] - cfg["h0"] - eps).any() or (dh > cfg["h"][1] - cfg["h0"] + eps).any() \
            or (roll < cfg["roll"][0] - eps).any() or (roll > cfg["roll"][1] + eps).any():
        raise ValueError("EX-42 posture pose_cmd is outside the posture ranges")
