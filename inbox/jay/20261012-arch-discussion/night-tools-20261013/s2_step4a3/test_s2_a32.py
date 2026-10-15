"""A3.2 (10/15, after attempt 3): held robot config, reset-aware sensor clock, one boundary formula, observed mesh and
collision evidence, derived provenance. CPU only; Kit, PhysX and Warp are replaced by small fakes."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile

import numpy as np

from s2_connect_check_17v import Criteria, check_arrays, scene_expectation
from s2_connect_diag_17v import finalize_provenance, fixed_pose_ok, terrain_assignment_ok, sha256_file
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
    """The attribute paths of the real Go2 rough cfg (final_cfg.json of attempt 3)."""
    ns = SimpleNamespace
    return ns(seed=0, decimation=4, episode_length_s=20.0, sim=ns(dt=0.005),
              scene=ns(num_envs=4096, terrain=ns(terrain_generator=object(), max_init_terrain_level=5, terrain_type="x"),
                       robot=ns(spawn=ns(rigid_props=ns(disable_gravity=False)))),
              terminations=ns(base_contact=ns(func="illegal_contact"), time_out=ns(func="time_out")),
              curriculum=ns(terrain_levels=ns()),
              events=ns(reset_base=ns(params={"pose_range": {"x": (-.5, .5), "y": (-.5, .5), "yaw": (-3.14, 3.14)}}),
                        push_robot=ns(), base_external_force_torque=ns(), add_base_mass=ns(), base_com=ns()),
              observations=ns(policy=ns(enable_corruption=True)),
              commands=ns(base_velocity=ns(resampling_time_range=(1, 2), heading_command=True, rel_heading_envs=1.0,
                                           rel_standing_envs=.1,
                                           ranges=ns(lin_vel_x=(-1, 1), lin_vel_y=(-1, 1), ang_vel_z=(-1, 1), heading=(-3, 3)))))


def main():
    from s2_known_scene_a2 import answer
    import s2_env_config_17v as ec
    # build_generator needs isaaclab.terrains (pxr, Kit only); the cfg logic under test does not.
    ec.build_generator = lambda seed: SimpleNamespace(sub_terrains={k: None for k in ec.DIAG_TERRAIN_ORDER})
    ans = answer()
    spec = EnvironmentSpec(7, 8, .15, .15, ans["step"]["top_z_m"],
                           ans["step"]["x_range"][1] - ans["step"]["x_range"][0], .002)

    # ---- 1. held robot: no gravity, no contact termination, nothing else of the cfg touched
    base = fake_cfg()
    cfg = configure_env(base, spec, diagnostic_kind="eight_case", reset_yaw_rad=0.0)
    check("A32 eight_case cfg: gravity off for the robot", cfg.scene.robot.spawn.rigid_props.disable_gravity is True)
    check("A32 eight_case cfg: base_contact termination removed, time_out kept",
          cfg.terminations.base_contact is None and cfg.terminations.time_out is not None)
    check("A32 the caller's cfg is not modified (deep copy)",
          base.scene.robot.spawn.rigid_props.disable_gravity is False and base.terminations.base_contact is not None)
    missing = fake_cfg(); missing.scene.robot.spawn.rigid_props = None
    try:
        configure_env(missing, spec, diagnostic_kind="eight_case", reset_yaw_rad=0.0); ok = False
    except ValueError:
        ok = True
    check("A32 missing rigid_props is refused, not silently skipped", ok)
    nobc = fake_cfg(); del nobc.terminations.base_contact
    try:
        configure_env(nobc, spec, diagnostic_kind="eight_case", reset_yaw_rad=0.0); ok = False
    except ValueError:
        ok = True
    check("A32 missing base_contact termination is refused", ok)

    # ---- 2. reset-aware sensor clock
    meta, data = fixture()
    check("A32 fixture (clock rewinds exactly at the step-128 reset) passes", check_arrays(meta, data, CRIT)["verdict"] == "PASS")
    d = copy.deepcopy(data); d["sensor_timestamp"][100:, 3] -= 0.5  # rewind without a reset, one env
    check("A32 clock rewind without an episode change -> sensor_timestamp", "sensor_timestamp" in reasons(meta, d))
    d = copy.deepcopy(data); d["sensor_timestamp"][128:] += 5.0  # reset happened but the clock did not rewind
    check("A32 reset without a clock rewind -> sensor_timestamp", "sensor_timestamp" in reasons(meta, d))
    d = copy.deepcopy(data); d["episode_ids"][200:, 5] += 1  # extra reset whose clock did not rewind
    check("A32 extra reset with no rewind -> sensor_timestamp", "sensor_timestamp" in reasons(meta, d))
    d = copy.deepcopy(data); d["episode_ids"][200:, 5] += 1; d["sensor_timestamp"][200:, 5] -= d["sensor_timestamp"][199, 5] + .02
    check("A32 extra reset with a rewind still HOLDs on stale_packet (episode must be constant before 128/after 128)",
          "stale_packet" in reasons(meta, d))

    # ---- 3. one boundary formula
    yaw, expected, oz, of, oe, edge = scene_expectation(data, .005)
    check("A32 scene_expectation edge equals the fixture's boundary mask", np.array_equal(edge, data["edge_excluded"]))
    d = copy.deepcopy(data)
    d["edge_excluded"] = edge.copy(); d["edge_excluded"][10, 6, 5] ^= True
    check("A32 a one-sample boundary difference is still caught", "boundary_mask" in reasons(meta, d))

    # ---- 4. derived flags
    check("A32 fixed_pose_ok true for a still pose", fixed_pose_ok(data))
    d = copy.deepcopy(data); d["root_pos_w"][5, 0, 2] += .05
    check("A32 fixed_pose_ok false when the pose moves 5 cm in warmup", not fixed_pose_ok(d))
    check("A32 terrain_assignment_ok true for the fixture", terrain_assignment_ok(data))
    d = copy.deepcopy(data); d["terrain_type"][0, 0] = 3
    check("A32 terrain_assignment_ok false for a wrong case", not terrain_assignment_ok(d))

    # ---- 5. mesh and collision evidence, pure parts
    rng = np.random.default_rng(1)
    pts = rng.normal(size=(50, 3)); idx = rng.integers(0, 50, size=90)
    cm = probe.compare_meshes(pts, idx, pts.astype(np.float32), idx)
    check("A32 warp float32 copy of the USD points agrees", cm["agree"] and cm["max_point_abs_m"] < 1e-4)
    cm = probe.compare_meshes(pts, idx, pts + 0.01, idx)
    check("A32 a 1 cm point offset disagrees", not cm["agree"])
    cm = probe.compare_meshes(pts, idx, pts, idx[::-1])
    check("A32 different face order disagrees", not cm["agree"])
    cm = probe.compare_meshes(pts, idx, pts[:-1], idx)
    check("A32 different point count disagrees", not cm["agree"])
    check("A32 sha_array depends on dtype and shape",
          probe.sha_array(np.zeros((2, 3), np.float32)) != probe.sha_array(np.zeros((2, 3), np.float64))
          and probe.sha_array(np.zeros((2, 3))) != probe.sha_array(np.zeros((3, 2))))

    def plane_cast(z0=0.0, robot_xy=None):
        def cast(origin, direction, max_dist):
            if robot_xy and abs(origin[0] - robot_xy[0]) < .06 and abs(origin[1] - robot_xy[1]) < .06:
                return {"hit": True, "position": (origin[0], origin[1], .3), "collision": "/World/envs/env_0/Robot/base"}
            if origin[2] <= z0:
                return {"hit": False}
            return {"hit": True, "position": (origin[0], origin[1], z0), "collision": "/World/ground/terrain/mesh"}
        return cast

    n = 2000
    starts = np.column_stack([rng.uniform(-2, 2, n), rng.uniform(-2, 2, n), np.full(n, 20.0)])
    dirs = np.tile([0., 0., -1.], (n, 1))
    ph = probe.physx_terrain_hits(starts, dirs, plane_cast(), terrain_prefix="/World/ground")
    check("A32 physx fake: every ray is a terrain hit", int((ph["status"] == 1).sum()) == n)
    rz = np.zeros(n); fin = np.ones(n, bool); edge0 = np.zeros(n, bool)
    cmp_ok = probe.compare_collision_to_raycaster(rz, fin, edge0, ph)
    check("A32 collision agrees when PhysX and the RayCaster give the same plane", probe.collision_agrees(cmp_ok))
    cmp_bad = probe.compare_collision_to_raycaster(rz + .05, fin, edge0, ph)
    check("A32 collision disagrees when the RayCaster plane is 5 cm higher", not probe.collision_agrees(cmp_bad))
    miss_ray = fin.copy(); miss_ray[:3] = False
    cmp_miss = probe.compare_collision_to_raycaster(rz, miss_ray, edge0, ph)
    check("A32 a hit/miss disagreement is counted and refused", cmp_miss["hit_miss_mismatch"] == 3 and not probe.collision_agrees(cmp_miss))
    cmp_few = probe.compare_collision_to_raycaster(rz[:50], fin[:50], edge0[:50],
                                                   probe.physx_terrain_hits(starts[:50], dirs[:50], plane_cast(), terrain_prefix="/World/ground"))
    check("A32 too few compared rays cannot count as observed", not probe.collision_agrees(cmp_few))
    ph2 = probe.physx_terrain_hits(starts, dirs, plane_cast(robot_xy=(starts[0, 0], starts[0, 1])), terrain_prefix="/World/ground")
    check("A32 a ray the robot occludes is counted as occluded, not compared", int((ph2["status"] == 2).sum()) >= 1)
    cmp_occ = probe.compare_collision_to_raycaster(rz, fin, edge0, ph2)
    check("A32 occluded rays do not break agreement", probe.collision_agrees(cmp_occ) and cmp_occ["occluded"] >= 1)
    edge_all = np.ones(n, bool)
    check("A32 boundary rays are skipped, not compared",
          probe.compare_collision_to_raycaster(rz + 1, fin, edge_all, ph)["compared"] == 0)

    def raising(*a):
        raise RuntimeError("no scene query")
    try:
        probe.physx_terrain_hits(starts[:3], dirs[:3], raising, terrain_prefix="/World/ground"); ok = False
    except RuntimeError:
        ok = True
    check("A32 physx_terrain_hits itself lets the caller see a query failure (observe_collision_kit swallows it)", ok)

    usd = {"vertices_sha256": "v" * 64, "faces_sha256": "f" * 64, "world_transform_sha256": "t" * 64}
    good = probe.build_mesh_evidence(prim_path="/World/ground", usd=usd, mesh_cmp={"agree": True}, collision_cmp=cmp_ok,
                                     collision_api=True, collision_enabled=True, approximation="none", errors=[])
    check("A32 evidence kind observed_collision_mesh only when all probes agree", good["kind"] == "observed_collision_mesh" and not good["reasons"])
    for label, kw in (("mesh disagrees", dict(mesh_cmp={"agree": False})), ("mesh probe missing", dict(mesh_cmp=None)),
                      ("collision probe missing", dict(collision_cmp=None)), ("collision bad", dict(collision_cmp=cmp_bad)),
                      ("no collision api", dict(collision_api=False)), ("collision disabled", dict(collision_enabled=False)),
                      ("probe error text", dict(errors=["physx_raycast:boom"]))):
        args = dict(prim_path="/World/ground", usd=usd, mesh_cmp={"agree": True}, collision_cmp=cmp_ok,
                    collision_api=True, collision_enabled=True, approximation="none", errors=[])
        args.update(kw)
        ev = probe.build_mesh_evidence(**args)
        check("A32 evidence is unverified when: " + label, ev["kind"] == "unverified_collision_mesh" and ev["reasons"])

    # ---- 6. provenance end to end: finalize_provenance + the real checker
    versions = {"isaac_version": "isaaclab=x;isaacsim=y", "kit_version": "k", "torch_version": "t", "driver_version": "d"}
    meta2, data2 = fixture()
    root = Path(tempfile.mkdtemp(prefix="s2_a32_prov_"))
    edge2 = scene_expectation(data2, .005)[5]
    base_meta = {k: meta2[k] for k in ("parent_sha256", "code_sha256", "capture_sha256", "env_config_sha256", "cases",
                                       "optimizer_steps", "control_steps", "scene_answer_sha256")}
    observed = {"evidence": good, "errors": [], "usd": {"prim_path": "/World/ground/terrain/mesh"}}
    prov = finalize_provenance(root, data2, edge2, observed, versions, "a" * 64, [0.0, 0.0, 0.0])
    full = {**base_meta, **prov}
    check("A32 finalize_provenance: derived flags true, mesh verified", prov["terrain_assignment_verified"] and prov["fixed_pose_verified"]
          and prov["mesh_collision_verified"])
    check("A32 diag-built meta plus the real checker -> PASS", check_arrays(full, data2, CRIT)["verdict"] == "PASS")
    check("A32 probe report file is written", (root / "a32_probe_report.json").is_file())
    # each ingredient removed -> HOLD with its reason
    for key, want in (("isaac_version", "provenance_missing"), ("driver_version", "provenance_missing"),
                      ("asset_sha256", "provenance_missing"), ("root_sensor_offset_b", "provenance_missing"),
                      ("mesh_evidence_sha256", "provenance_missing"), ("collision_mesh_sha256", "provenance_missing")):
        m = dict(full); m[key] = "" if key != "root_sensor_offset_b" else None
        check("A32 meta without %s -> %s" % (key, want), want in reasons(m, data2))
    m = dict(full); m["mesh_collision_verified"] = False
    check("A32 mesh_collision_verified false -> case_assignment", "case_assignment" in reasons(m, data2))
    m = dict(full); m["boundary_count"] = full["boundary_count"] + 1
    check("A32 wrong boundary_count -> boundary_unreported", "boundary_unreported" in reasons(m, data2))
    unver = {"evidence": {**good, "kind": "unverified_collision_mesh"}, "errors": ["x"], "usd": None}
    root2 = Path(tempfile.mkdtemp(prefix="s2_a32_prov_"))
    prov2 = finalize_provenance(root2, data2, edge2, unver, versions, "a" * 64, [0.0, 0.0, 0.0])
    check("A32 unverified evidence leaves mesh_collision_verified false and the checker HOLDs",
          not prov2["mesh_collision_verified"] and "mesh_evidence_content" in reasons({**base_meta, **prov2}, data2))
    root3 = Path(tempfile.mkdtemp(prefix="s2_a32_prov_"))
    prov3 = finalize_provenance(root3, data2, edge2, {"evidence": None, "errors": ["usd_mesh_not_found"], "usd": None},
                                versions, "", [0.0, 0.0, 0.0])
    check("A32 no evidence at all: no mesh keys, checker HOLDs provenance_missing",
          "mesh_evidence_path" not in prov3 and "provenance_missing" in reasons({**base_meta, **prov3}, data2))
    # a pose that moves must make fixed_pose_verified false and the checker agree
    d = copy.deepcopy(data2); d["root_pos_w"][4, 1, 2] += .03; d["pos_w"][4, 1, 2] += .03
    prov4 = finalize_provenance(Path(tempfile.mkdtemp(prefix="s2_a32_prov_")), d, edge2, observed, versions, "a" * 64, [0., 0., 0.])
    check("A32 moving pose: flag false and the checker HOLDs fixed_pose_evidence",
          not prov4["fixed_pose_verified"] and "fixed_pose_evidence" in reasons({**base_meta, **prov4}, d))

    print("SUMMARY", "ALL PASS" if not FAILS else "FAIL %s" % FAILS)
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
