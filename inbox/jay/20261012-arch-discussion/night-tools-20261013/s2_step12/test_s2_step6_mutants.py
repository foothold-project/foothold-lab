"""Normal-first source mutations. CAUGHT requires the exact first failing label."""
from __future__ import annotations
from pathlib import Path
import shutil
import tempfile
from s2_step6_audit import HERE,audit


MUTANTS=(
    ("allow_updates_3","s2_train_contract.py","p[\"updates\"] not in (1,2)",
     "p[\"updates\"] not in (1,2,3)","updates_3_guard"),
    ("remove_plumbing_only","s2_train_contract.py","if m.get(\"plumbing_only\") is not True:",
     "if False and m.get(\"plumbing_only\") is not True:","plumbing_only_guard"),
    ("allow_stage0_passed","s2_train_contract.py","if m.get(\"stage0_passed\") is not False:",
     "if False and m.get(\"stage0_passed\") is not False:","stage0_false_guard"),
    ("remove_parent_rehash","s2_train_launch.py","parent_after=sha(m[\"plan\"][\"parent\"])",
     "parent_after=parent_before","parent_remeasurement"),
    ("allow_plumbing_parent","s2_train_contract.py","if \"PLUMBING_ONLY_\" in str(p.get(\"parent\",\"\")):",
     "if False and \"PLUMBING_ONLY_\" in str(p.get(\"parent\",\"\")):","plumbing_parent_guard"),
    ("remove_input_path","s2_train_contract.py","if m.get(\"input_path\") not in (\"live_raycaster_unverified\",\"synthetic_known_answer\"):",
     "if False and m.get(\"input_path\") not in (\"live_raycaster_unverified\",\"synthetic_known_answer\"):","input_path_guard"),
    ("allow_diagnostic_cfg","s2_train_entry_17v.py","assert_training_cfg(cfg)",
     "pass  # diagnostic cfg bypass","training_cfg_guard"),
    ("allow_parallel_arms","s2_train_contract.py","try:check_sequence(m)",
     "try:pass","sequential_arm_guard"),
    ("remove_weight_change_check","s2_train_entry_17v.py","if current_hash==previous_hash:raise ValueError(\"weights_unchanged\")",
     "if False and current_hash==previous_hash:raise ValueError(\"weights_unchanged\")","weight_change_guard"),
    ("remove_nan_check","s2_train_entry_17v.py","if nans!=0:raise ValueError(\"nonfinite_record\")",
     "if False and nans!=0:raise ValueError(\"nonfinite_record\")","nan_guard"),
    ("mix_environment_steps","s2_train_launch.py","\"rollout_steps\":m[\"plan\"][\"rollout_steps\"]",
     "\"rollout_steps\":count","iteration_step_receipt"),
)


def test():
    normal=audit(HERE)
    assert len(normal)==11 and all(normal.values()),normal
    print("PASS normal_first_plumbing_audit_11")
    files={name for _,name,_,_,_ in MUTANTS}|{"s2_plumbing.py"}
    for label,file,old,new,want in MUTANTS:
        with tempfile.TemporaryDirectory(prefix="s2_step6_mutant_") as td:
            folder=Path(td)
            for name in files:shutil.copyfile(HERE/name,folder/name)
            path=folder/file;source=path.read_text(encoding="utf-8")
            assert source.count(old)==1,(label,source.count(old))
            path.write_text(source.replace(old,new,1),encoding="utf-8")
            observed=audit(folder)
            first=next((name for name,passed in observed.items() if not passed),None)
            assert first==want,(label,first,want)
            print(f"CAUGHT {label} first_FAIL={first} want={want}")


if __name__=="__main__":test()
