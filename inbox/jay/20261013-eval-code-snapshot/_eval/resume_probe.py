# Resume fidelity probe: runs the repository's scripts/rsl_rl/train.py unchanged (runpy), with the CTS
# runner's save / load / learn wrapped to dump the training state next to every checkpoint:
#   <model>.pt.state.json  runner iteration, env common_step_counter, command ranges and curriculum stage,
#                          zero-command probability, terrain levels, reward weights, episode phases,
#                          learning rate (algorithm attribute and optimizer groups), Adam steps,
#                          RNG hashes (torch CPU / CUDA, numpy, python), model and optimizer hashes
#   <model>.pt.state.npz   arrays needed to restore (terrain levels, RNG states)
# plus pre_learn.state.json in the log dir (state when learn() starts, after a resume load).
# RESUME_FIX=1 applies the candidate fix before learn() on a resumed run (not part of the repository):
#   next iteration label = loaded + 1, common_step_counter = (loaded + 1) * num_steps_per_env,
#   algorithm learning_rate = optimizer lr, terrain levels and RNG states from the checkpoint's sidecar.
# Usage: cd <logs root>; python resume_probe.py <train.py args...>
import hashlib
import json
import os
import pickle
import random
import runpy
import sys

import numpy as np

REPO = "C:/isaac/ext/go2_rl_robotlab"
sys.path.insert(0, os.path.join(REPO, "scripts", "rsl_rl"))
FIX = os.environ.get("RESUME_FIX") == "1"

import torch  # noqa: E402
from rsl_rl.runners import OnPolicyRunnerCTS  # noqa: E402

_orig_save, _orig_load, _orig_learn = OnPolicyRunnerCTS.save, OnPolicyRunnerCTS.load, OnPolicyRunnerCTS.learn


def _h(b):
    return hashlib.sha256(b).hexdigest()[:16]


def _tensor_hash(ts):
    h = hashlib.sha256()
    for t in ts:
        h.update(t.detach().float().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()[:16]


def state(runner, where):
    env = runner.env.unwrapped
    ct = env.command_manager.get_term("base_velocity")
    ter = env.scene.terrain
    rm = env.reward_manager
    lv = ter.terrain_levels.cpu().numpy()
    opt, opt2 = runner.alg.optimizer, runner.alg.optimizer_stu_enc

    def adam(o):
        steps = sorted({float(v["step"]) for v in o.state.values() if "step" in v}) if o.state else []
        ea = [v["exp_avg"] for v in o.state.values() if "exp_avg" in v]
        return {"lr_groups": [g["lr"] for g in o.param_groups], "adam_step_values": steps[:3], "n_state": len(o.state),
                "exp_avg_sha": _tensor_hash(ea) if ea else None}

    sd = runner.alg.policy.state_dict()
    return {
        "where": where,
        "runner_iteration": int(runner.current_learning_iteration),
        "env_common_step_counter": int(env.common_step_counter),
        "env_iter_from_counter": int(env.common_step_counter) // 24,
        "command_ranges": ct.command_ranges,
        "command_range_curriculum_remaining": [c["iter"] for c in ct.cfg.command_range_curriculum],
        "zero_command_prob": float(ct.zero_command_prob),
        "terrain_level_mean": float(lv.mean()),
        "terrain_level_hist": np.bincount(lv, minlength=10).tolist(),
        "reward_weights": {n: float(rm.get_term_cfg(n).weight) for n in rm.active_terms},
        "episode_length_buf_mean": float(env.episode_length_buf.float().mean()),
        "episode_length_buf_sha": _tensor_hash([env.episode_length_buf]),
        "alg_learning_rate": float(runner.alg.learning_rate),
        "optimizer": adam(opt),
        "optimizer_stu_enc": adam(opt2),
        "rng": {"torch_cpu": _h(torch.get_rng_state().numpy().tobytes()), "torch_cuda": _h(torch.cuda.get_rng_state().cpu().numpy().tobytes()),
                "numpy": _h(np.random.get_state()[1].tobytes()), "python": _h(pickle.dumps(random.getstate()))},
        "model_sha": _tensor_hash([sd[k] for k in sorted(sd)]),
        "action_std_mean": float(runner.alg.policy.action_std.mean()) if hasattr(runner.alg.policy, "action_std") else None,
        "sim_step_counter": int(env._sim_step_counter),
        "env_device": str(env.device), "runner_device": str(runner.device),
        "cuda0_uuid": str(torch.cuda.get_device_properties(0).uuid), "cuda_visible": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }


def sidecar(runner, path):
    env = runner.env.unwrapped
    np.savez(path + ".state.npz", terrain_levels=env.scene.terrain.terrain_levels.cpu().numpy(),
             torch_cpu=torch.get_rng_state().numpy(), torch_cuda=torch.cuda.get_rng_state().cpu().numpy(),
             numpy_state=np.array(pickle.dumps(np.random.get_state())), python_state=np.array(pickle.dumps(random.getstate())))


def save(self, path, it, last_model, infos=None):
    _orig_save(self, path, it, last_model, infos)
    json.dump(state(self, f"save it={it} last={last_model}"), open(path + ".state.json", "w"), indent=1)
    sidecar(self, path)


def load(self, path, load_optimizer=True, map_location=None):
    self._probe_loaded_path = path
    out = _orig_load(self, path, load_optimizer, map_location)
    if self.logger.log_dir:
        os.makedirs(self.logger.log_dir, exist_ok=True)
        json.dump(state(self, f"after load {os.path.basename(path)}"), open(os.path.join(self.logger.log_dir, "post_load.state.json"), "w"), indent=1)
    return out


def learn(self, num_learning_iterations, init_at_random_ep_len=False):
    applied = {}
    loaded = getattr(self, "_probe_loaded_path", None)
    if FIX and loaded is not None:
        env = self.env.unwrapped
        L = int(self.current_learning_iteration)
        self.current_learning_iteration = L + 1
        env.common_step_counter = (L + 1) * int(self.cfg["num_steps_per_env"])
        self.alg.learning_rate = float(self.alg.optimizer.param_groups[0]["lr"])
        sc = np.load(loaded + ".state.npz", allow_pickle=False)
        ter = env.scene.terrain
        ter.terrain_levels[:] = torch.as_tensor(sc["terrain_levels"], device=ter.terrain_levels.device)
        ter.env_origins[:] = ter.terrain_origins[ter.terrain_levels, ter.terrain_types]
        torch.set_rng_state(torch.as_tensor(sc["torch_cpu"]))
        torch.cuda.set_rng_state(torch.as_tensor(sc["torch_cuda"]))
        np.random.set_state(pickle.loads(sc["numpy_state"].item()))
        random.setstate(pickle.loads(sc["python_state"].item()))
        applied = {"next_label": L + 1, "common_step_counter": env.common_step_counter, "learning_rate": self.alg.learning_rate,
                   "terrain_levels": "from sidecar", "rng": "from sidecar"}
    st = state(self, "pre_learn")
    st["fix_applied"] = applied
    st["num_learning_iterations_arg"] = num_learning_iterations
    if self.logger.log_dir:
        os.makedirs(self.logger.log_dir, exist_ok=True)
        json.dump(st, open(os.path.join(self.logger.log_dir, "pre_learn.state.json"), "w"), indent=1)
    return _orig_learn(self, num_learning_iterations, init_at_random_ep_len)


OnPolicyRunnerCTS.save, OnPolicyRunnerCTS.load, OnPolicyRunnerCTS.learn = save, load, learn
sys.argv = [os.path.join(REPO, "scripts", "rsl_rl", "train.py")] + sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
