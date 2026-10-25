"""SONNET-X25e: G0-B 저장본을 turn_probe · eval_map_modes 에 넣기 위한 사전 점검 (CPU 만, Kit 없음)."""

import ast
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
G0B_ID = "FootholdS2-Go2-S2-G0B-v0"
SH = ROOT / "foothold_s2/eval/run_g0b_eval.sh"
BASH = r"C:\Program Files\Git\bin\bash.exe"


def _src(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def _class(rel, name):
    return next(n for n in ast.parse(_src(rel)).body if isinstance(n, ast.ClassDef) and n.name == name)


def test_g0b_task_is_in_the_gym_registry_and_points_to_existing_classes():
    gym = pytest.importorskip("gymnasium")
    import foothold_s2.g0b_tasks  # noqa: F401

    spec = gym.spec(G0B_ID)
    env_mod, env_cls = spec.kwargs["env_cfg_entry_point"].split(":")
    agent_mod, agent_cls = spec.kwargs["rsl_rl_cfg_entry_point"].split(":")

    assert _class(env_mod.replace(".", "/") + ".py", env_cls).name == "FootholdS2G0BEnvCfg"
    assert _class(agent_mod.replace(".", "/") + ".py", agent_cls).name == "S2G0BPPORunnerCfg"


def test_g0b_cfg_classes_inherit_the_b_cfg_and_the_friction_range_is_0_2_to_1_2():
    env = _class("foothold_s2/tasks/s2_g0b_cfg.py", "FootholdS2G0BEnvCfg")
    assert [ast.unparse(b) for b in env.bases] == ["FootholdS223FBEnvCfg"] and len(env.body) == 1 and isinstance(env.body[0], ast.Pass)
    b_src = _src("foothold_s2/tasks/s2_23f_b_cfg.py")

    assert '"static_friction_range": (0.2, 1.2)' in b_src and '"dynamic_friction_range": (0.2, 1.2)' in b_src and '"make_consistent": True' in b_src
    agent_src = _src("foothold_s2/tasks/agents/s2_g0b_ppo_cfg.py")

    assert '"map_input": "none"' in agent_src and '"force_gt": False' in agent_src and "S223FBPPORunnerCfg" in agent_src


def test_g0b_task_files_are_byte_equal_to_the_training_branch_copies_when_present():
    other = ROOT.parent / "impl-g0b"
    if not other.exists():
        pytest.skip("impl-g0b 없음")
    for rel in ("foothold_s2/g0b_tasks.py", "foothold_s2/tasks/s2_g0b_cfg.py", "foothold_s2/tasks/agents/s2_g0b_ppo_cfg.py"):
        assert (ROOT / rel).read_bytes() == (other / rel).read_bytes(), rel


def test_eval_scripts_register_the_g0b_task_before_loading_the_cfg():
    for rel in ("foothold_s2/eval/turn_probe.py", "foothold_s2/eval/eval_map_modes.py"):
        s = _src(rel)

        assert "import foothold_s2.g0b_tasks" in s and s.index("import foothold_s2.g0b_tasks") < s.index("load_cfg_from_registry(args.task"), rel


def test_map_input_none_zero_token_rule_is_in_both_eval_scripts_and_real_ie_gives_zero():
    for rel in ("foothold_s2/eval/turn_probe.py", "foothold_s2/eval/eval_map_modes.py"):
        s = _src(rel)

        assert "last_num_map_tokens" in s and "지도 토큰이" in s, rel
    torch = pytest.importorskip("torch")
    from foothold_s2.models.start_perception import IEEstimator, PerceptionCfg

    ie = IEEstimator(PerceptionCfg(map_input="none"))
    ie.estimate(torch.zeros(2, 128), None)

    assert ie.last_num_map_tokens == 0


def test_map_modes_for_a_no_map_checkpoint_are_none_only():
    """지도 없는 체크포인트에서 eval_gt · eval_pred 는 코드가 거절한다(같은 값인지 비교할 길이 없다): 두 도구의 관문 문장."""
    em, tp = _src("foothold_s2/eval/eval_map_modes.py"), _src("foothold_s2/eval/turn_probe.py")

    assert '(saved_map_input == "none") != (mode == "none")' in em and 'map_mode=None if mode == "none" else mode' in em
    assert '(map_input == "none") != (args.map_mode == "none")' in tp and 'map_mode=None if args.map_mode == "none" else args.map_mode' in tp


def test_run_g0b_eval_script_shape():
    raw = SH.read_bytes()
    s = raw.decode("utf-8")

    assert b"\r" not in raw
    for must in (G0B_ID, "--cases all", "--envs 16", "--map-mode none", "--fixed-terrain", "foothold_s2.eval.turn_probe", "foothold_s2.eval.eval_map_modes", "--envs 64", "--steps 300", "--modes none", "TURNPROBE_DONE", 'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"'):
        assert must in s, must
    assert "eval_gt" not in s.replace("eval_gt · eval_pred", "") and "eval_pred --" not in s
    assert "\ncd " not in s                                              # cd 에 기대지 않는다
    r = subprocess.run([BASH, "-n", str(SH)], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)

    assert r.returncode == 0, r.stderr


def test_run_g0b_eval_matches_the_b1500_conditions_of_the_existing_runs():
    s = SH.read_text(encoding="utf-8")
    sweep = Path("C:/mai/wt/foothold-lab/impl-t5/logs/onset_sweep/sweep.sh")

    if sweep.exists():
        t = sweep.read_text(encoding="utf-8")

        assert "--envs 64 --steps 300" in t and "--fixed-terrain" in t and "--envs 64 --steps 300" in s
