"""SONNET-X16 (EX-16 = EX-15 + motion_trot -0.1) CPU 시험: 구성 대조(EX-15 와의 차이가 motion_trot 한 항뿐) · 등록 · 기존 소비 파일 불변. Kit 이름은 test_kit_names 의 AST 대조가 본다."""

import ast
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _src(rel):
    return open(os.path.join(REPO, rel), encoding="utf-8").read()


def _post_init_assignments(src, cls):
    tree = ast.parse(src)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    post = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__post_init__")

    return [ast.unparse(a.targets[0]) for a in ast.walk(post) if isinstance(a, ast.Assign)], node


def test_x16_differs_from_x15_by_exactly_motion_trot():
    src = _src("foothold_s2/tasks/s2_x16_cfg.py")
    targets, node = _post_init_assignments(src, "FootholdS2X16EnvCfg")

    assert [ast.unparse(b) for b in node.bases] == ["FootholdS2X15EnvCfg"]            # EX-15 를 상속
    assert targets == ["self.rewards.motion_trot"]                                    # 그 위에 바꾸는 것은 이 한 항뿐
    assert "motion_trot_mgdp" in src and "weight=-0.1" in src and "stand_still" not in src.split('"""', 2)[2]
    x15_targets, _ = _post_init_assignments(_src("foothold_s2/tasks/s2_x15_cfg.py"), "FootholdS2X15EnvCfg")

    assert "self.rewards.motion_trot" not in x15_targets                              # EX-15 에는 motion_trot 이 없다(차이가 이 항 하나)
    assert "only_positive_rewards" not in src                                          # 자르기 · 토크 · 한계 · calf 는 EX-15 상속 그대로(여기서 다시 쓰지 않음)
    assert "joint_torques" not in src and "dof_pos_limits" not in src and "collision" not in src


def test_x16_uses_the_ex13_term_with_its_gates():
    terms = _src("foothold_s2/rewards/mgdp_terms.py")
    core = _src("foothold_s2/rewards/mgdp_core.py")

    assert "class motion_trot_mgdp" in terms and "env.scene.terrain.terrain_levels" in terms and "env.common_step_counter" in terms
    assert "ENV_GAIT_LEVEL = 3" in core and "TROT_STEP_LIMIT = 2e4" in core


def test_x16_registration_agent_and_run_script():
    import gymnasium as gym

    import foothold_s2.x16_tasks  # noqa: F401

    spec = gym.spec("FootholdS2-Go2-S2-X16-v0")

    assert spec.entry_point.endswith("s2_x13_env:FootholdS2PosRewardEnv")
    assert spec.kwargs["env_cfg_entry_point"].endswith("s2_x16_cfg:FootholdS2X16EnvCfg")
    assert spec.kwargs["rsl_rl_cfg_entry_point"].endswith("s2_x16_ppo_cfg:S2X16PPORunnerCfg")
    agent = _src("foothold_s2/tasks/agents/s2_x16_ppo_cfg.py")

    assert "S2X15PPORunnerCfg" in agent and 'experiment_name = "foothold_s2_x16"' in agent
    run = _src("foothold_s2/run_s2_x16.sh")

    assert "FootholdS2-Go2-S2-X16-v0" in run and "ex16-lgA1-trot" in run and "--num_envs 3072" in run and "--seed 42" in run and "--max_iterations 1501" in run
    assert "X15" not in run and "ex15" not in run
    assert "import foothold_s2.x16_tasks" in _src("foothold_s2/scripts/train_start.py")


def test_existing_consumed_files_are_untouched_by_x16():
    """실행 중인 EX-15 가 소비하는 기존 파일에는 EX-16 이름이 없다(manifest 감시로 EX-15 가 무효가 되지 않게 새 파일로만 더했다)."""
    for rel in ("foothold_s2/x15_tasks.py", "foothold_s2/tasks/s2_x15_cfg.py", "foothold_s2/tasks/agents/s2_x15_ppo_cfg.py", "foothold_s2/rewards/lg_core.py", "foothold_s2/rewards/lg_terms.py",
                "foothold_s2/tasks/__init__.py", "foothold_s2/tasks/s2_env_cfg.py", "foothold_s2/rewards/mgdp_terms.py", "foothold_s2/rewards/mgdp_core.py",
                "foothold_s2/tasks/s2_x13_env.py", "foothold_s2/runners/start_runner.py"):
        text = _src(rel)

        assert "X16" not in text and "x16" not in text, rel
