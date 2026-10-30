"""CPU-only independent check of W57 explicit null versus absent evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
destination = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(source))
from foothold_s2.tests import test_ex40_scorer_cpu as fixture
from foothold_s2.ex40_score import judge, config
from foothold_s2.eval.map_mode_cells import EX40_B3_COMMANDS, commands

rows = []
cases = {
    "zero_null": {"stop_complete_envs": 0, "stop_end_error_median_rad": None},
    "zero_missing_error": {"stop_complete_envs": 0},
    "positive_null": {"stop_complete_envs": 1, "stop_end_error_median_rad": None},
    "missing_complete": {"stop_end_error_median_rad": None},
    "zero_nan": {"stop_complete_envs": 0, "stop_end_error_median_rad": float("nan")},
    "positive_nan": {"stop_complete_envs": 1, "stop_end_error_median_rad": float("nan")},
    "zero_finite": {"stop_complete_envs": 0, "stop_end_error_median_rad": 0.01},
}
with tempfile.TemporaryDirectory(prefix="analyst-w57-h1-") as scratch:
    for stage, update in (("B0", 1500), ("B2", 3500)):
        root = Path(scratch) / stage
        root.mkdir()
        checkpoint, _ = fixture._source(root, update=update)
        evidence = root / "eval"
        main = fixture._evidence(evidence, checkpoint)
        fixture._axis(evidence, checkpoint)
        extra = {
            **main, "command_suite": "ex40_b3", "commands": commands("ex40_b3"),
            "policy_dt_s": 0.02,
            "modes": {mode: {name: {**copy.deepcopy(main["modes"][mode]["fwd0.5"]),
                                     "command": command}
                              for name, command in EX40_B3_COMMANDS.items()}
                      for mode in main["modes"]},
        }
        (evidence / "map64_b3").mkdir()
        (evidence / "map64_b3/map_modes.json").write_text(json.dumps(extra), encoding="utf-8")
        axis_path = evidence / "axis_v2/axis_v2.json"
        original = json.loads(axis_path.read_text(encoding="utf-8"))
        name = config(fixture.DEFAULT_CONFIG)["axis_goal"]["cases"][0]
        for label, value in cases.items():
            axis = copy.deepcopy(original)
            axis["modes"]["eval_gt"][name] = value
            axis_path.write_text(json.dumps(axis), encoding="utf-8")
            score, _ = judge(checkpoint, stage, evidence, fixture.DEFAULT_CONFIG,
                             fixture.DEFAULT_TABLE, "B")
            expected = ("PASS" if stage == "B0" else "FAIL") if label == "zero_null" else "HOLD"
            rows.append({"stage": stage, "case": label, "expected": expected,
                         "actual": score["verdict"], "match": score["verdict"] == expected,
                         "problems": score["problems"]})
result = {
    "source": str(source),
    "score_py_sha256": hashlib.sha256((source / "foothold_s2/ex40_score.py").read_bytes()).hexdigest(),
    "rows": rows, "passed": sum(row["match"] for row in rows), "total": len(rows),
    "gpu_or_kit_started": False, "live_evidence_written": False,
}
destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"passed": result["passed"], "total": result["total"], "result": str(destination)}))
sys.exit(0 if result["passed"] == result["total"] else 1)
