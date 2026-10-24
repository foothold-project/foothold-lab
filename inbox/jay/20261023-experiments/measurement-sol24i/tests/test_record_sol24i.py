"""CPU known-answer and mutation checks for the guarded SOL-24i recorder."""

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np


SOURCE = Path(__file__).resolve().parents[1] / "record_sol24i.py"
SPEC = importlib.util.spec_from_file_location("record_sol24i", SOURCE)
assert SPEC and SPEC.loader
rec = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rec)


class FakeSim:
    def __init__(self):
        self.current_time = 1.25
        self.render_count = 0
        self.on_render = lambda: None

    def render(self):
        self.render_count += 1
        self.on_render()


class FakeRaw:
    def __init__(self, frames):
        self.sim = FakeSim()
        self.common_step_counter = 37
        self.frames = iter(frames)
        self.render_calls = []

    def render(self, recompute=False):
        self.render_calls.append(recompute)
        return next(self.frames)


def fixture(frames):
    raw = FakeRaw(frames)
    robot = SimpleNamespace(data=SimpleNamespace(
        root_pos_w=np.array([[1.0, 2.0, 0.4]]),
        root_quat_w=np.array([[1.0, 0.0, 0.0, 0.0]]),
        root_lin_vel_b=np.array([[0.1, 0.0, 0.0]]),
        root_ang_vel_b=np.array([[0.0, 0.0, 0.2]])))
    command = SimpleNamespace(commands=np.array([[0.5, 0.0, 0.0]]))
    sensor = SimpleNamespace(_timestamp=np.array([1.25]),
                             _timestamp_last_update=np.array([1.24]))
    return raw, robot, command, sensor


BLACK = np.zeros((4, 6, 3), dtype=np.uint8)
BRIGHT = np.full((4, 6, 3), 90, dtype=np.uint8)


class GuardedRenderTests(unittest.TestCase):
    def test_black_then_bright_uses_sim_render_without_physics_step(self):
        raw, robot, command, sensor = fixture([BLACK, BRIGHT])
        frame, checks = rec.render_frame_guarded(raw, robot, command, sensor)
        np.testing.assert_array_equal(frame, BRIGHT)
        self.assertEqual(raw.sim.render_count, 1)
        self.assertEqual(raw.render_calls, [False, True])
        self.assertEqual(raw.common_step_counter, 37)
        self.assertEqual(checks[0]["before"], checks[0]["after"])
        self.assertEqual(checks[0]["before"]["sim_time_s"], 1.25)
        self.assertEqual(checks[0]["before"]["contact_timestamp"], [1.25])
        self.assertNotIn("app.update()", inspect.getsource(rec.render_frame_guarded))

    def test_bright_first_avoids_extra_render(self):
        raw, robot, command, sensor = fixture([BRIGHT])
        _frame, checks = rec.render_frame_guarded(raw, robot, command, sensor)
        self.assertEqual(checks, [])
        self.assertEqual(raw.sim.render_count, 0)

    def test_persistent_black_fails_before_success_metadata(self):
        raw, robot, command, sensor = fixture([BLACK] * 3)
        with self.assertRaisesRegex(RuntimeError, 'render_still_dark.*"retry_count": 2'):
            rec.render_frame_guarded(raw, robot, command, sensor, max_retries=2)
        source = inspect.getsource(rec._capture)
        self.assertLess(source.index("render_frame_guarded("),
                        source.index("_json_atomic(output.with_suffix"))

    def test_each_state_mutation_is_first_failure_with_evidence(self):
        mutations = {
            "sim_time_s": lambda r, b, c, s: setattr(r.sim, "current_time", 1.27),
            "env_step": lambda r, b, c, s: setattr(r, "common_step_counter", 38),
            "root_pos_w": lambda r, b, c, s: b.data.root_pos_w.__setitem__((0, 0), 9.0),
            "command": lambda r, b, c, s: c.commands.__setitem__((0, 0), 1.0),
            "contact_timestamp": lambda r, b, c, s: s._timestamp.__setitem__(0, 1.27),
        }
        for field, mutate in mutations.items():
            with self.subTest(field=field):
                raw, robot, command, sensor = fixture([BLACK, BRIGHT])
                raw.sim.on_render = lambda: mutate(raw, robot, command, sensor)
                with self.assertRaisesRegex(RuntimeError, "render_state_changed") as caught:
                    rec.render_frame_guarded(raw, robot, command, sensor)
                evidence = json.loads(str(caught.exception).split(" ", 1)[1])
                self.assertEqual(evidence["changed"], [field])
                self.assertNotEqual(evidence["before"][field], evidence["after"][field])

    def test_contract_retains_600_ticks_300_frames_and_commands(self):
        self.assertEqual(rec.step_contract(0.02)["physics_steps"], 600)
        self.assertEqual(rec.step_contract(0.02)["video_frames"], 300)
        self.assertEqual([row[1] for row in rec.COMMANDS],
                         [(0.5, 0.0, 0.0), (1.0, 0.0, 0.0),
                          (0.0, 0.0, 1.2), (0.0, 0.0, -1.2)])


if __name__ == "__main__":
    unittest.main()
