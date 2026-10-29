"""D51: 촬영기 x31 이 W15 연속 명령 셋 · eval_gt/eval_pred · 규칙 env 를 실제 parser(--plan-only)로 받는지.
평가 사본(eval-ex36-w15fix)과 저장본이 이 기계에 있어야 한다. 없으면 건너뛴다(관문이 사라지는 곳이라 CI 에서는 있어야 함)."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REC = Path(__file__).resolve().parents[1] / "eval/video25/record_25e_x31.py"
ROOT = "C:/mai/wt/foothold-lab/eval-ex36-w15fix"
RUNS = Path("C:/Users/AI-WS01/s2_lab/basic_gait_runs")
CK = RUNS / "main/EX-36A-basic-share30_20261029_013052_21044/model_3000.pt"
RECEIPT = next(iter((RUNS / "eval_w15/ex36a/m3000").glob("attempt_*/map64/map_modes.json")), None)
pytestmark = pytest.mark.skipif(not (Path(ROOT).is_dir() and CK.is_file() and RECEIPT is not None), reason="W15 평가 사본 · 저장본 · 배정 영수증이 없다")


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spec(w15_set="fwd_back", mode="eval_pred", rule="continuous_L1", env=23, kind="pyramid_stairs", col=0, **over):
    s = {"experiment": "SB", "source_profile": "W15", "source_root": ROOT, "w15_reference": True, "w15_set": w15_set, "w15_rule": rule,
         "map_mode": mode, "terrain_set": "fixed64", "map64_levels": True, "fixed_level": 0, "fixed_terrain": True, "envs": 64, "env_id": env,
         "kind": kind, "col": col, "selection_role": "w15_rule", "terrain_receipt": str(RECEIPT).replace("\\", "/"), "terrain_receipt_sha256": _sha(RECEIPT),
         "checkpoint_sha256": _sha(CK), "seed": 42, "z_mode": "mean", "act_mode": "mean", "hide_others": True}
    s.update(over)
    return s


def plan(s):
    label = "EX36A-basic-continuous_L1_env23-m3000-seq-1x"
    mp4 = Path(os.environ.get("TEMP", ".")) / "w15plan" / label / "plan.mp4"
    p = subprocess.run([sys.executable, str(REC), "--policy", json.dumps(s), "--checkpoint", str(CK), "--label", label, "--scene", "rough",
                        "--mp4", str(mp4), "--plan-only"], capture_output=True, text=True, env=dict(os.environ, CUDA_VISIBLE_DEVICES="", PYTHONUTF8="1"))
    return p


@pytest.mark.parametrize("w15_set,n", [("fwd_back", 5), ("side_diag", 6), ("spin_restart", 4), ("slope_fwd", 1)])
@pytest.mark.parametrize("mode", ["eval_gt", "eval_pred"])
def test_sets_and_modes_pass_the_real_parser(w15_set, n, mode):
    rule = dict(rule="slope_L1", env=41, kind="hf_pyramid_slope", col=18) if w15_set == "slope_fwd" else {}
    p = plan(spec(w15_set, mode, **rule))
    assert p.returncode == 0, p.stderr[-400:]
    out = json.loads(p.stdout[p.stdout.index("{"):])
    assert len(out["commands"]) == n and out["spec"]["map_mode"] == mode
    assert abs(sum(c[2] for c in out["commands"]) - 6.0) < 1e-6 and out["target_frames"] == 150


def test_command_vectors_come_from_the_w15_eval_code():
    o = plan(spec("fwd_back")).stdout
    out = json.loads(o[o.index("{"):])
    assert [c[1] for c in out["commands"]] == [[0.5, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [-0.5, 0.0, 0.0], [-1.0, 0.0, 0.0]]


@pytest.mark.parametrize("over,needle", [
    ({"commands": [["a", [1, 0, 0], 3.0]]}, "commands list is not accepted"),
    ({"command": [1.0, 0.0, 0.0]}, "w15_set only"),
    ({"source_root": "C:/mai/wt/foothold-lab/eval-x27m4"}, "root path mismatch"),
    ({"env_id": 24}, "lowest-numbered env"),
    ({"w15_set": "nope"}, "w15_set must be"),
    ({"map_mode": "probe_prop_only_x"}, "map_mode"),
    ({"source_profile": "W03"}, "w15_reference requires"),
])
def test_wrong_inputs_are_errors_not_ignored(over, needle):
    p = plan(spec(**over))
    assert p.returncode != 0 and needle in (p.stderr + p.stdout)


def test_slope_rule_picks_lowest_l1_slope_env():
    assert plan(spec("slope_fwd", "eval_gt", rule="slope_L1", env=41, kind="hf_pyramid_slope", col=18)).returncode == 0
    assert plan(spec("slope_fwd", "eval_gt", rule="slope_L1", env=42, kind="hf_pyramid_slope", col=19)).returncode != 0
