"""REQ430 D-2 stage A: the sim test-vector recorder hooks (deploy_go2/DESIGN_sim_vectors_v2.md).

The hooks WRAP methods of the training copy (they call the original first and only copy values afterwards): nothing here draws a random number,
writes a tensor the simulation uses, or calls a model again. They record, for a fixed set of robots (24: 12 terrains x 2 levels):
  frame   (every map fusion call that includes a recorded robot): episode index, call index, env step counter, episode length, the pose the runtime
          used (x, y, z, yaw) and the base quaternion, per sensor the raw world hit points (inf for invalid rays), the validity mask and the
          sensor stamp; the local grid the runtime built (66 x 48); the mapper output (mean, logvar) of that robot
  mapreset / recenter (map events of a recorded robot): origin, prior, the pose of the event
  policy  (every policy step, BEFORE env.step): the three student inputs exactly as the policy got them (prop history 20 x 42, goal command 4,
          policy map 29 x 13 x 4), the actor's raw action, its gaze (r) and integer window start, the robot state the observation describes
          (root position / quaternion, body angular velocity, joint positions / velocities, default joint positions / velocities), the last
          submitted action (action_manager.action), the goal (world position / heading), the command (pos_b, yaw_b), the far-goal yaw cache
  physics (every apply_actions call = physics substep): the target set on the robot (joint_pos_target) and the delay of the episode
  action  (process_actions): raw and processed (clipped +-100) targets;  actreset (term.reset): the delay drawn and the initial history
  done    (after env.step): done flags and the termination terms of the recorded robots
The episode index of a robot = the action-term resets seen for it since install (the explicit reset gives 0); a reset happens inside env.step
before the observation, so frames / policy rows after it carry the new index and the done row the ended one (ep - done).
mode "off": the hooks are installed the same way but only a per-step fingerprint (sha256 of the recorded robots' action and root pose) is kept,
for the off / off and off / on comparisons. Buffers are flushed to part files every FLUSH policy steps.
8th version (Codex 430_29 / 430_30): one more record, the rest unchanged -
  acq     (every write of a map sensor's buffer for a recorded robot: the runtime's sensors' _update_buffers_impl, wrapped on the instance, which
          Isaac Lab's _update_outdated_buffers calls with the outdated ids before it copies _timestamp into _timestamp_last_update): call index,
          env step counter, sensor index, env ids, episode index, episode length, the sensor time of the write (_timestamp = the stamp the scan
          gets), the robot / sensor update number since install (1, 2, ...), sha256 of the scan as written (scan_hash: the float32 bytes of the
          rays, inf for invalid, then the bytes of the validity mask) and its valid count. The replay ties every frame's rays to the scan acquired
          at the frame's time with it. The wrapper calls the original first, reads ._data (not .data, which would refresh again) and draws nothing."""
import hashlib
import os
import time

import torch

R = {}
FLUSH = 200


def _sel(ids):
    """positions inside the call's id list that are recorded, and those env ids"""
    ids = torch.as_tensor(ids, device=R["dev"]).flatten()
    m = R["is_rec"][ids]
    return m.nonzero(as_tuple=False).flatten(), ids[m]


def _c(t):
    return t.detach().clone().cpu()


def install(e, rec_ids, out_dir, mode, meta):
    """e: the unwrapped env (after the runner and the runtime exist, before the explicit reset); rec_ids: long tensor of env ids"""
    assert mode in ("on", "off"), mode
    rt = getattr(e, "go2_neural_map", None)
    assert rt is not None, "the neural map runtime is made at the first observation (the wrapper's reset) - install after it"
    assert getattr(rt, "frame_override", None) is None, "a frame override skips the mapper call the frames are taken from"
    dev = e.device
    is_rec = torch.zeros(e.num_envs, dtype=torch.bool, device=dev)
    is_rec[rec_ids] = True
    R.clear()
    R.update(e=e, rt=rt, dev=dev, mode=mode, out=out_dir, is_rec=is_rec, rec=rec_ids.clone().to(dev), ep=torch.full((e.num_envs,), -1, dtype=torch.long, device=dev),
             call=0, part=0, steps=0, fp=hashlib.sha256(), fp_rows=[], pending=None, t0=time.time(), parts=[],
             buf={k: [] for k in ("frame", "fexp", "mapreset", "recenter", "policy", "physics", "action", "actreset", "done", "acq")})
    os.makedirs(out_dir, exist_ok=False)
    torch.save(meta, os.path.join(out_dir, "meta.pt"))
    term = e.action_manager._terms["joint_pos"]
    robot = rt.robot
    R["term"], R["robot"] = term, robot
    # ---- action term: reset (episode index), process_actions, apply_actions
    o_reset, o_proc, o_apply = term.reset, term.process_actions, term.apply_actions

    def reset(env_ids=None):
        o_reset(env_ids)
        all_ = torch.arange(e.num_envs, device=dev)
        ids = all_ if env_ids is None else all_[env_ids] if isinstance(env_ids, slice) else torch.as_tensor(env_ids, device=dev).flatten()   # 430_14
        pos, eids = _sel(ids)
        if eids.numel():
            R["ep"][eids] += 1
            if mode == "on":
                R["buf"]["actreset"].append({"counter": int(e.common_step_counter), "env": _c(eids), "ep": _c(R["ep"][eids]), "delay": _c(term.delay_steps[eids]),
                                             "history": _c(term.action_history[eids]), "processed": _c(term._processed_actions[eids])})

    def process_actions(actions):
        o_proc(actions)
        if mode == "on":
            ids = R["rec"]
            R["buf"]["action"].append({"counter": int(e.common_step_counter), "ep": _c(R["ep"][ids]), "raw": _c(term.raw_actions[ids]),
                                       "processed": _c(term._processed_actions[ids]), "delay": _c(term.delay_steps[ids])})

    def apply_actions():
        o_apply()
        if mode == "on":
            ids = R["rec"]
            R["buf"]["physics"].append({"counter": int(e.common_step_counter), "target": _c(robot.data.joint_pos_target[ids]), "delay": _c(term.delay_steps[ids])})

    term.reset, term.process_actions, term.apply_actions = reset, process_actions, apply_actions
    # ---- map runtime: local grid (points, pose, grid), mapper output, map reset / recenter, fusion call count
    o_lg, o_mapper, m = rt.local_grid, rt.mapper, rt.map
    o_mreset, o_recenter, o_update = m.reset, m.recenter, m.update

    def local_grid(env_ids):
        grid = o_lg(env_ids)
        R["pending"] = None
        if mode == "on":
            pos, eids = _sel(env_ids)
            if eids.numel():   # the recorded robots this call must give a frame of - kept apart from the frames (Codex 430_24 P1-4)
                R["buf"]["fexp"].append({"call": R["call"], "counter": int(e.common_step_counter), "env": _c(eids)})
            if eids.numel():
                x, y, z, yaw = rt.pose()
                row = {"call": R["call"], "counter": int(e.common_step_counter), "env": _c(eids), "ep": _c(R["ep"][eids]), "ep_len": _c(e.episode_length_buf[eids]),
                       "pose": _c(torch.stack([x[eids], y[eids], z[eids], yaw[eids]], -1)), "quat": _c(robot.data.root_quat_w[eids]), "grid": _c(grid[pos]),
                       "pos": pos}
                for k, s in enumerate(rt.sensors):   # .data was refreshed by the runtime just before: reading it again draws nothing
                    row[f"pts{k}"] = _c(s.data.ray_hits_w[eids])
                    row[f"valid{k}"] = _c(s.valid[eids])
                    row[f"stamp{k}"] = _c(s._timestamp_last_update[eids])
                    for nm in ("pos_w", "quat_w"):   # the sensor origin of these rays (Codex 430_14 P3)
                        v_ = getattr(s.data, nm, None)
                        if v_ is not None:
                            row[f"{nm}{k}"] = _c(v_[eids])
                R["pending"] = row
        return grid

    class _MapperRec:
        def __init__(self, inner):
            self.inner = inner

        def __call__(self, x):
            mean, logvar = self.inner(x)
            row = R.get("pending")
            if row is not None:
                pos = row.pop("pos")
                row["mean"], row["logvar"] = _c(mean[pos].squeeze(1).float()), _c(logvar[pos].squeeze(1).float())
                R["buf"]["frame"].append(row)
                R["pending"] = None
            return mean, logvar

        def __getattr__(self, name):
            return getattr(self.inner, name)

    def map_reset(env_ids, x, y, z):
        out = o_mreset(env_ids, x, y, z)
        if mode == "on":
            pos, eids = _sel(env_ids)
            if eids.numel():
                R["buf"]["mapreset"].append({"call": R["call"], "counter": int(e.common_step_counter), "env": _c(eids), "ep": _c(R["ep"][eids]),
                                             "xyz": _c(torch.stack([x[pos], y[pos], z[pos]], -1)), "prior": _c(m.prior[eids]), "origin": _c(m.origin[eids])})
        return out

    def recenter(x, y, z):
        ids = R["rec"]
        before = m.origin[ids].clone()
        out = o_recenter(x, y, z)
        if mode == "on":
            moved = (m.origin[ids] != before).any(-1)
            if bool(moved.any()):
                eids = ids[moved]
                R["buf"]["recenter"].append({"call": R["call"], "counter": int(e.common_step_counter), "env": _c(eids), "ep": _c(R["ep"][eids]),
                                             "origin_before": _c(before[moved]), "origin": _c(m.origin[eids]), "prior": _c(m.prior[eids]),
                                             "xyz": _c(torch.stack([x[eids], y[eids], z[eids]], -1))})
        return out

    def update(*a, **k):
        out = o_update(*a, **k)
        R["call"] += 1
        return out

    rt.local_grid, rt.mapper = local_grid, _MapperRec(o_mapper)
    m.reset, m.recenter, m.update = map_reset, recenter, update
    # ---- 8th version (Codex 430_30 P1-2): the scans where the sensor buffers are written (sensor_base._update_outdated_buffers ->
    # _update_buffers_impl(outdated ids) -> the stamp), for the recorded robots among the ids written
    R["acq_n"] = torch.zeros(len(rt.sensors), e.num_envs, dtype=torch.long, device=dev)
    for k_s, s_ in enumerate(rt.sensors):
        def update_buffers_impl(env_ids, k=k_s, s=s_, o=s_._update_buffers_impl):
            out = o(env_ids)
            if mode == "on":
                all_ = torch.arange(e.num_envs, device=dev)
                ids = all_[env_ids] if isinstance(env_ids, slice) else torch.as_tensor(env_ids, device=dev).flatten()
                pos, eids = _sel(ids)
                if eids.numel():
                    R["acq_n"][k, eids] += 1
                    pts, val = _c(s._data.ray_hits_w[eids]), _c(s.valid[eids])   # ._data: reading .data here would refresh (and call this) again
                    R["buf"]["acq"].append({"call": R["call"], "counter": int(e.common_step_counter), "sensor": k, "env": _c(eids), "ep": _c(R["ep"][eids]),
                                            "ep_len": _c(e.episode_length_buf[eids]), "ts": _c(s._timestamp[eids]), "n": _c(R["acq_n"][k, eids]),
                                            "h": scan_hash(pts, val), "nvalid": val.sum(-1)})
            return out
        s_._update_buffers_impl = update_buffers_impl
    R["ct"] = e.command_manager.get_term("base_pose")


def scan_hash(pts, valid):
    """8th version: sha256 of each robot's scan as the buffer holds it - the float32 bytes of its rays (m, R, 3; inf for invalid, C order) followed by
    the bytes of its validity mask (m, R; bool), CPU tensors -> (m, 32) uint8 (the replay recomputes it from a frame's pts / valid)"""
    out = torch.zeros(pts.shape[0], 32, dtype=torch.uint8)
    for j in range(pts.shape[0]):
        h = hashlib.sha256(pts[j].contiguous().numpy().tobytes() + valid[j].contiguous().numpy().tobytes()).digest()
        out[j] = torch.tensor(list(h), dtype=torch.uint8)
    return out


def policy_step(step, obs, act, r, ox, oy):
    """BEFORE env.step: the inputs the policy got, its output, and the state the observation describes"""
    e, ids, robot = R["e"], R["rec"], R["robot"]
    a_ = act[ids]
    rp = robot.data.root_pos_w[ids]
    step_h = hashlib.sha256()   # per step (430_14 P2): action, pose, orientation and the three inputs of the recorded robots; the first differing step
    for t_ in (a_, rp, robot.data.root_quat_w[ids], obs["student_prop_hist"][ids], obs["student_cmds"][ids], obs["neural_map"][ids]):
        step_h.update(_c(t_).float().numpy().tobytes())
    R["fp"].update(step_h.digest())
    R["fp_rows"].append(step_h.hexdigest()[:16])
    R["steps"] += 1
    if R["mode"] == "on":
        cache = getattr(e, "_go2_far_goal_yaw", None)
        R["buf"]["policy"].append({
            "step": step, "counter": int(e.common_step_counter), "ep": _c(R["ep"][ids]), "ep_len": _c(e.episode_length_buf[ids]), "sst": _sst(ids),
            "prop": _c(obs["student_prop_hist"][ids]), "cmd": _c(obs["student_cmds"][ids]), "nmap": _c(obs["neural_map"][ids]),
            "act": _c(a_), "gaze_r": _c(r[ids]), "win": _c(torch.stack([ox[ids], oy[ids]], -1)),
            "root_pos": _c(rp), "root_quat": _c(robot.data.root_quat_w[ids]), "ang_vel_b": _c(robot.data.root_ang_vel_b[ids]),
            "q": _c(robot.data.joint_pos[ids]), "dq": _c(robot.data.joint_vel[ids]), "q0": _c(robot.data.default_joint_pos[ids]),
            "dq0": _c(robot.data.default_joint_vel[ids]), "last_action": _c(e.action_manager.action[ids]),
            "goal_w": _c(R["ct"].pos_command_w[ids]), "goal_head_w": _c(R["ct"].heading_command_w[ids]),
            "cmd_b": _c(e.command_manager.get_command("base_pose")[ids]),
            "far_key": None if cache is None else int(cache[0]), "far_yaw": None if cache is None else _c(cache[1][ids])})


def _sst(ids):
    """the map sensors' last-update stamps of the recorded robots (an attribute read: it refreshes nothing) - the replay rebuilds from them which
    robots the runtime fused at each step, apart from the frames and their expected list (Codex 430_25 P1-4)"""
    return _c(torch.stack([s._timestamp_last_update[ids] for s in R["rt"].sensors], -1))


def after_step(step, dones):
    e, ids = R["e"], R["rec"]
    d = dones[ids].bool()
    tm = e.termination_manager
    bits = torch.stack([tm.get_term(nm)[ids].bool() for nm in tm.active_terms], -1)
    R["fp"].update(_c(d).numpy().tobytes() + _c(bits).numpy().tobytes())   # the done flags / bits join the fingerprint in both modes
    if R["mode"] == "on":
        R["buf"]["done"].append({"step": step, "counter": int(e.common_step_counter), "done": _c(d), "ep_ended": _c(R["ep"][ids] - d.long()),
                                 "bits": _c(bits), "time_outs": _c(tm.time_outs[ids]), "sst": _sst(ids)})
    if R["steps"] % FLUSH == 0:
        flush()


def flush():
    if R["mode"] == "on" and any(R["buf"].values()):
        p = os.path.join(R["out"], f"part_{R['part']:04d}.pt")
        torch.save(R["buf"], p)
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        pol = R["buf"]["policy"]
        R["parts"].append({"file": os.path.basename(p), "sha256": h, "rows": {k: len(v) for k, v in R["buf"].items()},
                           "steps": [pol[0]["step"], pol[-1]["step"]] if pol else None})   # 430_14 P1-3 / range and counts per part
        R["part"] += 1
        R["buf"] = {k: [] for k in R["buf"]}


def episodes_done(need):
    """True when every recorded robot has finished `need` episodes (its episode index reached need)"""
    return bool((R["ep"][R["rec"]] >= need).all())


def finish(extra):
    flush()
    out = {"mode": R["mode"], "steps": R["steps"], "calls": R["call"], "parts": R["part"], "part_list": R["parts"], "fingerprint": R["fp"].hexdigest(),
           "fp_rows": R["fp_rows"],
           "episodes": _c(R["ep"][R["rec"]]), "wall_s": time.time() - R["t0"], **extra}
    torch.save(out, os.path.join(R["out"], "end.pt"))
    return out
