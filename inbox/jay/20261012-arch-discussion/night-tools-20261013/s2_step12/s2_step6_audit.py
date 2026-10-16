"""Static source audit for the eleven requested fail-closed plumbing mutations."""
from __future__ import annotations
import ast
from pathlib import Path

HERE=Path(__file__).resolve().parent


def _called(source,name):
    tree=ast.parse(source)
    return any(isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and
               node.func.id==name for node in ast.walk(tree))


def audit(folder=HERE):
    folder=Path(folder)
    contract=(folder/"s2_train_contract.py").read_text(encoding="utf-8")
    entry=(folder/"s2_train_entry_17v.py").read_text(encoding="utf-8")
    launch=(folder/"s2_train_launch.py").read_text(encoding="utf-8")
    plumbing=(folder/"s2_plumbing.py").read_text(encoding="utf-8")
    return {
      "updates_3_guard":"p[\"updates\"] not in (1,2)" in contract,
      "plumbing_only_guard":"if m.get(\"plumbing_only\") is not True:" in contract,
      "stage0_false_guard":"if m.get(\"stage0_passed\") is not False:" in contract,
      "parent_remeasurement":"parent_before=sha(m[\"plan\"][\"parent\"])" in launch and
          "parent_after=sha(m[\"plan\"][\"parent\"])" in launch and
          "parent_before==parent_after" in launch,
      "plumbing_parent_guard":"if \"PLUMBING_ONLY_\" in str(p.get(\"parent\",\"\")):" in contract,
      "input_path_guard":"if m.get(\"input_path\") not in (\"live_raycaster_unverified\",\"synthetic_known_answer\"):" in contract,
      "training_cfg_guard":_called(entry,"assert_training_cfg") and
          "diagnostic_gravity_leak" in plumbing and "diagnostic_contact_leak" in plumbing,
      "sequential_arm_guard":_called(contract,"check_sequence") and
          "prior.get(\"family_cleanup_confirmed\") is not True" in plumbing,
      "weight_change_guard":"if current_hash==previous_hash:raise ValueError(\"weights_unchanged\")" in entry and
          "result.get(\"parameter_changed\") is not True" in plumbing,
      "nan_guard":"if nans!=0:raise ValueError(\"nonfinite_record\")" in entry and
          "if result.get(\"nonfinite_count\")!=0:raise PlumbingHold(\"nonfinite_record\")" in plumbing,
      "iteration_step_receipt":"\"rollout_steps\":m[\"plan\"][\"rollout_steps\"]" in launch and
          "\"executed_updates\":count" in launch and
          "result.get(\"environment_steps\")!=p[\"updates\"]*p[\"rollout_steps\"]*p[\"num_envs\"]" in plumbing,
    }
