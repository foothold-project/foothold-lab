"""CPU-only: break each data-dependent HOLD reason of attempt 3 into its sub-conditions."""
import json
import math
import sys
from pathlib import Path

import numpy as np

A3 = Path(__file__).resolve().parents[1] / "s2_step4a3"
sys.path.insert(0, str(A3))
from s2_known_scene_a2 import oracle  # noqa: E402
from s2_connect_check_17v import GRID, CASES  # noqa: E402

RUN = Path(sys.argv[1])
z = np.load(RUN / "out" / "capture.npz", allow_pickle=False)
a = {k: z[k] for k in z.files}
meta = json.loads((RUN / "out" / "meta.json").read_text(encoding="utf-8"))
print("meta keys present:", sorted(meta))

print("\n== stale_packet sub-conditions")
sim = a["sim_step"]; sen = a["sensor_step"]; gen = a["sensor_generation"]
print("sim_step diff all 1:", bool(np.all(np.diff(sim) == 1)), "range", sim[0], sim[-1])
print("sensor_step == sim_step for all env:", bool(np.all(sen == sim[:, None])), "n_bad", int((sen != sim[:, None]).sum()))
print("sensor_step sample row0/row1:", sen[0].tolist(), sen[1].tolist(), "sim", sim[:3].tolist())
d = np.diff(gen, axis=0)
print("generation strictly increasing:", bool(np.all(d > 0)), "min diff", int(d.min()), "n nonpositive", int((d <= 0).sum()))
print("packet ids unique:", len(set(map(str, a["packet_id"]))), "of 256")
e = a["episode_ids"]
print("episode 128>127:", bool(np.all(e[128] > e[127])), "first128 const:", bool(np.all(e[:128] == e[0])), "after const:", bool(np.all(e[129:] == e[128])))
print("episode ids row0/127/128/129:", e[0].tolist(), e[127].tolist(), e[128].tolist(), e[129].tolist())

print("\n== sensor_timestamp")
ts = a["sensor_timestamp"]
dt = np.diff(ts, axis=0)
print("ts min/max", float(ts.min()), float(ts.max()), "diff min", float(dt.min()), "n neg", int((dt < 0).sum()), "n zero", int((dt == 0).sum()))
neg = np.argwhere(dt < 0)
print("first neg idx (step, env):", neg[:6].tolist())

print("\n== fixed_pose (first 16 steps)")
for k in ("root_pos_w", "root_quat_w", "pos_w"):
    dev = np.abs(a[k][:16] - a[k][0]).max()
    print(k, "max dev in first 16:", float(dev))
print("root_pos_w[0] per env:", np.round(a["root_pos_w"][0], 4).tolist())
print("root_pos_w[15] per env:", np.round(a["root_pos_w"][15], 4).tolist())

print("\n== geometry vs oracle")
q = a["root_quat_w"]
yaw = np.arctan2(2 * (q[..., 0] * q[..., 3] + q[..., 1] * q[..., 2]), 1 - 2 * (q[..., 2] ** 2 + q[..., 3] ** 2))
c, s = np.cos(yaw)[..., None], np.sin(yaw)[..., None]
xy = GRID[None, None, :, :]
expected = np.stack((a["pos_w"][..., 0, None] + c * xy[..., 0] - s * xy[..., 1],
                     a["pos_w"][..., 1, None] + s * xy[..., 0] + c * xy[..., 1]), axis=-1)
hits = a["ray_hits_w"]
finite = np.isfinite(hits).all(axis=-1)
oracle_z = np.zeros(finite.shape); oracle_finite = np.ones(finite.shape, dtype=bool); oracle_edge = np.full(finite.shape, np.inf)
for env in range(8):
    kind = ("flat", "obstacles", "gap", "stepping_stones")[env // 2]
    local = expected[:, env] - a["env_origin_w"][:, env, None, :2]
    zz, valid, edge = oracle(kind, local)
    oracle_z[:, env] = zz; oracle_finite[:, env] = valid; oracle_edge[:, env] = edge
expected_edge = oracle_edge <= 0.005
got_edge = a["edge_excluded"].astype(bool)
print("edge expected count", int(expected_edge.sum()), "got count", int(got_edge.sum()), "mismatch", int((expected_edge != got_edge).sum()))
print("meta boundary_count:", meta.get("boundary_count"))
for env in range(8):
    me = int((expected_edge[:, env] != got_edge[:, env]).sum())
    print("  env", env, CASES[env], "edge mismatch", me, "expected_edge", int(expected_edge[:, env].sum()), "got", int(got_edge[:, env].sum()))
interior = ~expected_edge
mask_bad = (finite != oracle_finite) & interior
print("scene_hit_mask mismatches (interior):", int(mask_bad.sum()))
for env in range(8):
    n = int(mask_bad[:, env].sum())
    if n:
        print("  env", env, CASES[env], "n", n, "finite_but_oracle_miss", int((finite[:, env] & ~oracle_finite[:, env] & interior[:, env]).sum()),
              "oracle_finite_but_miss", int((~finite[:, env] & oracle_finite[:, env] & interior[:, env]).sum()))
target_h = np.clip(a["pos_w"][..., 2, None] - .5 - oracle_z, -1, 1)
target_h[~oracle_finite] = 1
dh = np.abs(a["height"] - target_h)
print("world_height_answer max dev (interior):", float(dh[interior].max()), " n > 2mm:", int((dh[interior] > .002).sum()))
for env in range(8):
    m = interior[:, env]
    n = int((dh[:, env][m] > .002).sum())
    if n:
        print("  env", env, CASES[env], "n>2mm", n, "max", float(dh[:, env][m].max()))
print("miss count total", int(np.isposinf(hits).all(axis=-1).sum()), "per env", np.isposinf(hits).all(axis=-1).sum(axis=(0, 2)).tolist())
print("oracle non-finite per env", (~oracle_finite).sum(axis=(0, 2)).tolist())
