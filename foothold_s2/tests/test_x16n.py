"""SONNET-X16b (EX-16 = EX-11 환경 + NVIDIA Go2 rough 보상 세트 통째) CPU 시험: 설치본 cfg · 실행 기록 env.yaml 과 항 · 가중치 · 인자 일치, EX-11 과 보상 밖 차이 0, 등록.

Kit 없이 AST 와 파일 읽기로 본다(Kit 이름은 test_kit_names 의 AST 대조가 따로 본다).
"""

import ast
import math
import os

import pytest

from foothold_s2.runners.manifest import yaml_flat

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VEL = "C:/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity"
RUNS = ["C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_rough/2026-08-05_17-42-05/params/env.yaml",
        "C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-10_20-47-27_20260910_nvidia_gap_repro_seed42_iter1500/params/env.yaml"]
NAME_MAP = {"track_lin_vel_xy_exp": "track_lin_vel", "track_ang_vel_z_exp": "track_ang_vel", "lin_vel_z_l2": "lin_vel_z", "ang_vel_xy_l2": "ang_vel_xy", "dof_torques_l2": "joint_torques",
            "dof_acc_l2": "joint_acc", "action_rate_l2": "action_rate", "feet_air_time": "feet_air_time", "flat_orientation_l2": "flat_orientation", "dof_pos_limits": "dof_pos_limits"}
START_ONLY = ("action_smoothness", "joint_power", "joint_deviation", "stumble", "collision", "foot_edge")
needs_install = pytest.mark.skipif(not os.path.exists(VEL), reason="설치된 Isaac Lab 소스 없음")


def _src(rel):
    return open(os.path.join(REPO, rel), encoding="utf-8").read()


class _Scene(dict):
    def __init__(self, name, body_names=None):
        super().__init__(name=name, body_names=body_names)


def _my_terms():
    """nvidia_go2_rewards.py 의 RewTerm 들을 AST 로 읽어 {이름: {func, weight, params}}."""
    tree = ast.parse(_src("foothold_s2/rewards/nvidia_go2_rewards.py"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "NvidiaGo2RewardsCfg")
    out = {}
    env = {"math": math, "SceneEntityCfg": _Scene}

    for node in cls.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "RewTerm":
            kw = {k.arg: k.value for k in node.value.keywords}
            out[node.targets[0].id] = {"func": ast.unparse(kw["func"]).split(".")[-1], "weight": eval(ast.unparse(kw["weight"]), env),
                                       "params": eval(ast.unparse(kw["params"]), env) if "params" in kw else {}}

    return out


@needs_install
@pytest.mark.parametrize("path", RUNS)
def test_terms_and_weights_match_the_recorded_env_yaml(path):
    if not os.path.exists(path):
        pytest.skip("실행 기록 없음")

    ref = yaml_flat(path)
    mine = _my_terms()
    installed = {k.split(".")[1] for k in ref if k.startswith("rewards.") and k.endswith(".func")}

    assert installed == set(NAME_MAP)                                                    # 실행 기록의 항 목록이 우리 대응표와 같다
    assert ref["rewards.undesired_contacts"] == "None"                                   # Go2 cfg 가 끈다
    assert set(mine) == set(NAME_MAP.values())                                           # 우리 항 = 설치본 항 전부(START 고유 항 없음)

    for inst, name in NAME_MAP.items():
        t = mine[name]

        assert t["weight"] == pytest.approx(float(ref[f"rewards.{inst}.weight"])), name
        assert ref[f"rewards.{inst}.func"].endswith(":" + t["func"]), name              # 같은 함수 이름
        for key in ("std", "threshold", "command_name"):
            if f"rewards.{inst}.params.{key}" in ref:
                got = t["params"][key]

                assert (got == pytest.approx(float(ref[f"rewards.{inst}.params.{key}"])) if key != "command_name" else got == ref[f"rewards.{inst}.params.{key}"]), (name, key)

    assert mine["feet_air_time"]["params"]["sensor_cfg"]["body_names"] == ref["rewards.feet_air_time.params.sensor_cfg.body_names"] == ".*_foot"


@needs_install
def test_terms_match_the_installed_source_literals_and_cited_lines():
    base = open(f"{VEL}/velocity_env_cfg.py", encoding="utf-8").read().splitlines()
    go2 = open(f"{VEL}/config/go2/rough_env_cfg.py", encoding="utf-8").read().splitlines()
    mine = _my_terms()

    assert base[230].startswith("class RewardsCfg") and base[262].strip().startswith("dof_pos_limits = RewTerm")                     # 인용한 줄 범위 231~263
    wanted = {52: "self.rewards.feet_air_time.params[\"sensor_cfg\"].body_names = \".*_foot\"", 53: "self.rewards.feet_air_time.weight = 0.01",
              54: "self.rewards.undesired_contacts = None", 55: "self.rewards.dof_torques_l2.weight = -0.0002", 56: "self.rewards.track_lin_vel_xy_exp.weight = 1.5",
              57: "self.rewards.track_ang_vel_z_exp.weight = 0.75", 58: "self.rewards.dof_acc_l2.weight = -2.5e-7"}                          # 인용한 줄 52~58

    for line_no, text in wanted.items():
        assert go2[line_no - 1].strip() == text, (line_no, go2[line_no - 1])

    # 기본값 중 Go2 가 안 바꾸는 항: lin_vel_z -2.0 · ang_vel_xy -0.05 · action_rate -0.01 · feet_air_time 문턱 0.5 · flat_orientation 0 · dof_pos_limits 0 · std sqrt(0.25)
    assert "lin_vel_z_l2 = RewTerm(func=mdp.lin_vel_z_l2, weight=-2.0)" in base[241] and mine["lin_vel_z"]["weight"] == -2.0
    assert "ang_vel_xy_l2 = RewTerm(func=mdp.ang_vel_xy_l2, weight=-0.05)" in base[242] and mine["ang_vel_xy"]["weight"] == -0.05
    assert "action_rate_l2 = RewTerm(func=mdp.action_rate_l2, weight=-0.01)" in base[245] and mine["action_rate"]["weight"] == -0.01
    assert '"std": math.sqrt(0.25)' in base[235] and mine["track_lin_vel"]["params"]["std"] == pytest.approx(0.5) and mine["track_ang_vel"]["params"]["std"] == pytest.approx(0.5)
    assert '"threshold": 0.5' in "\n".join(base[246:256]) and mine["feet_air_time"]["params"]["threshold"] == 0.5
    assert mine["flat_orientation"]["weight"] == 0.0 and mine["dof_pos_limits"]["weight"] == 0.0


def test_no_start_only_terms_and_curriculum_names_exist():
    mine = _my_terms()

    assert not (set(START_ONLY) & set(mine))                                            # START 고유 항은 모두 빠졌다
    assert "track_lin_vel" in mine and "track_ang_vel" in mine                          # S1 command_range 커리큘럼이 이 이름으로 읽는다
    cur = _src("foothold_s2/curriculum/terrain_levels_mixed.py")

    assert 'lin_term: str = "track_lin_vel"' in cur and 'ang_term: str = "track_ang_vel"' in cur


def _post_init_targets(src, cls):
    tree = ast.parse(src)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    post = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__post_init__")

    return [ast.unparse(a.targets[0]) for a in ast.walk(post) if isinstance(a, ast.Assign)], node


def test_env_cfg_differs_from_ex11_only_in_rewards():
    src = _src("foothold_s2/tasks/s2_x16n_cfg.py")
    targets, node = _post_init_targets(src, "FootholdS2X16nEnvCfg")

    assert [ast.unparse(b) for b in node.bases] == ["FootholdS2X11EnvCfg"]             # EX-11 환경 상속
    assert targets == ["self.rewards"]                                                  # 바꾸는 것은 보상 하나뿐(종료 · 명령 · 관측 · PD · 지형 · 커리큘럼은 상속 그대로)
    body = src.split('"""', 2)[2]

    assert "terminations" not in body and "commands" not in body and "observations" not in body and "curriculum" not in body and "only_positive" not in body
    assert "NvidiaGo2RewardsCfg()" in body and body.index("super().__post_init__()") < body.index("self.rewards")      # G0 post_init 뒤에 교체


def test_agent_cfg_registration_and_run_script():
    import gymnasium as gym

    import foothold_s2.x16n_tasks  # noqa: F401

    spec = gym.spec("FootholdS2-Go2-S2-X16n-v0")

    assert spec.entry_point == "isaaclab.envs:ManagerBasedRLEnv"                        # only_positive 없음(자르지 않는 기본 env)
    assert spec.kwargs["env_cfg_entry_point"].endswith("s2_x16n_cfg:FootholdS2X16nEnvCfg")
    assert spec.kwargs["rsl_rl_cfg_entry_point"].endswith("s2_x16n_ppo_cfg:S2X16nPPORunnerCfg")
    agent = _src("foothold_s2/tasks/agents/s2_x16n_ppo_cfg.py")

    assert "S2X13PPORunnerCfg" in agent and "max_iterations = 501" in agent and "save_interval = 100" in agent and 'experiment_name = "foothold_s2_x16n"' in agent
    ppo = _src("foothold_s2/tasks/agents/s2_ppo_cfg.py")
    base = ppo[ppo.index("class S2X13PPORunnerCfg"):]

    assert '"est_mode": "zero"' in base and '"critic_mode": "clean52"' in base                      # est zero · clean critic 은 EX-11 과 같다
    run = _src("foothold_s2/run_s2_x16n.sh")

    assert "FootholdS2-Go2-S2-X16n-v0" in run and "ex16-nvgo2" in run and "--max_iterations 501" in run and "--num_envs 3072" in run and "--seed 42" in run
    assert "import foothold_s2.x16n_tasks" in _src("foothold_s2/scripts/train_start.py")


def test_previous_motion_trot_x16_is_kept_and_existing_consumed_files_untouched():
    assert os.path.exists(os.path.join(REPO, "foothold_s2/tasks/s2_x16_cfg.py")) and "motion_trot" in _src("foothold_s2/tasks/s2_x16_cfg.py")      # 먼저 만든 판은 보관(안 씀)

    for rel in ("foothold_s2/x15_tasks.py", "foothold_s2/tasks/s2_x15_cfg.py", "foothold_s2/tasks/agents/s2_x15_ppo_cfg.py", "foothold_s2/tasks/__init__.py", "foothold_s2/tasks/s2_env_cfg.py",
                "foothold_s2/tasks/agents/s2_ppo_cfg.py", "foothold_s2/rewards/lg_core.py", "foothold_s2/rewards/lg_terms.py", "foothold_s2/rewards/mgdp_terms.py",
                "foothold_s2/runners/start_runner.py", "foothold_s2/tasks/s2_x13_env.py"):
        text = _src(rel)

        assert "X16n" not in text and "x16n" not in text and "nvidia_go2" not in text, rel
