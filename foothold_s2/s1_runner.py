"""S1 학습 runner: 설치 `OnPolicyRunner` (rsl-rl-lib 3.1.2) 에 «재개해도 조용히 틀어지지 않게» 하는 저장 · 복원 · 상태 파일을 더한다.

rl 의 `StartRunner` 와 같은 항목을 같은 방식으로 한다 (env 상태 저장 · 복원 코드는 StartRunner 것을 그대로 가져다 쓴다):
  - common_step_counter (명령 모드 비율의 1,000 회 전후 전환 · p_advance 의 T) · 지형 레벨 · 칸 · 명령 term 의 range_curriculum
    (vmax_x · vmax_y · flag_vmax · history) 를 체크포인트에 넣고, load 때 되돌린다.
  - adaptive 학습률 (`ppo_learning_rate`) 과 난수 상태.
  - latest.pt 를 `latest_interval`(100) 회마다 임시 파일 + os.replace 로 덮어쓴다. 번호 붙은 model_N.pt 는 save_interval 마다 그대로.
  - 상태 파일 `train_start_status.json` (starting · running · done · failed), 첫 iteration 이 끝나는 순간부터 running.
  - 재개 때 저장된 iteration 은 «이미 끝난» 회차라 다음 회차부터 센다 (설치 runner 는 같은 회차를 한 번 더 돈다).
Kit 없이 import 된다 (가짜 env 시험).
"""

from __future__ import annotations

import os

import torch
from rsl_rl.runners import OnPolicyRunner

from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.runners.status import write_status

CKPT_FORMAT = "foothold-s1/1"
# 단계 전이(S1-a -> S1-b)에서 옮기는 env 상태: 지형 칸(terrain_levels · terrain_types)은 열 배치가 달라(23 열 -> 50 열) 옮기지 않는다.
STAGE_TRANSFER_KEYS = ("common_step_counter", "range_curriculum")
DEFAULTS = {"latest_interval": 100, "status_interval": 10}


class S1Runner(OnPolicyRunner):
    # rl 판이 정본인 env 상태 저장 · 복원 (같은 함수를 그대로 쓴다)
    _command_term = StartRunner._command_term
    _env_state = StartRunner._env_state
    _load_env_state = StartRunner._load_env_state
    rng_state = staticmethod(StartRunner.rng_state)
    set_rng_state = staticmethod(StartRunner.set_rng_state)

    def __init__(self, env, train_cfg, log_dir=None, device="cpu"):
        super().__init__(env, train_cfg, log_dir=log_dir, device=device)
        s = dict(DEFAULTS)
        s.update(train_cfg.get("s1_state", {}) or {})
        self.s1_state = s
        self._resumed = False
        self._tot_iter = None

    # ------------------------------------------------------------------ 저장 · 복원
    def state_dict(self, infos=None):
        return {
            "format": CKPT_FORMAT,
            "model_state_dict": self.alg.policy.state_dict(),
            "optimizer_state_dict": self.alg.optimizer.state_dict(),
            "ppo_learning_rate": self.alg.learning_rate,
            "env_state": self._env_state(),
            "env_seed": getattr(getattr(getattr(self.env, "unwrapped", self.env), "cfg", None), "seed", None),
            "iter": self.current_learning_iteration,
            "rng": self.rng_state(),
            "infos": infos,
        }

    def save(self, path, infos=None):
        torch.save(self.state_dict(infos), path)

    def save_latest(self):
        """쓰다 죽어도 이전 latest.pt 가 온전히 남도록 임시 파일에 쓴 뒤 바꿔치기한다."""
        path = os.path.join(self.log_dir, "latest.pt")
        tmp = f"{path}.tmp"
        torch.save(self.state_dict(), tmp)
        os.replace(tmp, path)

        return path

    def load(self, path, load_optimizer=True, map_location=None, env_keys=None):
        sd = torch.load(path, weights_only=False, map_location=map_location)

        if sd.get("format") != CKPT_FORMAT:
            raise ValueError(f"S1 체크포인트가 아니다: format={sd.get('format')} (설치 runner 의 model_N.pt 는 env 상태가 없어 여기서 못 받는다)")

        self.alg.policy.load_state_dict(sd["model_state_dict"])

        if load_optimizer:
            self.alg.optimizer.load_state_dict(sd["optimizer_state_dict"])
            self.alg.learning_rate = sd["ppo_learning_rate"]

        env_state = sd["env_state"]

        if env_keys is not None:                           # 단계 전이: 일부 상태만 옮긴다
            env_state = {k: v for k, v in env_state.items() if k in env_keys}

        self._load_env_state(env_state)
        self.set_rng_state(sd["rng"])
        self.current_learning_iteration = sd["iter"]
        self._resumed = True

        return sd["infos"]

    # ------------------------------------------------------------------ 학습 · 상태 파일
    def learn(self, num_learning_iterations, init_at_random_ep_len=False):
        if self._resumed:
            self.current_learning_iteration += 1          # 저장된 회차는 이미 끝난 것
            self._resumed = False

        self._tot_iter = self.current_learning_iteration + num_learning_iterations

        if self.log_dir is not None and not self.disable_logs:
            write_status(self.log_dir, {"state": "starting", "iter": self.current_learning_iteration,
                                        "tot_iter": self._tot_iter, "log_dir": self.log_dir})

        super().learn(num_learning_iterations, init_at_random_ep_len)

        if self.log_dir is not None and not self.disable_logs:
            self.save_latest()
            write_status(self.log_dir, {"state": "done", "iter": self.current_learning_iteration,
                                        "tot_iter": self._tot_iter, "log_dir": self.log_dir})

        self._resumed = True                              # 같은 runner 로 learn 을 또 부르면 끝난 회차 다음부터

    def log(self, locs, width=80, pad=35):
        super().log(locs, width, pad)
        it = locs["it"]
        start_iter = locs.get("start_iter", it)

        if self.log_dir is None or self.disable_logs:
            return

        if it % self.s1_state["latest_interval"] == 0:
            self.save_latest()

        if it == start_iter or it % self.s1_state["status_interval"] == 0:
            rew, ln = locs.get("rewbuffer"), locs.get("lenbuffer")
            collect, learn = locs.get("collection_time", 0.0), locs.get("learn_time", 0.0)
            iter_s = collect + learn
            steps = self.num_steps_per_env * self.env.num_envs * self.gpu_world_size
            cuda = torch.cuda.is_available() and str(self.device).startswith("cuda")
            write_status(self.log_dir, {
                "state": "running", "iter": it, "tot_iter": self._tot_iter, "iter_s": iter_s,
                "steps_per_s": (steps / iter_s) if iter_s > 0 else None,
                "mean_reward": (sum(rew) / len(rew)) if rew else None,
                "mean_episode_length": (sum(ln) / len(ln)) if ln else None,
                "gpu_max_allocated_GiB": (torch.cuda.max_memory_allocated(self.device) / 2**30) if cuda else None,
                "log_dir": self.log_dir,
            })
