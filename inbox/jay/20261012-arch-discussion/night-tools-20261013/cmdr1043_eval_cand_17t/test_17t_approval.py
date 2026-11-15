"""CPU fixture approvals for every new B value and applied comparison rule."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from s1043_manifest import approval_binding, launch_errors, sha256
from test_17r_e import approved_fixture

if os.environ.get("S1043_MANIFEST_OVERRIDE"):
    spec = importlib.util.spec_from_file_location("s1043_manifest_mutant", os.environ["S1043_MANIFEST_OVERRIDE"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.__file__ = str(HERE / "s1043_manifest.py")
    module.ROOT = HERE.parent
    launch_errors = module.launch_errors


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label, flush=True)
    if not condition:
        raise AssertionError(label)


def approved(m):
    e = m["execution"]
    path = Path(e["approval_path"])
    path.write_text(json.dumps({"approved": True, "by": "CPU_FIXTURE_ONLY", "approved_at": "fixture",
                                "reviewed": approval_binding(m)}, sort_keys=True), encoding="utf-8")
    e["approval_sha256"] = sha256(path)
    return e["approval_sha256"]


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    m, _, digest, _ = approved_fixture()
    check("approved strict rule accepted with full file checks",
          launch_errors(m, approved_digest=digest, require_files=True) == [])
    cases = [
        ("comparison_pass_rule", "UNDECIDED", "execution comparison_pass_rule unsupported"),
        ("comparison_pass_rule", "ignore_all_differences", "execution comparison_pass_rule unsupported"),
        ("comparison_pass_rule", False, "execution comparison_pass_rule unsupported"),
        ("comparison_pass_rule", None, "execution comparison_pass_rule unsupported"),
        ("comparison_pass_rule", "", "execution comparison_pass_rule unsupported"),
        ("approval_id", "UNDECIDED", "execution approval_id invalid"),
        ("approval_id", "none", "execution approval_id invalid"),
        ("approval_id", "", "execution approval_id invalid"),
        ("approval_id", "bad/path", "execution approval_id invalid"),
        ("approval_id", "a" * 65, "execution approval_id invalid"),
        ("attempt", "UNDECIDED", "execution attempt invalid"),
        ("attempt", "", "execution attempt invalid"),
        ("attempt", "bad/path", "execution attempt invalid"),
        ("attempt", "a" * 65, "execution attempt invalid"),
        ("log_name", "UNDECIDED", "execution log_name invalid"),
        ("log_name", "null", "execution log_name invalid"),
        ("log_name", "", "execution log_name invalid"),
        ("log_name", "bad/path", "execution log_name invalid"),
        ("log_name", "a" * 51, "execution log_name invalid"),
        ("restart_scope", "UNDECIDED", "execution restart_scope unsupported"),
        ("restart_scope", "multi_start", "execution restart_scope unsupported"),
        ("restart_scope", False, "execution restart_scope unsupported"),
        ("restart_scope", None, "execution restart_scope unsupported"),
        ("termination_policy", "UNDECIDED", "execution termination_policy invalid"),
        ("termination_policy", {"terminate_grace_s": 0, "partial_result": "held"}, "execution termination_policy invalid"),
        ("termination_policy", {"terminate_grace_s": -1, "partial_result": "held"}, "execution termination_policy invalid"),
        ("termination_policy", {"terminate_grace_s": "5", "partial_result": "held"}, "execution termination_policy invalid"),
        ("termination_policy", {"terminate_grace_s": True, "partial_result": "held"}, "execution termination_policy invalid"),
        ("termination_policy", {"terminate_grace_s": 0.5, "partial_result": "ignore"}, "execution termination_policy invalid"),
        ("termination_policy", {"terminate_grace_s": 0.5}, "execution termination_policy invalid"),
    ]
    for index, (field, value, want) in enumerate(cases):
        trial = copy.deepcopy(m)
        trial["execution"][field] = value
        trial["execution"]["approval_path"] = str(Path(m["execution"]["approval_path"]).with_name(f"case_{index}.json"))
        digest = approved(trial)
        got = launch_errors(trial, approved_digest=digest, require_files=True)
        check(f"{field} {index} rejected", want in got)
    for policy in ({"terminate_grace_s": 0.25, "partial_result": "held"},
                   {"terminate_grace_s": 12.7, "partial_result": "held"}):
        trial = copy.deepcopy(m)
        trial["execution"]["termination_policy"] = policy
        trial["execution"]["approval_path"] = str(Path(m["execution"]["approval_path"]).with_name(
            f"positive_{str(policy['terminate_grace_s']).replace('.', '_')}.json"))
        digest = approved(trial)
        check("positive grace shape accepted", launch_errors(trial, approved_digest=digest, require_files=True) == [])

    driver = Path(os.environ.get("S1043_DRIVER_OVERRIDE", HERE / "cmdr_eval_driver_s1043.py"))
    old = sys.argv
    try:
        sys.argv = [str(driver), "--manifest", str(HERE / "manifest_s1043.json"),
                    "--expect_self_sha", sha256(driver), "--cpu_plan"]
        g = runpy.run_path(str(driver), run_name="approval_17t_cpu_probe")["diagnostic_matches"].__globals__
    finally:
        sys.argv = old
    strict = "semantic_and_json_bytes_and_traj_bytes"
    same = {"one": {"semantic_equal": True, "json_sha_equal": True, "traj_sha_equal": True}}
    check("approved rule applied to equal fields", g["diagnostic_matches"](same, strict) is True)
    changed = copy.deepcopy(same)
    changed["one"]["json_sha_equal"] = False
    check("approved rule applies strict byte hold", g["diagnostic_matches"](changed, strict) is False)
    try:
        g["diagnostic_matches"](same, "ignore_all_differences")
    except ValueError:
        check("unsupported rule cannot be applied", True)
    else:
        check("unsupported rule cannot be applied", False)
    undecided = json.loads((HERE / "manifest_s1043.json").read_text(encoding="utf-8"))
    errors = launch_errors(undecided, require_files=False)
    check("UNDECIDED manifest still blocked", "execution comparison_pass_rule unsupported" in errors and
          "execution restart_scope unsupported" in errors)


if __name__ == "__main__":
    main()
