"""REQ430 D-2 stage A recorder, made by docs/stage1_logs/req430/rec/make_rec.py from req428/evstu/eval_student.py (md5 ddfc1b8b258814cca9eaceb45423ae0d). See rec_hooks.py.
REQ428 (11-23): eval_student.py =  req425/walk21/wk21/eval_gaze_map5.py (md5 39ac2820, the walk tests' evaluator) and copy
fpc_lib.py (7ddf212f) next to it. The benchmark part (frozen levels k % rows per column, final ramps, the first `need` played episodes per env,
rows / step sums / digests / gaze tallies, the saved keys) is left as it is; only the map side changes:
  * no walk_hook2: the STUDENT task (Ame2-Go2-Gaze-Student-N9P12-Eval5) builds its own range sensors and map (patch_stu.py: measured D435i, L2,
    GlobalMapV2, mapper in chunks of 512); --student_map tu sets the learned mapper (--mapper_jit), pass leaves the pass-through mapper;
  * the range sensors draw their random numbers from a private generator (seed + 987654), exactly as walk_hook2.install does
    (_seed_private / isolated on Go2RangeSensor._initialize_rays_impl / reset / _update_buffers_impl), so the env's own random stream
    (start randomisation, goals, robot randomisation) is not shifted by the sensors;
  * the actor is the student (AME2GazeLSIOModel; its gaze is the same crop module, read on the 29 x 13 neural map); PPO_IL is built with
    --teacher_jit (not used for actions); the teacher-map noise check becomes "teacher map noise 0" (student task) and the student settings
    (map source, mapper sha256, fusion, chunk, sensor specs, completed_updates, il_update_cnt, student checkpoint sha256) are printed and saved
    under "student428".
The docstring of eval_gaze_map5.py follows (its map sources are not used here).
REQ425 wk9 (11-21; req425/umask_tools.py): + the map source "model_umask". The REQ410 docstring follows.
REQ410 eval_gaze_map5.py, 2nd version (made by req410/make_walk410.py from req406/walk/wk1/eval_gaze_map4.py 9d1e7995): + the map sources "model_pmask" (the learned mapper's heights with the variance path of pass) and "model_low" (model with unwritten points read as the teacher's void fallback) through walk_hook2.py (= walk_hook.py + those sources + the cell classes). The earlier docstring follows.
REQ406 eval_gaze_map4.py (made by req406/make_walk406.py from req359/mapv3/eval_gaze_map3.py ab56f91e): + the map source "model" (--mapper_jit: the learned mapper, map_v3 ExportV3 TorchScript) through walk_hook.py (= mapv3_hook.py + that source). The earlier docstring follows.
Fixed-level evaluation of one teacher checkpoint (docs/TEST_DESIGN_DEMOTION_STAGE2.md, section 3).

Levels are frozen and assigned deterministically (the k-th env of a column -> level k % rows), the three ramps are
at their final values whatever the checkpoint's step counter says, the actor alone is loaded and (by default) acts
with the mean. Every env plays `--episodes` + 1 episodes; the first one (started by the explicit setup reset) is
not counted. The raw per-episode rows and per-env step totals are saved; `eval_compare.py` turns two such files
into the tables and the verdict.

REQ212 copy (docs/stage1_logs/req206/design_next_v3.md section 1): the pod's go2/scripts/eval_fixed.py (md5
8125ae19d7bf062d7137c0fb7c7b13c5, the 20000 Eval5 code) with the same evaluation, computed the same way and saved under the
same keys, plus the gaze of the SAME episodes. The gaze is the value the policy itself produced for the action of that step
(actor._last_gaze_r after the policy call; the policy is not called again and nothing random is drawn: the torch CPU / CUDA
generator states are compared before and after the added work at every step). Feet, contacts and the motion class are read
from the state the observation describes (right before the policy call), as in diag_footprint.py. The first --gaze_warmup
policy steps of every episode are left out of the gaze tallies (diag_footprint.py's warm-up), and counted separately.
Added to the saved file:
  EP       one row per kept row of `rows` (same order), the gaze of that episode (fields in ep_fields): robot, played index k
           (0 = the uncounted first episode), first / last step, policy steps, used steps (after the warm-up), sum r_x, sum r_x^2,
           r_x > 0.95 / 0.99 / 0.999 / 0.9999, front contact foot-steps and those inside the window (FL, FR), the same over
           the last --last_k used steps of the episode (fewer if the episode had fewer; nothing from another episode), the
           window-start histogram of the whole episode and of its last steps (columns win_*, last_win_*)
  RXH_A / RXC_A / RSC_A / WINC_A / FIN_A   per terrain type, level and motion class (footprint_lib.classify), over the used
           steps of the counted episodes (k = 1 .. episodes): r_x histogram (fpc_lib.EDGES), counts above the four
           thresholds, n / sum r_x / sum r_x^2, window starts, front contact foot-steps (all, inside)
  gaze_warmup, last_k, ep_fields, classes, rx_edges, rx_thresholds, rng_checks, tool, tool_md5
Every kept row is linked to the episode record of the same robot and played index (keyed by the pair); the number of rows whose
record's policy steps differ from the row's ep_len is saved as ep_len_mismatch (the file is still written; the queue's gaze check
refuses any non-zero count). After the evaluation (it cannot change the results), a fixed-input check calls the policy twice on
one stored observation: the same action and gaze, the generators untouched by the tallies.
The file lives OUTSIDE go2/scripts (on the pod in go2/_runs/evalgz/, next to fpc_lib.py); it is run from the main tree.

  cd <volume folder>/ame2 && go2/scripts/run.sh py go2/_runs/evalgz/eval_gaze.py --headless --task Ame2-Go2-Gaze-Gap12a-Eval5 \
    --num_envs 2400 --episodes 5 --checkpoint <model.pt> --seed 42 --out <file.pt> agent.actor.crop_x=12 agent.actor.crop_y=10
"""

import argparse
import hashlib
import os
import sys
import time

from isaaclab.app import AppLauncher

SCRIPTS = os.path.join(os.getcwd(), "go2", "scripts")  # the main tree's scripts (run from the main tree)
HERE = os.path.dirname(os.path.abspath(__file__))  # fpc_lib.py lives next to this file
assert os.path.isfile(os.path.join(SCRIPTS, "curriculum_split.py")) and os.path.isfile(os.path.join(SCRIPTS, "rsl_rl", "cli_args.py")), SCRIPTS
assert os.path.isfile(os.path.join(HERE, "fpc_lib.py")) and os.path.realpath(HERE) != os.path.realpath(SCRIPTS), HERE
sys.path.append(os.path.join(SCRIPTS, "rsl_rl"))
sys.path.append(SCRIPTS)
sys.path.append(HERE)
import cli_args  # isort: skip

parser = argparse.ArgumentParser()
parser.add_argument("--task", type=str, default="Ame2-Go2-Gaze")
parser.add_argument("--agent", type=str, default="rsl_rl_cfg_entry_point")
parser.add_argument("--num_envs", type=int, default=4096)
parser.add_argument("--seed", type=int, default=None, help="benchmark seed: terrain tiles, start randomisation, goals")
parser.add_argument("--episodes", type=int, default=6, help="counted episodes per env (after the uncounted first one)")
parser.add_argument("--max_steps", type=int, default=None, help="stop after this many policy steps even if episodes are missing")
parser.add_argument("--sample", action="store_true", help="sample the actions instead of using the mean")
parser.add_argument("--out", type=str, required=True)
parser.add_argument("--student_map", type=str, required=True, choices=["tu", "pass"], help="REQ428: the student's own map: tu = the learned mapper --mapper_jit, pass = the rule map (pass-through mapper)")
parser.add_argument("--teacher_jit", type=str, required=True, help="REQ428: the exported teacher of the student run (PPO_IL is built with it; it does not act)")
parser.add_argument("--mapper_jit", type=str, default=None, help="REQ406 / REQ410: the learned mapper (TorchScript, mapper(grid) -> (mean, logvar)) for --map_source model, model_pmask and model_low")
parser.add_argument("--probe_every", type=int, default=0, help="REQ359: diagnostic comparison every N policy steps (0 = off)")
parser.add_argument("--trace_out", type=str, default=None, help="REQ359: hashes per step and the diagnostics")
parser.add_argument("--no_trace", action="store_true", help="REQ359: no per-step hashes (cost runs)")
parser.add_argument("--smoke", action="store_true", help="REQ359: end after --max_steps without the end-of-run tallies; no .pt")
parser.add_argument("--save_actions", type=str, default=None, help="REQ359 stage 3: save the applied actions of every step (.pt)")
parser.add_argument("--replay_actions", type=str, default=None, help="REQ359 stage 3: give env.step these saved actions instead of the policy's")
parser.add_argument("--align_every", type=int, default=0, help="REQ359 stage 3: query alignment check every N policy steps (0 = off)")
parser.add_argument("--gaze_warmup", type=int, default=10, help="policy steps after a reset left out of the gaze tallies")
parser.add_argument("--last_k", type=int, default=50, help="used steps at the end of an episode for the last_* fields")
parser.add_argument("--rec_out", type=str, required=True, help="REQ430 D-2: the recording folder (must not exist)")
parser.add_argument("--rec_mode", type=str, default="on", choices=["on", "off"], help="REQ430 D-2: off = fingerprints only (reproducibility runs)")
parser.add_argument("--rec_episodes", type=int, default=3, help="REQ430 D-2: episodes per recorded robot, the first (explicit reset) included")
parser.add_argument("--rec_levels", type=str, default="4,9", help="REQ430 D-2: recorded levels of every terrain but the stones")
parser.add_argument("--rec_levels_stones", type=str, default="2,5", help="REQ430 D-2: recorded levels of the stones")
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args, hydra_args = parser.parse_known_args()
sys.argv = [sys.argv[0]] + hydra_args
app = AppLauncher(args).app

import gymnasium as gym
import torch

from rsl_rl.runners import OnPolicyRunner

from isaaclab.utils.math import euler_xyz_from_quat, yaw_quat
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
from isaaclab_tasks.utils.hydra import hydra_task_config

import ame2_go2.tasks  # noqa: F401
import curriculum_split as cs
import footprint_lib as fl
import fpc_lib as fpc
import rec_hooks as RH  # REQ430 D-2
from ame2_go2.provenance import code_id
from ame2_go2.sensors.virtual_floor import column_terrain_names
from ame2_go2.tasks.mdp.curriculums import ame2_terrain_levels_goalreaching

assert os.path.realpath(os.path.dirname(cs.__file__)) == os.path.realpath(SCRIPTS), cs.__file__
assert os.path.realpath(os.path.dirname(fl.__file__)) == os.path.realpath(SCRIPTS), fl.__file__
assert os.path.realpath(os.path.dirname(fpc.__file__)) == os.path.realpath(HERE), fpc.__file__

FINAL_COUNTER = 10**9  # far beyond any ramp length: the ramp functions clamp their progress at 1
STEP_KEYS = ("all", "valid", "air", "calf", "thigh", "moving", "air_moving", "calf_moving", "thigh_moving", "leap_pen", "nonfoot_pen", "jlim", "selfcol")
FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
NTH = len(fpc.THRESHOLDS)
# per-episode record: scalar fields, then the window-start histograms of the whole episode and of its last steps
EP_SCALARS = ("env", "k", "first_step", "last_step", "steps", "used", "sum_rx", "sum_rx2", "above_095", "above_099", "above_0999", "above_09999",
              "front_all", "front_in", "last_used", "last_sum_rx", "last_sum_rx2", "last_above_095", "last_above_099", "last_above_0999",
              "last_above_09999", "last_front_all", "last_front_in")  # fmt: skip


def P(*a):
    print("[EVAL]", *a, flush=True)


def sha(t):
    return hashlib.sha256(t.detach().cpu().contiguous().numpy().tobytes()).hexdigest()[:16]


def file_md5(p):
    with open(p, "rb") as f_:
        return hashlib.md5(f_.read()).hexdigest()


def rng_state():
    return torch.get_rng_state().clone(), (torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [])


RNG = {"cpu": None, "cuda": None, "depth": 0}  # REQ428: walk_hook2.py's private random state of the range sensors


def _seed_private(seed):
    assert torch.cuda.device_count() == 1, "the private random state handles one CUDA device"
    c0, g0 = torch.get_rng_state(), torch.cuda.get_rng_state()
    torch.manual_seed(int(seed) + 987654)
    RNG["cpu"], RNG["cuda"] = torch.get_rng_state(), torch.cuda.get_rng_state()
    torch.set_rng_state(c0)
    torch.cuda.set_rng_state(g0)


def isolated(fn):
    """swap in the private state at the outermost call only; a nested call runs in the same private stream (walk_hook2.py)"""

    def w(*a, **k):
        if RNG["depth"] > 0:
            return fn(*a, **k)
        c0, g0 = torch.get_rng_state(), torch.cuda.get_rng_state()
        torch.set_rng_state(RNG["cpu"])
        torch.cuda.set_rng_state(RNG["cuda"])
        RNG["depth"] = 1
        try:
            return fn(*a, **k)
        finally:
            RNG["depth"] = 0
            RNG["cpu"], RNG["cuda"] = torch.get_rng_state(), torch.cuda.get_rng_state()
            torch.set_rng_state(c0)
            torch.cuda.set_rng_state(g0)

    return w


def rng_equal(a, b):
    return torch.equal(a[0], b[0]) and len(a[1]) == len(b[1]) and all(torch.equal(x, y) for x, y in zip(a[1], b[1]))


@hydra_task_config(args.task, args.agent)
def main(env_cfg, agent_cfg):
    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args)
    # REQ430 D-2: deterministic GPU kernels and no TF32 (the ONNX comparison is float32 on the CPU); checked again before the loop
    DET = {"cudnn.deterministic": True, "cudnn.benchmark": False, "cuda.matmul.allow_tf32": False, "cudnn.allow_tf32": False}
    torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark = True, False
    torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = False, False
    env_cfg.seed = agent_cfg.seed
    env_cfg.scene.num_envs = args.num_envs
    gen = env_cfg.scene.terrain.terrain_generator
    env_cfg.scene.terrain.max_init_terrain_level = gen.num_rows - 1

    # the recording wrapper of stage 1, with every env on the authors' rule; the levels stay frozen throughout
    term = env_cfg.curriculum.terrain_levels
    assert term.func is ame2_terrain_levels_goalreaching, term.func
    up_dist = term.params["move_up_dist"]
    cs.STATE["orig"] = ame2_terrain_levels_goalreaching
    term.func = cs.split_terrain_levels

    # ---- REQ428: the student's own map (the task builds sensors, runtime and fusion; see patch_stu.py) and private sensor random numbers
    from ame2_go2.sensors.range_sensor import Go2RangeSensor

    assert args.task == "Ame2-Go2-Gaze-Student-N9P12-Eval5", args.task
    assert not (args.probe_every or args.trace_out or args.save_actions or args.replay_actions or args.align_every), "REQ428: walk-hook options are not used"
    nm_ = env_cfg.observations.neural_map.neural_map.params
    assert nm_.get("fusion") == "v2" and int(nm_.get("chunk", 0)) == 512 and nm_.get("mapper_path") is None, nm_
    mapper_sha = None
    if args.student_map == "tu":
        assert args.mapper_jit and os.path.isfile(args.mapper_jit), args.mapper_jit
        nm_["mapper_path"] = os.path.abspath(args.mapper_jit)
        with open(args.mapper_jit, "rb") as f_:
            mapper_sha = hashlib.sha256(f_.read()).hexdigest()
    else:
        assert args.mapper_jit is None, "REQ428: --student_map pass takes no --mapper_jit"
    assert os.path.isfile(args.teacher_jit), args.teacher_jit
    agent_cfg.algorithm.teacher_path = os.path.abspath(args.teacher_jit)
    dsp, lsp = env_cfg.scene.depth, env_cfg.scene.lidar
    assert abs(dsp.pattern_cfg.spec.mount_rpy[1] - 0.6108652381980153) < 1e-12 and tuple(dsp.pattern_cfg.spec.mount_pos) == (0.35, 0.0, 0.07), dsp.pattern_cfg.spec
    assert (dsp.pattern_cfg.spec.table_kwargs["width"], dsp.pattern_cfg.spec.table_kwargs["height"]) == (80, 60), dsp.pattern_cfg.spec.table_kwargs
    assert (dsp.dropout, dsp.artifact, lsp.dropout, lsp.artifact) == (0.15, 0.02, 0.15, 0.02) and abs(dsp.update_period - 0.1) < 1e-12 and abs(lsp.update_period - 0.1) < 1e-12
    _seed_private(env_cfg.seed)
    Go2RangeSensor._initialize_rays_impl = isolated(Go2RangeSensor._initialize_rays_impl)
    Go2RangeSensor.reset = isolated(Go2RangeSensor.reset)
    Go2RangeSensor._update_buffers_impl = isolated(Go2RangeSensor._update_buffers_impl)
    S428 = {"student_map": args.student_map, "mapper_jit": nm_["mapper_path"], "mapper_sha256": mapper_sha, "fusion": nm_["fusion"], "chunk": int(nm_["chunk"]),
            "teacher_jit": os.path.abspath(args.teacher_jit), "teacher_jit_md5": file_md5(args.teacher_jit), "sensor_private_seed": int(env_cfg.seed) + 987654,
            "depth": {"rpy": [float(x) for x in dsp.pattern_cfg.spec.mount_rpy], "pos": [float(x) for x in dsp.pattern_cfg.spec.mount_pos],
                      "table": dict(dsp.pattern_cfg.spec.table_kwargs), "noise_quadratic": float(dsp.pattern_cfg.spec.noise_quadratic),
                      "pos_jitter": float(dsp.pattern_cfg.spec.mount_pos_jitter), "dropout": float(dsp.dropout), "artifact": float(dsp.artifact)},
            "lidar": {"dropout": float(lsp.dropout), "artifact": float(lsp.artifact)}}
    # REQ430 D-2: the student's proprioception / command groups without the training noise (Codex 430_2 / 430_8: the replay compares inputs)
    env_cfg.observations.student_prop_hist.enable_corruption = False
    env_cfg.observations.student_cmds.enable_corruption = False
    env = RslRlVecEnvWrapper(gym.make(args.task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
    _om = env.unwrapped.observation_manager
    for _g in ("student_prop_hist", "student_cmds"):
        _tc = _om._group_obs_term_cfgs[_g]
        assert len(_tc) > 0 and all(getattr(t_, "noise", None) is None for t_ in _tc), f"REQ430: noise left on {_g}"   # isaaclab observation_manager 547
    # 11-27 pod run: the env's seed() (isaaclab utils/seed.py configure_seed, torch_deterministic False) turns cudnn.benchmark on and
    # deterministic off while the env is made -> the settings are set again here, right after the env, and what the env left is recorded
    det_env = {"cudnn.deterministic": torch.backends.cudnn.deterministic, "cudnn.benchmark": torch.backends.cudnn.benchmark,
               "cuda.matmul.allow_tf32": torch.backends.cuda.matmul.allow_tf32, "cudnn.allow_tf32": torch.backends.cudnn.allow_tf32}
    torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark = True, False
    torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = False, False
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    runner.load(args.checkpoint, load_cfg={"actor": True, "critic": False, "optimizer": False, "iteration": False})
    policy = runner.get_inference_policy(device=env.unwrapped.device)
    # The gaze crop size is not part of any weight shape, so a checkpoint loads under a wrong size without an error:
    # compare the actor that was built here with the settings the run was trained with.
    import yaml

    crop = None
    gaze = list({id(m): m for m in vars(runner.alg).values() if isinstance(m, torch.nn.Module) and hasattr(m, "crop_x")}.values())
    if gaze:
        assert len(gaze) == 1, [type(m).__name__ for m in gaze]
        crop = (int(gaze[0].crop_x), int(gaze[0].crop_y))
        yml = os.path.join(os.path.dirname(os.path.abspath(args.checkpoint)), "params", "agent.yaml")
        assert os.path.isfile(yml), f"cannot verify the crop size, missing {yml}"
        with open(yml) as f:
            trained = yaml.unsafe_load(f)["actor"]
        assert (int(trained["crop_x"]), int(trained["crop_y"])) == crop, f"actor crop {crop} != trained crop {(trained['crop_x'], trained['crop_y'])}"
    # REQ212: the module whose gaze value the inference policy refreshes (diag_footprint.py's rule); it must be the crop module
    found = list({id(m): m for m in vars(runner.alg).values() if isinstance(m, torch.nn.Module) and hasattr(m, "_last_gaze_r")}.values())
    assert len(found) == 1 and gaze and found[0] is gaze[0], ([type(m).__name__ for m in found], crop)
    actor = found[0]
    CX, CY = crop
    e = env.unwrapped
    dev, n = e.device, e.num_envs
    terrain = e.scene.terrain
    names = column_terrain_names(gen)
    type_names = list(dict.fromkeys(names))
    col_type = torch.tensor([type_names.index(c) for c in names], device=dev)
    T, NR, NC = len(type_names), gen.num_rows, gen.num_cols
    env_col = terrain.terrain_types.clone()
    env_type = col_type[env_col]
    term_names = list(e.termination_manager.active_terms)

    ck = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    state = ck.get("go2_env_state", {})
    actor_sha = hashlib.sha256()
    for k in sorted(ck["actor_state_dict"]):
        actor_sha.update(k.encode())
        actor_sha.update(ck["actor_state_dict"][k].cpu().contiguous().numpy().tobytes())
    P(f"code {code_id()}  checkpoint {os.path.basename(os.path.dirname(args.checkpoint))}/{os.path.basename(args.checkpoint)}"
      f"  completed_updates {state.get('completed_updates')}  actor {actor_sha.hexdigest()[:16]}  load actor only")  # fmt: skip
    S428["completed_updates"], S428["il_update_cnt"] = state.get("completed_updates"), state.get("il_update_cnt")
    S428["checkpoint_sha256"] = hashlib.sha256(open(args.checkpoint, "rb").read()).hexdigest()
    assert S428["il_update_cnt"] is not None and int(S428["il_update_cnt"]) == int(S428["completed_updates"]), "REQ428: not a student checkpoint (il_update_cnt)"
    P(f"REQ428 student: map {S428['student_map']}  mapper sha256 {str(S428['mapper_sha256'])[:12]}  fusion {S428['fusion']}  chunk {S428['chunk']}  "
      f"il_update_cnt {S428['il_update_cnt']}  checkpoint sha256 {S428['checkpoint_sha256'][:12]}  teacher jit md5 {S428['teacher_jit_md5']}")
    P(f"task {args.task}  envs {n}  seed {env_cfg.seed}  actions {'sampled' if args.sample else 'mean'}  counted episodes per env {args.episodes}  gaze crop {crop}")
    P(f"terrain: {NR} levels x {NC} columns; types " + ", ".join(f"{nm} x{names.count(nm)}" for nm in type_names))
    P(f"gaze of the same episodes: actor {type(actor).__name__}  roi_margin {actor.roi_margin}  warm-up {args.gaze_warmup}  last {args.last_k} used steps")

    # ---- start state: frozen levels, final ramps
    e._go2_freeze_terrain_curriculum = True
    e.common_step_counter = FINAL_COUNTER
    e.success_rate_reach_ema = torch.zeros(n, device=dev)
    first = torch.zeros(NC, dtype=torch.long, device=dev).scatter_reduce(0, env_col, torch.arange(n, device=dev), reduce="amin", include_self=False)
    terrain.terrain_levels[:] = (torch.arange(n, device=dev) - first[env_col]) % NR
    terrain.env_origins[:] = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
    lv0 = terrain.terrain_levels.clone()
    e.go2_rule_k1 = torch.zeros(n, dtype=torch.bool, device=dev)
    # ---- REQ430 D-2: the recorded robots (one per terrain type x recorded level), chosen before the explicit reset; then the hooks
    lv_n = [int(x) for x in args.rec_levels.split(",")]
    lv_s = [int(x) for x in args.rec_levels_stones.split(",")]
    rec_list, rec_cell = [], []
    for t_ in range(T):
        for l_ in (lv_s if type_names[t_] == "stones" else lv_n):
            cand = ((env_type == t_) & (lv0 == l_)).nonzero(as_tuple=False).flatten()
            assert cand.numel() > 0, f"REQ430: no robot on {type_names[t_]} level {l_} (raise --num_envs)"
            rec_list.append(int(cand[0]))
            rec_cell.append((type_names[t_], l_))
    rec_ids = torch.tensor(rec_list, dtype=torch.long, device=dev)
    term_ = e.action_manager._terms["joint_pos"]
    _hm = lambda p_: hashlib.md5(open(p_, "rb").read()).hexdigest()
    rec_meta = {"args": vars(args), "student428": S428, "rec_ids": rec_list, "rec_cells": rec_cell, "type_names": type_names, "num_envs": n,
                "joint_names": list(e.scene["robot"].data.joint_names), "action_joint_names": list(getattr(term_, "_joint_names", [])),
                "default_joint_pos": e.scene["robot"].data.default_joint_pos[rec_ids].cpu(), "action_scale": term_._scale if not torch.is_tensor(term_._scale) else term_._scale.cpu(),
                "delay_range": list(term_.cfg.delay_range), "step_dt": float(e.step_dt), "physics_dt": float(e.physics_dt), "decimation": int(e.cfg.decimation),
                "term_names": list(e.termination_manager.active_terms), "obs_groups": {k_: list(v_) for k_, v_ in e.observation_manager.active_terms.items()},
                "noise_none": {g_: all(getattr(t_, "noise", None) is None for t_ in e.observation_manager._group_obs_term_cfgs[g_]) for g_ in ("student_prop_hist", "student_cmds", "neural_map")},
                "torch": torch.__version__, "code": code_id(), "seed": env_cfg.seed, "crop": crop, "roi_margin": float(actor.roi_margin),
                "tool_md5": {"rec_student.py": _hm(os.path.abspath(__file__)), "rec_hooks.py": _hm(RH.__file__), "fpc_lib.py": _hm(fpc.__file__)},
                "source_eval_student_md5": "ddfc1b8b258814cca9eaceb45423ae0d", "det_after_env_made": det_env, "frame_period_steps": int(round(float(dsp.update_period) / float(e.step_dt)))}
    assert len(set(rec_list)) == len(rec_list) == 2 * T, f"REQ430: {len(rec_list)} recorded robots, {len(set(rec_list))} unique"
    det_pre = {"cudnn.deterministic": torch.backends.cudnn.deterministic, "cudnn.benchmark": torch.backends.cudnn.benchmark,
               "cuda.matmul.allow_tf32": torch.backends.cuda.matmul.allow_tf32, "cudnn.allow_tf32": torch.backends.cudnn.allow_tf32}
    assert det_pre == DET, f"REQ430: determinism settings before the explicit reset: {det_pre}"   # 430_14: also before the first map of the reset
    rec_meta["det_before_reset"] = det_pre
    RH.install(e, rec_ids, args.rec_out, args.rec_mode, rec_meta)
    P(f"REQ430 D-2 recorder {args.rec_mode}: robots {rec_list} cells {rec_cell}")
    obs, _ = env.reset()
    assert torch.equal(terrain.terrain_levels, lv0) and torch.equal(terrain.terrain_types, env_col)
    # REQ212 checks without random numbers or policy calls: the map size, and the window arithmetic of footprint_lib against the
    # model's own on a fixed grid of gaze values (diag_footprint.py does this with torch.rand, which would shift the generators)
    L_obs, W_obs = obs["neural_map"].shape[1:3]  # REQ428: the student reads its own map (29 x 13 x 4)
    assert (L_obs, W_obs) == (fl.MAP_L, fl.MAP_W), (L_obs, W_obs)
    with torch.inference_mode():
        g_ = torch.linspace(0.0, 1.0, 69, device=dev)
        rr = torch.cat([torch.stack([g_, g_.flip(0)], -1), torch.tensor([[0.0, 0.0], [1.0, 1.0], [0.5, 0.5], [0.5, 0.49], [0.9999, 0.0001]], device=dev)])
        ox_, oy_ = fl.crop_start(rr, crop[0], crop[1])
        cx_ = (crop[0] - 1) / 2.0 + rr[:, 0] * float(L_obs - crop[0])
        cy_ = (crop[1] - 1) / 2.0 + rr[:, 1] * float(W_obs - crop[1])
        mox, moy = gaze[0]._crop_window(cx_, cy_, L_obs, W_obs)
        assert torch.equal(ox_, mox) and torch.equal(oy_, moy), "window arithmetic differs from the model"
        idx_map = torch.arange(L_obs * W_obs, device=dev, dtype=torch.float32).view(1, L_obs, W_obs, 1).expand(len(rr), L_obs, W_obs, 1)
        patch = gaze[0]._hard_crop(idx_map, mox, moy)[..., 0]
        assert torch.equal(patch[:, 0, 0].long(), ox_ * W_obs + oy_) and torch.equal(patch[:, -1, -1].long(), (ox_ + crop[0] - 1) * W_obs + oy_ + crop[1] - 1), "crop cells"

    cmd_cfg = e.command_manager.get_term("base_pose").cfg
    yaw = e.event_manager.get_term_cfg("reset_base").params["pose_range"]["yaw"]
    noise = e.observation_manager.cfg.teacher_mapping.teacher_mapping.params["custom_noise"]  # what the ramp term writes to
    P(f"ramps: goal cone {cmd_cfg.cone_angle_deg:.2f} deg  start yaw {yaw}  map noise {list(noise)}")
    assert abs(cmd_cfg.cone_angle_deg - 45.0) < 1e-6 and abs(yaw[1] - 3.141592653589793) < 1e-6, "ramps are not at their final values"
    assert [float(x) for x in noise] == [0.0, 0.0, 0.0], f"REQ428: the student task keeps the teacher map noiseless: {noise}"

    robot = e.scene["robot"]
    digests = {"terrain_origins": sha(terrain.terrain_origins), "env_origins": sha(terrain.env_origins), "levels": sha(lv0), "types": sha(env_col)}
    patches = terrain.flat_patches  # goal positions come from these; they follow the generated tiles
    for key, get in (
        ("flat_patches", lambda: torch.cat([patches[k].flatten() for k in sorted(patches)]) if patches else torch.zeros(1)),
        ("masses", lambda: robot.root_physx_view.get_masses()),
        ("materials", lambda: robot.root_physx_view.get_material_properties()),
        ("coms", lambda: robot.root_physx_view.get_coms()),
        ("joint_stiffness", lambda: robot.data.joint_stiffness),
        ("joint_damping", lambda: robot.data.joint_damping),
        ("actuator_stiffness", lambda: torch.cat([torch.as_tensor(a.stiffness).flatten().float().cpu() for a in robot.actuators.values()])),
        ("actuator_damping", lambda: torch.cat([torch.as_tensor(a.damping).flatten().float().cpu() for a in robot.actuators.values()])),
    ):
        try:
            digests[key] = sha(get())
        except Exception as err:
            digests[key] = f"unavailable: {type(err).__name__}"
    P("benchmark digests: " + "  ".join(f"{k} {v}" for k, v in digests.items()))
    cells = torch.zeros(T, NR, dtype=torch.long, device=dev).index_put_((env_type, lv0), torch.ones(n, dtype=torch.long, device=dev), accumulate=True)
    P(f"envs per (terrain type, level): min {int(cells.min())}  max {int(cells.max())}  empty cells {int((cells == 0).sum())}")

    # ---- per-step readings (taken after the step; envs that were just reset are left out of that step)
    sensor = e.scene["contact_forces"]
    body_names = sensor.body_names
    feet = [i for i, b in enumerate(body_names) if b.endswith("_foot")]
    calf = [i for i, b in enumerate(body_names) if b.endswith("_calf")]
    thigh = [i for i, b in enumerate(body_names) if b.endswith("_thigh")]
    assert len(feet) == 4 and len(calf) == 4 and len(thigh) == 4, body_names
    rm = e.reward_manager
    rterms = list(rm.active_terms)

    def raw(name):  # raw value of a reward term at the last step (the step reward is weight * raw)
        return rm._step_reward[:, rterms.index(name)] / rm.get_term_cfg(name).weight

    # ---- REQ212: the gaze of the same episodes (read-only on the simulation; no random numbers)
    rb = [robot.body_names.index(b) for b in FEET]
    sb = [sensor.body_names.index(b) for b in FEET]
    L_, W_ = fl.MAP_L, fl.MAP_W
    NOX = L_ - CX + 1
    NCLS = len(fl.CLASSES)
    edges_dev = fpc.EDGES.to(dev)

    def gstate():
        """What the observation describes (as diag_footprint.py's state()): feet (world xy), contact, base xy, heading, planar velocity, yaw rate."""
        q = robot.data.root_quat_w
        yw = euler_xyz_from_quat(yaw_quat(q))[2]
        feet_w = robot.data.body_pos_w[:, rb, :2].clone()
        con = sensor.data.net_forces_w[:, sb].norm(dim=-1) > 1.0
        base = robot.data.root_pos_w[:, :2].clone()
        v = robot.data.root_lin_vel_w[:, :2]
        c, s = torch.cos(yw), torch.sin(yw)
        vx, vy = c * v[:, 0] + s * v[:, 1], -s * v[:, 0] + c * v[:, 1]
        return feet_w, con.clone(), base, yw.clone(), vx.clone(), vy.clone(), robot.data.root_ang_vel_w[:, 2].clone()

    Zl = lambda *shape: torch.zeros(*shape, dtype=torch.long, device=dev)
    RXH_A = Zl(T, NR, NCLS, fpc.NB)
    RXC_A = Zl(T, NR, NCLS, NTH)
    RSC_A = torch.zeros(T, NR, NCLS, 3, dtype=torch.float64, device=dev)
    WINC_A = Zl(T, NR, NCLS, NOX)
    FIN_A = Zl(T, NR, NCLS, 2)  # front contact foot-steps: all, inside the window
    # running per-episode accumulators (index = robot) and a ring of the last `last_k` used steps
    K_ = args.last_k
    a_first = Zl(n)
    a_steps = Zl(n)
    a_used = Zl(n)
    a_sum = torch.zeros(n, 2, dtype=torch.float64, device=dev)  # sum r_x, sum r_x^2
    a_above = Zl(n, NTH)
    a_front = Zl(n, 2)
    a_win = Zl(n, NOX)
    ring_rx = torch.zeros(n, K_, dtype=torch.float64, device=dev)
    ring_ox = Zl(n, K_)
    ring_front = Zl(n, K_, 2)
    ep_step = Zl(n)  # policy steps of the running episode before this one
    ep_records = []
    ar = torch.arange(n, device=dev)
    rng_checks = 0

    sums = {k: torch.zeros(n, dtype=torch.float64, device=dev) for k in STEP_KEYS}
    ep_done = torch.zeros(n, dtype=torch.long, device=dev)
    jlim_max = torch.zeros(n, device=dev)
    need = args.episodes + 1
    max_steps = args.max_steps or int(args.rec_episodes * e.max_episode_length + 50)   # REQ430 D-2
    cs.STATE["record"], cs.STATE["rows"] = True, []
    row_step = []
    t0 = time.time()
    step = 0
    obs_check = None
    det_now = {"cudnn.deterministic": torch.backends.cudnn.deterministic, "cudnn.benchmark": torch.backends.cudnn.benchmark,
               "cuda.matmul.allow_tf32": torch.backends.cuda.matmul.allow_tf32, "cudnn.allow_tf32": torch.backends.cudnn.allow_tf32}
    assert det_now == DET, f"REQ430: determinism settings changed during the set-up: {det_now}"
    while step < max_steps and not RH.episodes_done(args.rec_episodes):   # REQ430 D-2: until every recorded robot finished its episodes
        with torch.inference_mode():
            feet_w, con, base, yw, vx, vy, wz = gstate()  # REQ212: the state the observation describes
            actor._last_gaze_r = None
            act = policy(obs, stochastic_output=True) if args.sample else policy(obs)
            assert actor._last_gaze_r is not None and tuple(actor._last_gaze_r.shape) == (n, 2), "the inference policy does not refresh this actor's gaze"
            g0 = rng_state()
            r = actor._last_gaze_r.detach().clone()
            if obs_check is None:
                obs_check = {k: v.clone() for k, v in obs.items()} if isinstance(obs, dict) else obs.clone()
                fb0 = fl.to_base_yaw(feet_w, base, yw)
                assert float(fb0[:, 0, 0].median()) > 0 > float(fb0[:, 2, 0].median()) and float(fb0[:, 0, 1].median()) > 0 > float(fb0[:, 1, 1].median()), "foot order / frame"
            # -- the added tallies: same r, same state; nothing here draws a random number or touches the simulation
            rx = r[:, 0]
            rx64 = rx.double()
            rxb = fpc.rx_bin(rx, edges_dev)
            rxa = fpc.above(rx)
            ox, oy = fl.crop_start(r, CX, CY)
            RH.policy_step(step, obs, act, r, ox, oy)   # REQ430 D-2: copies only (no random number, no model call)
            fb = fl.to_base_yaw(feet_w, base, yw)
            x0, x1, y0, y1 = fl.window_rect(ox, oy, CX, CY)
            inw = fl.inside(fb, x0, x1, y0, y1)
            fcon = con[:, :2]
            front = torch.stack([fcon.sum(1), (fcon & inw[:, :2]).sum(1)], -1).long()
            cls = fl.classify(vx, vy, wz)
            used = ep_step >= args.gaze_warmup
            u = used
            a_steps += 1
            a_used += u.long()
            a_sum += torch.stack([rx64, rx64 * rx64], -1) * u.unsqueeze(-1).double()
            a_above += rxa.long() * u.unsqueeze(-1).long()
            a_front += front * u.unsqueeze(-1).long()
            a_win.index_put_((ar[u], ox[u]), torch.ones(int(u.sum()), dtype=torch.long, device=dev), accumulate=True)
            slot = (a_used - 1).remainder(K_)  # the used step just added goes to slot (used count - 1) mod K
            ring_rx[ar[u], slot[u]] = rx64[u]
            ring_ox[ar[u], slot[u]] = ox[u]
            ring_front[ar[u], slot[u]] = front[u]
            cnt = u & (ep_done >= 1) & (ep_done < need)  # used steps of the counted episodes
            ty, lv, cl = env_type[cnt], lv0[cnt], cls[cnt]
            RXH_A.index_put_((ty, lv, cl, rxb[cnt]), torch.ones(int(cnt.sum()), dtype=torch.long, device=dev), accumulate=True)
            for j in range(NTH):
                mm = cnt & rxa[:, j]
                RXC_A.index_put_((env_type[mm], lv0[mm], cls[mm], torch.full((int(mm.sum()),), j, device=dev)), torch.ones(int(mm.sum()), dtype=torch.long, device=dev), accumulate=True)
            RSC_A.index_put_((ty, lv, cl), torch.stack([torch.ones_like(rx64), rx64, rx64 * rx64], -1)[cnt], accumulate=True)
            WINC_A.index_put_((ty, lv, cl, ox[cnt]), torch.ones(int(cnt.sum()), dtype=torch.long, device=dev), accumulate=True)
            FIN_A.index_put_((ty, lv, cl), front[cnt], accumulate=True)
            assert rng_equal(g0, rng_state()), "the gaze tallies changed a random number generator"
            rng_checks += 1
            obs, _, dones, _ = env.step(act)
        while len(row_step) < len(cs.STATE["rows"]):
            row_step.append(step)
        dones = dones.bool()
        RH.after_step(step, dones)   # REQ430 D-2
        in_window = (ep_done >= 1) & (ep_done < need)  # the step just taken belongs to a counted episode
        counted = in_window & ~dones  # sensors already show the new episode for envs that were reset: leave those out
        force = sensor.data.net_forces_w.norm(dim=-1)  # (n, bodies)
        air = (force[:, feet] < 1.0).all(dim=1)
        c_calf = (force[:, calf] > 1.0).any(dim=1)
        c_thigh = (force[:, thigh] > 1.0).any(dim=1)
        dist = torch.norm(e.command_manager.get_command("base_pose")[:, :2], dim=1)
        moving = (e.episode_length_buf > 50) & (dist > up_dist)
        w = counted.double()
        wm = (counted & moving).double()
        sums["valid"] += w
        sums["air"] += w * air
        sums["calf"] += w * c_calf
        sums["thigh"] += w * c_thigh
        sums["moving"] += wm
        sums["air_moving"] += wm * air
        sums["calf_moving"] += wm * c_calf
        sums["thigh_moving"] += wm * c_thigh
        # the reward terms were computed before the reset, so these include the last step of every episode
        wa = in_window.double()
        sums["all"] += wa
        sums["leap_pen"] += wa * (raw("undesired_leaping") > 0)
        sums["nonfoot_pen"] += wa * (raw("undesired_non_foot_contacts") > 0)
        sums["jlim"] += wa * (raw("joint_pos_limits") > 0)
        sums["selfcol"] += wa * ((raw("undesired_self_col_front") + raw("undesired_self_col_rear")) > 0)
        jl = raw("joint_pos_limits")
        jlim_max = torch.where(in_window, torch.maximum(jlim_max, jl), jlim_max)
        # REQ212: close the episode records of the robots whose episode ended in this step (before ep_done counts it)
        with torch.inference_mode():
            g1 = rng_state()
            ids = dones.nonzero(as_tuple=False).flatten()
            if len(ids):
                lu = a_used[ids].clamp(max=K_)
                valid = torch.arange(K_, device=dev).unsqueeze(0) < lu.unsqueeze(1)  # slots 0 .. min(used, K) - 1 hold this episode
                lrx = torch.where(valid, ring_rx[ids], torch.zeros_like(ring_rx[ids]))
                labove = torch.stack([(fpc.above(ring_rx[ids])[..., j] & valid).sum(1) for j in range(NTH)], -1)
                lfront = (ring_front[ids] * valid.unsqueeze(-1).long()).sum(1)
                lwin = torch.zeros(len(ids), NOX, dtype=torch.long, device=dev)
                lwin.scatter_add_(1, ring_ox[ids], valid.long())
                scal = torch.stack([ids.double(), ep_done[ids].double(), a_first[ids].double(), torch.full((len(ids),), float(step), device=dev, dtype=torch.float64),
                                    a_steps[ids].double(), a_used[ids].double(), a_sum[ids, 0], a_sum[ids, 1]]
                                   + [a_above[ids, j].double() for j in range(NTH)] + [a_front[ids, 0].double(), a_front[ids, 1].double(), lu.double(),
                                   lrx.sum(1), (lrx * lrx).sum(1)] + [labove[:, j].double() for j in range(NTH)] + [lfront[:, 0].double(), lfront[:, 1].double()], -1)  # fmt: skip
                ep_records.append(torch.cat([scal, a_win[ids].double(), lwin.double()], -1).cpu())
                a_first[ids] = step + 1
                for t_ in (a_steps, a_used, a_above, a_front, a_win):
                    t_[ids] = 0
                a_sum[ids] = 0.0
            ep_step = torch.where(dones, torch.zeros_like(ep_step), ep_step + 1)
            assert rng_equal(g1, rng_state()), "closing the episode records changed a random number generator"
        ep_done += dones.long()
        step += 1
        if step % 800 == 0:
            P(f"step {step}/{max_steps}  {(time.time() - t0) / step:.3f} s/step  envs with all episodes {int((ep_done >= need).sum())}/{n}")
    # ---- REQ430 D-2: the recording ends here (the evaluator's own tables are not made)
    assert torch.equal(terrain.terrain_levels, lv0), "a level changed during the recording"
    end_ = RH.finish({"det": det_now, "complete": RH.episodes_done(args.rec_episodes), "max_steps": max_steps, "levels_frozen": True,
                      "rec_levels": [int(x) for x in lv0[rec_ids].tolist()], "rec_types": [int(x) for x in env_type[rec_ids].tolist()]})
    P(f"REC_DONE mode {end_['mode']} steps {end_['steps']} calls {end_['calls']} parts {end_['parts']} complete {end_['complete']} "
      f"fingerprint {end_['fingerprint'][:16]} wall {end_['wall_s']:.0f} s")
    sys.stdout.flush()
    os._exit(0 if end_["complete"] else 3)
    cs.STATE["record"] = False
    assert torch.equal(terrain.terrain_levels, lv0), "a level changed during the evaluation"
    P(f"steps {step}  wrapper calls {cs.STATE['calls']}  envs short of {need} episodes: {int((ep_done < need).sum())}")

    if args.smoke:  # REQ359: no tallies, no output file
        P(f"SMOKE_END steps {step} wall {time.time() - t0:.1f} s  {(time.time() - t0) / max(step, 1):.3f} s/step")
        sys.stdout.flush()
        env.close()
        os._exit(0)
    assert cs.STATE["rows"], "evaluation incomplete: no episode ended (raise --max_steps)"
    R = torch.cat(cs.STATE["rows"])
    rstep = torch.cat([torch.full((len(r),), s, dtype=torch.long) for r, s in zip(cs.STATE["rows"], row_step)])
    # envs that fail fast keep resetting until the slowest env is done: keep the first `need` played episodes per env
    c_ = {k: i for i, k in enumerate(cs.FIELDS)}
    was_played = R[:, c_["played"]] > 0
    env_of = R[:, c_["env"]].long()
    order = torch.argsort(env_of, stable=True)  # chronological inside every env
    first = torch.searchsorted(env_of[order], torch.arange(n))
    seen = torch.cumsum(was_played[order].long(), dim=0)
    before_env = torch.cat([torch.zeros(1, dtype=torch.long), seen])[first]  # played rows before each env's first row
    rank = seen - before_env[env_of[order]]  # 1 for an env's first played row
    keep = torch.zeros(len(R), dtype=torch.bool)
    keep[order] = was_played[order] & (rank <= need)
    n_all = len(R)
    # REQ212: the played index of every row (0 for an env's first played row), before the rows are cut
    rank_all = torch.full((n_all,), -1, dtype=torch.long)
    rank_all[order] = torch.where(was_played[order], rank - 1, torch.full_like(rank, -1))
    R, rstep = R[keep], rstep[keep]
    kept_rank = rank_all[keep]
    P(f"rows kept {len(R)} of {n_all} recorded resets (first {need} played episodes per env)")

    # ---- REQ212: link every kept row to the episode record of the same robot and played index
    Erec = torch.cat(ep_records) if ep_records else torch.zeros(0, len(EP_SCALARS) + 2 * NOX, dtype=torch.float64)
    fi = {k: i for i, k in enumerate(EP_SCALARS)}
    rec_env, rec_k = Erec[:, fi["env"]].long(), Erec[:, fi["k"]].long()
    assert torch.equal(torch.bincount(env_of[was_played], minlength=n), torch.bincount(rec_env, minlength=n)), "played rows and episode ends differ per robot"
    key = list(zip(rec_env.tolist(), rec_k.tolist()))  # (robot, played index): no bound on the played index (212th review P3)
    pos = {kk: i for i, kk in enumerate(key)}
    assert len(pos) == len(key), "two episode records with the same robot and played index"
    want = list(zip(R[:, c_["env"]].long().tolist(), kept_rank.tolist()))
    assert all(w_ in pos for w_ in want), "a kept row without its episode record"
    EP = Erec[torch.tensor([pos[w_] for w_ in want], dtype=torch.long)]
    assert torch.equal(EP[:, fi["env"]].long(), R[:, c_["env"]].long()) and torch.equal(EP[:, fi["k"]].long(), kept_rank), "link"
    # the record's policy steps against the row's ep_len: saved, not asserted, so that a mismatch can be looked at (the queue refuses it)
    len_mismatch = int((EP[:, fi["steps"]] != R[:, c_["ep_len"]].double()).sum())
    # bookkeeping of the added tallies
    cntk = (EP[:, fi["k"]] >= 1) & (EP[:, fi["k"]] < need)
    assert int(RXH_A.sum()) == int(EP[cntk, fi["used"]].sum()), "class histograms vs the counted episodes' used steps"
    assert torch.equal(RXH_A.sum(-1), WINC_A.sum(-1)) and torch.equal(RSC_A[..., 0], RXH_A.sum(-1).double()), "class tallies"
    for j, t_ in enumerate(fpc.THRESHOLDS):
        i_ = fpc.first_bin_at_or_above(t_)
        assert bool((RXC_A[..., j] <= RXH_A[..., i_:].sum(-1)).all()) and bool((RXC_A[..., j] >= RXH_A[..., i_ + 1:].sum(-1)).all()), f"count above {t_}"
    assert bool((EP[:, fi["used"]] <= EP[:, fi["steps"]]).all()) and bool((EP[:, fi["last_used"]] <= EP[:, fi["used"]]).all()), "used steps"
    assert bool((EP[:, fi["front_in"]] <= EP[:, fi["front_all"]]).all()) and bool((EP[:, fi["last_front_in"]] <= EP[:, fi["last_front_all"]]).all()), "front feet"
    win0 = len(EP_SCALARS)
    assert torch.equal(EP[:, win0:win0 + NOX].sum(1), EP[:, fi["used"]]) and torch.equal(EP[:, win0 + NOX:].sum(1), EP[:, fi["last_used"]]), "window histograms"
    P(f"episode records linked {len(EP)} (of {len(Erec)} ended); policy steps differing from the rows' ep_len {len_mismatch}; gaze of the counted "
      f"episodes: used steps {int(RXH_A.sum())}  mean r_x {float(RSC_A[..., 1].sum() / RSC_A[..., 0].sum().clamp(min=1)):.4f}  rng checks {rng_checks}")
    gaze_extra = {
        "EP": EP, "ep_fields": list(EP_SCALARS) + [f"win_{i}" for i in range(NOX)] + [f"last_win_{i}" for i in range(NOX)],
        "RXH_A": RXH_A.cpu(), "RXC_A": RXC_A.cpu(), "RSC_A": RSC_A.cpu(), "WINC_A": WINC_A.cpu(), "FIN_A": FIN_A.cpu(),
        "gaze_warmup": args.gaze_warmup, "last_k": K_, "classes": list(fl.CLASSES), "rx_edges": fpc.EDGES.clone(), "rx_thresholds": list(fpc.THRESHOLDS),
        "rng_checks": rng_checks, "ep_len_mismatch": len_mismatch, "roi_margin": float(actor.roi_margin), "tool": "eval_student (REQ428)",
        "tool_md5": {"eval_student.py": file_md5(os.path.abspath(__file__)), "fpc_lib.py": file_md5(fpc.__file__)},
    }  # fmt: skip
    torch.save(
        {
            "fields": cs.FIELDS, "rows": R, "row_step": rstep, "env_col": env_col.cpu(), "env_type": env_type.cpu(), "level": lv0.cpu(),
            "type_names": type_names, "col_names": names, "term_names": term_names, "step_sums": {k: v.cpu() for k, v in sums.items()},
            "episodes": args.episodes, "steps": step, "seed": env_cfg.seed, "sample": bool(args.sample), "task": args.task,
            "checkpoint": args.checkpoint, "completed_updates": state.get("completed_updates"), "actor_sha": actor_sha.hexdigest(),
            "digests": digests, "code": code_id(), "num_envs": n, "num_levels": NR, "jlim_max": jlim_max.cpu(), "crop": crop,
            "ramps": {"cone": float(cmd_cfg.cone_angle_deg), "yaw": float(yaw[1]), "map_noise": float(noise[-1])},
            **gaze_extra,
            "student428": S428,
        },
        args.out,
    )  # fmt: skip

    # ---- REQ212: fixed-input check after the evaluation (it cannot change the results): one stored observation, twice
    with torch.inference_mode():
        actor._last_gaze_r = None
        a1 = policy(obs_check)
        g1_ = actor._last_gaze_r.detach().clone()
        s0 = rng_state()
        _ = fpc.rx_bin(g1_[:, 0], edges_dev), fpc.above(g1_[:, 0]), fl.crop_start(g1_, CX, CY)
        same_rng = rng_equal(s0, rng_state())
        actor._last_gaze_r = None
        a2 = policy(obs_check)
        g2_ = actor._last_gaze_r.detach().clone()
    fixed_ok = bool(torch.equal(a1, a2) and torch.equal(g1_, g2_) and same_rng)
    P(f"fixed-input check: same action {bool(torch.equal(a1, a2))}  same gaze {bool(torch.equal(g1_, g2_))}  generators untouched {same_rng}")
    assert fixed_ok, "fixed-input check failed"

    # quick look (the real tables come from eval_compare.py)
    c = {k: i for i, k in enumerate(cs.FIELDS)}
    played = R[:, c["played"]] > 0
    succ = R[played, c["success"]].float().mean().item()
    P(f"rows {len(R)} (played {int(played.sum())}); success over all recorded episodes {succ:.3f}; saved {args.out}")
    P("DONE")
    sys.stdout.flush()
    os._exit(0)  # app.close() hangs after this script


if __name__ == "__main__":
    main()
