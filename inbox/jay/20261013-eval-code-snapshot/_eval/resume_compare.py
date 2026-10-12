# Compare the state dumps of the resume test runs (CPU only) -> out/resume_test/compare.json
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "out", "resume_test", "logs", "rsl_rl", "go2_moe_cts")


def run_dir(name):
    d = sorted(glob.glob(os.path.join(ROOT, f"*_{name}")))
    return d[-1] if d else None


def load(name, f):
    d = run_dir(name)
    p = os.path.join(d, f) if d else None
    return json.load(open(p)) if p and os.path.exists(p) else None


KEYS = ["runner_iteration", "env_common_step_counter", "env_iter_from_counter", "command_ranges", "command_range_curriculum_remaining",
        "zero_command_prob", "terrain_level_mean", "terrain_level_hist", "reward_weights", "episode_length_buf_mean", "episode_length_buf_sha",
        "alg_learning_rate", "optimizer", "optimizer_stu_enc", "rng", "model_sha", "action_std_mean", "sim_step_counter"]


def diff(a, b):
    if a is None or b is None:
        return {"missing": [x is None for x in (a, b)]}
    out = {}
    for k in KEYS:
        if json.dumps(a.get(k), sort_keys=True) != json.dumps(b.get(k), sort_keys=True):
            out[k] = [a.get(k), b.get(k)]
    return out


R = {"dirs": {n: run_dir(n) for n in ("rt_cont", "rt_split1", "rt_split2", "rt_fix2")}}
# after 100 updates (label 99 in all runs that have it)
c99 = load("rt_cont", "model_99.pt.state.json")
s99 = load("rt_split1", "model_99.pt.state.json")
R["at100_cont_vs_split1_saved"] = diff(c99, s99)
R["split2_post_load"] = load("rt_split2", "post_load.state.json")
R["split2_pre_learn"] = load("rt_split2", "pre_learn.state.json")
R["fix2_pre_learn"] = load("rt_fix2", "pre_learn.state.json")
R["at100_cont_vs_split2_pre_learn"] = diff(c99, R["split2_pre_learn"])
R["at100_cont_vs_fix2_pre_learn"] = diff(c99, R["fix2_pre_learn"])
# after 200 updates: continuous label 199, plain resume label 198 (it repeats label 99), fixed resume label 199
c199 = load("rt_cont", "model_199.pt.state.json")
s198 = load("rt_split2", "model_198.pt.state.json")
f199 = load("rt_fix2", "model_199.pt.state.json")
R["at200_cont_vs_split2"] = diff(c199, s198)
R["at200_cont_vs_fix2"] = diff(c199, f199)
R["labels"] = {n: sorted(int(os.path.basename(p)[6:-3]) for p in glob.glob(os.path.join(run_dir(n) or "", "model_*.pt"))) for n in R["dirs"] if run_dir(n)}
# trajectory of schedule values at every saved label
traj = {}
for n in ("rt_cont", "rt_split1", "rt_split2", "rt_fix2"):
    d = run_dir(n)
    if not d:
        continue
    rows = []
    for p in sorted(glob.glob(os.path.join(d, "model_*.pt.state.json")), key=lambda x: int(os.path.basename(x).split("_")[1].split(".")[0])):
        s = json.load(open(p))
        rows.append({"label": s["runner_iteration"], "counter_iter": s["env_iter_from_counter"], "zero_prob": round(s["zero_command_prob"], 5),
                     "w_base_height": s["reward_weights"].get("base_height_l2"), "w_lin_vel_z": s["reward_weights"].get("lin_vel_z_l2"),
                     "lr_alg": s["alg_learning_rate"], "lr_opt": s["optimizer"]["lr_groups"][0], "adam_step": s["optimizer"]["adam_step_values"],
                     "terrain_mean": round(s["terrain_level_mean"], 3), "vx_range": s["command_ranges"]["lin_vel_x"]})
    traj[n] = rows
R["schedule_by_label"] = traj
json.dump(R, open(os.path.join(HERE, "out", "resume_test", "compare.json"), "w"), indent=1)
print(json.dumps({k: (v if not isinstance(v, dict) or len(json.dumps(v)) < 1500 else list(v)) for k, v in R.items() if k.startswith("at") or k == "labels"}, indent=1)[:6000])
