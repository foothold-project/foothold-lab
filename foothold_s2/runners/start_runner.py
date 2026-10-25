"""START 전용 runner (12 §6.1 · 13 §6 · 18 §5.1). 설치 rsl_rl 3.1.2 `OnPolicyRunner` 를 물려받아 한 iteration 을 다시 짠다.

한 iteration 의 순서(12 §6.1, 바꾸면 ratio 입력이 수집 때와 달라지므로 금지):
    ① rollout 수집(inference_mode) · 지각 50 Hz 진행 · actor 입력 96 을 PPO 버퍼에 그대로 저장 · 지각 재생 버퍼 채움
    ② PPO update(설치 PPO 그대로 · 저장된 입력과 log prob 로만)
    ③ 지각 재생 · L_TR + L_IE 를 한 번의 backward(계수 1 · 1) · 지각 optimizer 따로
    ④ AdaSmpl 통계 갱신(분산이면 count · sum · sumsq 전 rank 합)
    ⑤ 로그 · 저장(12 §6.1 상태 목록 전부)

env 가 내야 하는 관측 묶음(env cfg 쪽 계약 · lead 의 s2_env_cfg 와 맞출 것):
    policy (N, 45)    o_t (13 §2 식 1 순서 · 스케일)
    depth  (N, 60, 60) 정규화 · 증강 뒤 깊이, 미검출 1.0 (11 §2)
    gt_map (N, 512) 또는 (N, 32, 16)  정답 H^b (중력 정렬 yaw 틀)
    gt_feet (N, 100)  정답 H^f (발 4 개 x 5 x 5)
    base_vel (N, 3)   몸 틀 선속도 (특권)
    contacts (N, 4)   발 접촉 (특권)
critic 입력 664 는 이 runner 가 [policy, base_vel, contacts, gt_map, gt_feet] 순으로 묶는다(13 §2).

설치 `save()` 는 정책 · PPO optimizer · RND 만 저장한다(on_policy_runner.py 291~303 행). 여기서 덧붙인다.
"""

from __future__ import annotations

import json
import os
import random
import time
from collections import deque

import numpy as np
import torch
import torch.nn as nn
from tensordict import TensorDict

from rsl_rl.algorithms import PPO
from rsl_rl.runners import OnPolicyRunner
from rsl_rl.utils import resolve_obs_groups, store_code_state

import rsl_rl
from foothold_s2.models.start_perception import AdaSmpl, PerceptionCfg, StartPerception
from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY, OBS_GROUPS, StartActorCritic
from foothold_s2.runners import kl_probe, manifest as run_manifest
from foothold_s2.runners.contracts import start_contract_bad
from foothold_s2.runners.action_stats import ActionStats, phys_probe
from foothold_s2.runners.map_switch import MapSwitchRecorder, draw_map_off, make_generator
from foothold_s2.runners.perception_replay import PerceptionReplay
from foothold_s2.runners.reward_split import RewardSplit
from foothold_s2.runners.status import write_status

CKPT_FORMAT = "foothold-start/1"
MODE_DEFAULTS = {"est_mode": "learned", "critic_mode": "legacy"}   # 옛 체크포인트(G0 · G1 · EX-09 · EX-10)에는 이 칸이 없다: 그때의 동작이 이 값이다

# 지각 optimizer 수치: 전부 가정 (12 §6.1, START · 선행에 없음)
PERCEPTION_DEFAULTS = {
    "learning_rate": 5e-4,
    "weight_decay": 0.0,
    "num_learning_epochs": 5,
    "num_mini_batches": 4,
    "microbatch_envs": 256,
    "max_grad_norm": 1.0,
    "depth_dtype": "float16",
    "replay_impl": "a3",  # loop · a1 · a2 · a3 (models/replay_fast.py · 계산 순서만 다르고 학습 내용은 같음 · lead 결정 10/20 RL-3)
    "replay_autocast": None,  # None · "bf16" (RL-3 B · 정확도 차이는 손실 값으로 따로 기록)
    "kl_fp32": False,  # bf16 일 때 I-E heads · KL 만 fp32 (RL-3 B 후보)
    "latest_interval": 100,  # latest.pt 를 이 간격으로 덮어쓴다(무인 재개용 · 번호 붙은 model_N.pt 는 save_interval 마다 그대로)
    "status_interval": 10,  # train_start_status.json 을 이 간격으로 갱신한다(첫 iteration 은 항상)
    # ---- SONNET-X11 (EX-11 · EX-12). 기본값은 기존 G0 · G1 동작 그대로다 ----
    "est_mode": "learned",  # learned | zero | oracle_vel. zero: 지각은 그대로 돌고 actor 입력의 est 51 칸만 0. oracle_vel: est 51 칸 중 앞 3 칸 = env 의 실제 몸 선속도(몸 좌표, oracle_vel_noise 만큼 균일 잡음), 나머지 48 칸 0. 수집 · PPO 저장 · 평가 모두 _ppo_obs 하나를 지난다
    "oracle_vel_noise": 0.1,  # oracle_vel 일 때 선속도에 더하는 균일 잡음 ±(v2 의 base_lin_vel 관측 잡음과 같은 값). 평가 경계(adapters.load_s2_runner)에서는 0 으로 둔다(관측 잡음을 끄는 평가 규칙)
    "critic_mode": "legacy",  # legacy | clean52. clean52: critic = env 의 잡음 없는 critic 묶음 52 + 지도 512 + 발 지도 100 = 664 (vel3 · contact4 는 52 안에 있어 중복 없음)
    "log_action_stats": False,  # raw a · clip 뒤 a 분위 · 포화율 · 관절별 연속 포화 · PD target · 토크 포화를 action_stats.jsonl 에 (X5)
    "log_reward_split": False,  # 항별 보상을 움직이는 env · 멈춘 env 로 나눠 train_extra.jsonl 에 (lead 요청, 기록만)
    "log_kl": False,  # PPO 전후 · 지각 phi 전후 조건부 policy KL 을 train_extra.jsonl 에 (X6, scheduler 에 연결하지 않는다)
    "kl_probe_envs": 256,
    "contract": None,  # "start": 명령이 START 원문 범위를 벗어나면 실행 무효(멈추고 기록)
    "stop_on_nonfinite": False,  # NaN/Inf(보상 · 행동 · 손실)이면 실행 무효
    # ---- SONNET-X25f (EX-33 S-B). 기본값 0 은 B 와 같은 동작이다 ----
    "p_map_off": 0.0,  # env 마다 에피소드 시작(reset) 때 이 확률로 «지도 끔» 을 뽑아 그 에피소드 끝까지 유지한다(끔 = est 를 만들 때 지도 토큰을 attention 키에서 뺌). 0 이면 뽑지 않고 기록기도 안 켠다
    "map_switch_seed": 20251025,  # 끔 뽑기 전용 난수열의 시드(전역 난수를 건드리지 않는다)
}


def _nan_to_none(x):
    """json 에 NaN 을 쓰지 않는다(집단에 끝난 에피소드가 없으면 평균이 NaN)."""
    if isinstance(x, dict):
        return {k: _nan_to_none(v) for k, v in x.items()}
    if isinstance(x, float) and x != x:
        return None

    return x


class StartRunner(OnPolicyRunner):
    def __init__(self, env, train_cfg: dict, log_dir: str | None = None, device: str = "cpu") -> None:
        # 설치 __init__ 은 env 관측 묶음으로 obs_groups 를 풀고 정책을 만든다. 우리는 정책이 지각 뒤 입력을 받으므로
        # 같은 일을 그 입력 모양으로 한다(설치 54~78 행과 같은 속성을 채운다).
        # TF32 를 끈 채로 고정한다: cuDNN GRU 가 TF32 면 GRUCell 과 hidden 이 3e-4 까지 달라진다(lead 결정 10/20 RL-3)
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cuda.matmul.allow_tf32 = False
        self.cfg = train_cfg
        self.alg_cfg = train_cfg["algorithm"]
        self.policy_cfg = train_cfg["policy"]
        self.device = device
        self.env = env
        self._configure_multi_gpu()
        self.num_steps_per_env = self.cfg["num_steps_per_env"]
        self.save_interval = self.cfg["save_interval"]

        pcfg = dict(PERCEPTION_DEFAULTS)
        pcfg.update(train_cfg.get("perception", {}))
        self.pcfg = pcfg
        if pcfg["est_mode"] not in ("learned", "zero", "oracle_vel") or pcfg["critic_mode"] not in ("legacy", "clean52"):
            raise ValueError(f"est_mode {pcfg['est_mode']!r} · critic_mode {pcfg['critic_mode']!r} 는 허용값이 아니다")
        p_off = float(pcfg["p_map_off"])
        if not 0.0 <= p_off <= 1.0:
            raise ValueError(f"p_map_off 는 [0, 1]: {p_off}")
        if p_off > 0.0 and pcfg.get("map_input", "reconstruction") == "none":
            raise ValueError("p_map_off > 0 은 지도 입력이 있는 판에서만 쓴다")
        self.p_map_off = p_off
        self.manifest = None
        self.manifest_dir = None
        self.perception = StartPerception(
            PerceptionCfg(map_input=pcfg.get("map_input", "reconstruction"), force_gt=bool(pcfg.get("force_gt", False)),
                          depth_delay_ticks=pcfg.get("depth_delay_ticks", 1))
        ).to(device)
        self.perception.ie.heads_fp32 = bool(pcfg.get("kl_fp32", False))
        self.perception_optimizer = torch.optim.Adam(
            self.perception.parameters(), lr=pcfg["learning_rate"], weight_decay=pcfg["weight_decay"]
        )
        self.adasmpl = AdaSmpl(self.perception.cfg.p_smpl_init, self.perception.cfg.cv_eps, self.perception.cfg.force_gt)

        raw = self.env.get_observations().to(device)
        self._check_raw(raw)
        template = self._ppo_obs(raw, torch.zeros(raw.batch_size[0], 51, device=device))
        self.cfg["obs_groups"] = resolve_obs_groups(template, dict(OBS_GROUPS), ["critic"])
        self.alg = self._construct_algorithm(template)
        self.replay = PerceptionReplay(
            self.env.num_envs, self.num_steps_per_env, device, getattr(torch, pcfg["depth_dtype"])
        )
        self.map_switch_gen = make_generator(device, pcfg["map_switch_seed"]) if p_off > 0.0 else None
        self.map_switch = MapSwitchRecorder(self.env.num_envs, device) if p_off > 0.0 else None

        self.disable_logs = self.is_distributed and self.gpu_global_rank != 0
        self.log_dir = log_dir
        self.writer = None
        self.tot_timesteps = 0
        self.tot_time = 0
        self.current_learning_iteration = 0
        self.git_status_repos = [rsl_rl.__file__]
        self.last_perception_losses: dict[str, float] = {}
        self._resumed = False
        self.memory_marks: dict[str, int] = {}
        self.memory_log: list[dict] = []  # iteration 마다 단계별 peak (18 §5.2 측정)
        self.iter_log: list[dict] = []

    # ------------------------------------------------------------------ 관측
    REQUIRED = {"policy": (45,), "depth": (60, 60), "gt_feet": (100,), "base_vel": (3,), "contacts": (4,)}

    def _check_raw(self, raw: TensorDict) -> None:
        for k, shape in self.REQUIRED.items():
            if k not in raw.keys():
                raise KeyError(f"env 관측에 '{k}' 묶음이 없다 (start_runner 머리말 계약)")
            got = tuple(raw[k].shape[1:])
            if k == "depth" and raw[k][0].numel() == 3600:
                got = shape  # (60, 60) · (60, 60, 1) · 평탄화 3600 모두 받는다
            if got != shape:
                raise ValueError(f"'{k}' 모양 {got} 이 계약 {shape} 과 다르다")
        if self.pcfg["critic_mode"] == "clean52":
            if "critic" not in raw.keys() or tuple(raw["critic"].shape[1:]) != (52,):
                raise KeyError("critic_mode=clean52 인데 env 관측에 (N, 52) 'critic' 묶음이 없다")
        if "gt_map" not in raw.keys() or raw["gt_map"][0].numel() != 512:
            raise ValueError("'gt_map' 은 512 칸(32 x 16)이어야 한다")

    @staticmethod
    def _split(raw: TensorDict):
        n = raw.batch_size[0]
        return (
            raw["policy"],
            raw["depth"].reshape(n, 60, 60),
            raw["gt_map"].reshape(n, 32, 16),
            raw["gt_feet"].reshape(n, 100),
            raw["base_vel"],
            raw["contacts"],
        )

    def _est_in(self, est: torch.Tensor, vel: torch.Tensor, noise: float | None = None) -> torch.Tensor:
        """actor 입력의 est 51 칸을 est_mode 로 정한다. learned: 지각 est 그대로 · zero: 전부 0 · oracle_vel: 앞 3 칸 = 실제 몸 선속도 vel(+균일 잡음 ±noise), 나머지 48 칸 0.
        est (..., 51) · vel (..., 3) 는 같은 앞 차원을 가진다. noise 가 None 이면 pcfg 의 oracle_vel_noise."""
        mode = self.pcfg["est_mode"]

        if mode == "zero":
            return torch.zeros_like(est)

        if mode == "oracle_vel":
            n = self.pcfg["oracle_vel_noise"] if noise is None else noise
            v = vel + (torch.empty_like(vel).uniform_(-n, n) if n > 0 else 0.0)
            out = torch.zeros_like(est)
            out[..., :3] = v

            return out

        return est

    def _ppo_obs(self, raw: TensorDict, est: torch.Tensor) -> TensorDict:
        """actor 입력 = o45 + est51 (est_mode=zero 면 est 칸이 0, oracle_vel 이면 앞 3 칸만 실제 선속도), critic 입력 664. 수집 · 부트스트랩 · 평가 adapter 가 모두 이 함수를 지난다."""
        o, _, gmap, gfeet, vel, con = self._split(raw)
        n = o.shape[0]
        est_in = self._est_in(est, vel)
        if self.pcfg["critic_mode"] == "clean52":
            critic = torch.cat([raw["critic"].reshape(n, 52), gmap.reshape(n, -1), gfeet], -1)
        else:
            critic = torch.cat([o, vel, con, gmap.reshape(n, -1), gfeet], -1)
        return TensorDict(
            {
                ACTOR_KEY: torch.cat([o, est_in], -1),
                CRITIC_KEY: critic,
            },
            batch_size=[n],
            device=o.device,
        )

    def _construct_algorithm(self, obs: TensorDict) -> PPO:
        self.policy_cfg.pop("class_name", None)
        policy = StartActorCritic(obs, self.cfg["obs_groups"], self.env.num_actions, **self.policy_cfg).to(self.device)
        alg_cfg = dict(self.alg_cfg)
        alg_cfg.pop("class_name", None)
        alg = PPO(policy, device=self.device, **alg_cfg, multi_gpu_cfg=self.multi_gpu_cfg)
        alg.init_storage("rl", self.env.num_envs, self.num_steps_per_env, obs, [self.env.num_actions])
        return alg

    # ------------------------------------------------------------------ 메모리 표 (18 §5.2)
    def _cuda(self) -> bool:
        return torch.cuda.is_available() and str(self.device).startswith("cuda")

    def _mark(self, name: str, it: int | None = None) -> None:
        """누적 peak(프로세스 시작부터) 와 단계 peak(직전 _phase_start 부터) 를 함께 남긴다."""
        if self._cuda():
            torch.cuda.synchronize(self.device)
            cum = int(torch.cuda.max_memory_allocated(self.device))
            self.memory_marks[name] = max(self.memory_marks.get(name, 0), cum)
            self.memory_log.append({"it": it, "phase": name, "cum_peak": cum,
                                    "phase_peak": int(torch.cuda.max_memory_allocated(self.device)) if self._phase_reset else cum,
                                    "allocated": int(torch.cuda.memory_allocated(self.device))})

    _phase_reset = False

    def _phase_start(self) -> None:
        """단계 peak 를 재려면 measure_phases=True. 누적 peak 는 memory_log 의 cum_peak 를 최댓값으로 다시 모은다."""
        if self._cuda() and self.pcfg.get("measure_phases", False):
            self._phase_reset = True
            prev = int(torch.cuda.max_memory_allocated(self.device))
            self._cum_before = max(getattr(self, "_cum_before", 0), prev)
            torch.cuda.reset_peak_memory_stats(self.device)

    # ------------------------------------------------------------------ 학습
    def learn(self, num_learning_iterations: int, init_at_random_ep_len: bool = False) -> None:
        self._prepare_logging_writer()
        if init_at_random_ep_len:
            self.env.episode_length_buf = torch.randint_like(
                self.env.episode_length_buf, high=int(self.env.max_episode_length)
            )
        raw = self.env.get_observations().to(self.device)
        self.train_mode()
        n = self.env.num_envs
        self.pstate = self.perception.init_state(n, self.device)
        self.pstate.use_gt = self.adasmpl.sample(n, self.device)
        self.pstate.map_off = draw_map_off(n, self.p_map_off, self.device, self.map_switch_gen)
        print("EX33_MAP_SWITCH p_off=%s realized=%.4f envs=%d seed=%s" % (self.p_map_off, float(self.pstate.map_off.float().mean()), n, self.pcfg["map_switch_seed"]), flush=True)
        ms_levels, ms_track = self._map_switch_probes() if self.map_switch is not None else (None, None)

        ep_infos = []
        rewbuffer, lenbuffer = deque(maxlen=100), deque(maxlen=100)
        cur_reward_sum = torch.zeros(n, device=self.device)
        cur_episode_length = torch.zeros(n, device=self.device)
        gt_steps = torch.zeros((), device=self.device)
        act_stats = None
        rs_rec = RewardSplit() if self.pcfg["log_reward_split"] else None
        if rs_rec is not None:
            rs_rec.attach(getattr(self.env, "unwrapped", self.env))
        if self.pcfg["log_action_stats"]:
            act_stats = ActionStats(float(self.cfg.get("clip_actions") or 1e9), n, self.env.num_actions, device=self.device)

        if self.is_distributed:
            self.broadcast_all()

        # 재개 때는 저장된 iteration 이 «이미 끝난» 회차이므로 다음 회차부터 센다(설치 runner 는 같은 회차를 한 번 더 돈다)
        start_iter = self.current_learning_iteration + (1 if self._resumed else 0)
        self.current_learning_iteration = start_iter
        tot_iter = start_iter + num_learning_iterations
        trace = getattr(self, "training_trace", None)
        for it in range(start_iter, tot_iter):
            if trace is not None:
                trace.begin_update(it)
            start = time.time()
            self._phase_start()
            self.replay.start(self.pstate.h_prop, self.pstate.h_terr)
            gt_steps.zero_()
            contract_bad = torch.zeros(n, dtype=torch.bool, device=self.device) if self.pcfg["contract"] == "start" else None
            contract_example = torch.zeros(n, 3, device=self.device)
            # ① 수집
            with torch.inference_mode():
                for step_k in range(self.num_steps_per_env):
                    o, depth, gmap, gfeet, vel, _ = self._split(raw)
                    inp = self.perception.ingest(self.pstate, o, depth)
                    est = self.perception.step(self.pstate, inp, gmap)
                    ppo_obs = self._ppo_obs(raw, est)
                    self.replay.add_pre(inp, o, gmap, gfeet, vel, self.pstate.use_gt, self.pstate.map_off)
                    gt_steps += self.pstate.use_gt.float().mean()
                    actions = self.alg.act(ppo_obs)
                    if contract_bad is not None:
                        consumed = self._consumed_command(it)               # 이 step 의 행동이 따른 명령(env.step 전 값)
                        bad_now = start_contract_bad(consumed)
                        contract_example = torch.where(bad_now[:, None] & ~contract_bad[:, None], consumed, contract_example)
                        contract_bad |= bad_now
                    if trace is not None:
                        trace.pre_step(actions)
                    raw, rewards, dones, extras = self.env.step(actions.to(self.env.device))
                    raw, rewards, dones = raw.to(self.device), rewards.to(self.device), dones.to(self.device)
                    if self.map_switch is not None:                       # 켬 · 끔 집단 기록: 이 step 의 행동을 만든 map_off(reset 전 값)로 센다
                        lv, tl, ta = self._map_switch_step_values(ms_levels, ms_track)
                        self.map_switch.add_step(self.pstate.map_off, rewards, dones, lv, tl, ta)
                    if trace is not None:
                        trace.post_step(step_k, rewards, dones)
                    if rs_rec is not None:
                        rs_rec.add()
                    if act_stats is not None:
                        act_stats.add(actions, dones, phys_probe(getattr(self.env, "unwrapped", self.env)) if (step_k % 8 == 0) else None)
                    if self.pcfg["stop_on_nonfinite"]:
                        self._check_finite(it, rewards=rewards, actions=actions)
                    self.replay.add_post(raw["policy"], dones)
                    # 정규화 통계는 이번 스텝의 actor 입력으로 갱신한다(설치는 다음 관측: 한 스텝 어긋날 뿐 같은 흐름)
                    self.alg.process_env_step(ppo_obs, rewards, dones, extras)
                    if "episode" in extras:
                        ep_infos.append(extras["episode"])
                    elif "log" in extras:
                        ep_infos.append(extras["log"])
                    cur_reward_sum += rewards
                    cur_episode_length += 1
                    done_ids = (dones > 0).nonzero(as_tuple=False).flatten()
                    if done_ids.numel():
                        self.adasmpl.add(cur_reward_sum[done_ids])
                        rewbuffer.extend(cur_reward_sum[done_ids].cpu().tolist())
                        lenbuffer.extend(cur_episode_length[done_ids].cpu().tolist())
                        cur_reward_sum[done_ids] = 0
                        cur_episode_length[done_ids] = 0
                    self.perception.reset_envs(self.pstate, dones > 0, self.adasmpl.sample(n, self.device),
                                               draw_map_off(n, self.p_map_off, self.device, self.map_switch_gen) if self.p_map_off > 0.0 else None)
                self._mark("2_rollout", it)
                collection_time = time.time() - start
                start = time.time()
                self.alg.compute_returns(self._ppo_obs(raw, torch.zeros(n, 51, device=self.device)))
            if trace is not None:
                trace.end_update()
            if contract_bad is not None and bool(contract_bad.any()):
                self._invalid(it, f"START 명령 계약 위반 {int(contract_bad.sum())} env (rollout 중 소비된 명령), 예 {contract_example[contract_bad][0].tolist()}")
            # ② PPO update
            self._phase_start()
            klp = self._kl_ppo_before(it) if self.pcfg["log_kl"] else None
            loss_dict = self.alg.update()
            kl_info = {}
            if klp is not None:
                kl_info["ppo"] = self._kl_ppo_after(klp)
            self._mark("3_ppo_update", it)
            if self.pcfg["stop_on_nonfinite"]:
                self._check_finite(it, **{k: torch.as_tensor(v, dtype=torch.float32) for k, v in loss_dict.items() if isinstance(v, (int, float)) or hasattr(v, "dtype")})
            # ③ 지각
            self._phase_start()
            klf = self._kl_phi_before(it) if self.pcfg["log_kl"] else None
            ploss = self.update_perception()
            if self.pcfg["stop_on_nonfinite"]:
                self._check_finite(it, **{f"perception/{k}": torch.as_tensor(v, dtype=torch.float32) for k, v in ploss.items()})
                self._check_params_finite(it)
            if klf is not None:
                kl_info["phi"] = self._kl_phi_after(klf)
            self._mark("4_perception_update", it)
            loss_dict.update({f"perception/{k}": v for k, v in ploss.items()})
            for name, res in kl_info.items():
                loss_dict[f"kl_probe/{name}_mean"] = res["all"]["mean"]
            split = rs_rec.summary() if rs_rec is not None else None
            if split is not None and "unavailable" not in split:
                loss_dict["reward_split/frac_moving"] = split["frac_moving"]
                loss_dict["reward_split/frac_stalled"] = split["frac_stalled"]
            extra = {"it": it, "kl_probe": kl_info or None, "action_stats": act_stats.summary() if act_stats is not None else None, "reward_split": split}
            if (kl_info or act_stats is not None or split is not None) and self.log_dir is not None and not self.disable_logs:
                with open(os.path.join(self.log_dir, "train_extra.jsonl"), "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(extra, ensure_ascii=False) + "\n")
            # ④ AdaSmpl
            p = self.update_adasmpl()
            if self.pcfg["stop_on_nonfinite"]:
                self._check_finite(it, adasmpl_p=torch.as_tensor(p, dtype=torch.float32))
            loss_dict["adasmpl/p_smpl"] = p
            loss_dict["adasmpl/gt_fraction"] = float(gt_steps) / self.num_steps_per_env
            if self.map_switch is not None:
                self._map_switch_log(it, loss_dict)
            learn_time = time.time() - start
            self.current_learning_iteration = it
            steps = self.num_steps_per_env * n * self.gpu_world_size
            self.iter_log.append({"it": it, "collection_s": collection_time, "learn_s": learn_time,
                                  "steps_per_s": steps / (collection_time + learn_time)})
            # ⑤ 로그 · 저장
            if self.log_dir is not None and not self.disable_logs:
                self.log(locals())
                if it % self.save_interval == 0:
                    self.save(os.path.join(self.log_dir, f"model_{it}.pt"))
                    self._manifest_checkpoint(it, f"model_{it}.pt", n)
                if it % self.pcfg["latest_interval"] == 0:
                    self._check_code(it)
                    self.save_latest()
                if it == start_iter or it % self.pcfg["status_interval"] == 0:
                    self._write_running_status(it, tot_iter, rewbuffer, lenbuffer, collection_time + learn_time, steps)
            ep_infos.clear()
            if it == start_iter and not self.disable_logs and self.log_dir is not None:
                store_code_state(self.log_dir, self.git_status_repos)
        if self.log_dir is not None and not self.disable_logs:
            self.save(os.path.join(self.log_dir, f"model_{self.current_learning_iteration}.pt"))
            self._manifest_checkpoint(self.current_learning_iteration, f"model_{self.current_learning_iteration}.pt", n)
            self.save_latest()
        self._resumed = True  # 같은 runner 로 learn 을 또 부르면 끝난 회차 다음부터 이어 간다

    # ------------------------------------------------------------------ SONNET-X25f: EX-33 S-B 켬 · 끔 기록
    def _map_switch_probes(self):
        """지형 레벨 텐서와 track 두 항의 reward_manager 열 번호. 없으면 None(기록에서 빠지고 jsonl 에 이유가 남는다)."""
        raw_env = getattr(self.env, "unwrapped", self.env)
        terrain = getattr(getattr(raw_env, "scene", None), "terrain", None)
        levels = getattr(terrain, "terrain_levels", None)
        rm = getattr(raw_env, "reward_manager", None)
        track = None
        if rm is not None and hasattr(rm, "_step_reward"):
            names = list(rm.active_terms)
            lin = [i for i, nm in enumerate(names) if "track_lin_vel" in nm]
            ang = [i for i, nm in enumerate(names) if "track_ang_vel" in nm]
            if len(lin) == 1 and len(ang) == 1:
                track = (rm, lin[0], ang[0])
        self.map_switch_unavailable = {"terrain_levels": levels is None, "track_terms": track is None}

        return (raw_env if levels is not None else None), track

    def _map_switch_step_values(self, raw_env, track):
        levels = raw_env.scene.terrain.terrain_levels.to(self.device) if raw_env is not None else None
        if track is None:
            return levels, None, None
        rm, i, j = track

        return levels, rm._step_reward[:, i].to(self.device), rm._step_reward[:, j].to(self.device)

    def _map_switch_log(self, it: int, loss_dict: dict) -> None:
        s = self.map_switch.summary()
        self.map_switch.reset_window()
        loss_dict["map_switch/off_frac"] = s["off_frac_steps"]
        for g in ("on", "off"):
            for k, v in s[g].items():
                if isinstance(v, float) and v == v:
                    loss_dict[f"map_switch/{g}_{k}"] = v
        if self.log_dir is not None and not self.disable_logs:
            row = {"it": it, "p_off": self.p_map_off, "unavailable": getattr(self, "map_switch_unavailable", None), **s}
            with open(os.path.join(self.log_dir, "map_switch.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(_nan_to_none(row), ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ SONNET-X11: 실행 무효 · manifest · KL 기록
    def attach_manifest(self, log_dir: str, manifest: dict) -> None:
        """실행 시작 때 만든 manifest 를 붙인다. 체크포인트 저장 때마다 소비 코드 변경을 검사하고 진행 수를 갱신한다."""
        self.manifest_dir, self.manifest = log_dir, manifest

    def _invalid(self, it: int, reason: str) -> None:
        """실행 무효 · 안전 중단: 성능 승패가 아니라 기록한 뒤 멈춘다."""
        write_status(self.log_dir, {"state": "failed", "invalid_run": True, "iter": it, "reason": reason})
        raise RuntimeError(f"실행 무효 (iter {it}): {reason}")

    def _check_finite(self, it: int, **tensors) -> None:
        for k, v in tensors.items():
            if not bool(torch.isfinite(v).all()):
                self._invalid(it, f"NaN/Inf: {k}")

    def _consumed_command(self, it: int) -> torch.Tensor:
        """이번 step 에 행동이 따른 명령 (N, 3). 명령 term 이 없으면 계약을 확인할 수 없으므로 실행 무효."""
        term = self._command_term()
        if term is None:
            self._invalid(it, "START 명령 계약을 검사해야 하는데 command_manager 의 base_velocity term 이 없다")
        return term.vel_command_b[:, :3].detach().clone().to(self.device)      # env 와 runner 의 장치가 다를 수 있다(예: env cuda:1 · runner 기본 cuda:0): 누적 텐서와 같은 장치로

    def _check_params_finite(self, it: int) -> None:
        """갱신 뒤 정책 · 지각 파라미터가 모두 유한한지."""
        for owner, module in (("policy", self.alg.policy), ("perception", self.perception)):
            for name, prm in module.named_parameters():
                if not bool(torch.isfinite(prm).all()):
                    self._invalid(it, f"NaN/Inf 파라미터: {owner}.{name}")

    def _check_code(self, it: int) -> None:
        """시작 때 기록한 소비 파일이 바뀌었거나 사라졌으면 실행 무효. 새로 import 된 소비 파일은 manifest 에 덧붙이고 알린다(무효 아님)."""
        if self.manifest is None:
            return
        ch = run_manifest.file_changes(self.manifest)
        if ch["changed"] or ch["missing"]:
            self._invalid(it, "실행 중 소비 코드가 바뀜: 변경 " + ",".join(ch["changed"][:8]) + " 소실 " + ",".join(ch["missing"][:8]))
        if ch["added"]:
            self.manifest["files"].setdefault("added_after_start", {}).update(ch["added"])

    def _manifest_checkpoint(self, it: int, name: str, num_envs: int) -> None:
        if self.manifest is None:
            return
        self._check_code(it)
        done = it + 1
        run_manifest.update_progress(self.manifest_dir, self.manifest, done, done * self.num_steps_per_env * num_envs * self.gpu_world_size,
                                     (name, os.path.join(self.log_dir, name)))

    def _kl_select(self):
        k = min(int(self.pcfg["kl_probe_envs"]), self.env.num_envs)
        return torch.arange(k, device=self.device)

    def _kl_ppo_before(self, it: int) -> dict:
        """PPO update 전: 저장된 actor 입력 부분집합에서 행동 분포(mean, std)를 잡아 둔다."""
        sel = self._kl_select()
        sub = self.alg.storage.observations[:, sel]
        sub = sub.reshape(sub.batch_size[0] * sub.batch_size[1]).clone()
        mu, std = kl_probe.policy_dist(self.alg.policy, sub)
        return {"obs": sub, "mu": mu, "std": std}

    def _kl_ppo_after(self, snap: dict) -> dict:
        mu1, std1 = kl_probe.policy_dist(self.alg.policy, snap["obs"])
        kl = kl_probe.gaussian_kl(snap["mu"], snap["std"], mu1, std1)
        return kl_probe.summarize(kl, kl_probe.command_branch(snap["obs"][ACTOR_KEY][:, 6:9]))

    def _kl_phi_before(self, it: int) -> dict:
        """지각 phi update 전: 같은 history · 시작 hidden · epsilon 으로 est 시퀀스를 계산하고 theta(PPO 뒤 값)로 행동 분포를 잡는다."""
        sel = self._kl_select()
        batch = self.replay.gather(sel)
        gen = torch.Generator(device="cpu").manual_seed(1234 + it)
        T, K = batch["obs"].shape[0], batch["obs"].shape[1]
        eps = torch.randn(T, K, 16, generator=gen).to(self.device)
        snap = {"batch": batch, "eps": eps}
        snap["mu"], snap["std"] = self._phi_dist(snap)
        return snap

    def _phi_dist(self, snap):
        est = self.perception.est_sequence(snap["batch"], snap["eps"])
        est_in = self._est_in(est, snap["batch"]["base_vel"], noise=0.0)          # zero · oracle_vel 은 phi 와 무관하게 정해져 phi 전후 KL 이 0 이다(잡음 0: 전 · 후 같은 입력)
        o = snap["batch"]["obs"]
        T, K = o.shape[0], o.shape[1]
        td = TensorDict({ACTOR_KEY: torch.cat([o, est_in], -1).reshape(T * K, -1)}, batch_size=[T * K], device=o.device)
        return kl_probe.policy_dist(self.alg.policy, td)

    def _kl_phi_after(self, snap: dict) -> dict:
        mu1, std1 = self._phi_dist(snap)
        kl = kl_probe.gaussian_kl(snap["mu"], snap["std"], mu1, std1)
        return kl_probe.summarize(kl, kl_probe.command_branch(snap["batch"]["obs"].reshape(-1, snap["batch"]["obs"].shape[-1])[:, 6:9]))

    def update_perception(self) -> dict[str, float]:
        if not self.replay.full():
            raise RuntimeError("지각 재생 버퍼가 덜 찼다")
        pc = self.pcfg
        params = [p for p in self.perception.parameters() if p.requires_grad]
        acc: dict[str, float] = {}
        n_updates = 0
        for idx in self.replay.env_batches(pc["num_mini_batches"], pc["num_learning_epochs"]):
            self.perception_optimizer.zero_grad(set_to_none=True)
            chunks = torch.split(idx, pc["microbatch_envs"])  # microbatch + gradient accumulation (18 §5.2)
            for c in chunks:
                with self._autocast():
                    res = self.perception.sequence_loss(self.replay.gather(c), impl=pc["replay_impl"])
                (res["loss"] * (len(c) / len(idx))).backward()
                for k in ("l_tr", "l_ie", "kl", "o_next", "v", "hf", "hb"):
                    acc[k] = acc.get(k, 0.0) + float(res[k]) * len(c) / len(idx)
            if self.is_distributed:
                self._allreduce_grads(params)
            nn.utils.clip_grad_norm_(params, pc["max_grad_norm"])
            self.perception_optimizer.step()
            n_updates += 1
        self.last_perception_losses = {k: v / n_updates for k, v in acc.items()}
        return self.last_perception_losses

    def _autocast(self):
        if self.pcfg.get("replay_autocast") == "bf16" and self._cuda():
            return torch.autocast("cuda", dtype=torch.bfloat16)
        import contextlib

        return contextlib.nullcontext()

    def update_adasmpl(self) -> float:
        if self.is_distributed:
            t = torch.tensor([self.adasmpl.count, self.adasmpl.sum, self.adasmpl.sumsq], dtype=torch.float64, device=self.device)
            torch.distributed.all_reduce(t, op=torch.distributed.ReduceOp.SUM)
            self.adasmpl.count, self.adasmpl.sum, self.adasmpl.sumsq = (float(x) for x in t)
        return self.adasmpl.update()

    # ------------------------------------------------------------------ 분산 (18 §5.1 · Linux 에서만 · 이 판에서 실행 안 함)
    def _allreduce_grads(self, params) -> None:
        grads = [p.grad.view(-1) for p in params if p.grad is not None]
        flat = torch.cat(grads)
        torch.distributed.all_reduce(flat, op=torch.distributed.ReduceOp.SUM)
        flat /= self.gpu_world_size
        off = 0
        for p in params:
            if p.grad is not None:
                k = p.numel()
                p.grad.copy_(flat[off : off + k].view_as(p.grad))
                off += k

    def broadcast_all(self) -> None:
        objs = [self.alg.policy.state_dict(), self.perception.state_dict(), self.adasmpl.state_dict()]
        torch.distributed.broadcast_object_list(objs, src=0)
        self.alg.policy.load_state_dict(objs[0])
        self.perception.load_state_dict(objs[1])
        self.adasmpl.load_state_dict(objs[2])

    # ------------------------------------------------------------------ 저장 · 복원 (12 §6.1 상태 목록)
    # env 가 학습 회차에 걸쳐 들고 가는 상태. 저장하지 않고 재개하면 «오류 없이» 처음 값으로 돌아간다:
    #   common_step_counter  명령 모드 비율의 1,000 회 전후 전환 · p_advance 의 T 가 이 값에서 나온다(반복 수 = 이 값 // 24)
    #   terrain_levels / terrain_types  env 마다 서 있는 지형 칸
    #   명령 term 의 range_curriculum  자유 속도 상한 vmax (1.0 에서 시작해 올라간다)
    # env 가 `foothold_state_dict` / `foothold_load_state_dict` 를 내면 그것을 «더해서» 쓴다(위 셋은 항상 저장).
    def _command_term(self):
        u = getattr(self.env, "unwrapped", self.env)
        cm = getattr(u, "command_manager", None)
        try:
            return cm.get_term("base_velocity") if cm is not None else None
        except Exception:
            return None

    def _env_state(self) -> dict:
        u = getattr(self.env, "unwrapped", self.env)
        out: dict = {}
        if getattr(u, "common_step_counter", None) is not None:
            out["common_step_counter"] = int(u.common_step_counter)
        terrain = getattr(getattr(u, "scene", None), "terrain", None)
        for k in ("terrain_levels", "terrain_types"):
            if terrain is not None and getattr(terrain, k, None) is not None:
                out[k] = getattr(terrain, k).clone()
        rc = getattr(self._command_term(), "range_curriculum", None)
        if rc is not None:
            out["range_curriculum"] = {k: (list(v) if isinstance(v, list) else v) for k, v in vars(rc).items()}
        hook = getattr(u, "foothold_state_dict", None)
        if callable(hook):
            out["env_hook"] = hook()
        return out

    def _load_env_state(self, sd: dict) -> None:
        u = getattr(self.env, "unwrapped", self.env)
        if "common_step_counter" in sd:
            u.common_step_counter = int(sd["common_step_counter"])
        terrain = getattr(getattr(u, "scene", None), "terrain", None)
        for k in ("terrain_levels", "terrain_types"):
            if k in sd and terrain is not None and getattr(terrain, k, None) is not None:
                getattr(terrain, k).copy_(sd[k])
        if terrain is not None and "terrain_levels" in sd and "terrain_types" in sd:
            origins = getattr(terrain, "terrain_origins", None)
            active = getattr(terrain, "env_origins", None)
            if origins is not None and active is not None:
                restored = origins[terrain.terrain_levels, terrain.terrain_types]
                active.copy_(restored)
                scene_origins = getattr(u.scene, "env_origins", None)
                if scene_origins is not None and not torch.equal(scene_origins, restored):
                    raise RuntimeError("restored terrain origins differ from scene env origins")
        rc = getattr(self._command_term(), "range_curriculum", None)
        if rc is not None and "range_curriculum" in sd:
            for k, v in sd["range_curriculum"].items():
                setattr(rc, k, v)
        if "env_hook" in sd:
            hook = getattr(u, "foothold_load_state_dict", None)
            if not callable(hook):
                raise RuntimeError("체크포인트에 env_hook 상태가 있는데 이 env 에는 foothold_load_state_dict 가 없다")
            hook(sd["env_hook"])

    @staticmethod
    def rng_state() -> dict:
        s = {"torch": torch.get_rng_state(), "numpy": np.random.get_state(), "python": random.getstate()}
        if torch.cuda.is_available():
            s["cuda"] = torch.cuda.get_rng_state_all()
        return s

    @staticmethod
    def set_rng_state(s: dict) -> None:
        torch.set_rng_state(s["torch"])
        np.random.set_state(s["numpy"])
        random.setstate(s["python"])
        if "cuda" in s and torch.cuda.is_available():
            torch.cuda.set_rng_state_all(s["cuda"])

    def state_dict(self, infos: dict | None = None) -> dict:
        return {
            "format": CKPT_FORMAT,
            "model_state_dict": self.alg.policy.state_dict(),  # 정책 + 관측 정규화 통계(EmpiricalNormalization 버퍼)
            "optimizer_state_dict": self.alg.optimizer.state_dict(),
            "ppo_learning_rate": self.alg.learning_rate,  # adaptive 학습률은 optimizer 밖 속성에도 있다
            "perception_state_dict": self.perception.state_dict(),
            "perception_optimizer_state_dict": self.perception_optimizer.state_dict(),
            "perception_cfg": dict(self.pcfg),
            "adasmpl": self.adasmpl.state_dict(),
            "env_state": self._env_state(),
            "env_seed": getattr(getattr(getattr(self.env, "unwrapped", self.env), "cfg", None), "seed", None),
            "iter": self.current_learning_iteration,
            "rng": self.rng_state(),
            "map_switch": self.map_switch_state(),
            "infos": infos,
        }

    def map_switch_state(self) -> dict:
        """EX-33 S-B: 끔 확률 · 시드 · 끔 전용 난수열 상태. 이어 갈 때 p 가 다르면 거절하고, 같으면 난수열을 이어 간다."""
        gen = self.map_switch_gen

        return {"p_map_off": self.p_map_off, "map_switch_seed": int(self.pcfg["map_switch_seed"]),
                "generator_state": gen.get_state() if gen is not None else None}

    def load_map_switch_state(self, saved: dict | None) -> None:
        """체크포인트의 끔 설정을 이 runner 와 대조한다. 옛 체크포인트(칸 없음)는 p=0 으로 본다(B). p 가 다르거나 난수열 상태가 없는데 p>0 이면 거절."""
        saved = saved or {"p_map_off": 0.0, "map_switch_seed": None, "generator_state": None}
        if float(saved["p_map_off"]) != self.p_map_off:
            raise ValueError(f"체크포인트의 p_map_off={saved['p_map_off']} 와 이 runner 의 {self.p_map_off} 가 다르다 (지도 끔 비율이 다른 체크포인트를 섞지 않는다)")
        if self.p_map_off > 0.0:
            if int(saved["map_switch_seed"]) != int(self.pcfg["map_switch_seed"]):
                raise ValueError(f"체크포인트의 map_switch_seed={saved['map_switch_seed']} 와 이 runner 의 {self.pcfg['map_switch_seed']} 가 다르다")
            if saved["generator_state"] is None:
                raise ValueError("체크포인트에 지도 끔 난수열 상태가 없다")
            self.map_switch_gen.set_state(saved["generator_state"].cpu())

    def save(self, path: str, infos: dict | None = None) -> None:
        torch.save(self.state_dict(infos), path)

    def save_latest(self) -> str:
        """latest.pt 를 임시 파일에 쓴 뒤 바꿔치기한다. 쓰다 죽어도 이전 latest.pt 가 온전히 남는다."""
        path = os.path.join(self.log_dir, "latest.pt")
        tmp = f"{path}.tmp"
        torch.save(self.state_dict(), tmp)
        os.replace(tmp, path)
        return path

    def _write_running_status(self, it, tot_iter, rewbuffer, lenbuffer, iter_s, steps) -> None:
        write_status(self.log_dir, {
            "state": "running", "iter": it, "tot_iter": tot_iter, "iter_s": iter_s, "steps_per_s": steps / iter_s,
            "mean_reward": (sum(rewbuffer) / len(rewbuffer)) if rewbuffer else None,
            "mean_episode_length": (sum(lenbuffer) / len(lenbuffer)) if lenbuffer else None,
            "p_smpl": self.adasmpl.p,
            "gpu_max_allocated_GiB": (torch.cuda.max_memory_allocated(self.device) / 2**30) if self._cuda() else None,
            "perception": {k: round(v, 5) for k, v in self.last_perception_losses.items()},
            "log_dir": self.log_dir,
        })

    def load(self, path: str, load_optimizer: bool = True, map_location: str | None = None) -> dict:
        sd = torch.load(path, weights_only=False, map_location=map_location)
        if sd.get("format") != CKPT_FORMAT:
            raise ValueError(f"START 체크포인트가 아니다: format={sd.get('format')}")
        saved = sd.get("perception_cfg") or {}
        for key, default in MODE_DEFAULTS.items():
            if saved.get(key, default) != self.pcfg[key]:
                raise ValueError(f"체크포인트의 {key}={saved.get(key, default)!r} 와 이 runner 의 {self.pcfg[key]!r} 가 다르다 (처치가 다른 체크포인트를 섞지 않는다)")
        self.alg.policy.load_state_dict(sd["model_state_dict"])
        self.perception.load_state_dict(sd["perception_state_dict"])
        self.adasmpl.load_state_dict(sd["adasmpl"])
        if load_optimizer:
            self.alg.optimizer.load_state_dict(sd["optimizer_state_dict"])
            self.alg.learning_rate = sd["ppo_learning_rate"]
            self.perception_optimizer.load_state_dict(sd["perception_optimizer_state_dict"])
        self.load_map_switch_state(sd.get("map_switch"))
        self._load_env_state(sd["env_state"])
        self.set_rng_state(sd["rng"])
        self.current_learning_iteration = sd["iter"]
        self._resumed = True
        return sd["infos"]

    def train_mode(self) -> None:
        super().train_mode()
        self.perception.train()

    def eval_mode(self) -> None:
        super().eval_mode()
        self.perception.eval()

    def log(self, locs: dict, width: int = 80, pad: int = 35) -> None:
        super().log(locs, width, pad)
        if self.memory_marks and self.writer is not None:
            for k, v in self.memory_marks.items():
                self.writer.add_scalar(f"Memory/{k}_GiB", v / 2**30, locs["it"])
