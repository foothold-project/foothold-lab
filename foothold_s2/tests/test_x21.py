"""SONNET-X21: EX-21 (EX-16 + EX-19 DR + EX-20 행동 · 종료 + EX-18 oracle_vel) · EX-22 (EX-21 + v2 명령 분포) CPU 시험.

구성 대조(AST: 각 판의 차이가 이 묶음뿐) + v2 실행 기록 env.yaml 해당 칸 일치 + EX-22 에서 끈 충돌 근거. Kit 이름은 test_kit_names 의 AST 대조가 본다.
"""

import ast
import math
import os

import pytest

from foothold_s2.runners.manifest import yaml_flat

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V2_YAML = "C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/params/env.yaml"
INSTALLED_CMD = "C:/isaac/IsaacLab/source/isaaclab/isaaclab/envs/mdp/commands/velocity_command.py"
needs_v2 = pytest.mark.skipif(not os.path.exists(V2_YAML), reason="v2 실행 기록 없음")


def _src(rel):
    return open(os.path.join(REPO, rel), encoding="utf-8").read()


def _post_init(rel, cls):
    tree = ast.parse(_src(rel))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    post = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__post_init__")

    return {ast.unparse(a.targets[0]): ast.unparse(a.value) for a in ast.walk(post) if isinstance(a, ast.Assign)}, node


def _fields(rel, cls):
    node = next(n for n in ast.parse(_src(rel)).body if isinstance(n, ast.ClassDef) and n.name == cls)

    return {(n.targets[0].id if isinstance(n, ast.Assign) else n.target.id): n.value for n in node.body if isinstance(n, (ast.Assign, ast.AnnAssign))}, node


# ------------------------------------------------------------------ EX-21
def test_x21_adds_exactly_the_x19_events_on_top_of_x20():
    a21, n21 = _post_init("foothold_s2/tasks/s2_x21_cfg.py", "FootholdS2X21EnvCfg")
    a19, _ = _post_init("foothold_s2/tasks/s2_x19_cfg.py", "FootholdS2X19EnvCfg")
    a20, n20 = _post_init("foothold_s2/tasks/s2_x20_cfg.py", "FootholdS2X20EnvCfg")

    assert [ast.unparse(b) for b in n21.bases] == ["FootholdS2X20EnvCfg"] and [ast.unparse(b) for b in n20.bases] == ["FootholdS2X16nEnvCfg"]
    assert a21 == a19                                                               # EX-21 이 더하는 대입 = EX-19 의 다섯(식까지 같음)
    assert set(a21) == {"self.events.physics_material.params", "self.events.add_base_mass.params", "self.events.base_com", "self.events.actuator_gains", "self.events.motor_strength"}
    assert set(a20) == {"self.actions.joint_pos", "self.terminations.bad_orientation", "self.terminations.foot_below_ground", "self.terminations.base_contact"}      # 행동 · 종료는 EX-20 상속
    body = _src("foothold_s2/tasks/s2_x21_cfg.py").split('"""', 2)[2]

    assert "rewards" not in body and "commands" not in body and "curriculum" not in body and "observations" not in body


def test_x21_agent_is_the_x18_agent_with_only_the_experiment_folder_changed():
    fields, node = _fields("foothold_s2/tasks/agents/s2_x21_ppo_cfg.py", "S2X21PPORunnerCfg")

    assert [ast.unparse(b) for b in node.bases] == ["S2X18PPORunnerCfg"] and set(fields) == {"experiment_name"}
    assert ast.literal_eval(fields["experiment_name"]) == "foothold_s2_x21"
    x18, _ = _fields("foothold_s2/tasks/agents/s2_x18_ppo_cfg.py", "S2X18PPORunnerCfg")
    perc = ast.literal_eval(x18["perception"])

    assert perc["est_mode"] == "oracle_vel" and perc["oracle_vel_noise"] == 0.1 and perc["contract"] == "start"                  # EX-18 의 est 입력(잡음 0.1)과 START 명령 계약 그대로
    assert ast.literal_eval(x18["max_iterations"]) == 301 and ast.literal_eval(x18["save_interval"]) == 50


def test_x21_registration_and_run_script():
    import gymnasium as gym

    import foothold_s2.x21_tasks  # noqa: F401

    spec = gym.spec("FootholdS2-Go2-S2-X21-v0")

    assert spec.entry_point == "isaaclab.envs:ManagerBasedRLEnv" and spec.kwargs["env_cfg_entry_point"].endswith("s2_x21_cfg:FootholdS2X21EnvCfg")
    assert spec.kwargs["rsl_rl_cfg_entry_point"].endswith("s2_x21_ppo_cfg:S2X21PPORunnerCfg")
    run = _src("foothold_s2/run_s2_x21.sh")

    assert "FootholdS2-Go2-S2-X21-v0" in run and "ex21-v2triple" in run and "--max_iterations 301" in run and "--num_envs 3072" in run and "--seed 42" in run


# ------------------------------------------------------------------ EX-22
def test_x22_differs_from_x21_only_by_command_and_the_two_conflicting_curricula():
    a22, n22 = _post_init("foothold_s2/tasks/s2_x22_cfg.py", "FootholdS2X22EnvCfg")

    assert [ast.unparse(b) for b in n22.bases] == ["FootholdS2X21EnvCfg"]
    assert set(a22) == {"self.commands.base_velocity", "self.curriculum.terrain_levels", "self.curriculum.command_range"}
    assert a22["self.curriculum.command_range"] == "None" and a22["self.curriculum.terrain_levels"] == "CurrTerm(func=mdp.terrain_levels_vel)"
    body = _src("foothold_s2/tasks/s2_x22_cfg.py").split('"""', 2)[2]

    assert "rewards" not in body and "events" not in body and "actions" not in body and "terminations" not in body and "penalty_on" not in body.split("class")[1]


@needs_v2
def test_x22_command_equals_the_v2_env_yaml():
    ref = yaml_flat(V2_YAML)
    src = _src("foothold_s2/tasks/s2_x22_cfg.py")
    call = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and ast.unparse(n.func) == "mdp.UniformVelocityCommandCfg")
    env = {"math": math, "mdp": type("M", (), {"UniformVelocityCommandCfg": type("C", (), {"Ranges": staticmethod(lambda **kw: kw)})})}
    kw = {k.arg: eval(ast.unparse(k.value), env) for k in call.keywords}
    r = kw.pop("ranges")
    debug_vis = kw.pop("debug_vis")

    assert ref["commands.base_velocity.class_type"].endswith(":UniformVelocityCommand")
    assert kw == {"asset_name": ref["commands.base_velocity.asset_name"], "resampling_time_range": (float(ref["commands.base_velocity.resampling_time_range[0]"]), float(ref["commands.base_velocity.resampling_time_range[1]"])),
                  "rel_standing_envs": float(ref["commands.base_velocity.rel_standing_envs"]), "rel_heading_envs": float(ref["commands.base_velocity.rel_heading_envs"]),
                  "heading_command": ref["commands.base_velocity.heading_command"] == "True", "heading_control_stiffness": float(ref["commands.base_velocity.heading_control_stiffness"])}
    assert kw["resampling_time_range"] == (10.0, 10.0) and kw["rel_standing_envs"] == 0.1 and kw["rel_heading_envs"] == 1.0 and kw["heading_command"] is True and kw["heading_control_stiffness"] == 0.5
    for key, name in (("lin_vel_x", "lin_vel_x"), ("lin_vel_y", "lin_vel_y"), ("ang_vel_z", "ang_vel_z"), ("heading", "heading")):
        assert tuple(r[key]) == (float(ref[f"commands.base_velocity.ranges.{name}[0]"]), float(ref[f"commands.base_velocity.ranges.{name}[1]"])), key

    assert r["lin_vel_x"] == (0.4, 1.5) and r["lin_vel_y"] == (0.0, 0.0) and r["ang_vel_z"] == (-1.0, 1.0) and r["heading"][1] == pytest.approx(math.pi)
    assert debug_vis is False and ref["commands.base_velocity.debug_vis"] == "True"                                  # 유일한 차이: headless 라 마커를 끈다(문서에 적음)
    assert ref["curriculum.terrain_levels.func"].endswith(":terrain_levels_vel")                                     # v2 의 지형 커리큘럼


def test_x22_why_the_two_curricula_are_replaced():
    """S1 커리큘럼은 MixedVelocityCommand 전용 속성을 읽는다: UniformVelocityCommand 에는 없어 그대로 두면 reset 때 AttributeError."""
    cur = _src("foothold_s2/curriculum/terrain_levels_mixed.py")

    assert "term.is_flag_env" in cur and "term.cmd_sum_xy" in cur and "term.range_curriculum" in cur
    if os.path.exists(INSTALLED_CMD):
        installed = open(INSTALLED_CMD, encoding="utf-8").read()

        assert "is_flag_env" not in installed and "cmd_sum_xy" not in installed and "range_curriculum" not in installed
    s1 = _src("foothold_s2/tasks/s1_env_cfg.py")
    cfg = s1[s1.index("class CurriculumCfg"):s1.index("class FootholdS1aScanEnvCfg")]

    assert "terrain_levels = CurrTerm(" in cfg and "command_range = CurrTerm(" in cfg and "penalty_on = CurrTerm(" in cfg                # 바꾸는 이름이 실제로 있다


def test_x22_agent_turns_off_only_the_contract_and_registration():
    fields, node = _fields("foothold_s2/tasks/agents/s2_x22_ppo_cfg.py", "S2X22PPORunnerCfg")

    assert [ast.unparse(b) for b in node.bases] == ["S2X21PPORunnerCfg"] and set(fields) == {"experiment_name", "perception"}
    x18, _ = _fields("foothold_s2/tasks/agents/s2_x18_ppo_cfg.py", "S2X18PPORunnerCfg")
    base, new = ast.literal_eval(x18["perception"]), ast.literal_eval(fields["perception"])

    assert {k: v for k, v in new.items() if k != "contract"} == {k: v for k, v in base.items() if k != "contract"}      # 계약 검사 외 같음
    assert new["contract"] is None and base["contract"] == "start"
    import gymnasium as gym

    import foothold_s2.x22_tasks  # noqa: F401

    spec = gym.spec("FootholdS2-Go2-S2-X22-v0")

    assert spec.kwargs["env_cfg_entry_point"].endswith("s2_x22_cfg:FootholdS2X22EnvCfg") and spec.kwargs["rsl_rl_cfg_entry_point"].endswith("s2_x22_ppo_cfg:S2X22PPORunnerCfg")
    run = _src("foothold_s2/run_s2_x22.sh")

    assert "FootholdS2-Go2-S2-X22-v0" in run and "ex22-v2cmd" in run and "--max_iterations 301" in run
    ts = _src("foothold_s2/scripts/train_start.py")

    assert "import foothold_s2.x21_tasks" in ts and "import foothold_s2.x22_tasks" in ts


def test_runner_skips_the_contract_check_when_contract_is_none():
    src = _src("foothold_s2/runners/start_runner.py")

    assert 'self.pcfg["contract"] == "start"' in src                                                                  # None 이면 검사 · 명령 term 요구가 모두 꺼진다
