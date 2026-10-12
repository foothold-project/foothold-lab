# Full per-step recording for q_eval.py --full_record (reads simulator buffers only; the rollout is unchanged).
# Representative episodes per (family, cell), chosen by a fixed rule after q_post:
#   first success (lowest episode index that passes the current cell rule), first failure (lowest index that fails),
#   median (episode whose MAE sum vx+vy+wz is closest to the cell median, ties -> lower index). Duplicates merged.
# Output: out/full/<tag>/<family>_<cell>_ep<NNN>.csv, out/full/<tag>/episodes_summary.csv, out/full/<tag>/SCHEMA.md
import csv
import os

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
FEET = ["FL_foot", "FR_foot", "RL_foot", "RR_foot"]
CONTACT_N = 1.0


class Recorder:
    def __init__(self, u, robot, T, N, ground_z_fn):
        self.u, self.robot, self.ground_z = u, robot, ground_z_fn
        jt = u.action_manager.get_term("joint_pos")
        self.jt = jt
        jids = jt._joint_ids
        self.jids = list(range(robot.num_joints)) if isinstance(jids, slice) else list(jids)
        self.jnames = list(jt._joint_names)
        self.fb = [robot.find_bodies(n)[0][0] for n in FEET]
        self.cs = u.scene["contact_forces"]
        self.cf = [self.cs.find_bodies(n)[0][0] for n in FEET]
        self.S = np.full((T + 1, N, 86), np.nan, np.float32)
        self.A = np.full((T + 1, N, 24), np.nan, np.float32)
        act = list(robot.actuators.values())[0]
        self.kp = act.stiffness[:, self.jids].cpu().numpy()
        self.kd = act.damping[:, self.jids].cpu().numpy()
        self.mass = robot.root_physx_view.get_masses().sum(dim=1).cpu().numpy()
        self.offset = jt._offset.cpu().numpy()
        self.scale = float(jt._scale) if not torch.is_tensor(jt._scale) else jt._scale.cpu().numpy()

    def state(self, k):
        d = self.robot.data
        f = self.cs.data.net_forces_w[:, self.cf]  # (N,4,3) world, last physics substep
        gz = self.ground_z()
        parts = [d.root_pos_w, d.root_quat_w, d.root_lin_vel_w, d.root_lin_vel_b, d.root_ang_vel_w, d.root_ang_vel_b,
                 d.projected_gravity_b, gz[:, None], (d.root_pos_w[:, 2] - gz)[:, None],
                 d.joint_pos[:, self.jids], d.joint_vel[:, self.jids], d.applied_torque[:, self.jids],
                 d.body_pos_w[:, self.fb].reshape(-1, 12), f[..., 2], f[..., :2].norm(dim=-1), (f.norm(dim=-1) > CONTACT_N).float(),
                 self._flag("reset_terminated"), self._flag("reset_time_outs")]
        self.S[k] = torch.cat([p.float() for p in parts], dim=1).cpu().numpy()

    def _flag(self, name):
        v = getattr(self.u, name, None)  # created by the first env.step
        return (torch.zeros(self.u.num_envs, device=self.u.device) if v is None else v.float())[:, None]

    def action_raw(self, k, act):
        self.A[k, :, :12] = act.float().cpu().numpy()

    def action_processed(self, k):
        self.A[k, :, 12:] = self.jt.processed_actions.float().cpu().numpy()

    def columns(self):
        c = ["base_x_m", "base_y_m", "base_z_m", "quat_w", "quat_x", "quat_y", "quat_z",
             "linvel_world_x_mps", "linvel_world_y_mps", "linvel_world_z_mps", "linvel_body_x_mps", "linvel_body_y_mps", "linvel_body_z_mps",
             "angvel_world_x_radps", "angvel_world_y_radps", "angvel_world_z_radps", "angvel_body_x_radps", "angvel_body_y_radps", "angvel_body_z_radps",
             "gravity_body_x", "gravity_body_y", "gravity_body_z", "ground_z_m", "base_height_above_ground_m"]
        c += [f"q_{j}_rad" for j in self.jnames] + [f"dq_{j}_radps" for j in self.jnames] + [f"tau_{j}_Nm" for j in self.jnames]
        for ft in FEET:
            c += [f"{ft}_x_m", f"{ft}_y_m", f"{ft}_z_m"]
        c += [f"{ft}_force_vertical_N" for ft in FEET] + [f"{ft}_normal_force_horizontal_N" for ft in FEET] + [f"{ft}_contact" for ft in FEET]
        c += ["terminated", "time_out"]
        a = [f"action_{j}" for j in self.jnames] + [f"target_{j}_rad" for j in self.jnames]
        return c, a


def _rule(cell):
    return "q2_pass" if cell == "stop03" else "q1_pass"


def _tf(v):
    return str(v) in ("True", "true", "1")


def select(rows):
    """rows of one (family, cell) sorted by episode -> list of (episode, env, labels)."""
    rows = sorted(rows, key=lambda r: int(r["episode"]))
    k = _rule(rows[0]["cell"])
    picks = {}
    succ = [r for r in rows if _tf(r[k])]
    fail = [r for r in rows if not _tf(r[k])]
    if succ:
        picks.setdefault(int(succ[0]["episode"]), [succ[0], []])[1].append("first_success")
    if fail:
        picks.setdefault(int(fail[0]["episode"]), [fail[0], []])[1].append("first_failure")
    m = np.array([sum(float(r[x]) if r[x] not in ("", "nan") else np.nan for x in ("mae_vx", "mae_vy", "mae_wz")) for r in rows])
    if np.isfinite(m).any():
        med = np.nanmedian(m)
        i = int(np.nanargmin(np.abs(m - med)))
        picks.setdefault(int(rows[i]["episode"]), [rows[i], []])[1].append("median_mae")
    return [(ep, int(v[0]["env"]), v[1], v[0]) for ep, v in sorted(picks.items())]


SCHEMA = """# Full record schema

One CSV per representative episode, one row per policy sample (50 Hz, dt 0.02 s). Row j is the state after j policy
steps (row 0 = after the seeded reset). Rows end at the cell duration or one row before the env was reset by a
termination (the post-reset state is not written). Columns:

- `t_s` (s), `step`
- `cmd_vx_mps`, `cmd_vy_mps`, `cmd_wz_radps`: velocity command in force for this state (body frame; what the policy saw)
- base: `base_{x,y,z}_m` world position of the base link; `quat_{w,x,y,z}` world orientation (w first);
  `linvel_world_*`, `linvel_body_*` (m/s, centre of mass), `angvel_world_*`, `angvel_body_*` (rad/s);
  `gravity_body_*` unit gravity vector in the body frame (standing upright: z = -1)
- `ground_z_m`: mean height of the finite hits of the small foot-print scanner (0.4 x 0.3 m around the base);
  `base_height_above_ground_m` = base z - ground_z
- joints, in the action term order used in training (`JOINT_NAMES`: FL, FR, RL, RR x hip, thigh, calf, as named in the columns):
  `q_*_rad` angle, `dq_*_radps` velocity, `tau_*_Nm` applied torque after the actuator model (positive = positive joint direction)
- `action_*`: raw policy output computed from this row's observation (dimensionless; NaN on the last row);
  `target_*_rad`: joint position target of that action = motor zero offset (default pose + randomized offset) + 0.25 x action.
  The actuator applies it with the randomized delay of 0..4 physics steps (5 ms each).
- feet `FL_foot, FR_foot, RL_foot, RR_foot`: `*_{x,y,z}_m` world position of the foot link origin (sphere centre within 2 mm);
  `*_force_vertical_N` world z component of the net NORMAL contact force on the foot (ground pushing up = positive);
  `*_normal_force_horizontal_N` horizontal magnitude |(Fx, Fy)| of the same net NORMAL force (not zero on slopes, risers
  and edges; on flat ground about 0); `*_contact` = 1 when |normal force| > 1 N. Forces are from the last 5 ms physics substep.
  Source: Isaac Lab `ContactSensor.data.net_forces_w`, which holds the sum of NORMAL contact forces only. Friction
  (tangential) forces are NOT recorded: they need `track_friction_forces=True` with filter prims, which these runs did not use.
  (Files written before 2026-10-12 14:10 named this column `*_force_tangential_N`; the header was renamed, values unchanged.)
- `terminated` (illegal base contact at this step), `time_out`

`episodes_summary.csv`: one row per written file with the selection labels, the q_post result of the episode
(current and span pass, survival, fall reason and time, MAE), the env index, the number of rows, and per-episode
constants (mean Kp, mean Kd of the randomized actuator gains, total robot mass).
"""


def write_representatives(out_dir, tag, R, meta, cmd_hist, term, cells, families, dt):
    eps = list(csv.DictReader(open(os.path.join(out_dir, "episodes.csv"), encoding="utf-8")))
    dest = os.path.join(HERE, "out", "full", tag)
    os.makedirs(dest, exist_ok=True)
    open(os.path.join(dest, "SCHEMA.md"), "w", encoding="utf-8").write(SCHEMA)
    scol, acol = R.columns()
    cols = ["t_s", "step", "cmd_vx_mps", "cmd_vy_mps", "cmd_wz_radps"] + scol + acol
    dur = {c["name"]: c["duration_s"] for c in cells}
    groups = {}
    for r in eps:
        groups.setdefault((r["family"], r["cell"]), []).append(r)
    summ, nbytes = [], 0
    T = term.shape[0] - 1
    for (fam, cell), rows in groups.items():
        for ep, e, labels, r in select(rows):
            J = int(round(dur[cell] / dt))
            tt = np.flatnonzero(term[1:, e])
            first_term = int(tt[0]) + 1 if tt.size else None
            end = min(J, first_term - 1) if first_term else J
            j = np.arange(end + 1)
            M = np.concatenate([np.stack([j * dt, j], 1), cmd_hist[j, e], R.S[j, e], R.A[j, e]], axis=1)
            fn = f"{fam}_{cell}_ep{ep:03d}.csv"
            path = os.path.join(dest, fn)
            np.savetxt(path, M, delimiter=",", header=",".join(cols), comments="", fmt="%.7g")
            nbytes += os.path.getsize(path)
            summ.append({"file": fn, "family": fam, "cell": cell, "episode": ep, "env": e, "labels": "+".join(labels),
                         "pass_current": r[_rule(cell)], "pass_span": r["span_" + _rule(cell)], "survived": r["survived"],
                         "fall_reason": r["fall_reason"], "fall_t": r["fall_t"], "mae_vx": r["mae_vx"], "mae_vy": r["mae_vy"], "mae_wz": r["mae_wz"],
                         "rows": int(end + 1), "terminated_at_step": first_term, "kp_mean": float(R.kp[e].mean()), "kd_mean": float(R.kd[e].mean()),
                         "robot_mass_kg": float(R.mass[e]), "tag": tag, "checkpoint": os.path.basename(meta["args"].get("checkpoint") or ""),
                         "obs_noise": meta["args"].get("obs_noise")})
    with open(os.path.join(dest, "episodes_summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0].keys()))
        w.writeheader()
        for s_ in summ:
            w.writerow(s_)
    np.savez_compressed(os.path.join(dest, "statics.npz"), kp=R.kp, kd=R.kd, mass=R.mass, offset=R.offset, joint_names=np.array(R.jnames))
    return {"dir": dest, "files": len(summ), "bytes": nbytes, "columns": len(cols), "rule": "first success, first failure, median MAE sum per (family, cell)"}
