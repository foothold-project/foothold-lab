"""Known-input CPU tests for the SOL-23f recorder's portable contract."""

from types import SimpleNamespace
from contextlib import redirect_stdout
import io
import unittest

import numpy as np

from foothold_s2.eval.record_sol23f import (
    COMMANDS,
    configure_physics_mode,
    configure_topdown_evaluation,
    height_map_display,
    physics_actual_readback,
    pin_segment_command,
    preload_kit_dependencies,
    exit_after_flush,
    apply_map_mode,
    assert_map_mode,
    frame_steps,
    main,
    parse_spec,
    step_contract,
    termination_record,
    validate_depth_delay,
)


class FakePolicy:
    def __init__(self, force_gt: bool):
        flags = np.full((1,), force_gt, dtype=np.bool_)
        self.pstate = SimpleNamespace(use_gt=flags)
        self.no_gt = flags.copy()

    def reset(self, _dones):
        self.pstate.use_gt[:] = self.no_gt


class RecorderContractTests(unittest.TestCase):
    def test_topdown_keeps_generator_curriculum_but_freezes_env_level(self):
        cfg = SimpleNamespace(scene=SimpleNamespace(terrain=SimpleNamespace(
            terrain_generator=SimpleNamespace(curriculum=False))),
            curriculum=SimpleNamespace(terrain_levels="enabled"))
        augmentation = SimpleNamespace(enabled=True)
        configure_topdown_evaluation(cfg, augmentation)
        self.assertTrue(cfg.scene.terrain.terrain_generator.curriculum)
        self.assertIsNone(cfg.curriculum.terrain_levels)
        self.assertFalse(augmentation.enabled)

    def test_tensordict_precedes_kit_import(self):
        calls = []
        preload_kit_dependencies(lambda name: calls.append("preload:" + name),
                                 lambda: calls.append("kit"))
        self.assertEqual(calls, ["preload:tensordict", "kit"])

    def test_segment_command_survives_reset_and_resampling(self):
        class FakeTerm:
            def __init__(self):
                self.cfg = SimpleNamespace(fixed_cmd=None, resampling_time_range=(4.0, 4.0))
                self.commands = np.zeros((1, 3), dtype=np.float32)
            def reset(self):
                self.commands[0] = self.cfg.fixed_cmd
            def resample(self):
                self.commands[0] = self.cfg.fixed_cmd
        term = FakeTerm()
        cfg = SimpleNamespace(fixed_cmd=None, resampling_time_range=(4.0, 4.0))
        pin_segment_command(cfg, term, (0.5, 0.0, 0.0))
        term.reset()
        np.testing.assert_allclose(term.commands[0], [0.5, 0, 0])
        term.resample()
        np.testing.assert_allclose(term.commands[0], [0.5, 0, 0])
        self.assertGreater(cfg.resampling_time_range[0], 12.0)

    def test_fixed_physics_disables_randomizers_and_training_preserves_config(self):
        cfg = SimpleNamespace(events=SimpleNamespace(
            physics_material=SimpleNamespace(params={"static_friction_range": (0.2, 1.2), "dynamic_friction_range": (0.2, 1.2)}),
            add_base_mass=object(), base_com=object(), actuator_gains=object(), motor_strength=object()),
            actions=SimpleNamespace(joint_pos=SimpleNamespace(max_delay_s=0.2)))
        record = configure_physics_mode(cfg, "fixed")
        self.assertEqual(cfg.events.physics_material.params["static_friction_range"], (0.8, 0.8))
        self.assertIsNone(cfg.events.add_base_mass)
        self.assertEqual(cfg.actions.joint_pos.max_delay_s, 0.0)
        self.assertEqual(record["mode"], "fixed")
        training_cfg = SimpleNamespace(events=SimpleNamespace(base_com=object()))
        original = training_cfg.events.base_com
        configure_physics_mode(training_cfg, "training")
        self.assertIs(training_cfg.events.base_com, original)

    def test_live_physics_readback_prefers_runtime_values(self):
        robot = SimpleNamespace(
            data=SimpleNamespace(root_mass_w=np.array([[12.4]]), root_com_pos_b=np.array([[0.0, 0.0, 0.1]])),
            root_physx_view=SimpleNamespace(get_masses=lambda: np.array([[12.4]]),
                                            get_material_properties=lambda: np.array([[[0.8, 0.6, 0.0]]])),
            actuators={"legs": SimpleNamespace(stiffness=np.full((1, 12), 25.0),
                                                 damping=np.full((1, 12), 0.5))})
        actual = physics_actual_readback(SimpleNamespace(scene={"robot": robot}))
        self.assertEqual(actual["mass"], [[12.4]])
        self.assertEqual(actual["material"], [[[0.8, 0.6, 0.0]]])
        self.assertEqual(actual["stiffness"][0][0], 25.0)
        self.assertEqual(actual["damping"][0][0], 0.5)

    def test_height_maps_share_32_by_16_scale_and_depth_is_separate(self):
        maps = height_map_display(np.zeros((60, 60)), np.arange(512),
                                  np.arange(512) * 0.5, np.arange(512) * 0.25)
        self.assertEqual(maps["gt"].shape, (32, 16))
        self.assertEqual(maps["rough"].shape, (32, 16))
        self.assertEqual(maps["refined"].shape, (32, 16))
        self.assertEqual(maps["depth"].shape, (60, 60))
        self.assertEqual(maps["height_scale_m"], [-1.0, 1.0])
        self.assertNotEqual(maps["depth_scale"], maps["height_scale_m"])

    def test_exit_flushes_outputs_before_os_exit_and_does_not_close_kit(self):
        for code in (0, 1):
            events = []
            class Stream:
                def flush(self): events.append("flush")
            exit_after_flush(code, Stream(), Stream(), lambda rc: events.append(("exit", rc)))
            self.assertEqual(events, ["flush", "flush", ("exit", code)])

    def test_b_flat_and_rough_specs_are_distinct_selection_only(self):
        flat = parse_spec('{"experiment":"B","terrain":"flat","seed":42}')
        rough = parse_spec('{"experiment":"B","terrain":"rough","seed":42}')
        self.assertEqual(flat["terrain"], "flat")
        self.assertEqual(rough["terrain"], "rough")
        self.assertEqual(flat["seed"], rough["seed"])

    def test_topdown_native_selection_contract(self):
        spec = parse_spec('{"experiment":"TD","terrain_type":"stepping_beams","level":7,"seed":43}')
        self.assertEqual((spec["terrain_type"], spec["level"], spec["seed"]), ("stepping_beams", 7, 43))
        with self.assertRaises(ValueError):
            parse_spec('{"experiment":"TD","terrain_type":"unknown","level":2}')
        self.assertEqual(validate_depth_delay("TD", 0)["depth_delay_ticks"], 0)
        with self.assertRaises(ValueError):
            validate_depth_delay("TD", 1)
        self.assertEqual(validate_depth_delay("B", 1)["depth_delay_ticks"], 1)

    def test_mean_action_and_latent_are_required(self):
        with self.assertRaises(ValueError):
            parse_spec('{"experiment":"B","act_mode":"sample"}')
        with self.assertRaises(ValueError):
            parse_spec('{"experiment":"B","z_mode":"sample"}')

    def test_map_mode_applies_to_initial_and_reset_masks(self):
        for mode, expected in (("saved", True), ("pred", False), ("gt", True)):
            policy = FakePolicy(force_gt=True)
            row = apply_map_mode(policy, mode, "reconstruction", True, np)
            self.assertEqual(row["effective_use_gt"], expected)
            assert_map_mode(policy, expected)
            policy.pstate.use_gt[:] = not expected
            policy.reset(np.array([True]))
            assert_map_mode(policy, expected)

    def test_pred_and_gt_override_require_reconstruction_input(self):
        policy = FakePolicy(force_gt=False)
        with self.assertRaises(ValueError):
            apply_map_mode(policy, "pred", "none", False, np)
        with self.assertRaises(ValueError):
            apply_map_mode(policy, "gt", "none", False, np)

    def test_600_physics_steps_sample_exactly_300_frames_and_four_commands(self):
        contract = step_contract(0.02)
        self.assertEqual(contract["physics_steps"], 600)
        self.assertEqual(contract["video_frames"], 300)
        self.assertEqual(len(set(contract["video_sample_step_indices"])), 300)
        self.assertEqual(len(COMMANDS), 4)
        self.assertEqual(sum(row["duration_s"] for row in contract["commands"]), 12.0)
        self.assertEqual(frame_steps(600), contract["video_sample_step_indices"])

    def test_reset_does_not_become_a_fall_judgment(self):
        record = termination_record(True, {"time_out": False, "base_contact": True}, False)
        self.assertEqual(record["reason"], "termination_terms")
        self.assertEqual(record["active_terms"], ["base_contact"])
        self.assertEqual(record["classification"], "not_a_fall_judgment")
        unknown = termination_record(True, None, False)
        self.assertEqual(unknown["reason"], "terminated_unclassified")

    def test_plan_only_cli_reports_the_seq_video_output_contract(self):
        output = io.StringIO()
        argv = ["--policy", '{"experiment":"B","terrain":"flat","seed":42}',
                "--checkpoint", "known.pt", "--label", "CPU", "--scene", "flat",
                "--mp4", "unused.mp4", "--plan-only"]
        with redirect_stdout(output):
            self.assertEqual(main(argv), 0)
        import json
        plan = json.loads(output.getvalue())
        self.assertEqual(plan["target_frames"], 300)
        self.assertEqual(plan["duration_s"], 12.0)
        self.assertEqual(plan["receipt_consumer"], "foothold_s2.eval.seq_video")
        self.assertEqual(len(plan["commands"]), 4)
        self.assertEqual(plan["spec"]["physics_mode"], "fixed")


if __name__ == "__main__":
    unittest.main()
