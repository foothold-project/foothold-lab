"""CPU counterexamples for reset interception and case fingerprints."""
from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace

import numpy as np

from s2_eval_pre_reset import PreResetStep, PreResetHold
from s2_eval_case_fingerprint import (assign_one_case, case_row, tile_mesh_sha,
                                      initial_state_sha, case_fingerprint, FingerprintHold)
from s2_eval_driver import _state, EvalHold


class FakeRaw:
    def __init__(self):
        self.state = [dict(pos=[1., 0., .4], term=False), dict(pos=[2., 0., .5], term=False)]

    def _reset_idx(self, ids):
        for i in ids:
            self.state[i] = dict(pos=[0., 0., .7], term=False)


class FakeWrapped:
    def __init__(self, raw):
        self.raw = raw

    def step(self, action):
        self.raw.state[0] = dict(pos=[4., 0., .1], term=True)
        self.raw.state[1] = dict(pos=[2.1, 0., .5], term=False)
        self.raw._reset_idx([0])
        return "post_reset_obs", None, [True, False], {}


class TestHooks(unittest.TestCase):
    def test_pre_reset_and_other_env_unchanged(self):
        raw = FakeRaw()
        hook = PreResetStep(FakeWrapped(raw), raw, lambda: copy.deepcopy(raw.state), num_envs=2)
        _, _, done, first, _, receipt = hook.step_recorded(None, env_index=0)
        self.assertTrue(done)
        self.assertEqual(first["pos"], [4., 0., .1])
        self.assertEqual(raw.state[0]["pos"], [0., 0., .7])
        self.assertEqual(raw.state[1]["pos"], [2.1, 0., .5])
        self.assertEqual(receipt["reset_env_ids"], [0])
        self.assertNotIn("_reset_idx", vars(raw))

    def test_reset_ids_mismatch_is_hold(self):
        raw = FakeRaw()
        class Mismatch(FakeWrapped):
            def step(self, action):
                self.raw._reset_idx([0])
                return None, None, [False, True], {}
        with self.assertRaisesRegex(PreResetHold, "reset_ids_vs_done"):
            PreResetStep(Mismatch(raw), raw, lambda: copy.deepcopy(raw.state), num_envs=2).step_recorded(None, env_index=0)
        self.assertNotIn("_reset_idx", vars(raw))

    def test_tile_scope_and_case_row(self):
        mesh = {"prim_path": "/World/ground/mesh", "points": [[0, 0, 0], [1, 0, 0], [0, 1, 0],
                [10, 0, 0], [11, 0, 0], [10, 1, 0]], "faces": [[0, 1, 2], [3, 4, 5]]}
        a = tile_mesh_sha([mesh], center_xy=(0, 0), size_xy=(4, 4))
        b = tile_mesh_sha([mesh], center_xy=(10, 0), size_xy=(4, 4))
        self.assertNotEqual(a, b)
        case = {"case_id": "gap-009-s123", "eval_seed": 123}
        self.assertEqual(case_row(case), 1)
        terrain = SimpleNamespace(terrain_origins=np.arange(24, dtype=float).reshape(8, 1, 3),
                terrain_types=np.array([9]), terrain_levels=np.array([9]),
                env_origins=np.zeros((1, 3)))
        self.assertEqual(assign_one_case(terrain, case)["terrain_row"], 1)
        self.assertEqual(terrain.terrain_levels.tolist(), [1])

    def test_initial_state_and_pair_mutation(self):
        args = dict(root_state_w=np.arange(13), joint_pos=[0., 1.], joint_vel=[0., 0.],
                    body_masses=[1., 2.], body_materials=[1., 1.],
                    actuator_state={"stiffness": [20.]}, command=[1., 0., 0.],
                    physics_dt=.005, policy_dt=.02)
        first, payload = initial_state_sha(**args)
        self.assertEqual(initial_state_sha(**args)[0], first)
        args["body_materials"] = [.7, 1.]
        self.assertNotEqual(initial_state_sha(**args)[0], first)
        with self.assertRaisesRegex(FingerprintHold, "actuator_state_missing"):
            initial_state_sha(**{**args, "actuator_state": {}})

    def test_contact_final_state_receipt(self):
        physical = {"pos": [1., 0., .1], "yaw": 0., "vb": [0., 0., 0.],
                    "wb": [0., 0., 0.], "grav_z": -1., "hag": .1, "term": True,
                    "contact_force_max_n": 14., "contact_forces_sha256": "a"*64}
        self.assertEqual(_state(physical)["contact_force_max_n"], 14.)
        with self.assertRaisesRegex(EvalHold, "contact_physical_state"):
            _state({**physical, "contact_forces_sha256": "bad"})


if __name__ == "__main__":
    unittest.main()
