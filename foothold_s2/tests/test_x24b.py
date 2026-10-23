"""SONNET-X24b: EX-24 launcher 가 train.py 의 형제 import(cli_args) 를 찾는지 + EX-24a(v2 그대로 처음부터) 실행 스크립트 시험."""

import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAUNCHER = os.path.join(REPO, "foothold_s2", "scripts", "train_v2_noscan.py")


def _fake_isaaclab(tmp_path):
    d = tmp_path / "scripts" / "reinforcement_learning" / "rsl_rl"
    d.mkdir(parents=True)
    (d / "cli_args.py").write_text("MARK = 'sibling-found'\n", encoding="utf-8")
    (d / "train.py").write_text("import cli_args\nprint('RESULT', cli_args.MARK)\n", encoding="utf-8")

    return str(tmp_path)


def _run(launcher, root):
    env = dict(os.environ, ISAACLAB_PATH=root, KMP_DUPLICATE_LIB_OK="TRUE")

    return subprocess.run([sys.executable, launcher], capture_output=True, text=True, env=env, cwd=str(root), timeout=300)


def test_launcher_puts_the_train_script_folder_on_sys_path(tmp_path):
    r = _run(LAUNCHER, _fake_isaaclab(tmp_path))

    assert "RESULT sibling-found" in r.stdout, r.stderr[-800:]


def test_without_the_sys_path_line_the_same_check_fails(tmp_path):
    """관문을 깨뜨려 본다: 줄을 뺀 사본에서는 ModuleNotFoundError 가 재현돼야 한다(사본은 저장소 안 scripts 옆이 아니라 REPO 를 직접 지정)."""
    src = open(LAUNCHER, encoding="utf-8").read()
    broken = src.replace("sys.path.insert(0, os.path.dirname(TRAIN))", "pass").replace("REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))", f"REPO = {REPO!r}")
    p = tmp_path / "broken_launcher.py"
    p.write_text(broken, encoding="utf-8")
    root = tmp_path / "isl"
    root.mkdir()
    r = _run(str(p), _fake_isaaclab(root))

    assert "No module named 'cli_args'" in r.stderr and "RESULT" not in r.stdout


def test_ex24a_run_script_is_v2b_from_scratch():
    run = open(os.path.join(REPO, "foothold_s2", "run_s2_x24a.sh"), encoding="utf-8").read()

    assert "train_v2_noscan.py" in run and "--task Isaac-Velocity-V2b-Unitree-Go2-v0" in run and "agent.resume=false" in run and "agent.save_interval=50" in run
    assert "--max_iterations 301" in run and "--num_envs 4096" in run and "--seed 42" in run and "agent.device=$DEV" in run and "ex24a-v2-scan" in run
    assert "--resume" not in run.split("\n", 4)[-1] and "--load_run" not in run


def test_v2b_task_and_the_hydra_keys_exist_in_the_installed_files():
    root = "C:/isaac/IsaacLab"
    init = os.path.join(root, "source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/gap_training/__init__.py")
    cli = os.path.join(root, "scripts/reinforcement_learning/rsl_rl/cli_args.py")

    if not os.path.exists(init):
        return

    assert 'id="Isaac-Velocity-V2b-Unitree-Go2-v0"' in open(init, encoding="utf-8").read()
    c = open(cli, encoding="utf-8").read()

    assert "agent_cfg.resume = args_cli.resume" in c and 'add_argument("--resume", action="store_true", default=False' in c         # 플래그를 안 주면 resume False
