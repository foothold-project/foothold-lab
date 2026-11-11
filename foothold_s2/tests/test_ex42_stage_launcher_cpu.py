"""The launcher the automatic stage start calls: EX42_AUTO_* + profile -> one torchrun command, notice, exec."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from foothold_s2.scripts import ex42_stage_launcher as L
from foothold_s2.scripts.ex42_training_entry import E_STAGE_SPECS

STAGE = "E1"
SH = Path(L.__file__).with_suffix(".sh")


def _env(tmp_path, *, action="next_stage", stage=STAGE):
    mesh = tmp_path / "mesh"
    mesh.mkdir(exist_ok=True)
    (mesh / "terrain_manifest.json").write_text("{}")
    env = {"EX42_AUTO_ACTION": action, "EX42_AUTO_TARGET_STAGE": stage, "EX42_AUTO_PARENT_MANIFEST": "/p/manifest.json",
           "EX42_AUTO_PARENT_CHECKPOINT": "/p/model_250.pt", "EX42_AUTO_GATE_RECEIPT": "/g/r.json",
           "EX42_AUTO_GATE_SHA256": "ab" * 32, "ISAAC311_PYTHON": "/py/python", "GPU_JOBS_QUEUE": "/q/queue.json",
           "EX42_MESH_DIR": str(mesh), "EX42_MESH_SHA256": "cd" * 32, "EX42_SOURCE_REF": "origin/x",
           "EX42_MAIN_ROOT": str(tmp_path / "main")}
    if action == "continue":
        run = tmp_path / "main" / "EX-42-B-E1_old"
        run.mkdir(parents=True, exist_ok=True)
        (run / "manifest.json").write_text("{}")
        env.update(EX42_AUTO_RESUME_CHECKPOINT=str(run / "model_250.pt"), EX42_AUTO_SEGMENT_END="500")
    return env


def _flag(argv, name):
    return next(a.split("=", 1)[1] for a in argv if a.startswith(name + "="))


def test_a_next_stage_command_takes_every_stage_value_from_the_plan_table_and_the_environment(tmp_path):
    argv, child, summary = L.build(_env(tmp_path), now=0)
    assert argv[:7] == ["/py/python", "-m", "torch.distributed.run", "--standalone", "--nnodes=1", "--nproc_per_node=2",
                        str(L.TRAIN_START)]
    assert _flag(argv, "--max_iterations") == str(E_STAGE_SPECS[STAGE]["updates"])
    assert _flag(argv, "--ex42_stage") == STAGE and "--ex42_stage_approved" in argv and "--ex42_stage_dry_run" not in argv
    assert _flag(argv, "--ex42_log_dir").startswith(str(tmp_path / "main" / f"EX-42-B-{STAGE}_"))
    assert _flag(argv, "--ex42_parent_manifest") == "/p/manifest.json"
    assert not any(a.startswith("--ex42_resume_from") or a.startswith("--ex42_segment_end") for a in argv)
    p1 = json.loads(_flag(argv, "--ex42_p1_score_argv_json"))
    assert p1[p1.index("--p1-stage-id") + 1] == STAGE and p1[p1.index("--checkpoint") + 1].endswith("/model_{iteration}.pt")
    assert p1[p1.index("--checkpoint") + 1].startswith(summary["run_dir"]) and p1[-1] == "--execute"
    assert "CUDA_VISIBLE_DEVICES" not in child and child["OMNI_KIT_ACCEPT_EULA"] == "YES"
    assert child["PYTHONPATH"].startswith(str(L.SOURCE_ROOT))


def test_a_continue_command_resumes_in_the_checkpoint_folder_up_to_the_segment_end(tmp_path):
    env = _env(tmp_path, action="continue")
    argv, _, summary = L.build(env)
    run = str(Path(env["EX42_AUTO_RESUME_CHECKPOINT"]).parent)
    assert _flag(argv, "--ex42_log_dir") == run == summary["run_dir"]
    assert _flag(argv, "--ex42_resume_from") == env["EX42_AUTO_RESUME_CHECKPOINT"] and _flag(argv, "--ex42_segment_end") == "500"


def test_the_dry_run_is_the_single_rank_command_with_the_dry_run_flag(tmp_path):
    argv, child, _ = L.build(_env(tmp_path), dry_run=True)
    assert argv[:2] == ["/py/python", str(L.TRAIN_START)] and "torch.distributed.run" not in argv
    assert "--ex42_stage_dry_run" in argv and "--ex42_stage_approved" in argv   # the entry wants both switches
    assert (child["WORLD_SIZE"], child["RANK"]) == ("2", "0")


def test_stage_suffixed_values_win_over_the_plain_ones_and_split_device_is_passed_on(tmp_path):
    env = _env(tmp_path)
    other = tmp_path / "mesh_e1"
    other.mkdir()
    (other / "terrain_manifest.json").write_text("{}")
    env.update(EX42_MESH_DIR_E1=str(other), EX42_MESH_SHA256_E1="ee" * 32, EX42_P1_SPLIT_DEVICE="cuda:0")
    argv, _, _ = L.build(env)
    assert _flag(argv, "--ex42_terrain_mesh_dir") == str(other)
    p1 = json.loads(_flag(argv, "--ex42_p1_score_argv_json"))
    assert p1[p1.index("--expected-mesh-sha256") + 1] == "ee" * 32 and p1[p1.index("--split-device") + 1] == "cuda:0"


@pytest.mark.parametrize("change,match", [
    ({"EX42_AUTO_ACTION": "start"}, "next_stage or continue"),
    ({"EX42_AUTO_TARGET_STAGE": "E1F"}, "no pinned parent"),
    ({"EX42_AUTO_TARGET_STAGE": "Z9"}, "no pinned parent"),
    ({"EX42_AUTO_PARENT_MANIFEST": ""}, "AUTO_PARENT_MANIFEST"),
    ({"EX42_MESH_SHA256": ""}, "MESH_SHA256"),
    ({"EX42_SOURCE_REF": ""}, "SOURCE_REF"),
    ({"EX42_MAIN_ROOT": ""}, "MAIN_ROOT"),
    ({"GPU_JOBS_QUEUE": ""}, "GPU_JOBS_QUEUE"),
    ({"ISAAC311_PYTHON": ""}, "ISAAC311_PYTHON"),
    ({"EX42_MESH_DIR": "/nonexistent-mesh"}, "terrain_manifest.json"),
])
def test_a_missing_or_inconsistent_value_refuses_the_launch(tmp_path, change, match):
    with pytest.raises(L.LaunchRefused, match=match):
        L.build({**_env(tmp_path), **change})


@pytest.mark.parametrize("end", ["0", "abc", str(E_STAGE_SPECS[STAGE]["updates"] + 250), ""])
def test_a_continue_segment_end_outside_the_stage_or_a_folder_without_manifest_is_refused(tmp_path, end):
    env = _env(tmp_path, action="continue")
    env["EX42_AUTO_SEGMENT_END"] = end
    with pytest.raises(L.LaunchRefused):
        L.build(env)
    env = _env(tmp_path, action="continue")
    (Path(env["EX42_AUTO_RESUME_CHECKPOINT"]).parent / "manifest.json").unlink()
    with pytest.raises(L.LaunchRefused, match="manifest.json"):
        L.build(env)


def test_main_sends_the_notice_then_execs_and_a_refusal_execs_nothing(tmp_path):
    calls, sent = [], []
    env = {**_env(tmp_path), "ORCA_CLI_COMMAND": "orca-x", "EX42_NOTIFY_TO": "run:run_1"}
    order = []
    real_notify = L.notify
    L.notify = lambda e, s: (order.append("notify"), sent.append((e["EX42_NOTIFY_TO"], s)))[0]
    try:
        assert L.main([], env=env, execvpe=lambda f, a, e: (order.append("exec"), calls.append((f, a)))) == 0
        assert order == ["notify", "exec"] and calls[0][0] == "/py/python" and sent[0][0] == "run:run_1"
        order.clear()
        assert L.main(["--dry-run"], env=env, execvpe=lambda *a: order.append("exec")) == 0
        assert order == ["exec"]                                  # a dry run sends no notice
        order.clear()
        assert L.main([], env={**env, "EX42_AUTO_TARGET_STAGE": "E1F"}, execvpe=lambda *a: order.append("exec")) == 2
        assert order == []
    finally:
        L.notify = real_notify


def test_the_notice_is_one_time_stamped_line_to_the_run_and_a_failed_send_never_raises(tmp_path):
    env = {**_env(tmp_path), "ORCA_CLI_COMMAND": "orca-x --a", "EX42_NOTIFY_TO": "run:run_1"}
    seen = []

    def runner(cmd, **kw):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    summary = {"action": "next_stage", "stage": STAGE, "run_dir": "/r", "segment_end": None}
    assert L.notify(env, summary, runner=runner, clock=lambda f: "12:34")
    cmd = seen[0]
    assert cmd[:4] == ["orca-x", "--a", "orchestration", "send"] and cmd[cmd.index("--to") + 1] == "run:run_1"
    subject = cmd[cmd.index("--subject") + 1]
    assert subject.startswith("(12:34) ") and "\n" not in subject and "—" not in subject
    assert not L.notify(env, summary, runner=lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    assert not L.notify({k: v for k, v in env.items() if k != "EX42_NOTIFY_TO"}, summary, runner=runner)


def test_the_shell_launcher_keeps_one_pid_from_the_queue_registered_process_to_the_trainer(tmp_path):
    # fake interpreter: logs its pid, then runs the real python for the launcher module and stops at the torchrun call
    pids = tmp_path / "pids"
    fake = tmp_path / "py"
    real = os.environ.get("ISAAC311_PYTHON") or "python3"
    fake.write_text(f'#!/bin/bash\necho $$ >> {pids}\nif [[ "$1" == "-m" ]]; then exit 0; fi\nexec {real} "$@"\n')
    fake.chmod(0o755)
    profile = tmp_path / "profile.env"
    profile.write_text(f"ISAAC311_PYTHON={fake}\n")
    env = {**_env(tmp_path), "FOOTHOLD_LINUX_ENV": str(profile), "ISAAC311_PYTHON": "", "PATH": os.environ["PATH"]}
    env["EX42_MAIN_ROOT"] = str(tmp_path / "main")
    child = subprocess.Popen([str(SH)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             cwd=str(L.SOURCE_ROOT))
    out, err = child.communicate(timeout=120)
    assert child.returncode == 0, err
    assert {line.strip() for line in pids.read_text().split()} == {str(child.pid)}
    assert len(pids.read_text().split()) == 2                      # the module launch and the exec'd trainer


def test_the_shell_launcher_print_mode_shows_the_command_and_refusal_is_rc_2(tmp_path):
    profile = tmp_path / "profile.env"
    profile.write_text("ISAAC311_PYTHON=" + (os.environ.get("ISAAC311_PYTHON") or "python3") + "\n")
    env = {**_env(tmp_path), "FOOTHOLD_LINUX_ENV": str(profile), "PATH": os.environ["PATH"]}
    done = subprocess.run([str(SH), "--print"], env=env, capture_output=True, text=True, cwd=str(L.SOURCE_ROOT))
    assert done.returncode == 0 and "torch.distributed.run" in done.stdout and "--ex42_stage_approved" in done.stdout
    bad = subprocess.run([str(SH), "--print"], env={**env, "EX42_AUTO_ACTION": "x"}, capture_output=True, text=True,
                         cwd=str(L.SOURCE_ROOT))
    assert bad.returncode == 2 and "refused" in bad.stderr
