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
    select_batch_rows_to_cpu_float32,
    should_capture_update,
    to_cpu_float32,
)


class FakeDeviceTensor:
    def __init__(self, values, events=None):
        self.values = np.asarray(values)
        self.events = events if events is not None else []
        self.requires_grad = True
        self.device = "cpu"
        self.shape = self.values.shape

    def detach(self):
        self.events.append("detach")
        result = FakeDeviceTensor(self.values.copy(), self.events)
        result.requires_grad = False
        return result

    def cpu(self):
        self.events.append("cpu")
        return self

    def index_select(self, dim, indices):
        self.events.append("index_select")
        result = FakeDeviceTensor(np.take(self.values, indices.numpy(), axis=dim), self.events)
        result.requires_grad = False
        return result

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

    def test_full_batch_tensor_is_indexed_before_cpu_and_copies_only_selected_rows(self):
        events = []
        source = FakeDeviceTensor(np.arange(3072 * 3, dtype=np.float32).reshape(3072, 3), events)
        selected = select_batch_rows_to_cpu_float32(source, np.array([5, 100, 3071]), 3072,
                                                     (3,), "root_pos_w")
        self.assertEqual(selected.shape, (3, 3))
        self.assertEqual(events, ["detach", "index_select", "cpu", "numpy"])
        np.testing.assert_array_equal(selected[:, 0], [15, 300, 9213])

    def test_full_3072_env_torch_batch_selects_eight_and_preserves_rng_and_output(self):
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")
        num_envs = 3072
        labels = torch.repeat_interleave(torch.arange(6, dtype=torch.float32), num_envs // 6)
        with tempfile.TemporaryDirectory() as temp:
            observer = TrainTraceObserver(Path(temp) / "full", "full3072", "synthetic_known_input",
                                          labels, steps_per_update=1)
            self.assertEqual(len(observer.env_ids), 8)
            self.assertEqual(observer.num_envs, 3072)
            self.assertEqual(observer.sample_terrain_types, [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 0.0, 1.0])
            ids = torch.arange(num_envs, dtype=torch.float32)
            fields = {}
            for offset, (name, trailing_shape) in enumerate(TRACE_FIELDS.items(), start=1):
                expanded_shape = (num_envs, *trailing_shape)
                view = ids.reshape(num_envs, *([1] * len(trailing_shape))).expand(expanded_shape)
                fields[name] = view + offset * 10000.0
            # Keep terrain labels meaningful while every row remains distinguishable.
            fields["terrain_type"] = labels
            expected = fields["root_pos_w"][torch.as_tensor(observer.env_ids)]
            policy_before = fields["root_pos_w"] * 2.0 + fields["command"]
            rng_before = torch.random.get_rng_state().clone()
            observer.begin_update(0)
            observer.capture_step(0, 0, fields)
            rng_after = torch.random.get_rng_state()
            self.assertTrue(torch.equal(rng_before, rng_after))
            policy_after = fields["root_pos_w"] * 2.0 + fields["command"]
            self.assertTrue(torch.equal(policy_before, policy_after))
            self.assertTrue(torch.equal(fields["root_pos_w"], ids[:, None].expand(num_envs, 3) + 10000.0 +
                                        list(TRACE_FIELDS).index("root_pos_w") * 10000.0))
            shard = observer.end_update(0)
            with np.load(observer.out_dir / shard["file"], allow_pickle=False) as archive:
                root = archive["root_pos_w"][0]
                self.assertEqual(root.shape, (8, 3))
                np.testing.assert_array_equal(root[:, 0], expected[:, 0].numpy())
                np.testing.assert_array_equal(root[:, 1], expected[:, 1].numpy())
                self.assertEqual(archive["depth2"].shape, (1, 8, 2, 60, 60))
                self.assertEqual(archive["terrain_type"].shape, (1, 8))
            observer.close()

    def test_perception_tap_captures_real_inputs_and_trnet_outputs(self):
        depth_events = []
        rough_events = []
        refined_events = []
        class FakePerception:
            def _advance(self, h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map):
                return h_prop, h_terr, {
                    "rough": FakeDeviceTensor(np.full((8, 32, 16), 0.1), rough_events),
                    "refined": FakeDeviceTensor(np.full((8, 32, 16), 0.2), refined_events),
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
            fields["depth2"] = FakeDeviceTensor(fields["depth2"], depth_events)
            state = type("State", (), {"use_gt": fields["use_gt"]})()
            inp = {"hist": np.zeros((8, 10, 45)), "depth2": fields["depth2"],
                   "tick": fields["tick"], "first": fields["first"]}
            perception.step(state, inp, fields["gt_map"])
            snapshot = observer.perception_snapshot
            self.assertIs(snapshot["depth2"], fields["depth2"])
            self.assertEqual(snapshot["depth2"].shape, (8, 2, 60, 60))
            self.assertEqual(snapshot["refined_map"].shape, (8, 32, 16))
            self.assertEqual(depth_events + rough_events + refined_events, [])
            fields.update(snapshot)
            for key in ("depth2", "tick", "first", "use_gt", "gt_map", "rough_map", "refined_map"):
                fields.pop(key, None)
            observer.capture_step(0, 0, fields)
            self.assertEqual(depth_events, ["detach", "index_select", "cpu", "numpy"])
            self.assertEqual(rough_events, ["detach", "index_select", "cpu", "numpy"])
            self.assertEqual(refined_events, ["detach", "index_select", "cpu", "numpy"])
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
