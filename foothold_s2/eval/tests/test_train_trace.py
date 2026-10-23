"""CPU known-input tests for the opt-in training trace observer."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from foothold_s2.eval.train_trace import (
    TRACE_FIELDS,
    TrainTraceObserver,
    TraceError,
    select_env_ids_by_terrain,
    should_capture_update,
    to_cpu_float32,
)


class FakeDeviceTensor:
    def __init__(self, values, events=None):
        self.values = np.asarray(values)
        self.events = events if events is not None else []
        self.requires_grad = True

    def detach(self):
        self.events.append("detach")
        result = FakeDeviceTensor(self.values.copy(), self.events)
        result.requires_grad = False
        return result

    def cpu(self):
        self.events.append("cpu")
        return self

    def numpy(self):
        self.events.append("numpy")
        return self.values


def fixture_fields(envs=8):
    fields = {}
    for offset, (name, shape) in enumerate(TRACE_FIELDS.items(), start=1):
        fields[name] = np.full((envs, *shape), offset, dtype=np.float64)
    fields["terrain_type"] = np.tile(np.array([0, 1], dtype=np.float64), envs // 2)
    fields["terrain_level"] = np.arange(envs, dtype=np.float64)
    fields["use_gt"] = np.arange(envs, dtype=np.float64) % 2
    fields["reset"] = np.zeros(envs, dtype=np.float64)
    fields["episode_id"] = np.ones(envs, dtype=np.float64)
    return fields


class TrainTraceTests(unittest.TestCase):
    def test_update_schedule_is_first_25_then_each_100(self):
        self.assertTrue(should_capture_update(0))
        self.assertTrue(should_capture_update(24))
        self.assertFalse(should_capture_update(25))
        self.assertFalse(should_capture_update(99))
        self.assertTrue(should_capture_update(100))
        self.assertTrue(should_capture_update(124))
        self.assertFalse(should_capture_update(125))

    def test_env_selection_is_deterministic_and_balanced_by_terrain(self):
        ids, labels = select_env_ids_by_terrain(np.array([0] * 8 + [1] * 8), 8)
        np.testing.assert_array_equal(ids, [0, 8, 1, 9, 2, 10, 3, 11])
        self.assertEqual(labels.count(0.0), 4)
        self.assertEqual(labels.count(1.0), 4)

    def test_tensor_conversion_detaches_moves_cpu_and_owns_float32_copy(self):
        events = []
        tensor = FakeDeviceTensor(np.arange(8, dtype=np.float64), events)
        copied = to_cpu_float32(tensor)
        self.assertEqual(copied.dtype, np.float32)
        self.assertFalse(np.shares_memory(copied, tensor.values))
        self.assertTrue(tensor.requires_grad)
        self.assertEqual(events, ["detach", "cpu", "numpy"])
        self.assertEqual(copied.tolist(), list(range(8)))

    def test_perception_tap_captures_real_inputs_and_trnet_outputs(self):
        class FakePerception:
            def _advance(self, h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map):
                return h_prop, h_terr, {
                    "rough": np.full((8, 32, 16), 0.1, dtype=np.float64),
                    "refined": np.full((8, 32, 16), 0.2, dtype=np.float64),
                }
            def step(self, state, inp, gt_map, deterministic=False):
                self._advance(None, None, inp["hist"], inp["depth2"], inp["tick"],
                              inp["first"], state.use_gt, gt_map)
                return np.zeros((8, 51), dtype=np.float32)

        with tempfile.TemporaryDirectory() as temp:
            observer = TrainTraceObserver(Path(temp) / "tap", "tapA", "training",
                                          np.tile([0, 1], 4), steps_per_update=1)
            perception = FakePerception()
            original_step, original_advance = perception.step, perception._advance
            observer.attach_perception(perception)
            observer.begin_update(0)
            fields = fixture_fields()
            state = type("State", (), {"use_gt": fields["use_gt"]})()
            inp = {"hist": np.zeros((8, 10, 45)), "depth2": fields["depth2"],
                   "tick": fields["tick"], "first": fields["first"]}
            perception.step(state, inp, fields["gt_map"])
            snapshot = observer.perception_snapshot
            self.assertEqual(snapshot["depth2"].shape, (8, 2, 60, 60))
            self.assertEqual(snapshot["refined_map"].shape, (8, 32, 16))
            fields.update(snapshot)
            for key in ("depth2", "tick", "first", "use_gt", "gt_map", "rough_map", "refined_map"):
                fields.pop(key, None)
            observer.capture_step(0, 0, fields)
            shard = observer.end_update(0)
            with np.load(observer.out_dir / shard["file"], allow_pickle=False) as archive:
                self.assertAlmostEqual(float(archive["refined_map"][0, 0, 0, 0]), 0.2)
            observer.close()
            self.assertEqual(perception.step.__func__, original_step.__func__)
            self.assertEqual(perception._advance.__func__, original_advance.__func__)

    def test_complete_update_writes_atomic_shard_and_hash_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "trace"
            observer = TrainTraceObserver(out, "runA", "training", np.tile([0, 1], 4),
                                          steps_per_update=2, step_dt_s=0.02)
            self.assertTrue(observer.begin_update(0))
            self.assertTrue(observer.capture_step(0, 0, fixture_fields()))
            self.assertTrue(observer.capture_step(0, 1, fixture_fields()))
            shard = observer.end_update(0)
            self.assertEqual(shard["status"], "complete")
            shard_path = out / shard["file"]
            self.assertEqual(shard["sha256"], hashlib.sha256(shard_path.read_bytes()).hexdigest())
            with np.load(shard_path, allow_pickle=False) as archive:
                self.assertEqual(archive["depth2"].shape, (2, 8, 2, 60, 60))
                self.assertEqual(archive["gt_map"].shape, (2, 8, 32, 16))
                self.assertTrue(all(archive[key].dtype == np.float32 for key in archive.files))
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["source"], "training")
            self.assertEqual(manifest["shards"][0]["sha256"], shard["sha256"])
            observer.close()
            self.assertEqual(json.loads((out / "manifest.json").read_text())["status"], "closed")

    def test_replay_label_and_partial_capture_remain_distinct_and_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "replay"
            observer = TrainTraceObserver(out, "evalA", "replay_evaluation", np.tile([2, 3], 4),
                                          steps_per_update=2, step_dt_s=0.02)
            observer.capture_step(0, 0, fixture_fields())
            shard = observer.end_update(0)
            self.assertEqual(shard["status"], "incomplete")
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["source"], "replay_evaluation")
            self.assertEqual(manifest["windows"]["0"]["status"], "incomplete")
            self.assertEqual(manifest["shards"][0]["steps_observed"], 1)

    def test_full_two_update_fixture_window_is_complete_only_after_both_updates(self):
        with tempfile.TemporaryDirectory() as temp:
            observer = TrainTraceObserver(Path(temp) / "complete", "cpuA", "synthetic_known_input",
                                          np.tile([0, 1], 4), steps_per_update=1, step_dt_s=0.02,
                                          window_updates=2, stride_updates=2)
            for update in range(2):
                observer.capture_step(update, 0, fixture_fields())
                observer.end_update(update)
            manifest = json.loads((observer.out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["windows"]["0"]["status"], "complete")

    def test_noncontiguous_steps_and_unsafe_mode_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(TraceError):
                TrainTraceObserver(Path(temp) / "bad", "x", "unknown", np.tile([0, 1], 4))
            observer = TrainTraceObserver(Path(temp) / "valid", "x", "training", np.tile([0, 1], 4),
                                          steps_per_update=2)
            with self.assertRaises(TraceError):
                observer.capture_step(0, 1, fixture_fields())


if __name__ == "__main__":
    unittest.main()
