"""SONNET-X19: EX-19 (EX-16 + 도메인 무작위화를 v2 와 같게) · EX-20 (EX-16 + 행동 · 종료를 v2 와 같게) CPU 시험.

구성 대조(AST: EX-16 과의 차이가 각 묶음뿐) + v2 실행 기록 env.yaml 의 해당 칸과 값 일치. Kit 이름은 test_kit_names 의 AST 대조가 본다.
"""

import ast
import os

import pytest

from foothold_s2.runners.manifest import yaml_flat

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V2_YAML = "C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/params/env.yaml"
needs_v2 = pytest.mark.skipif(not os.path.exists(V2_YAML), reason="v2 실행 기록 없음")


class _Scene(dict):
    def __init__(self, name, body_names=None):
        super().__init__(name=name, body_names=body_names)


def _src(rel):
    return open(os.path.join(REPO, rel), encoding="utf-8").read()


def _post_init(src, cls):
    """{대입 대상: 값 식(ast)} 와 클래스 노드."""
    tree = ast.parse(src)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    post = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__post_init__")
    assigns = {ast.unparse(a.targets[0]): a.value for a in ast.walk(post) if isinstance(a, ast.Assign)}

    return assigns, node


def _ev(expr):
    return eval(ast.unparse(expr), {"SceneEntityCfg": _Scene, "None": None})


# ------------------------------------------------------------------ EX-19
def test_x19_differs_from_x16n_only_by_the_five_event_changes():
    assigns, node = _post_init(_src("foothold_s2/tasks/s2_x19_cfg.py"), "FootholdS2X19EnvCfg")

    assert [ast.unparse(b) for b in node.bases] == ["FootholdS2X16nEnvCfg"]
    assert set(assigns) == {"self.events.physics_material.params", "self.events.add_base_mass.params", "self.events.base_com", "self.events.actuator_gains", "self.events.motor_strength"}
    src = _src("foothold_s2/tasks/s2_x19_cfg.py").split('"""', 2)[2]

    assert "rewards" not in src and "actions" not in src and "terminations" not in src and "commands" not in src and "reset_base" not in src


@needs_v2
def test_x19_event_values_equal_the_v2_env_yaml():
    ref = yaml_flat(V2_YAML)
    assigns, _ = _post_init(_src("foothold_s2/tasks/s2_x19_cfg.py"), "FootholdS2X19EnvCfg")
    mat = _ev(assigns["self.events.physics_material.params"])
    mass = _ev(assigns["self.events.add_base_mass.params"])

    assert tuple(mat["static_friction_range"]) == (float(ref["events.physics_material.params.static_friction_range[0]"]), float(ref["events.physics_material.params.static_friction_range[1]"])) == (0.8, 0.8)
    assert tuple(mat["dynamic_friction_range"]) == (float(ref["events.physics_material.params.dynamic_friction_range[0]"]), float(ref["events.physics_material.params.dynamic_friction_range[1]"])) == (0.6, 0.6)
    assert tuple(mat["restitution_range"]) == (0.0, 0.0) and mat["num_buckets"] == int(ref["events.physics_material.params.num_buckets"]) == 64
    assert mat["asset_cfg"]["body_names"] == ref["events.physics_material.params.asset_cfg.body_names"] == ".*" and "make_consistent" not in mat                  # v2 에는 make_consistent 인자가 없다
    assert tuple(mass["mass_distribution_params"]) == (float(ref["events.add_base_mass.params.mass_distribution_params[0]"]), float(ref["events.add_base_mass.params.mass_distribution_params[1]"])) == (-1.0, 3.0)
    assert mass["operation"] == ref["events.add_base_mass.params.operation"] == "add" and mass["asset_cfg"]["body_names"] == ref["events.add_base_mass.params.asset_cfg.body_names"] == "base"
    assert ref["events.base_com"] == "None"                                                                        # v2: COM 무작위 없음
    assert not any(k.startswith("events.actuator_gains") or k.startswith("events.motor_strength") for k in ref)    # v2: PD 이득 · 모터 세기 이벤트 없음 (끈 것과 같다)
    assert ref["events.physics_material.mode"] == "startup" and ref["events.add_base_mass.mode"] == "startup"
    for name in ("base_com", "actuator_gains", "motor_strength"):
        assert ast.unparse(assigns[f"self.events.{name}"]) == "None"


def test_x19_changed_terms_exist_in_the_s1_event_cfg_and_registration():
    s1 = _src("foothold_s2/tasks/s1_env_cfg.py")
    events = s1[s1.index("class EventCfg"):s1.index("class TerminationsCfg")]

    for name in ("physics_material", "add_base_mass", "base_com", "actuator_gains", "motor_strength"):
        assert f"    {name} = EventTerm(" in events                                                               # 바꾸는 이벤트가 S1 에 실제로 있다(없는 이름을 대입해 조용히 넘어가지 않는다)
    import gymnasium as gym

    import foothold_s2.x19_tasks  # noqa: F401

    spec = gym.spec("FootholdS2-Go2-S2-X19-v0")

    assert spec.entry_point == "isaaclab.envs:ManagerBasedRLEnv" and spec.kwargs["env_cfg_entry_point"].endswith("s2_x19_cfg:FootholdS2X19EnvCfg")
    assert spec.kwargs["rsl_rl_cfg_entry_point"].endswith("s2_x19_ppo_cfg:S2X19PPORunnerCfg")
    agent = _src("foothold_s2/tasks/agents/s2_x19_ppo_cfg.py")

    assert "S2X16nPPORunnerCfg" in agent and "max_iterations = 301" in agent and "save_interval = 50" in agent and 'experiment_name = "foothold_s2_x19"' in agent
    run = _src("foothold_s2/run_s2_x19.sh")

    assert "FootholdS2-Go2-S2-X19-v0" in run and "ex19-dr-v2" in run and "--max_iterations 301" in run and "--num_envs 3072" in run and "--seed 42" in run


# ------------------------------------------------------------------ EX-20
def test_x20_differs_from_x16n_only_by_actions_and_terminations():
    assigns, node = _post_init(_src("foothold_s2/tasks/s2_x20_cfg.py"), "FootholdS2X20EnvCfg")

    assert [ast.unparse(b) for b in node.bases] == ["FootholdS2X16nEnvCfg"]
    assert set(assigns) == {"self.actions.joint_pos", "self.terminations.bad_orientation", "self.terminations.foot_below_ground", "self.terminations.base_contact"}
    body = _src("foothold_s2/tasks/s2_x20_cfg.py").split('"""', 2)[2]

    assert "rewards" not in body and "events" not in body and "commands" not in body and "observations" not in body and "curriculum" not in body
    assert ast.unparse(assigns["self.terminations.bad_orientation"]) == "None" and ast.unparse(assigns["self.terminations.foot_below_ground"]) == "None"      # time_out 은 그대로 남는다
    assert "time_out" not in ast.unparse(assigns["self.terminations.base_contact"])


@needs_v2
def test_x20_action_and_terminations_equal_the_v2_env_yaml():
    ref = yaml_flat(V2_YAML)
    src = _src("foothold_s2/tasks/s2_x20_cfg.py")
    act = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and ast.unparse(n.func) == "mdp.JointPositionActionCfg")
    kw = {k.arg: ast.literal_eval(k.value) for k in act.keywords}

    assert ref["actions.joint_pos.class_type"].endswith(":JointPositionAction")                                    # 지연 없는 기본 행동
    assert kw == {"asset_name": ref["actions.joint_pos.asset_name"], "joint_names": [ref["actions.joint_pos.joint_names[0]"]], "scale": float(ref["actions.joint_pos.scale"]),
                  "use_default_offset": ref["actions.joint_pos.use_default_offset"] == "True"} == {"asset_name": "robot", "joint_names": [".*"], "scale": 0.25, "use_default_offset": True}
    assert ref["actions.joint_pos.offset"] == "0.0" and ref["actions.joint_pos.clip"] == "None"                    # 기본값과 같다(우리가 따로 안 넘기는 인자)
    done = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and ast.unparse(n.func) == "DoneTerm")
    params = next(k.value for k in done.keywords if k.arg == "params")
    sensor = next(n for n in ast.walk(params) if isinstance(n, ast.Call) and ast.unparse(n.func) == "SceneEntityCfg")
    threshold = ast.literal_eval(next(v for k, v in zip(params.keys, params.values) if ast.literal_eval(k) == "threshold"))

    assert ast.unparse(next(k.value for k in done.keywords if k.arg == "func")) == "mdp.illegal_contact" and ref["terminations.base_contact.func"].endswith(":illegal_contact")
    assert ast.literal_eval(next(k.value for k in sensor.keywords if k.arg == "body_names")) == ref["terminations.base_contact.params.sensor_cfg.body_names"] == "base"
    assert threshold == float(ref["terminations.base_contact.params.threshold"]) == 1.0 and ref["terminations.time_out.time_out"] == "True"
    assert "terminations.bad_orientation.func" not in ref and "terminations.foot_below_ground.func" not in ref                                              # v2 에는 이 둘이 없다


def test_x20_removed_terminations_exist_in_s1_and_registration():
    s1 = _src("foothold_s2/tasks/s1_env_cfg.py")
    terms = s1[s1.index("class TerminationsCfg"):s1.index("class CurriculumCfg")]

    for name in ("time_out = DoneTerm", "bad_orientation = DoneTerm", "foot_below_ground = DoneTerm"):
        assert name in terms
    import gymnasium as gym

    import foothold_s2.x20_tasks  # noqa: F401

    spec = gym.spec("FootholdS2-Go2-S2-X20-v0")

    assert spec.entry_point == "isaaclab.envs:ManagerBasedRLEnv" and spec.kwargs["env_cfg_entry_point"].endswith("s2_x20_cfg:FootholdS2X20EnvCfg")
    assert spec.kwargs["rsl_rl_cfg_entry_point"].endswith("s2_x20_ppo_cfg:S2X20PPORunnerCfg")
    agent = _src("foothold_s2/tasks/agents/s2_x20_ppo_cfg.py")

    assert "S2X16nPPORunnerCfg" in agent and "max_iterations = 301" in agent and "save_interval = 50" in agent and 'experiment_name = "foothold_s2_x20"' in agent
    run = _src("foothold_s2/run_s2_x20.sh")

    assert "FootholdS2-Go2-S2-X20-v0" in run and "ex20-act-term-v2" in run and "--max_iterations 301" in run
    ts = _src("foothold_s2/scripts/train_start.py")

    assert "import foothold_s2.x19_tasks" in ts and "import foothold_s2.x20_tasks" in ts


def test_x20_does_not_break_old_eval_hooks_and_running_files_untouched():
    """EX-17 · 18 이 소비하는 기존 파일에는 EX-19 · 20 이름이 없다(manifest 감시로 도는 판이 무효가 되지 않게 새 파일로만 더했다). 평가 도구의 max_delay_s 는 hasattr 로 지킨다."""
    for rel in ("foothold_s2/x17_tasks.py", "foothold_s2/x18_tasks.py", "foothold_s2/tasks/s2_x17_cfg.py", "foothold_s2/tasks/agents/s2_x17_ppo_cfg.py", "foothold_s2/tasks/agents/s2_x18_ppo_cfg.py",
                "foothold_s2/tasks/s2_x16n_cfg.py", "foothold_s2/runners/start_runner.py", "foothold_s2/eval/adapters.py", "foothold_s2/tasks/__init__.py", "foothold_s2/tasks/s2_env_cfg.py"):
        text = _src(rel)

        assert "x19" not in text.lower() and "x20" not in text.lower(), rel

    for rel in ("foothold_s2/eval/diag_z_action.py", "foothold_s2/eval/diag_cmd_response.py"):
        assert 'hasattr(env_cfg.actions.joint_pos, "max_delay_s")' in _src(rel)
