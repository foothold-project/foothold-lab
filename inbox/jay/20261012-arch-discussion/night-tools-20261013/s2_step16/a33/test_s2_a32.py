"""A3.2 (10/15, after attempt 3 and ASTRA 17ac): held-robot config, scheduled-reset sensor clock, ray frame checks,
one boundary formula with a known-input 5 mm test, per-branch sampled PhysX comparison, raw query preservation, derived
provenance. CPU only; Kit, PhysX and Warp are replaced by small fakes."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile

import numpy as np

from s2_connect_check_17v import Criteria, check_arrays, scene_expectation
from s2_connect_diag_17v import (finalize_provenance, fixed_pose_ok, terrain_assignment_ok, sha256_file, asset_sha256_of)
from s2_env_config_17v import EnvironmentSpec, configure_env
import s2_mesh_probe_a2 as probe
from test_s2_connect_a2 import fixture

CRIT = Criteria(.002, .002, .005, 256, 16)
FAILS = []


def check(name, good):
    print(("PASS" if good else "FAIL") + " " + name, flush=True)
    if not good:
        FAILS.append(name)


def reasons(meta, data):
    return check_arrays(meta, data, CRIT)["reasons"]


def fake_cfg():
    """RobotLab Go2 attribute paths; sensor and geometry remain the A3.2 fixture."""
    ns = SimpleNamespace
    return ns(seed=0, decimation=4, episode_length_s=20.0, sim=ns(dt=0.005),
              scene=ns(num_envs=4096, terrain=ns(terrain_generator=object(), max_init_terrain_level=5, terrain_type="x"),
                       robot=ns(spawn=ns(rigid_props=ns(disable_gravity=False)))),
              terminations=ns(illegal_contact=ns(func="illegal_contact"), time_out=ns(func="time_out")),
              curriculum=ns(terrain_levels=ns()),
              events=ns(reset_base=ns(params={"pose_range": {"x": (-.5, .5), "y": (-.5, .5), "yaw": (-3.14, 3.14)}}),
                        randomize_push_robot=ns(), randomize_rigid_body_mass_base=ns(),
                        randomize_rigid_body_mass_others=ns(), randomize_com_positions=ns(),
                        randomize_rigid_body_material=ns(), randomize_actuator_gains=ns(),
                        randomize_motor_zero_offset=ns()),
              observations=ns(policy=ns(enable_corruption=True)),
              commands=ns(base_velocity=ns(resampling_time_range=(1, 2), resampling_time=5.,
                                           dynamic_resample_commands=True, command_range_curriculum=[{"iter": 1}],
                                           limit_vel_prob=.2, zero_command_curriculum={"start_iter":0},
                                           ranges=ns(lin_vel_x=(-1, 1), lin_vel_y=(-1, 1), ang_vel_yaw=(-1, 1)))))


def synthetic_branch_inputs(steps=10, with_holes=True):
    """(steps, 8, 187) arrays for a scene with every pre-registered branch present: raised tops in envs 2,3,6,7, holes and
    deep floor in envs 4,5, ground elsewhere. PhysX agrees with the RayCaster and with the known scene."""
    S, n, r = steps, 8, 187
    cls = np.full((S, n, r), 3, dtype=np.int8)
    for env in (2, 3, 6, 7):
        cls[:, env, 0:4] = 2
    for env in (4, 5):
        cls[:, env, 4:9] = 0 if with_holes else 3
        cls[:, env, 9:14] = 1
    ofin = cls != 0
    z = np.zeros((S, n, r)); z[cls == 2] = .2; z[cls == 1] = -1.5
    hits_z = np.where(ofin, z, np.inf)
    fin = ofin.copy()
    edge = np.zeros((S, n, r), dtype=bool)
    samples = {}
    for k in range(S):
        st = np.where(ofin[k], probe.ST_TERRAIN, probe.ST_MISS).astype(np.int8)
        pz = np.where(ofin[k], z[k], np.nan)
        samples[k] = {"status": st.reshape(-1), "z": pz.reshape(-1), "path_idx": np.where(ofin[k], 0, -1).astype(np.int32).reshape(-1),
                      "paths": ["/World/ground/terrain/mesh"], "errors": [], "raw_samples": []}
    return dict(samples=samples, ray_hits_z=hits_z, ray_finite=fin, edge_excluded=edge, oracle_finite=ofin, cls=cls), z


def main():
    from s2_known_scene_a2 import answer, oracle
    import s2_env_config_17v as ec
    # build_generator needs isaaclab.terrains (pxr, Kit only); the cfg logic under test does not.
    ec.build_generator = lambda seed: SimpleNamespace(sub_terrains={k: None for k in ec.DIAG_TERRAIN_ORDER})
    ans = answer()
    spec = EnvironmentSpec(7, 8, .15, .15, ans["step"]["top_z_m"],
                           ans["step"]["x_range"][1] - ans["step"]["x_range"][0], .002)

    # ---- 1. held-robot config (the claim "gravity off means fixed" is NOT made here; the first 16 rows are measured)
    base = fake_cfg()
    cfg = configure_env(base, spec, diagnostic_kind="eight_case", reset_yaw_rad=0.0)
    check("A32 eight_case cfg: gravity off for the robot", cfg.scene.robot.spawn.rigid_props.disable_gravity is True)
    check("A33 eight_case cfg: illegal_contact termination removed, time_out kept",
          cfg.terminations.illegal_contact is None and cfg.terminations.time_out is not None)
    check("A32 the caller's cfg is not modified (deep copy)",
          base.scene.robot.spawn.rigid_props.disable_gravity is False and base.terminations.illegal_contact is not None)
    missing = fake_cfg(); missing.scene.robot.spawn.rigid_props = None
    try:
        configure_env(missing, spec, diagnostic_kind="eight_case", reset_yaw_rad=0.0); ok = False
    except ValueError:
        ok = True
    check("A32 missing rigid_props is refused, not silently skipped", ok)
    nobc = fake_cfg(); del nobc.terminations.illegal_contact
    try:
        configure_env(nobc, spec, diagnostic_kind="eight_case", reset_yaw_rad=0.0); ok = False
    except ValueError:
        ok = True
    check("A33 missing illegal_contact termination is refused", ok)

    # ---- 2. sensor clock and resets (ASTRA 17ac section 4): only the scheduled step-128 reset may rewind
    meta, data = fixture()
    check("A32 scheduled reset: fixture passes", check_arrays(meta, data, CRIT)["verdict"] == "PASS")
    d = copy.deepcopy(data); d["sensor_timestamp"][100:128, 3] -= 0.5   # one backward step, the rest stays consistent
    check("A32 same-episode clock regress -> sensor_timestamp", "sensor_timestamp" in reasons(meta, d))
    d = copy.deepcopy(data); d["sensor_timestamp"][100:128, 3] = d["sensor_timestamp"][100, 3]   # zero advance, no backward step
    check("A32 same-episode clock stall (constant time) -> sensor_timestamp", "sensor_timestamp" in reasons(meta, d))
    d = copy.deepcopy(data); d["sensor_timestamp"][50:, 2] += .02
    check("A32 clock jumps two control steps in one row -> sensor_timestamp", "sensor_timestamp" in reasons(meta, d))
    d = copy.deepcopy(data); d["sensor_timestamp"][128:] = d["sensor_timestamp"][127] + .02 * (np.arange(128)[:, None] + 1)
    check("A32 scheduled reset without a clock rewind (old buffer reused) -> sensor_timestamp", "sensor_timestamp" in reasons(meta, d))
    d = copy.deepcopy(data); d["sensor_timestamp"][128:] += .5
    check("A32 clock after the reset not at one control step -> sensor_timestamp", "sensor_timestamp" in reasons(meta, d))
    d = copy.deepcopy(data); d["episode_ids"][200:, 5] += 1
    check("A32 fake episode increment (no reset marker, no rewind) -> stale_packet", "stale_packet" in reasons(meta, d))
    d = copy.deepcopy(data); d["episode_ids"][128:, 4] += 1
    check("A32 episode jumps by 2 at the scheduled reset -> stale_packet", "stale_packet" in reasons(meta, d))
    d = copy.deepcopy(data); d["termination"][40, 4] = 1; d["episode_ids"][41:, 4] += 1
    d["sensor_timestamp"][41:, 4] = np.arange(215) * .02 + .02
    r = reasons(meta, d)
    check("A32 an unscheduled termination with a real reset is its own HOLD", "unscheduled_termination" in r and "sensor_timestamp" in r)
    d = copy.deepcopy(data); d["timeout"][60, 1] = True
    check("A32 a timeout flag -> unscheduled_termination", "unscheduled_termination" in reasons(meta, d))
    d = copy.deepcopy(data); d["reset_mask"][:] = False
    check("A32 scheduled reset with no reset marker -> reset_marker", "reset_marker" in reasons(meta, d))
    d = copy.deepcopy(data); d["reset_mask"][90, 2] = True
    check("A32 a reset marker outside step 128 -> reset_marker", "reset_marker" in reasons(meta, d))

    # ---- 3. ray frame (ASTRA 17ac section 1): the rays must be valid, not only the hits
    d = copy.deepcopy(data); d["ray_starts_w"][:, :, :, 0] += .01
    check("A32 ray start XY 1 cm off the analysis XY -> ray_start_xy", "ray_start_xy" in reasons(meta, d))
    d = copy.deepcopy(data); d["ray_directions_w"][..., 0] = .01
    check("A32 tilted ray direction -> ray_direction", "ray_direction" in reasons(meta, d))
    d = copy.deepcopy(data); d["ray_starts_w"][173:, 5, :, 2] = -.3
    check("A32 rays that start below the terrain surface -> ray_start_height", "ray_start_height" in reasons(meta, d))

    # ---- 4. boundary: one formula, plus a known-input 5 mm test of the oracle distance itself
    yaw, expected, oz, of, oe, edge = scene_expectation(data, .005)
    check("A32 scene_expectation edge equals the fixture's boundary mask", np.array_equal(edge, data["edge_excluded"]))
    x0 = ans["step"]["x_range"][0]
    ym = (ans["step"]["y_range"][0] + ans["step"]["y_range"][1]) / 2   # mid-width, so the x edge is the nearest one
    xy = np.asarray([[x0 - .0049, ym], [x0 - .0051, ym], [x0 + .0049, ym], [x0 + .0051, ym]])
    dist = oracle("obstacles", xy)[2]
    check("A32 oracle edge distance reads 4.9 / 5.1 mm on either side of the step edge, so the 5 mm cut separates them",
          np.allclose(dist, [.0049, .0051, .0049, .0051], atol=1e-6) and list(dist <= .005) == [True, False, True, False])
    d = copy.deepcopy(data); d["edge_excluded"] = edge.copy(); d["edge_excluded"][10, 6, 5] ^= True
    check("A32 a one-sample boundary difference is still caught", "boundary_mask" in reasons(meta, d))

    # ---- 5. derived flags
    check("A32 fixed_pose_ok true for a still pose", fixed_pose_ok(data))
    d = copy.deepcopy(data); d["root_pos_w"][5, 0, 2] += .05
    check("A32 fixed_pose_ok false when the pose moves 5 cm in warmup", not fixed_pose_ok(d))
    check("A32 terrain_assignment_ok true for the fixture", terrain_assignment_ok(data))
    d = copy.deepcopy(data); d["terrain_type"][0, 0] = 3
    check("A32 terrain_assignment_ok false for a wrong case", not terrain_assignment_ok(d))

    # ---- 6. Warp vs USD mesh
    rng = np.random.default_rng(1)
    pts = rng.normal(size=(50, 3)); idx = rng.integers(0, 50, size=90)
    check("A32 warp float32 copy of the USD points agrees", probe.compare_meshes(pts, idx, pts.astype(np.float32), idx)["agree"])
    check("A32 a 1 cm point offset disagrees", not probe.compare_meshes(pts, idx, pts + 0.01, idx)["agree"])
    check("A32 different face order disagrees", not probe.compare_meshes(pts, idx, pts, idx[::-1])["agree"])
    check("A32 different point count disagrees", not probe.compare_meshes(pts, idx, pts[:-1], idx)["agree"])
    check("A32 sha_array depends on dtype and shape",
          probe.sha_array(np.zeros((2, 3), np.float32)) != probe.sha_array(np.zeros((2, 3), np.float64))
          and probe.sha_array(np.zeros((2, 3))) != probe.sha_array(np.zeros((3, 2))))

    # ---- 7. PhysX query wrapper
    def plane_cast(z0=0.0, robot_xy=None, bad_every=None):
        count = {"n": 0}
        def cast(origin, direction, max_dist):
            count["n"] += 1
            if bad_every and count["n"] % bad_every == 0:
                raise RuntimeError("scene query failed")
            if robot_xy and abs(origin[0] - robot_xy[0]) < .06 and abs(origin[1] - robot_xy[1]) < .06:
                return {"hit": True, "position": (origin[0], origin[1], .3), "collision": "/World/envs/env_0/Robot/base"}
            if origin[2] <= z0:
                return {"hit": False}
            return {"hit": True, "position": (origin[0], origin[1], z0), "collision": "/World/ground/terrain/mesh"}
        return cast
    n = 40
    starts = np.column_stack([rng.uniform(-2, 2, n), rng.uniform(-2, 2, n), np.full(n, 20.0)])
    dirs = np.tile([0., 0., -1.], (n, 1))
    ph = probe.physx_terrain_hits(starts, dirs, plane_cast(), terrain_prefix="/World/ground")
    check("A32 physx: every fake ray is a terrain hit and the raw answers are kept",
          int((ph["status"] == probe.ST_TERRAIN).sum()) == n and len(ph["raw_samples"]) == 5 and ph["paths"] == ["/World/ground/terrain/mesh"])
    ph2 = probe.physx_terrain_hits(starts, dirs, plane_cast(robot_xy=(starts[0, 0], starts[0, 1])), terrain_prefix="/World/ground")
    check("A32 physx: a ray the robot collider takes is occluded, not a ground sample", int((ph2["status"] == probe.ST_OCCLUDED).sum()) >= 1)
    ph3 = probe.physx_terrain_hits(starts, dirs, plane_cast(bad_every=4), terrain_prefix="/World/ground")
    check("A32 physx: a failing query is recorded per ray and the loop goes on",
          int((ph3["status"] == probe.ST_ERROR).sum()) == n // 4 and len(ph3["errors"]) >= 1)
    sm = probe.PhysxSampler("/World/ground", steps=(3, 5), raycast=plane_cast())
    sm.observe(3, starts, dirs); sm.observe(4, starts, dirs); sm.observe(5, starts, dirs)
    check("A32 PhysxSampler records only the pre-registered steps", sorted(sm.samples) == [3, 5])
    old_budget = probe.PHYSX_TIME_BUDGET_S
    probe.PHYSX_TIME_BUDGET_S = -1.0
    sm2 = probe.PhysxSampler("/World/ground", steps=(3,), raycast=plane_cast())
    sm2.observe(3, starts, dirs)
    probe.PHYSX_TIME_BUDGET_S = old_budget
    check("A32 PhysxSampler stops at its time budget and says so", not sm2.samples and "physx_time_budget_exceeded" in sm2.errors)

    # ---- 8. per-branch comparison (ASTRA 17ac section 3): the all-occluded-holes counterexample must not pass
    inp, z = synthetic_branch_inputs()
    rep_ok = probe.branch_report(**inp)
    check("A32 branches: a scene where PhysX, the RayCaster and the known scene agree satisfies every required branch",
          rep_ok["branches_ok"] and not rep_ok["missing_required"] and not rep_ok["unsatisfied_required"])
    inp2, _ = synthetic_branch_inputs()
    for k, sm_ in inp2["samples"].items():
        st = sm_["status"].reshape(8, -1)
        st[4:6][inp2["cls"][k][4:6] == 0] = probe.ST_OCCLUDED
        sm_["status"] = st.reshape(-1)
    rep_occ = probe.branch_report(**inp2)
    check("A32 branches: every hole ray occluded -> not ok (the occluded-holes counterexample)",
          not rep_occ["branches_ok"] and [4, "hole"] in rep_occ["unsatisfied_required"])
    inp3, _ = synthetic_branch_inputs()
    for k, sm_ in inp3["samples"].items():
        st = sm_["status"].reshape(8, -1); zz = sm_["z"].reshape(8, -1)
        st[5][inp3["cls"][k][5] == 0] = probe.ST_TERRAIN; zz[5][inp3["cls"][k][5] == 0] = -5.0
        sm_["status"] = st.reshape(-1); sm_["z"] = zz.reshape(-1)
    r3 = probe.branch_report(**inp3)
    check("A32 branches: PhysX finds ground in a hole -> not ok, counted as oracle and hit/miss mismatch",
          not r3["branches_ok"] and r3["totals"]["oracle_mismatch"] > 0 and r3["totals"]["hit_miss_mismatch"] > 0)
    inp4, _ = synthetic_branch_inputs()
    for k, sm_ in inp4["samples"].items():
        zz = sm_["z"].reshape(8, -1); zz[2][inp4["cls"][k][2] == 2] += .05
        sm_["z"] = zz.reshape(-1)
    r4 = probe.branch_report(**inp4)
    check("A32 branches: a 5 cm height difference on the step top -> not ok", not r4["branches_ok"] and r4["totals"]["hit_z_bad"] > 0)
    inp5, _ = synthetic_branch_inputs()
    for k, sm_ in inp5["samples"].items():
        st = sm_["status"].reshape(8, -1); st[0, 0] = probe.ST_ERROR; sm_["status"] = st.reshape(-1)
    check("A32 branches: a query error inside a required branch -> not ok", not probe.branch_report(**inp5)["branches_ok"])
    inp6, _ = synthetic_branch_inputs(with_holes=False)
    r6 = probe.branch_report(**inp6)
    check("A32 branches: a scene sample that never looks into a hole -> missing_required, not ok",
          [4, "hole"] in r6["missing_required"] and not r6["branches_ok"])
    inp7, _ = synthetic_branch_inputs()
    inp7["edge_excluded"][:, 2, 0:4] = True
    r7 = probe.branch_report(**inp7)
    check("A32 branches: boundary rays are skipped, and a branch left with too few rays is not satisfied",
          not r7["branches_ok"] and r7["totals"]["boundary_skipped"] > 0)
    check("A32 branches: classify_oracle labels hole / deep / raised / ground",
          list(probe.classify_oracle([np.nan, -2., .2, 0.], [False, True, True, True])) == [0, 1, 2, 3])
    raw = probe.raw_query_arrays(inp["samples"])
    check("A32 raw query arrays keep steps, status, hit z, path index and the path table",
          raw["status"].shape == (10, 8 * 187) and raw["paths"].tolist() == ["/World/ground/terrain/mesh"] and len(raw["steps"]) == 10)
    fp = probe.raw_fingerprint(raw)
    raw2 = dict(raw); raw2["status"] = raw["status"].copy(); raw2["status"][0, 0] ^= 1
    check("A32 the query fingerprint changes when one answer changes", fp != probe.raw_fingerprint(raw2))

    usd = {"vertices_sha256": "v" * 64, "faces_sha256": "f" * 64, "world_transform_sha256": "t" * 64}
    kw = dict(prim_path="/World/ground", usd=usd, mesh_cmp={"agree": True}, report=rep_ok, collision_api=True,
              collision_enabled=True, approximation="none", errors=[], raw_fingerprint=fp)
    good = probe.build_mesh_evidence(**kw)
    check("A32 evidence is observed_collision_mesh, sampled scope, only when everything agrees",
          good["kind"] == "observed_collision_mesh" and good["scope"] == "sampled_collision_response" and good["branches_ok"] is True)
    check("A32 evidence says the collision hash is a query-response fingerprint, not a mesh byte hash",
          good["collision_sha256_kind"] == "sampled_query_response_fingerprint")
    for label, over in (("mesh disagrees", dict(mesh_cmp={"agree": False})), ("mesh probe missing", dict(mesh_cmp=None)),
                        ("branches not ok", dict(report=rep_occ)), ("no report", dict(report=None)),
                        ("no collision api", dict(collision_api=False)), ("collision disabled", dict(collision_enabled=False)),
                        ("probe error text", dict(errors=["physx_raycast:boom"]))):
        ev = probe.build_mesh_evidence(**{**kw, **over})
        check("A32 evidence is unverified when: " + label,
              ev["kind"] == "unverified_collision_mesh" and ev["reasons"] and ev["branches_ok"] is False)

    # ---- 9. provenance end to end: finalize_provenance + the real checker
    versions = {"isaac_version": "isaaclab=x;isaacsim=y", "kit_version": "k", "torch_version": "t", "driver_version": "d"}
    meta2, data2 = fixture()
    edge2 = scene_expectation(data2, .005)[5]
    base_meta = {k: meta2[k] for k in ("parent_sha256", "code_sha256", "capture_sha256", "env_config_sha256", "cases",
                                       "optimizer_steps", "control_steps", "scene_answer_sha256")}
    observed = {"evidence": good, "errors": [], "usd": {"prim_path": "/World/ground/terrain/mesh"}, "raw": raw,
                "sensor_frame": {"ray_alignment": "yaw"}, "recorded_edge_differences": []}
    root = Path(tempfile.mkdtemp(prefix="s2_a32_prov_"))
    prov = finalize_provenance(root, data2, edge2, observed, versions, "a" * 64, [0.0, 0.0, 0.0])
    full = {**base_meta, **prov}
    check("A32 finalize_provenance: derived flags true, mesh verified", prov["terrain_assignment_verified"] and prov["fixed_pose_verified"]
          and prov["mesh_collision_verified"])
    check("A32 diag-built meta plus the real checker -> PASS", check_arrays(full, data2, CRIT)["verdict"] == "PASS")
    ev_file = json.loads((root / "mesh_evidence.json").read_text(encoding="utf-8"))
    check("A32 the raw query file is written and its hash is in the evidence",
          (root / "physx_queries.npz").is_file() and ev_file["raw_query_file_sha256"] == sha256_file(root / "physx_queries.npz"))
    check("A32 probe report keeps the sensor frame facts and the recorded-mask differences",
          json.loads((root / "a32_probe_report.json").read_text(encoding="utf-8"))["sensor_frame"] == {"ray_alignment": "yaw"})
    for key, want in (("isaac_version", "provenance_missing"), ("driver_version", "provenance_missing"),
                      ("asset_sha256", "provenance_missing"), ("root_sensor_offset_b", "provenance_missing"),
                      ("mesh_evidence_sha256", "provenance_missing"), ("collision_mesh_sha256", "provenance_missing")):
        m = dict(full); m[key] = "" if key != "root_sensor_offset_b" else None
        check("A32 meta without %s -> %s" % (key, want), want in reasons(m, data2))
    m = dict(full); m["mesh_collision_verified"] = False
    check("A32 mesh_collision_verified false -> case_assignment", "case_assignment" in reasons(m, data2))
    m = dict(full); m["boundary_count"] = full["boundary_count"] + 1
    check("A32 wrong boundary_count -> boundary_unreported", "boundary_unreported" in reasons(m, data2))
    unver = {"evidence": probe.build_mesh_evidence(**{**kw, "report": rep_occ}), "errors": ["x"], "usd": None, "raw": raw}
    prov2 = finalize_provenance(Path(tempfile.mkdtemp(prefix="s2_a32_prov_")), data2, edge2, unver, versions, "a" * 64, [0.0, 0.0, 0.0])
    check("A32 unverified evidence leaves mesh_collision_verified false and the checker HOLDs",
          not prov2["mesh_collision_verified"] and "mesh_evidence_content" in reasons({**base_meta, **prov2}, data2))
    scopeless = dict(good); scopeless.pop("scope")
    prov2b = finalize_provenance(Path(tempfile.mkdtemp(prefix="s2_a32_prov_")), data2, edge2,
                                 {"evidence": scopeless, "errors": [], "usd": None, "raw": raw}, versions, "a" * 64, [0., 0., 0.])
    check("A32 evidence without the sampled-scope statement is refused by the checker",
          "mesh_evidence_content" in reasons({**base_meta, **prov2b}, data2))
    prov3 = finalize_provenance(Path(tempfile.mkdtemp(prefix="s2_a32_prov_")), data2, edge2,
                                {"evidence": None, "errors": ["usd_mesh_not_found"], "usd": None, "raw": None}, versions, "", [0.0, 0.0, 0.0])
    check("A32 no evidence at all: no mesh keys, checker HOLDs provenance_missing",
          "mesh_evidence_path" not in prov3 and "provenance_missing" in reasons({**base_meta, **prov3}, data2))
    d = copy.deepcopy(data2); d["root_pos_w"][4, 1, 2] += .03; d["pos_w"][4, 1, 2] += .03
    prov4 = finalize_provenance(Path(tempfile.mkdtemp(prefix="s2_a32_prov_")), d, edge2, observed, versions, "a" * 64, [0., 0., 0.])
    check("A32 moving pose: flag false and the checker HOLDs fixed_pose_evidence",
          not prov4["fixed_pose_verified"] and "fixed_pose_evidence" in reasons({**base_meta, **prov4}, d))

    # ---- 10. asset digest: a local file is hashed; an https reference with no Kit gives "" (never a made-up value)
    f = Path(tempfile.mkdtemp(prefix="s2_a32_asset_")) / "a.usd"
    f.write_bytes(b"usd-bytes")
    check("A32 asset digest of a local file is its sha256", asset_sha256_of(str(f)) == hashlib.sha256(b"usd-bytes").hexdigest())
    check("A32 asset digest of an unreachable https reference is empty, not invented",
          asset_sha256_of("https://invalid.invalid/Isaac/go2.usd") == "")
    check("A32 a missing local path gives an empty digest", asset_sha256_of(str(f.parent / "missing.usd")) == "")

    print("SUMMARY", "ALL PASS" if not FAILS else "FAIL %s" % FAILS)
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
