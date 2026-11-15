"""Known-answer CPU connection and staged gate tests. No Isaac import."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

import numpy as np
import torch

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from s2_connect_check import CASES, Criteria, check_arrays, check_path
from s2_connect_diag import capture
from s2_env_config import EnvironmentSpec, configure_env
from s2_stage_gate import claim_once, digest, frozen_digest, verdict
sys.path.insert(0, str(HERE.parent / "s2_step2"))
from s2_env_adapter import expected_world_xy
from base_step1.s2_map_obs import height_and_mask


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label, flush=True)
    if not condition:
        raise AssertionError(label)


def fixture():
    criteria = Criteria(.001, .001, .001, .1, 2, 4, .06, 3, 3, 1.0)
    pos = np.zeros((5, 2, 1, 3), np.float32)
    pos[..., 2] = 1.0
    root = pos.copy()
    origin = np.zeros_like(pos)
    quat = np.zeros((5, 2, 1, 4), np.float32)
    quat[..., 0] = 1.0
    quat[1, ..., 0] = math.sqrt(.5)
    quat[1, ..., 3] = math.sqrt(.5)
    hits = np.empty((5, 2, 1, 187, 3), np.float32)
    for case in range(5):
        yaw = torch.full((1,), math.pi/2 if case == 1 else 0, dtype=torch.float32)
        xy = expected_world_xy(torch.tensor([[0., 0., 1.]]), yaw).numpy()[0]
        hits[case, :, 0, :, :2] = xy
        hits[case, :, 0, :, 2] = .5
    hits[2, :, 0, 93, 2] = .7
    hits[3, :, 0, [92, 93], :] = math.inf
    for idx in (3, 6, 9, 12):
        hits[4, :, 0, 5*17+idx, :] = math.inf
    hits[4, :, 0, 5*17+4, 2] = .54
    flat_pos = torch.as_tensor(pos.reshape(-1, 3))
    flat_hit = torch.as_tensor(hits.reshape(-1, 187, 3))
    height, mask, faults = height_and_mask(flat_pos, flat_hit, strict=True)
    assert faults.total == 0
    arrays = {"pos_w": pos, "ray_hits_w": hits, "root_pos_w": root, "root_quat_w": quat,
              "env_origin_w": origin, "height": height.numpy().reshape(5, 2, 1, 187),
              "mask": mask.numpy().reshape(5, 2, 1, 187),
              "episode_ids": np.ones((5, 2, 1), np.int64),
              "frame_tokens": np.broadcast_to(np.array([0, 4])[None, :, None], (5, 2, 1)).copy(),
              "reset_receipt": np.ones((5, 1), np.int64)}
    meta = {"cases": list(CASES), "isaac_version": "synthetic", "torch_version": torch.__version__,
            "driver_version": "synthetic", "env_config_sha256": "a"*64, "code_sha256": "b"*64,
            "parent_sha256": "c"*64, "capture_sha256": "fixture", "reset_evidence": "sensor_timestamp",
            "terrain_assignment_verified": True}
    return meta, arrays, criteria


def write_capture(root, meta, arrays):
    root.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(root / "capture.npz", **arrays)
    meta = copy.deepcopy(meta)
    meta["capture_sha256"] = digest(root / "capture.npz")
    (root / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def stage_fixture(root, meta, arrays, criteria):
    capture_root = root / "connect"
    write_capture(capture_root, meta, arrays)
    manifest = {"inputs": {"parent_sha256": "c"*64, "code_sha256": "b"*64,
                           "env_config_sha256": "a"*64},
                "stages": {"connect": {"max_launches": 1, "max_wall_s": 10, "diag_steps": 4},
                           "smoke": {"max_launches": 2, "max_wall_s": 10, "updates_per_arm": 2,
                                     "epochs": 2, "minibatches": 2},
                           "short_ab": {"max_launches": 2, "max_wall_s": 10, "updates_per_arm": 2,
                                        "epochs": 2, "minibatches": 2}},
                "criteria": vars(criteria), "stop_file": str(root / "STOP"), "deadline_epoch": 200.,
                "approval": {"status": "APPROVED", "by": "synthetic-fixture", "frozen_sha256": None}}
    manifest["approval"]["frozen_sha256"] = frozen_digest(manifest)
    rec = {"stage": "connect", "attempt": "c1", "launches": 1, "wall_s": 2,
           "exit_code": 0, "traceback": False, "log_tail": "ok",
           "parent_sha256": "c"*64, "code_sha256": "b"*64, "env_config_sha256": "a"*64,
           "artifacts": {"connect_meta": {"path": str(capture_root / "meta.json"),
                                          "sha256": digest(capture_root / "meta.json")},
                         "connect_npz": {"path": str(capture_root / "capture.npz"),
                                         "sha256": digest(capture_root / "capture.npz")}}}
    return manifest, rec


def train_result(arm):
    return {"arm": arm, "status": "PASS", "fault_counts": {}, "discarded_transitions": 0,
            "nonfinite_count": 0, "map_time_valid": True, "executed_updates": 2,
            "planned_updates": 2, "optimizer_steps_actual": 8, "optimizer_steps_expected": 8,
            "encounters_verified": True, "device_peak_mib": 100, "device_min_free_mib": 100,
            "iterations_per_hour": 100}


def train_record(root, previous):
    artifacts = {}
    for arm in ("A", "B"):
        rp, lp = root / f"{arm}.json", root / f"{arm}.log"
        rp.write_text(json.dumps(train_result(arm)), encoding="utf-8")
        lp.write_text("valid\n", encoding="utf-8")
        artifacts[f"{arm}_result"] = {"path": str(rp), "sha256": digest(rp)}
        artifacts[f"{arm}_log"] = {"path": str(lp), "sha256": digest(lp)}
    prev_sha = hashlib.sha256(json.dumps(previous, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"attempt": "t1", "launches": 2, "wall_s": 2, "exit_code": 0,
            "traceback": False, "log_tail": "ok", "previous_sha256": prev_sha,
            "parent_sha256": "c"*64, "code_sha256": "b"*64, "env_config_sha256": "a"*64,
            "artifacts": artifacts}


def tests():
    meta, arrays, criteria = fixture()
    class Provider:
        def __init__(self, kind, spec, yaw):
            self.case = CASES.index(kind)
            self.t = 0
        def reset(self): self.t = 0
        def step_zero(self): self.t = 1
        def sample(self):
            row = {k: arrays[k][self.case, self.t].copy() for k in
                   ("pos_w", "ray_hits_w", "root_pos_w", "root_quat_w", "env_origin_w",
                    "height", "mask", "episode_ids", "frame_tokens")}
            row["reset_receipt"] = arrays["reset_receipt"][self.case].copy()
            return row
        def close(self): pass
    spec = EnvironmentSpec(11, 1, .1, .2, .1, .5, .01)
    captured = capture(Provider, spec=spec, steps=4, reset_yaw_rad=math.pi/2)
    check("diagnostic capture two instants five cases", all(np.array_equal(captured[k], arrays[k]) for k in arrays))
    sub = {k: SimpleNamespace(proportion=v) for k, v in
           (("flat", .5), ("obstacles", .3), ("gap", 0.), ("stepping_stones", .2))}
    terrain = SimpleNamespace(sub_terrains=sub, curriculum=True, num_rows=10, num_cols=20)
    base = SimpleNamespace(seed=0, scene=SimpleNamespace(num_envs=8,
        terrain=SimpleNamespace(terrain_generator=terrain, max_init_terrain_level=3)),
        curriculum=SimpleNamespace(terrain_levels=object()),
        events=SimpleNamespace(reset_base=SimpleNamespace(params={"pose_range": {"x": (-1,1)}})))
    train_cfg = configure_env(base, spec, diagnostic_kind=None, reset_yaw_rad=None)
    diag_cfg = configure_env(base, spec, diagnostic_kind="step", reset_yaw_rad=0.)
    check("same S2 overlay builder and parent untouched",
          train_cfg.scene.terrain.terrain_generator.sub_terrains["gap"].proportion == .1 and
          diag_cfg.scene.terrain.terrain_generator.sub_terrains["obstacles"].num_obstacles == 1 and
          base.scene.terrain.terrain_generator.sub_terrains["gap"].proportion == 0.)
    check("connection known flat step gap stones yaw", check_arrays(meta, arrays, criteria)["verdict"] == "PASS")
    mutations = (
        ("origin_missing", lambda m, a: a["env_origin_w"].__setitem__((0, 0, 0, 0), np.nan)),
        ("reset_stale", lambda m, a: a["frame_tokens"].__setitem__((0, 1, 0), 0)),
        ("sensor_nonfinite", lambda m, a: a["pos_w"].__setitem__((0, 0, 0, 2), np.nan)),
        ("ray_packet_bad", lambda m, a: a["ray_hits_w"].__setitem__((0, 0, 0, 0, 2), np.nan)),
        ("grid_order_or_yaw", lambda m, a: a["ray_hits_w"].__setitem__((0, 0, 0, 0, 0), 9.)),
        ("yaw_probe_missing", lambda m, a: a["root_quat_w"].__setitem__((1, slice(None), slice(None), slice(None)), np.array([1, 0, 0, 0]))),
        ("height_or_offset", lambda m, a: a["height"].__setitem__((0, 0, 0, 0), 1.)),
        ("flat_not_flat", lambda m, a: a["ray_hits_w"].__setitem__((0, 0, 0, 0, 2), .8)),
        ("step_not_seen", lambda m, a: a["ray_hits_w"].__setitem__((2, slice(None), 0, 93, 2), .5)),
        ("gap_not_seen", lambda m, a: a["ray_hits_w"].__setitem__(3, a["ray_hits_w"][0])),
        ("stones_not_seen", lambda m, a: a["ray_hits_w"].__setitem__(4, a["ray_hits_w"][0])),
        ("stones_spacing", lambda m, a: a["ray_hits_w"].__setitem__((4, slice(None), 0, 5*17+6, slice(None)),
                                                                     a["ray_hits_w"][0, :, 0, 5*17+6, :])),
        ("provenance_missing", lambda m, a: m.__setitem__("driver_version", None)),
        ("terrain_assignment_missing", lambda m, a: m.__setitem__("terrain_assignment_verified", False)),
    )
    for want, mutate in mutations:
        m, a = copy.deepcopy(meta), copy.deepcopy(arrays)
        mutate(m, a)
        result = check_arrays(m, a, criteria)
        check("connection counterexample " + want, result["verdict"] == "HOLD" and want in result["reasons"])
    with tempfile.TemporaryDirectory(prefix="s2_step3_") as tmp:
        root = Path(tmp)
        manifest, rec = stage_fixture(root, meta, arrays, criteria)
        connect = verdict(manifest, "connect", rec, now_epoch=100.)
        check("connect gate pass and next args", connect["verdict"] == "PASS" and
              connect["next_args"]["stage"] == "smoke")
        train = train_record(root, connect)
        smoke = verdict(manifest, "smoke", train, previous=connect, now_epoch=100.)
        check("smoke A B pass and next args", smoke["verdict"] == "PASS" and
              smoke["next_args"]["stage"] == "short_ab")
        short = copy.deepcopy(train)
        short["attempt"] = "t2"
        short["previous_sha256"] = hashlib.sha256(json.dumps(smoke, sort_keys=True,
                separators=(",", ":")).encode()).hexdigest()
        check("short A B final pass", verdict(manifest, "short_ab", short, previous=smoke,
                                              now_epoch=100.)["verdict"] == "PASS")
        for want, change in (
            ("approval_unbound", lambda m, r: m["approval"].__setitem__("status", "UNDECIDED")),
            ("manifest_unfrozen", lambda m, r: m["stages"]["smoke"].__setitem__("updates_per_arm", None)),
            ("previous_hash", lambda m, r: r.__setitem__("previous_sha256", "0"*64)),
            ("attempt_reused", lambda m, r: None),
            ("budget", lambda m, r: r.__setitem__("wall_s", 11)),
            ("exit_code", lambda m, r: r.__setitem__("exit_code", 42)),
            ("traceback", lambda m, r: r.__setitem__("log_tail", "Traceback (most recent call last)")),
            ("artifact_missing", lambda m, r: r["artifacts"].pop("A_log")),
            ("artifact_hash", lambda m, r: r["artifacts"]["A_log"].__setitem__("sha256", "0"*64)),
            ("fingerprint", lambda m, r: r.__setitem__("code_sha256", "0"*64)),
            ("deadline", lambda m, r: m.__setitem__("deadline_epoch", 99.)),
        ):
            m, r = copy.deepcopy(manifest), copy.deepcopy(train)
            change(m, r)
            seen = ("t1",) if want == "attempt_reused" else ()
            got = verdict(m, "smoke", r, previous=connect, seen_attempts=seen, now_epoch=100.)
            check("stage counterexample " + want, got["verdict"] == "HOLD" and want in got["reasons"])
        no_previous = verdict(manifest, "smoke", train, previous=None, now_epoch=100.)
        check("stage counterexample previous_missing", "previous_missing" in no_previous["reasons"])
        (root / "STOP").write_text("stop", encoding="utf-8")
        stopped = verdict(manifest, "smoke", train, previous=connect, now_epoch=100.)
        check("stage counterexample stop_file", "stop_file" in stopped["reasons"])
        (root / "STOP").unlink()
        bad_meta = copy.deepcopy(meta)
        bad_meta["driver_version"] = None
        bad_root = root / "bad_connect"
        write_capture(bad_root, bad_meta, arrays)
        bad_rec = copy.deepcopy(rec)
        for key, file in (("connect_meta", "meta.json"), ("connect_npz", "capture.npz")):
            bad_rec["artifacts"][key] = {"path": str(bad_root / file), "sha256": digest(bad_root / file)}
        bad_connect = verdict(manifest, "connect", bad_rec, now_epoch=100.)
        check("stage counterexample connect_hold", "connect_hold" in bad_connect["reasons"])
        for want, edit in (
            ("train_hold", lambda x: x.__setitem__("status", "HOLD")),
            ("fault_count", lambda x: x.__setitem__("fault_counts", {"ray_packet_bad": 1})),
            ("nonfinite", lambda x: x.__setitem__("nonfinite_count", 1)),
            ("map_time", lambda x: x.__setitem__("map_time_valid", False)),
            ("step_count", lambda x: x.__setitem__("optimizer_steps_actual", 7)),
            ("encounter_missing", lambda x: x.__setitem__("encounters_verified", False)),
            ("device_metrics", lambda x: x.__setitem__("device_peak_mib", None)),
        ):
            r = copy.deepcopy(train)
            file = root / "A_changed.json"
            x = train_result("A")
            edit(x)
            file.write_text(json.dumps(x), encoding="utf-8")
            r["artifacts"]["A_result"] = {"path": str(file), "sha256": digest(file)}
            got = verdict(manifest, "smoke", r, previous=connect, now_epoch=100.)
            check("stage result counterexample " + want, got["verdict"] == "HOLD" and want in got["reasons"])
        c = claim_once(root / "claims", "smoke", "once")
        try: claim_once(root / "claims", "smoke", "once")
        except FileExistsError: duplicate = True
        else: duplicate = False
        check("single claim rejects reuse", c.is_dir() and duplicate)


if __name__ == "__main__":
    tests()
