"""SONNET-X25g: S-B(EX-33 · EX-34) 저장본을 평가하기 위한 사전 점검 (CPU 만, Kit 없음)."""

import ast
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SB_ID = "FootholdS2-Go2-S2-SB-v0"
RUN_SH = ROOT / "foothold_s2/eval/run_sb_eval.sh"
CHAIN_SH = ROOT / "foothold_s2/eval/post_train_eval.sh"
BASH = r"C:\Program Files\Git\bin\bash.exe"
TASK_FILES = ("foothold_s2/sb_tasks.py", "foothold_s2/tasks/s2_sb_cfg.py", "foothold_s2/tasks/agents/s2_sb_ppo_cfg.py")


_SPAWNED = []


def _spawn(cmd, **kw):
    """Popen 한 뒤 목록에 올린다. 시험이 끝나면 아래 fixture 가 자식 셸까지 통째로 끈다(Git Bash 는 런처 아래 진짜 bash 를 두어, 런처만 죽이면 진짜 bash 가 고아로 남는다)."""
    proc = subprocess.Popen(cmd, **kw)
    _SPAWNED.append(proc)

    return proc


@pytest.fixture(autouse=True)
def _kill_spawned_shells():
    yield
    while _SPAWNED:
        proc = _SPAWNED.pop()
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=60)
        try:
            proc.wait(timeout=15)
        except Exception:
            pass


def _src(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def _class(rel, name):
    return next(n for n in ast.parse(_src(rel)).body if isinstance(n, ast.ClassDef) and n.name == name)


def _bash(path):
    """Git Bash 에 넘길 POSIX 경로."""
    p = str(path).replace("\\", "/")
    return "/" + p[0].lower() + p[2:] if len(p) > 1 and p[1] == ":" else p


def test_sb_task_is_in_the_gym_registry_and_points_to_existing_classes():
    gym = pytest.importorskip("gymnasium")
    import foothold_s2.sb_tasks  # noqa: F401

    spec = gym.spec(SB_ID)
    env_mod, env_cls = spec.kwargs["env_cfg_entry_point"].split(":")
    agent_mod, agent_cls = spec.kwargs["rsl_rl_cfg_entry_point"].split(":")

    assert _class(env_mod.replace(".", "/") + ".py", env_cls).name == "FootholdS2SBEnvCfg"
    assert _class(agent_mod.replace(".", "/") + ".py", agent_cls).name == "S2SBPPORunnerCfg"


def test_sb_cfg_is_the_b_cfg_plus_p_map_off_only():
    env = _class("foothold_s2/tasks/s2_sb_cfg.py", "FootholdS2SBEnvCfg")
    assert [ast.unparse(b) for b in env.bases] == ["FootholdS223FBEnvCfg"] and len(env.body) == 1 and isinstance(env.body[0], ast.Pass)
    agent = _src("foothold_s2/tasks/agents/s2_sb_ppo_cfg.py")

    assert "S223FBPPORunnerCfg" in agent and '"p_map_off": P_MAP_OFF_DEFAULT' in agent and "P_MAP_OFF_DEFAULT = 0.5" in agent
    assert "\"map_input\"" not in agent and "\"force_gt\"" not in agent                     # 지도 입력은 B(reconstruction, force_gt 참) 그대로
    b_src = _src("foothold_s2/tasks/s2_23f_b_cfg.py")

    assert '"static_friction_range": (0.2, 1.2)' in b_src and '"dynamic_friction_range": (0.2, 1.2)' in b_src


def test_sb_task_files_are_byte_equal_to_the_training_branch_copies_when_present():
    other = ROOT.parent / "impl-sb"
    if not other.exists():
        pytest.skip("impl-sb 없음")
    for rel in TASK_FILES:
        assert (ROOT / rel).read_bytes() == (other / rel).read_bytes(), rel


def test_eval_scripts_register_the_sb_task_before_loading_the_cfg():
    for rel in ("foothold_s2/eval/turn_probe.py", "foothold_s2/eval/eval_map_modes.py"):
        s = _src(rel)

        assert "import foothold_s2.sb_tasks" in s and s.index("import foothold_s2.sb_tasks") < s.index("load_cfg_from_registry(args.task"), rel
        assert "import foothold_s2.g0b_tasks" in s, rel                          # X25e 의 G0-B 등록은 그대로


def test_evaluation_never_draws_the_training_switch():
    """평가 경로(adapters)에는 끔 난수 · map_switch 가 없다. load_s2_runner 는 agent cfg 가 p_map_off 를 들고 와도 0 으로 덮는다."""
    s = _src("foothold_s2/eval/adapters.py")

    for banned in ("draw_map_off", "map_switch", "MapSwitch", "new_map_off"):
        assert banned not in s, banned
    fn = next(n for n in ast.parse(s).body if isinstance(n, ast.FunctionDef) and n.name == "load_s2_runner")
    seg = ast.get_source_segment(s, fn)

    assert 'pc["p_map_off"] = 0.0' in seg
    assert seg.index('pc["p_map_off"] = 0.0') < seg.index("StartRunner(env, cfg")
    assert "map_off" not in _src("foothold_s2/eval/turn_probe.py") and "draw_map_off" not in _src("foothold_s2/eval/eval_map_modes.py")


def test_the_two_map_modes_are_what_the_adapter_offers_and_prop_only_masks_keys_not_heights():
    s = _src("foothold_s2/eval/adapters.py")

    assert 'MAP_MODES = ("eval_gt", "eval_pred", "probe_prop_only")' in s
    assert 'ie.mask_map_tokens = self.map_mode == "probe_prop_only"' in s
    assert '"eval_gt": True, "eval_pred": False, "probe_prop_only": False' in s
    assert "choices=(\"eval_gt\", \"eval_pred\", \"probe_prop_only\", \"none\")" in _src("foothold_s2/eval/turn_probe.py")
    assert 'default="eval_gt,eval_pred,probe_prop_only"' in _src("foothold_s2/eval/eval_map_modes.py")


def test_real_estimator_eval_gt_uses_the_map_and_probe_prop_only_ignores_it():
    torch = pytest.importorskip("torch")
    from foothold_s2.models.start_perception import IEEstimator, PerceptionCfg

    torch.manual_seed(0)
    ie = IEEstimator(PerceptionCfg(map_input="reconstruction")).eval()
    z = torch.randn(3, 128)
    h1, h2 = torch.randn(3, 32, 16), torch.randn(3, 32, 16)
    with torch.no_grad():
        ie.mask_map_tokens = False
        on1, on2 = ie.estimate(z, h1)["mu"], ie.estimate(z, h2)["mu"]
        ie.mask_map_tokens = True
        off1, off2 = ie.estimate(z, h1)["mu"], ie.estimate(z, h2)["mu"]
        ie.mask_map_tokens = False
        again = ie.estimate(z, h1)["mu"]

    assert not torch.equal(on1, on2)                  # 지도 켬: 지도가 출력에 닿는다
    assert torch.equal(off1, off2)                    # 지도 가림: 지도를 바꿔도 출력이 같다
    assert not torch.equal(on1, off1)
    assert torch.equal(on1, again)                    # 모드를 되돌리면 마스크가 새어 남지 않는다


def test_run_sb_eval_script_shape():
    raw = RUN_SH.read_bytes()
    s = raw.decode("utf-8")

    assert b"\r" not in raw
    for must in (SB_ID, "--cases all", "--envs 16", "--fixed-terrain", "foothold_s2.eval.turn_probe", "foothold_s2.eval.eval_map_modes", "--envs 64", "--steps 300",
                 '--modes "${MODES// /,}"', "for MODE in $MODES", '--map-mode "$MODE"', "TURNPROBE_DONE", 'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"'):
        assert must in s, must
    assert "\ncd " not in s and "--map-mode none" not in s and "G0B" not in s
    r = subprocess.run([BASH, "-n", str(RUN_SH)], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)

    assert r.returncode == 0, r.stderr


def test_run_sb_eval_matches_the_conditions_of_the_g0b_and_b1500_runs():
    sb, g0b = RUN_SH.read_text(encoding="utf-8"), (ROOT / "foothold_s2/eval/run_g0b_eval.sh").read_text(encoding="utf-8")

    for flag in ("--envs 16", "--fixed-terrain", "--cases all", "--envs 64", "--steps 300", "$GAITS"):
        assert flag in sb and flag in g0b, flag
    assert 'GAITS="${FORWARD_GAITS_FLAG---forward-gaits}"' in sb


def test_chain_script_shape():
    raw = CHAIN_SH.read_bytes()
    s = raw.decode("utf-8")

    assert b"\r" not in raw and "\ncd " not in s
    for must in ('RUN="$HERE/run_sb_eval.sh"', "seq 100 100 1500", "seq 50 100 1450", "DONE ok=", 'while [ ! -f "$TRAIN_RC" ]'):
        assert must in s, must
    assert s.index("seq 100 100 1500") < s.index("seq 50 100 1450")
    r = subprocess.run([BASH, "-n", str(CHAIN_SH)], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)

    assert r.returncode == 0, r.stderr


def _chain_sandbox(tmp_path, stub_body):
    """저장소 밖 임시 폴더에 실제 post_train_eval.sh 와 가짜 run_sb_eval.sh 를 둔다(Kit 없음)."""
    eval_dir = tmp_path / "foothold_s2" / "eval"
    eval_dir.mkdir(parents=True)
    shutil.copy(CHAIN_SH, eval_dir / "post_train_eval.sh")
    (eval_dir / "run_sb_eval.sh").write_text(stub_body, encoding="utf-8", newline="\n")
    ck = tmp_path / "ck"
    ck.mkdir()

    return eval_dir / "post_train_eval.sh", ck


def _run_chain(sh, ck, out, rc_file, timeout=60):
    env = dict(os.environ, POLL_SECONDS="1")

    return subprocess.run([BASH, _bash(sh), "cuda:1", _bash(ck), _bash(out), _bash(rc_file)], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=timeout, env=env)


STUB = '#!/usr/bin/env bash\nmkdir -p "$3"\necho "$2" >> "$(dirname "$3")/calls.txt"\ncase "$2" in *model_300.pt) echo "turn16_eval_gt rc=1" > "$3/rc.txt"; exit 0;; esac\necho "map64 rc=0" > "$3/rc.txt"\n'


def test_chain_waits_for_train_rc_then_runs_m100_units_first_skips_missing_and_continues_after_a_failure(tmp_path):
    sh, ck = _chain_sandbox(tmp_path, STUB)
    for n in (50, 100, 150, 200, 300, 1500):
        (ck / ("model_%d.pt" % n)).write_bytes(b"x")
    out, rc_file = tmp_path / "out", tmp_path / "train_rc.txt"
    proc = _spawn([BASH, _bash(sh), "cuda:1", _bash(ck), _bash(out), _bash(rc_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True, env=dict(os.environ, POLL_SECONDS="1"))
    import time

    time.sleep(3)
    assert proc.poll() is None and not (out / "calls.txt").exists()          # 학습 rc.txt 가 없으면 평가를 시작하지 않는다
    rc_file.write_text("rc=0\n", encoding="utf-8")
    proc.communicate(timeout=60)
    calls = [Path(c).name for c in (out / "calls.txt").read_text(encoding="utf-8").split()]

    assert calls == ["model_100.pt", "model_200.pt", "model_300.pt", "model_1500.pt", "model_50.pt", "model_150.pt"]       # m100 단위 먼저(오름차순), 그다음 50 단위
    assert (out / "DONE").read_text(encoding="utf-8").startswith("DONE ok=5 fail=1")
    assert (out / "m300" / "CHAIN_ITEM_FAILED").exists() and not (out / "m300" / "CHAIN_ITEM_DONE").exists()
    assert (out / "m100" / "CHAIN_ITEM_DONE").exists()
    assert "ITEM m400 skip" in (out / "chain.log").read_text(encoding="utf-8")


def test_chain_rerun_skips_finished_items_and_retries_the_failed_one(tmp_path):
    sh, ck = _chain_sandbox(tmp_path, STUB)
    for n in (100, 300):
        (ck / ("model_%d.pt" % n)).write_bytes(b"x")
    out, rc_file = tmp_path / "out", tmp_path / "train_rc.txt"
    rc_file.write_text("rc=0\n", encoding="utf-8")
    _run_chain(sh, ck, out, rc_file)
    (out / "calls.txt").unlink()
    _run_chain(sh, ck, out, rc_file)
    calls = [Path(c).name for c in (out / "calls.txt").read_text(encoding="utf-8").split()]

    assert calls == ["model_300.pt"]                  # 끝난 m100 은 건너뛰고 실패한 m300 만 다시
