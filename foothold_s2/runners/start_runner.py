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
from foothold_s2.runners.perception_replay import PerceptionReplay

CKPT_FORMAT = "foothold-start/1"

# 지각 optimizer 수치: 전부 가정 (12 §6.1, START · 선행에 없음)
PERCEPTION_DEFAULTS = {
    "learning_rate": 5e-4,
    "weight_decay": 0.0,
    "num_learning_epochs": 5,
    "num_mini_batches": 4,
    "microbatch_envs": 256,
    "max_grad_norm": 1.0,
    "depth_dtype": "float16",
}


class StartRunner(OnPolicyRunner):
    def __init__(self, env, train_cfg: dict, log_dir: str | None = None, device: str = "cpu") -> None:
        # 설치 __init__ 은 env 관측 묶음으로 obs_groups 를 풀고 정책을 만든다. 우리는 정책이 지각 뒤 입력을 받으므로
        # 같은 일을 그 입력 모양으로 한다(설치 54~78 행과 같은 속성을 채운다).
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
        self.perception = StartPerception(
            PerceptionCfg(map_input=pcfg.get("map_input", "reconstruction"), force_gt=bool(pcfg.get("force_gt", False)))
        ).to(device)
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

        self.disable_logs = self.is_distributed and self.gpu_global_rank != 0
        self.log_dir = log_dir
        self.writer = None
        self.tot_timesteps = 0
        self.tot_time = 0
        self.current_learning_iteration = 0
        self.git_status_repos = [rsl_rl.__file__]
        self.last_perception_losses: dict[str, float] = {}
        self.memory_marks: dict[str, int] = {}

    # ------------------------------------------------------------------ 관측
    REQUIRED = {"policy": (45,), "depth": (60, 60), "gt_feet": (100,), "base_vel": (3,), "contacts": (4,)}

    def _check_raw(self, raw: TensorDict) -> None:
        for k, shape in self.REQUIRED.items():
            if k not in raw.keys():
                raise KeyError(f"env 관측에 '{k}' 묶음이 없다 (start_runner 머리말 계약)")
            got = tuple(raw[k].shape[1:])
            if k == "depth":
                got = tuple(s for s in got if s != 1)
            if got != shape:
                raise ValueError(f"'{k}' 모양 {got} 이 계약 {shape} 과 다르다")
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

    def _ppo_obs(self, raw: TensorDict, est: torch.Tensor) -> TensorDict:
        o, _, gmap, gfeet, vel, con = self._split(raw)
        n = o.shape[0]
        return TensorDict(
            {
                ACTOR_KEY: torch.cat([o, est], -1),
                CRITIC_KEY: torch.cat([o, vel, con, gmap.reshape(n, -1), gfeet], -1),
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
    def _mark(self, name: str) -> None:
        if torch.cuda.is_available() and str(self.device).startswith("cuda"):
            self.memory_marks[name] = int(torch.cuda.max_memory_allocated(self.device))

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

        ep_infos = []
        rewbuffer, lenbuffer = deque(maxlen=100), deque(maxlen=100)
        cur_reward_sum = torch.zeros(n, device=self.device)
        cur_episode_length = torch.zeros(n, device=self.device)
        gt_steps = torch.zeros((), device=self.device)

        if self.is_distributed:
            self.broadcast_all()

        start_iter = self.current_learning_iteration
        tot_iter = start_iter + num_learning_iterations
        for it in range(start_iter, tot_iter):
            start = time.time()
            self.replay.start(self.pstate.h_prop, self.pstate.h_terr)
            gt_steps.zero_()
            # ① 수집
            with torch.inference_mode():
                for _ in range(self.num_steps_per_env):
                    o, depth, gmap, gfeet, vel, _ = self._split(raw)
                    inp = self.perception.ingest(self.pstate, o, depth)
                    est = self.perception.step(self.pstate, inp, gmap)
                    ppo_obs = self._ppo_obs(raw, est)
                    self.replay.add_pre(inp, o, gmap, gfeet, vel, self.pstate.use_gt)
                    gt_steps += self.pstate.use_gt.float().mean()
                    actions = self.alg.act(ppo_obs)
                    raw, rewards, dones, extras = self.env.step(actions.to(self.env.device))
                    raw, rewards, dones = raw.to(self.device), rewards.to(self.device), dones.to(self.device)
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
                    self.perception.reset_envs(self.pstate, dones > 0, self.adasmpl.sample(n, self.device))
                self._mark("2_rollout")
                collection_time = time.time() - start
                start = time.time()
                self.alg.compute_returns(self._ppo_obs(raw, torch.zeros(n, 51, device=self.device)))
            # ② PPO
            loss_dict = self.alg.update()
            self._mark("3_ppo_update")
            # ③ 지각
            ploss = self.update_perception()
            self._mark("4_perception_update")
            loss_dict.update({f"perception/{k}": v for k, v in ploss.items()})
            # ④ AdaSmpl
            p = self.update_adasmpl()
            loss_dict["adasmpl/p_smpl"] = p
            loss_dict["adasmpl/gt_fraction"] = float(gt_steps) / self.num_steps_per_env
            learn_time = time.time() - start
            self.current_learning_iteration = it
            # ⑤ 로그 · 저장
            if self.log_dir is not None and not self.disable_logs:
                self.log(locals())
                if it % self.save_interval == 0:
                    self.save(os.path.join(self.log_dir, f"model_{it}.pt"))
            ep_infos.clear()
            if it == start_iter and not self.disable_logs and self.log_dir is not None:
                store_code_state(self.log_dir, self.git_status_repos)
        if self.log_dir is not None and not self.disable_logs:
            self.save(os.path.join(self.log_dir, f"model_{self.current_learning_iteration}.pt"))

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
                res = self.perception.sequence_loss(self.replay.gather(c))
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
    def _env_state(self) -> dict:
        u = getattr(self.env, "unwrapped", self.env)
        hook = getattr(u, "foothold_state_dict", None)
        if callable(hook):
            return hook()  # 커리큘럼 · 명령 생성기 상태는 env 쪽(lead) 이 이 이름으로 낸다
        out = {}
        terrain = getattr(getattr(u, "scene", None), "terrain", None)
        for k in ("terrain_levels", "terrain_types"):
            if terrain is not None and getattr(terrain, k, None) is not None:
                out[k] = getattr(terrain, k).clone()
        return out

    def _load_env_state(self, sd: dict) -> None:
        u = getattr(self.env, "unwrapped", self.env)
        hook = getattr(u, "foothold_load_state_dict", None)
        if callable(hook):
            hook(sd)
            return
        terrain = getattr(getattr(u, "scene", None), "terrain", None)
        for k, v in sd.items():
            if terrain is not None and getattr(terrain, k, None) is not None:
                getattr(terrain, k).copy_(v)

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
            "infos": infos,
        }

    def save(self, path: str, infos: dict | None = None) -> None:
        torch.save(self.state_dict(infos), path)

    def load(self, path: str, load_optimizer: bool = True, map_location: str | None = None) -> dict:
        sd = torch.load(path, weights_only=False, map_location=map_location)
        if sd.get("format") != CKPT_FORMAT:
            raise ValueError(f"START 체크포인트가 아니다: format={sd.get('format')}")
        self.alg.policy.load_state_dict(sd["model_state_dict"])
        self.perception.load_state_dict(sd["perception_state_dict"])
        self.adasmpl.load_state_dict(sd["adasmpl"])
        if load_optimizer:
            self.alg.optimizer.load_state_dict(sd["optimizer_state_dict"])
            self.alg.learning_rate = sd["ppo_learning_rate"]
            self.perception_optimizer.load_state_dict(sd["perception_optimizer_state_dict"])
        self._load_env_state(sd["env_state"])
        self.set_rng_state(sd["rng"])
        self.current_learning_iteration = sd["iter"]
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
