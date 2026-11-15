"""CPU tests for the Linux baseline runner (no Kit, no GPU). Anything that imports the ex41 modules runs in a
subprocess with a Linux machine environment, because those modules read the machine profile at import."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "foothold_s2/eval/linux_baseline_1110.sh"
LAB = Path("/mnt/win-d/mai/data/foothold/s2_lab")
EX41 = LAB / "ex41_main_20261104_235522"
WIN_EVAL = EX41 / "eval/score-watch/model_6000_1c6af6319c82/evaluation"
WIN_SCORE = EX41 / "eval/scores/score_6000_1c6af6319c82.json"
PUSH_REL = "runner/ex41_push_ladder_m6000_20261103_161418/push_ladder_bundle.json"
have_windows_data = pytest.mark.skipif(not WIN_SCORE.is_file(), reason="Windows reference data not mounted")


def linux_env(tmp_path):
    home = tmp_path / "home"
    env = dict(os.environ, FOOTHOLD_MACHINE_PROFILE="machines/AI-WS01-linux.yaml", CUDA_VISIBLE_DEVICES="",
               PYTHONPATH=str(ROOT), MAI_TMP_ROOT=str(tmp_path / "tmp"), MAI_WORKTREE_ROOT=str(tmp_path / "wt"),
               S2_LAB_ROOT=str(LAB), ISAAC_CACHE_ROOT="/cache/isaac", ISAACLAB_ROOT="/isaaclab",
               ISAAC311_PYTHON="/opt/isaac311/bin/python", RSL_RL_MODULE="/opt/rsl_rl/__init__.py",
               ISAAC_SIM_ROOT="/opt/isaacsim", FOOTHOLD_BASH="/bin/bash", HOME=str(home))
    for key, rel in (("GPU_JOBS_CONFIG", "gj/jobs.json"), ("PLAYLIST_ROOT", "pl"), ("C_LAYER_LOCK", "c/lock"),
                     ("A_LAYER_MARKER", "c/a"), ("GPU0_TRAINING_MARKER", "c/t"), ("GPU_JOBS_QUEUE", "q.json"),
                     ("GPU0_TRAINING_MARKER_ALT", "m/t0"), ("GPU1_TRAINING_MARKER", "m/t1"),
                     ("GPU0_EVAL_MARKER", "m/e0"), ("GPU1_EVAL_MARKER", "m/e1"), ("RUNNER_HOME", "r"),
                     ("EX41_W78_VIDEO_ROOT", "w"), ("EX41_PUSH250_OUTPUT", "p"), ("EX41_STAGE_VIDEO_OUTPUT", "sv"),
                     ("FOOTHOLD_EX42_GATE_REPORT", "g.md"), ("EX41_STAGE_VIDEO_SOURCE", "svs"),
                     ("TELEGRAM_SCRIPT", "tg.py"), ("TELEGRAM_OUTBOX", "tg.txt")):
        env[key] = str(tmp_path / "x" / rel)
    env["GPU0_UUID"] = "GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b"
    env["GPU1_UUID"] = "GPU-315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f"
    return env


def with_push_bundle(env, tmp_path):
    src = Path("/mnt/win-d/mai/tmp") / PUSH_REL
    if not src.is_file():
        pytest.skip("pinned push-ladder bundle not mounted")
    dst = Path(env["MAI_TMP_ROOT"]) / PUSH_REL
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())
    return env


def py(code, env):
    done = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, cwd=ROOT)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def printed(env):
    out = subprocess.run(["bash", str(SCRIPT), "print"], env=env, capture_output=True, text=True, check=True).stdout
    return [shlex.split(l) for l in out.splitlines() if l.startswith("env ")]


def test_print_splits_the_two_checkpoints_over_the_two_cards(tmp_path):
    first, second = printed(linux_env(tmp_path))
    for argv in (first, second):
        assert "OMNI_KIT_ACCEPT_EULA=YES" in argv and "CUDA_DEVICE_ORDER=PCI_BUS_ID" in argv
        assert "CUDA_VISIBLE_DEVICES" not in " ".join(argv)
        assert argv[argv.index("-m") + 1] == "foothold_s2.ex41_linux_baseline" and "--execute" in argv
    assert first[first.index("--device") + 1] == "cuda:0" and second[second.index("--device") + 1] == "cuda:1"
    assert first[first.index("--expected-sha256") + 1].startswith("1c6af631")
    assert second[second.index("--expected-sha256") + 1].startswith("20365a2c")
    assert first[first.index("--checkpoint") + 1].endswith("EX-41-B-main_20261104_235522/model_6000.pt")
    assert second[second.index("--checkpoint") + 1].endswith("EX-42-B-stagezero_20261108_123914/model_1000.pt")
    assert first[first.index("--out-root") + 1].endswith("ex41_main_20261104_235522/eval/linux-baseline-1110/m12000")
    assert second[second.index("--out-root") + 1].endswith("ex42_main_20261108_123914/eval/linux-baseline-1110/m13000")
    assert "# then after 90s:" in subprocess.run(["bash", str(SCRIPT), "print"], env=linux_env(tmp_path),
                                                capture_output=True, text=True).stdout


def test_modules_the_script_calls_exist_in_this_checkout(tmp_path):
    sys.path.insert(0, str(ROOT))
    try:
        for argv in printed(linux_env(tmp_path)):
            spec = importlib.util.find_spec(argv[argv.index("-m") + 1])
            assert spec is not None and str(ROOT) in spec.origin
        assert importlib.util.find_spec("foothold_s2.eval.ex41_baseline_compare") is not None
        for module in ("foothold_s2.ex41_eval_once", "foothold_s2.ex41_score_watch"):
            assert importlib.util.find_spec(module) is not None
    finally:
        sys.path.remove(str(ROOT))
    text = SCRIPT.read_text()
    assert "foothold_s2.eval.ex41_baseline_compare" in text


def test_baseline_definition_changes_only_the_three_roles_and_leaves_ex41_alone(tmp_path):
    out = py("import json\nfrom foothold_s2 import ex41_linux_baseline as b\nfrom foothold_s2.experiment_registry import operational_definition as o\n"
             "d=b.baseline_definition('cuda:0'); r=o('EX-41')\n"
             "bad=None\ntry: b.baseline_definition('cuda:2')\nexcept ValueError as e: bad=str(e)\n"
             "print(json.dumps({'d':d['devices'],'r':r['devices'],'bad':bad,'same':{k:d[k]==r[k] for k in r if k!='devices'}}))",
             linux_env(tmp_path))
    assert out["d"] == {"training": "cuda:0", "evaluation": "cuda:0", "video": "cuda:0", "w78": "cuda:0"}
    assert out["r"]["evaluation"] == "cuda:1" and out["bad"] and "cuda:2" in out["bad"]
    assert all(out["same"].values())


@have_windows_data
def test_commands_match_the_windows_receipt_except_python_cache_device_and_paths(tmp_path):
    env = with_push_bundle(linux_env(tmp_path), tmp_path)
    ck = str(EX41 / "main/EX-41-B-main_20261104_235522/model_6000.pt")
    got = py("import json,sys\nfrom foothold_s2 import ex41_linux_baseline as b\n"
             f"print(json.dumps(b.phase_commands({ck!r}, {str(tmp_path / 'out')!r}, 'cuda:0')))", env)
    steps = json.loads((WIN_EVAL / "eval_receipt.json").read_text())["steps"]

    def norm(argv, python):
        out = []
        for i, a in enumerate(argv):
            prev = argv[i - 1] if i else ""
            if i == 0:
                assert a == python
                out.append("<python>")
            elif prev == "--checkpoint":
                out.append("<ckpt>")
            elif prev == "--out":
                out.append("<out>")
            elif prev == "--device":
                out.append("<dev>")
            elif a.startswith("--kit_args=--/UJITSO/datastore/localCachePath="):
                out.append("<kit-cache>")
            else:
                out.append(a)
        return out

    by_name = {r["name"]: r["argv"] for r in got}
    assert set(by_name) == set(steps), (set(by_name), set(steps))
    for name, win in steps.items():
        assert norm(by_name[name], "/opt/isaac311/bin/python") == norm(win["argv"], win["argv"][0]), name
    assert {r["name"]: r["device"] for r in got} == {n: "cuda:0" for n in steps}
    assert "localCachePath=/cache/isaac" in " ".join(by_name["map64"])


@have_windows_data
def test_score_step_reproduces_the_windows_score_from_the_windows_evaluation_files(tmp_path):
    env = with_push_bundle(linux_env(tmp_path), tmp_path)
    ck = str(EX41 / "main/EX-41-B-main_20261104_235522/model_6000.pt")
    code = ("import json\nfrom pathlib import Path\nfrom foothold_s2 import ex41_eval_once as eo\n"
            "from foothold_s2.ex41_score_watch import collect\nfrom foothold_s2.curriculum.continuous import load_plan\n"
            f"ev=Path({str(WIN_EVAL)!r})\n"
            f"row=collect({ck!r},'T0_prime',ev,load_plan(eo.DEFAULT_TABLE,arm='B'),eo.DEFAULT_CONFIG,"
            "periodic_w78_path=ev/'w78_v2_sides/terrain_skill_v2.json',include_auxiliary=False)\n"
            f"w=json.load(open({str(WIN_SCORE)!r}))\n"
            "print(json.dumps({'state':row['evaluation_state'],'mp':row['maintenance_pass'],'wmp':w['maintenance_pass'],"
            "'same':{k:row['metrics'].get(k)==w['metrics'][k] for k in w['metrics']}}))")
    out = py(code, env)
    assert out["state"] == "complete" and out["mp"] is True and out["wmp"] is True
    differing = sorted(k for k, v in out["same"].items() if not v)
    assert differing == ["training_knee_effort"], differing  # needs the training metrics file, not given on Linux


def test_run_refuses_a_wrong_checkpoint_and_an_existing_output_before_any_work(tmp_path):
    env = linux_env(tmp_path)
    ck = tmp_path / "m.pt"
    ck.write_bytes(b"not it")
    code = ("import json\nfrom foothold_s2 import ex41_linux_baseline as b\nr=[]\n"
            f"for out in ({str(tmp_path / 'o1')!r},):\n"
            "    try: b.run(%r, out, 'cuda:0', '0'*64)\n    except ValueError as e: r.append(str(e))\n"
            "print(json.dumps(r))" % str(ck))
    assert "sha256 differs" in py(code, env)[0]
    assert not (tmp_path / "o1").exists()


def test_run_calls_the_real_evaluation_and_score_functions_on_the_real_path():
    tree = ast.parse((ROOT / "foothold_s2/ex41_linux_baseline.py").read_text())
    run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run")
    calls = [n for n in ast.walk(run) if isinstance(n, ast.Call)]
    names = {ast.unparse(c.func) for c in calls}
    assert {"eo._evaluate_bundle", "collect", "load_plan"} <= names
    ev = next(c for c in calls if ast.unparse(c.func) == "eo._evaluate_bundle")
    kw = {k.arg: ast.unparse(k.value) for k in ev.keywords}
    assert kw["scope"] == "SCOPE" and kw["device"] == "device" and "baseline_definition(device)" in kw["definition"]
    col = next(c for c in calls if ast.unparse(c.func) == "collect")
    ckw = {k.arg: ast.unparse(k.value) for k in col.keywords}
    assert ckw["include_auxiliary"] == "False" and "w78_v2_sides/terrain_skill_v2.json" in ckw["periodic_w78_path"]
    assert "SCOPE = 'periodic'" in (ROOT / "foothold_s2/ex41_linux_baseline.py").read_text()


def test_script_refuses_wrong_sha_and_existing_output(tmp_path):
    env = linux_env(tmp_path)
    fake = tmp_path / "m.pt"
    fake.write_bytes(b"x")
    env.update(BASELINE_CK_M12000=str(fake), BASELINE_LAB_ROOT=str(tmp_path / "lab"), BASELINE_STAGGER="0")
    bad = subprocess.run(["bash", str(SCRIPT), "run-one", "m12000"], env=with_push_bundle(env, tmp_path), capture_output=True, text=True)
    assert bad.returncode == 2 and "sha256 differs" in bad.stderr
    no_env = {k: v for k, v in env.items() if k != "ISAAC311_PYTHON"}
    assert "ISAAC311_PYTHON is not set" in subprocess.run(["bash", str(SCRIPT), "print"], env=no_env, capture_output=True, text=True).stderr


@pytest.mark.skipif(not (LAB / "ex42_main_20261108_123914").is_dir(), reason="checkpoints not mounted")
def test_run_starts_m12000_on_cuda0_then_m13000_on_cuda1_after_the_stagger(tmp_path):
    env = with_push_bundle(linux_env(tmp_path), tmp_path)
    log = tmp_path / "calls.log"
    fake = tmp_path / "py"
    fake.write_text(f'#!/usr/bin/env bash\necho "$(date +%s.%N) $*" >> {log}\nsleep 0.2\n')
    fake.chmod(0o755)
    env.update(ISAAC311_PYTHON=str(fake), BASELINE_STAGGER="2", BASELINE_NAME="t-" + tmp_path.name)
    done = subprocess.run(["bash", str(SCRIPT), "run"], env=env, capture_output=True, text=True)
    out12, out13 = [Path(a[a.index("--out-root") + 1]) for a in printed(env)]
    for d in (out12.parent, out13.parent):
        try:  # the fake python wrote nothing; remove only the empty dirs this test made (never a pre-existing eval dir)
            d.rmdir()
            d.parent.rmdir()
        except OSError:
            pass
    assert done.returncode == 0, done.stderr
    rows = [l.split(" ", 1) for l in log.read_text().splitlines()]
    assert len(rows) == 2
    assert "--device cuda:0" in rows[0][1] and "model_6000.pt" in rows[0][1]
    assert "--device cuda:1" in rows[1][1] and "model_1000.pt" in rows[1][1]
    assert float(rows[1][0]) - float(rows[0][0]) >= 1.9


@have_windows_data
def test_compare_is_a_table_only_and_shows_a_changed_cell(tmp_path):
    sys.path.insert(0, str(ROOT))
    try:
        from foothold_s2.eval import ex41_baseline_compare as cmp
    finally:
        sys.path.remove(str(ROOT))
    win = json.loads(WIN_SCORE.read_text())
    wmap = json.loads((WIN_EVAL / "map64/map_modes.json").read_text())
    same = cmp.build(win, wmap, win, wmap)
    assert same["changed_cells"] == [] and len(same["cells"]) == 39
    assert sum(1 for v in same["cells"].values() if v["judged"]) == 26
    lin = json.loads(json.dumps(win))
    lmap = json.loads(json.dumps(wmap))
    lin["metrics"]["record_counts"]["eval_gt/fwd1.0"]["passed"] -= 3
    lmap["modes"]["eval_gt"]["fwd1.0"]["alive_envs_at_end"] -= 3
    lin["metrics"]["stand_counts"]["eval_pred"]["passed"] -= 1
    diff = cmp.build(win, wmap, lin, lmap)
    assert diff["changed_cells"] == ["eval_gt/fwd1.0"]
    assert diff["cells"]["eval_gt/fwd1.0"]["passed"]["delta"] == -3
    assert diff["cells"]["eval_gt/fwd1.0"]["alive_envs_at_end"]["delta"] == -3
    assert diff["stand"]["eval_pred"]["delta"] == -1
    text = cmp.render(diff)
    assert "no verdict" in text and "PASS" not in text and "FAIL" not in text
    assert "eval_gt/fwd1.0" in text
