"""속도 추정 탐침 자식 (planner-lx 11/15): actor 가 받는 지각 추정 est 의 앞 3 칸 (몸 선속도 추정) 과 실제 몸 선속도를 step 마다 적는다.
평균 행동 그대로 · 잠근 사본은 읽기만. 명령은 PROBE_CASES 로 칸마다 덮어쓴다 (run_child_cases.py 와 같은 길 · <EXTRA>_<n>.npz = 실제 칸 n-1).
쓰는 법: PROBE_CASES="0.1/0;0.3/0;0.5/0;0/0;0.1/0" PROBE_EXTRA=<npz 앞부분> python -B run_child_est.py <eval_map_modes 인자>"""
import os, runpy, sys

import numpy as np

from foothold_s2.eval import adapters, map_mode_cells
from foothold_s2.runners import start_runner

CASES = [tuple(float(x) for x in item.split("/")) for item in os.environ["PROBE_CASES"].split(";")]
EXTRA = os.environ["PROBE_EXTRA"]
state = {"case": -1, "rows": []}
_disable = map_mode_cells.disable_heading_for_fixed_eval
_assert = map_mode_cells.assert_heading_off_for_fixed_eval
RUNNER = next(value for name, value in vars(start_runner).items() if isinstance(value, type) and "_ppo_obs" in vars(value))
_ppo_obs = RUNNER._ppo_obs


SAVE_O = os.environ.get("EST_SAVE_O", "") == "1"       # 1 이면 고유감각 o (45 칸) 도 step 마다 적는다 (정보 유무 회귀용 · lead 07:31 설계)


SAVE_P = os.environ.get("EST_SAVE_P", "") == "1"
SAVE_R = os.environ.get("EST_SAVE_R", "") == "1"
SAVE_H = os.environ.get("EST_SAVE_H", "") == "1"         # 1 이면 지각 머리 층 (ie.heads) 의 입력을 step 마다 적는다 (머리 층 다시 맞추기용)
LINEAR = os.environ.get("EST_LINEAR", "")                # "ax,bx,ay,by": actor 에 들어가는 속도 칸을 v' = a v + b 로 바꾼다 (선형 보정 시험)
HEAD = os.environ.get("EST_HEAD", "")                    # npz (W (3, TOKEN) · b (3,)): 머리 층의 속도 행만 이 값으로 바꾼다 (메모리 안에서만)
if LINEAR:
    LINEAR = tuple(float(x) for x in LINEAR.split(","))
ORACLE_V = os.environ.get("EST_ORACLE_V", "") == "1"   # 1 이면 actor 에 들어가는 est 의 속도 칸 (16:19) 만 실제 몸 선속도로 바꾼다 (개입 시험)


def ppo_obs(self, raw, est, *rest):   # 새 코드 (actor 대칭 손실 판) 는 거울 줄기 est_m 을 셋째 값으로 준다: 그대로 넘긴다
    if SAVE_H and "h" not in state:                      # runner 를 만들 때의 틀 호출 (지각이 아직 안 돎) 은 적지 않는다
        return _ppo_obs(self, raw, est, *rest)
    row = (est.detach().float().cpu().numpy().copy(), raw["base_vel"].detach().float().cpu().numpy().copy())
    if ORACLE_V:
        est = est.clone()
        est[..., 16:19] = raw["base_vel"].to(est.dtype)
    if LINEAR:
        est = est.clone()
        est[..., 16] = LINEAR[0] * est[..., 16] + LINEAR[1]
        est[..., 17] = LINEAR[2] * est[..., 17] + LINEAR[3]
    if SAVE_O:
        row += (self._split(raw)[0].detach().float().cpu().numpy().copy(),)
    if SAVE_H:
        row += (state["h"],)
    if SAVE_P:                                            # 몸 위치 · 자세 (세계 좌표) · lead 19:12 재출발 탐침
        robot = getattr(self.env, "unwrapped", self.env).scene["robot"].data
        state.setdefault("p", []).append(np.concatenate([robot.root_pos_w.detach().float().cpu().numpy(),
                                                          robot.root_quat_w.detach().float().cpu().numpy(),
                                                          robot.root_ang_vel_b.detach().float().cpu().numpy()], -1))
    if SAVE_R:                                            # 보상항별 step 값 (가중 곱한 값 · 가중 0 인 항은 0) · lead 15:15
        rm = getattr(self.env, "unwrapped", self.env).reward_manager
        state.setdefault("r", []).append(rm._step_reward.detach().float().cpu().numpy().copy())
        state["r_names"] = list(rm._term_names)
        state["r_weights"] = [float(c.weight) for c in rm._term_cfgs]
    state["rows"].append(row)
    return _ppo_obs(self, raw, est, *rest)


# 명령 바꿈 칸 (planner-lx 11/15 08:0x): PROBE_SWITCH="<CASES 번호>:<step>:<vx>/<vy>" 면 그 칸은 그 step 부터 명령을 바꾼다 (걷다가 내림).
SWITCH = os.environ.get("PROBE_SWITCH", "")
if SWITCH:                                                # 여러 칸이면 "a:b:c/d;e:f:g/h" (11/15 19:4x)
    SWITCH = {int(_slot): (int(_step), tuple(float(x) for x in _value.split("/")))
              for _slot, _step, _value in (item.split(":") for item in SWITCH.split(";"))}


SPREAD = os.environ.get("EST_SPREAD", "")               # "lo:hi"
if SPREAD:
    SPREAD = tuple(float(x) for x in SPREAD.split(":"))


def write(term) -> None:
    vx, vy, *_wz = CASES[state["case"] % len(CASES)]; wz = _wz[0] if _wz else 0.0   # 셋째 값 = yaw 명령 rad/s (planner-lx 11/19 · lead 14:43)
    _sw = SWITCH.get(state["case"] % len(CASES)) if SWITCH else None
    if _sw and len(state["rows"]) >= _sw[0]:
        vx, vy = _sw[1]
    if SPREAD and vy == 0 and abs(vx - 0.1) < 1e-9:      # 명령 0.1 칸을 env 마다 lo~hi 로 고르게 편다 (수집의 저속 띠 흉내)
        import torch
        term.vel_command_b[:, 0] = torch.linspace(SPREAD[0], SPREAD[1], term.vel_command_b.shape[0], device=term.vel_command_b.device)
        term.vel_command_b[:, 1] = 0.0
        term.vel_command_b[:, 2] = 0.0
        return
    term.vel_command_b[:, 0] = vx
    term.vel_command_b[:, 1] = vy
    term.vel_command_b[:, 2] = wz if "wz" in dir() else 0.0


def flush() -> None:
    if state["rows"]:
        est, true = (np.stack([row[i] for row in state["rows"]]) for i in range(2))
        extra = {"o": np.stack([row[2] for row in state["rows"]])} if SAVE_O else {}
        if SAVE_H:
            extra["h"] = np.stack([row[-1] for row in state["rows"]])
        if SAVE_R and state.get("r"):
            extra.update(r=np.stack(state["r"]), r_names=np.array(state["r_names"]), r_weights=np.array(state["r_weights"]))
            state["r"] = []
        if SAVE_P and state.get("p"):
            extra["p"] = np.stack(state["p"]); state["p"] = []
        np.savez(f"{EXTRA}_{state['case']}.npz", est=est, true=true, command=np.array(CASES[state["case"] % len(CASES)]), **extra)
    state["rows"] = []


def disable(term):
    _disable(term)
    flush()
    state["case"] += 1
    write(term)


def check(term):
    _assert(term)
    write(term)


# 학습 판과 평가 판의 차이를 하나씩 켜 보는 칸 (planner-lx 11/15 06:2x): EST_ACT=sample 이면 행동을 정책 std × EST_SCALE 로 표집,
# EST_Z=sample 이면 지각 잠재 z 를 표집 (학습 수집과 같음 · 평가 기본은 평균). 둘 다 비우면 평가 그대로.
EST_ACT = os.environ.get("EST_ACT", "")
EST_Z = os.environ.get("EST_Z", "")
EST_SCALE = float(os.environ.get("EST_SCALE", "1.0"))
_init = adapters.S2Policy.__init__


def init(self, runner, n, z_mode=None, act_mode=None, map_mode=None):
    _init(self, runner, n, z_mode=(EST_Z or z_mode), act_mode=(EST_ACT or act_mode), map_mode=map_mode)
    if EST_ACT == "sample" and EST_SCALE != 1.0:
        import torch
        with torch.no_grad():
            runner.alg.policy.std.mul_(EST_SCALE)
    print("EST_PROBE", {"act": self.act_mode, "z": self.z_mode, "scale": EST_SCALE}, flush=True)


def head_hook(module, args):
    state["h"] = args[0].detach().float().cpu().numpy().copy()


def init_head(self, runner, n, z_mode=None, act_mode=None, map_mode=None):
    (init if (EST_ACT or EST_Z) else _init)(self, runner, n, z_mode=z_mode, act_mode=act_mode, map_mode=map_mode)
    import torch
    heads = runner.perception.ie.heads
    if HEAD:
        fit = np.load(HEAD)
        with torch.no_grad():
            heads.weight[32:35] = torch.as_tensor(fit["W"], dtype=heads.weight.dtype, device=heads.weight.device)
            heads.bias[32:35] = torch.as_tensor(fit["b"], dtype=heads.bias.dtype, device=heads.bias.device)
        print("EST_HEAD patched", HEAD, tuple(fit["W"].shape), flush=True)
    if SAVE_H:
        heads.register_forward_pre_hook(head_hook)


if EST_ACT or EST_Z:
    adapters.S2Policy.__init__ = init
if SAVE_H or HEAD:
    adapters.S2Policy.__init__ = init_head
# 관측 잡음 칸 (planner-lx 11/15 07:5x): EST_OBS_NOISE=on|off 이면 평가기가 DR 을 끄는 자리 (disable_eval_randomization · env 만들기 전)
# 에서 policy 관측 묶음의 enable_corruption 을 그 값으로 두고, 바꾸기 전 값을 찍는다. 비우면 평가 그대로 (값만 찍음).
EST_OBS_NOISE = os.environ.get("EST_OBS_NOISE", "")
_disable_dr = adapters.disable_eval_randomization


PIN_MASS = os.environ.get("PROBE_MASS_ADD", "")      # 몸통 질량 더하기 한 값 (run_child_dr.py 와 같은 길)
PIN_FRICTION = os.environ.get("PROBE_FRICTION", "")  # 평가 마찰 정책 값을 한 값으로 (로봇 · 지형 둘 다)


def disable_dr(env_cfg):
    keep = None
    if PIN_MASS:
        keep = env_cfg.events.add_base_mass
        keep.params["mass_distribution_params"] = (float(PIN_MASS), float(PIN_MASS))
    names = _disable_dr(env_cfg)
    if keep is not None:
        env_cfg.events.add_base_mass = keep
    before = bool(env_cfg.observations.policy.enable_corruption)
    if EST_OBS_NOISE:
        env_cfg.observations.policy.enable_corruption = EST_OBS_NOISE == "on"
    print("EST_OBS_NOISE", {"before": before, "after": bool(env_cfg.observations.policy.enable_corruption)}, flush=True)
    return names


adapters.disable_eval_randomization = disable_dr
if PIN_FRICTION:
    from foothold_s2.eval import ex42_friction as _friction
    _map_policy = _friction.map_policy

    def _pinned_policy(args):
        policy = _map_policy(args)
        return None if policy is None else {**policy, "static": float(PIN_FRICTION), "dynamic": float(PIN_FRICTION)}

    _friction.map_policy = _pinned_policy
# DR 켠 칸 (planner-lx 11/15 08:1x): EST_DRON=1 이면 run_child_dron.py 와 같은 두 우회 (EX-42 고정 마찰 정책 비움 · N21 진입 검사 건너뜀)
# 를 걸어 --dr-mode on 인자를 받게 한다. 이 출력은 기록 · 판정에 쓰지 않는 내 폴더 측정이다.
if os.environ.get("EST_DRON", "") == "1":
    from foothold_s2.eval import ex42_friction, n21_dr_record
    ex42_friction.map_policy = lambda args: None
    n21_dr_record.validate_entrypoint = lambda args: None
RUNNER._ppo_obs = ppo_obs
map_mode_cells.disable_heading_for_fixed_eval = disable
map_mode_cells.assert_heading_off_for_fixed_eval = check
sys.argv = ["eval_map_modes"] + sys.argv[1:]
try:
    runpy.run_module("foothold_s2.eval.eval_map_modes", run_name="__main__")
finally:
    flush()
