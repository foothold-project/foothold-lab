"""CPU dry training entry contract with real E1 strict CPU parent load."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

import numpy as np
import torch

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "s2_step3"))
from s2_train_entry import execute, parser, validated
sys.path.insert(0, str(HERE / "s2_step2"))


def same_state(left, right):
    if isinstance(left, torch.Tensor):
        return isinstance(right, torch.Tensor) and torch.equal(left, right)
    if isinstance(left, np.ndarray):
        return isinstance(right, np.ndarray) and np.array_equal(left, right)
    if isinstance(left, dict):
        return isinstance(right, dict) and left.keys() == right.keys() and all(
            same_state(left[k], right[k]) for k in left)
    if isinstance(left, (tuple, list)):
        return isinstance(right, type(left)) and len(left) == len(right) and all(
            same_state(a, b) for a, b in zip(left, right))
    return left == right

torch.set_num_threads(2)
RUN = Path("C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192")
PARENT = RUN / "model_20000.pt"
AGENT = RUN / "params" / "agent.yaml"


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label, flush=True)
    if not condition:
        raise AssertionError(label)


def args(root, *, resume=None, stop=None, deadline=4102444800., mode="full_freeze", W=None, r=None, updates=1):
    argv = ["--cpu_dry", "--parent", str(PARENT), "--agent_yaml", str(AGENT),
            "--out_root", str(root), "--stop_file", str(stop or root.parent / "STOP"),
            "--arm", "B", "--encoder_mode", mode, "--schedule", "fixed",
            "--seed", "11", "--num_envs", "2", "--updates", str(updates), "--rollout_steps", "2",
            "--epochs", "1", "--minibatches", "1", "--checkpoint_interval", "1",
            "--map_init_seed", "7", "--gap_proportion", ".1", "--stones_proportion", ".1",
            "--step_height_m", ".1", "--step_width_m", ".5", "--geometry_tolerance_m", ".02",
            "--deadline_epoch", str(deadline), "--lr", ".001", "--clip_param", ".2",
            "--gamma", ".99", "--lam", ".95", "--value_loss_coef", "1.0",
            "--entropy_coef", ".01", "--max_grad_norm", "1.0", "--desired_kl", ".01",
            "--use_clipped_value_loss", "true"]
    if resume:
        argv += ["--resume", str(resume)]
    if W is not None:
        argv += ["--freeze_updates", str(W)]
    if r is not None:
        argv += ["--encoder_lr_ratio", str(r)]
    return parser(True).parse_args(argv)


def tests():
    assert PARENT.is_file() and AGENT.is_file()
    with tempfile.TemporaryDirectory(prefix="s2_step3_entry_") as tmp:
        root = Path(tmp)
        a = args(root / "run", updates=2)
        spec, cfg = validated(a)
        check("entry explicit plan and environment", spec.num_envs == cfg.num_envs == 2)
        try: validated(args(root / "bad_mode", mode="schedule"))
        except ValueError: bad_mode = True
        else: bad_mode = False
        check("schedule W r required", bad_mode)
        try: validated(args(root / "bad_full", W=3, r=.2))
        except ValueError: bad_full = True
        else: bad_full = False
        check("full freeze forbids W r", bad_full)
        first = execute(a, cpu_dry=True)
        ckpt = root / "run" / "checkpoint_000001.pt"
        check("CPU dry update log checkpoint result", first["status"] == "PASS" and
              first["executed_updates"] == 2 and first["optimizer_steps_actual"] == 2 and
              ckpt.is_file() and (root / "run" / "updates.jsonl").is_file() and
              json.loads((root / "run" / "result.json").read_text())["status"] == "PASS")
        second = execute(args(root / "resume", resume=ckpt), cpu_dry=True)
        check("CPU dry resumed runner and control", second["status"] == "PASS" and
              second["executed_updates"] == 1 and (root / "resume" / "checkpoint_000001.pt").is_file())
        uninterrupted = torch.load(root / "run" / "checkpoint_000002.pt", map_location="cpu", weights_only=False)
        resumed = torch.load(root / "resume" / "checkpoint_000001.pt", map_location="cpu", weights_only=False)
        check("CPU dry resume bit identical policy control optimizer env RNG",
              all(same_state(uninterrupted[key], resumed[key]) for key in
                  ("policy", "s2_control", "optimizer", "env_state", "rng")))
        stop = root / "STOP"
        stop.write_text("stop", encoding="utf-8")
        stopped = execute(args(root / "stopped", stop=stop), cpu_dry=True)
        check("STOP before update holds", stopped["status"] == "HOLD" and
              stopped["executed_updates"] == 0 and stopped["stop_reason"] == "STOP file")
        stop.unlink()
        late = execute(args(root / "deadline", deadline=1.), cpu_dry=True)
        check("deadline before update holds", late["status"] == "HOLD" and
              late["executed_updates"] == 0 and late["stop_reason"] == "deadline")


if __name__ == "__main__":
    tests()
