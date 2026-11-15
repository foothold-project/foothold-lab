"""Read saved EX23/B/EX29 YAML and verify the declared B friction-only delta."""
from __future__ import annotations

import json
from pathlib import Path

from audit_s1_history_1024 import diff, sha, yaml_read


BASE = Path(__file__).resolve().parent
OLD = Path("C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl")
NEW = Path("C:/mai/wt/foothold-lab/lead-tmp-start-b/logs/rsl_rl")
RUNS = {
    "EX23": OLD / "foothold_s2_x23/2026-10-22_21-52-26_ex23-g1",
    "B": NEW / "foothold_s2_23f_b/2026-10-24_06-52-56_ex28-b-main",
    "EX29": NEW / "foothold_s2_23f_topdown/2026-10-24_08-20-33_ex29-td-main",
}


def main() -> None:
    known = diff({"x": [1, 2], "y": "old"}, {"x": [1, 3], "z": "new"})
    assert [row["key"] for row in known] == ["/x/1", "/y", "/z"]
    assert known[0]["before"] == 2 and known[0]["after"] == 3
    result = {"runs": {}, "diffs": {}}
    for label, folder in RUNS.items():
        result["runs"][label] = {
            name: yaml_read(folder / "params" / f"{name}.yaml")
            for name in ("env", "agent")
        }
    for label in ("B", "EX29"):
        result["diffs"][f"EX23__{label}"] = {
            name: diff(result["runs"]["EX23"][name]["data"],
                       result["runs"][label][name]["data"])
            for name in ("env", "agent")
        }
    changes = result["diffs"]["EX23__B"]
    expected = {"/log_dir", "/events/physics_material/params/make_consistent"}
    expected.update(f"/events/physics_material/params/{kind}_friction_range/{bound}"
                    for kind in ("static", "dynamic") for bound in (0, 1))
    assert {row["key"] for row in changes["env"]} == expected
    assert {row["key"] for row in changes["agent"]} == {"/experiment_name", "/run_name"}
    output = BASE / "figs/history-audit-1024/ex23_b_ex29_saved_diff.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "sha256": sha(output),
                      "known_input_pass": True, "b_env_deltas": len(changes["env"]),
                      "b_agent_deltas": len(changes["agent"])}))


if __name__ == "__main__":
    main()
